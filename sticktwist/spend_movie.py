"""Cloud-only paper-cutout films from the approved, immutable narrated drafts."""
import bisect
import json
import math
import os
import re
import subprocess
from pathlib import Path
from .core import ROOT, cloud_only, digest, write_json, srt_time
from .paper_motion import PaperStage, ease, mix

AUDIO_COMMIT='7bb04ab4ab850763abf9045a548c881e502a53d5'
AUDIO_HASHES={
 '01-short-voice.mp3':'ab864bbb1e02a469f42c779cbb3573fd7ca23d096f140d4bc5a6a55d70734dd2',
 '02-short-working-mix.mp3':'3c4b4a9187db73ec27cbc1b6779875e97777434fd1def55604f6343234dbe2be',
 '03-long-voice.mp3':'4f741d155e74aabc0cf6b22cae42296156de5bf87fee5bf60cbfd4d07ce8a1c9',
 'short-timeline.json':'18846f6257ef667383a5d0dfae41bf5f1b5b711b54c2dc9b8784688a2bbaafe4',
 'long-timeline.json':'bf1de40d2f0f853ecebd3f4cc7e7c585d8b16bebfed1d8edef65571e27eaa3b5'}
# Each cut is tied to an actual spoken phrase, never a guessed chapter fraction.
SHORT_CUTS=[
 [(None,'offer'),('Finish it','reward'),('But no gifts','rules')],
 [(None,'house'),('A supercar','car'),('I needed','idea')],
 [(None,'jet'),('advertising time','billboard'),('an arena','arena'),('a private stunt show','show'),('Every rental','return')],
 [(None,'three'),('A coffee','cafe'),('paper cup','cup')],
 [(None,'stop'),('lose a billion','cup')],
 [(None,'mug'),('I drank','drink'),('then returned','return-mug'),('Midnight','zero'),('One billion','winner')]]
LONG_CUTS=[
 [(None,'three'),('The barista','cup'),('I had spent','stop'),('Twenty-four hours earlier','offer'),('On its screen','offer'),('He said','reward'),('I laughed','reaction')],
 [(None,'rules'),('Anything I acquired','rules'),('Food and drinks','mug'),('Renting was allowed','return'),('I immediately','house'),('I tried a supercar','car'),('Jewelry','jewel'),('That was when','idea')],
 [(None,'idea'),('A charter company','jet'),('Twenty-eight million','jet'),('I flew over','flight'),('The crew asked','flight'),('Seventy-two million','balance72'),('When we landed','souvenir'),('The judge cleared','stop')],
 [(None,'billboard'),('Thirty-six million','billboard'),('The message was simple','ad-message'),('For a while','big-face'),('The judge confirmed','return'),('Then I rented','arena'),('I walked through','arena-empty')],
 [(None,'show-contract'),('The package was available','show-contract'),('I checked every page','return'),('It was a live experience','show'),('Cars jumped ramps','stunt'),('I was the entire audience','arena-empty'),('Every time something','alone'),('I had bought','alone')],
 [(None,'return'),('The judge','three'),('Three dollars','three'),('I could not tip','no-tip'),('I could not buy','souvenir'),('The judge offered','reaction'),('Across the street','cafe'),('For the first time','run')],
 [(None,'cup'),('The judge','stop'),('Seven seconds','countdown'),('Then I saw','mug'),('I asked','mug'),('She poured','drink'),('set her mug','return-mug'),('Midnight','zero'),('A second later','winner'),('I waited','winner'),('The next morning','morning'),('For the first time','morning')]]


def normalized(text):
    return re.sub(r'[^a-z0-9]','',text.lower())


def phrase_time(beat,phrase):
    if phrase is None:
        return beat['start']
    joined=''; spans=[]
    for token in beat['tokens']:
        word=normalized(token['text'])
        spans.append((len(joined),len(joined)+len(word),token['start']))
        joined+=word
    at=joined.find(normalized(phrase))
    if at<0:
        raise ValueError('Shot anchor absent from spoken tokens: '+phrase)
    return next(start for a,b,start in spans if a<=at<b)


def shot_plan(timeline,fmt,seconds):
    cuts=SHORT_CUTS if fmt=='short' else LONG_CUTS
    if len(timeline)!=len(cuts):
        raise ValueError('Narration chapters changed')
    shots=[]
    for beat,entries in zip(timeline,cuts):
        for phrase,scene in entries:
            shots.append({'start':phrase_time(beat,phrase),'scene':scene,'anchor':phrase or beat['title']})
    for i,shot in enumerate(shots):
        shot['end']=shots[i+1]['start'] if i+1<len(shots) else seconds
        if shot['end']<=shot['start']:
            raise ValueError('Nonmonotonic shot plan')
    return shots


def captions(timeline,seconds):
    result=[]
    for beat in timeline:
        group=[]
        def finish():
            if group:
                text=' '.join(w['text'] for w in group)
                # Kokoro sometimes returns punctuation as a separate token.
                text=re.sub(r'\s+([,.!?;:])',r'\1',text)
                result.append({'start':group[0]['start'],'end':min(seconds,group[-1]['end']+.06),'text':text})
                group.clear()
        for token in beat['tokens']:
            if token['end']<=token['start']:
                continue
            if group and (len(group)>=4 or len(' '.join(w['text'] for w in group))+len(token['text'])>27):
                finish()
            group.append(token)
            if re.search(r'[.!?]$',token['text']):
                finish()
        finish()
    for i in range(len(result)-1):
        result[i]['end']=min(result[i]['end'],result[i+1]['start'])
    if not result or any(c['end']<=c['start'] for c in result):
        raise ValueError('Invalid native-timed captions')
    return result


class Film:
    def __init__(self,fmt,timeline,seconds):
        cloud_only()
        from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageChops
        self.Image=Image;self.Draw=ImageDraw;self.Font=ImageFont
        self.Filter=ImageFilter;self.Chops=ImageChops
        self.fmt=fmt;self.w,self.h=(720,1280) if fmt=='short' else (1280,720)
        self.seconds=seconds;self.shots=shot_plan(timeline,fmt,seconds)
        self.starts=[s['start'] for s in self.shots]
        self.caps=captions(timeline,seconds);self.capstarts=[c['start'] for c in self.caps]
        self.rig=PaperStage();self.cache={};self.puppets={};self.fonts={}
        self.grain=Image.effect_noise((self.w,self.h),9).convert('RGB')
        self.paper=Image.blend(Image.new('RGB',(self.w,self.h),'#eedcbd'),self.grain,.065).convert('RGBA')
        self.floor=Image.open(ROOT/'assets/paper-test/room-clear.png').convert('RGBA')
        # Existing real paper textures remain visible on all cutout scenery.
        self.texture=self.floor.crop((int(self.floor.width*.48),int(self.floor.height*.05),int(self.floor.width*.7),int(self.floor.height*.25))).resize((self.w,self.h))

    def font(self,size):
        if size not in self.fonts:
            self.fonts[size]=self.Font.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',size)
        return self.fonts[size]

    def text(self,image,text,xy,size=34,fill='#302b26',anchor='mm'):
        self.Draw.Draw(image).text(xy,text,font=self.font(size),fill=fill,anchor=anchor,stroke_width=0)

    def cut(self,image,points,color):
        mask=self.Image.new('L',image.size,0);d=self.Draw.Draw(mask)
        d.polygon(points,fill=255)
        solid=self.Image.new('RGBA',image.size,color)
        solid=self.Image.blend(solid,self.texture,.10)
        solid.putalpha(mask)
        shadow=self.Image.new('RGBA',image.size,'#493a29')
        shadow.putalpha(mask.point(lambda a:int(a*.20)).filter(self.Filter.GaussianBlur(3)))
        image.alpha_composite(shadow,(4,6));image.alpha_composite(solid)
        self.Draw.Draw(image).line(points+[points[0]],fill='#584837',width=2,joint='curve')

    def rect(self,image,box,color):
        x,y,r,b=box
        self.cut(image,[(x,y+2),(r-2,y),(r,b-2),(x+1,b)],color)

    def card(self,image,label,box,color='#fff3d6',size=32):
        self.rect(image,box,color)
        self.text(image,label,((box[0]+box[2])/2,(box[1]+box[3])/2),size)

    def background(self,scene):
        if scene in self.cache:
            return self.cache[scene].copy()
        w,h=self.w,self.h; image=self.paper.copy();d=self.Draw.Draw(image)
        horizon=int(h*(.69 if self.fmt=='short' else .75))
        self.rect(image,(0,horizon,w,h),'#c9a071')
        for y in range(horizon+20,h,45):
            d.line((0,y,w,y-8),fill='#b18b63',width=1)
        cafe=scene in {'three','cafe','cup','stop','mug','drink','return-mug','zero','winner','morning','countdown','run'}
        arena=scene in {'arena','arena-empty','show','stunt','alone','show-contract'}
        city=scene in {'billboard','ad-message','big-face'}
        if cafe:
            self.rect(image,(w*.60,h*.20,w*.91,h*.48),'#58777a')
            for xx in [.66,.77,.87]:
                self.rect(image,(w*xx,h*.23,w*xx+8,h*.45),'#e8d8bb')
            self.card(image,'COFFEE  $3',(w*.57,h*.12,w*.94,h*.20),size=24 if self.fmt=='short' else 30)
            self.rect(image,(w*.55,h*.54,w*.97,h*.62),'#76513c')
            self.rect(image,(w*.57,h*.62,w*.95,horizon+30),'#a16e4c')
            self.rect(image,(w*.08,h*.16,w*.34,h*.43),'#b8d4cd' if scene=='morning' else '#3c4e60')
            d.line((w*.21,h*.16,w*.21,h*.43),fill='#f0dfc0',width=8)
        elif arena:
            self.rect(image,(w*.05,h*.24,w*.95,h*.66),'#454653')
            for row in range(4):
                for col in range(12):
                    x=w*(.09+col*.069);y=h*(.28+row*.072)
                    d.rounded_rectangle((x,y,x+w*.045,y+h*.036),radius=4,fill='#945d52',outline='#ad7d66',width=2)
            self.rect(image,(w*.15,h*.60,w*.85,h*.69),'#bd9264')
            for x in [w*.2,w*.8]:
                self.cut(image,[(x,h*.12),(x-w*.12,h*.63),(x+w*.12,h*.63)],'#e7ce88')
        elif city:
            for i in range(8):
                x=i*w/7;height=h*(.25+(i*7%5)*.04)
                self.rect(image,(x,horizon-height,x+w*.13,horizon),'#778887' if i%2 else '#8d7765')
                for row in range(4):
                    for col in range(2):
                        self.rect(image,(x+14+col*w*.045,horizon-height+20+row*34,x+30+col*w*.045,horizon-height+36+row*34),'#e7cfa1')
        elif scene in {'jet','flight','balance72'}:
            self.rect(image,(0,h*.20,w,horizon),'#afced0')
            for x in [w*.15,w*.55,w*.85]:
                d.ellipse((x-90,h*.28,x+100,h*.34),fill='#f1e9d2')
            self.rect(image,(0,horizon,w,h),'#8a9290')
            d.line((0,h*.85,w,h*.83),fill='#e7cf8e',width=8)
        else:
            # Apartment retains the approved tactile background, without foreground clutter.
            room=self.floor.resize((w,h)) if self.fmt=='short' else self.floor.crop((0,0,self.floor.width,int(self.floor.width*9/16))).resize((w,h))
            image=self.Image.blend(image,room,.63)
        self.cache[scene]=image.copy()
        return image

    def character(self,image,t,scene,shot_age):
        # Draw each articulated pose once; reuse bounded 12fps gesture frames.
        worried=scene in {'cup','stop','three','countdown','alone'}
        angry=scene in {'rules','house','car','jewel','no-tip'}
        head=1 if worried else (2 if angry else 0)
        frame=int(t*12);key=(scene,frame%96)
        if key not in self.puppets:
            phase=(frame%96)/12
            walking=scene=='run'
            motion=math.sin(phase*3.2)
            left=(-96,160+18*motion) if worried else (-68,250-8*motion)
            right=(126,98+15*motion) if scene in {'offer','reward','idea','winner','rules'} else (98,180+22*motion)
            if scene in {'drink','mug'}:
                right=(65,55 if scene=='drink' else 155)
            if scene=='return-mug':right=(155,196)
            pose={'x':240,'y':115+2*math.sin(phase*2.4),'head':head,
                  'left_hand':left,'right_hand':right,'walk':walking,'phase':phase*8,
                  'head_angle':3*motion,'torso_angle':1.2*motion}
            puppet=self.Image.new('RGBA',(500,630),(0,0,0,0))
            self.rig.puppet(puppet,pose,True,t,props=False)
            scale=.84 if self.fmt=='short' else .77
            puppet=puppet.resize((int(500*scale),int(630*scale)),self.Image.Resampling.LANCZOS)
            if len(self.puppets)>450:self.puppets.clear()
            self.puppets[key]=puppet
        puppet=self.puppets[key]
        x=int(self.w*(.01 if self.fmt=='short' else .07))
        y=int(self.h*(.34 if self.fmt=='short' else .19))
        if scene=='run':x+=int(18*math.sin(shot_age*2))
        image.alpha_composite(puppet,(x,y))
        return x,y

    def object(self,image,scene,t,age):
        w,h=self.w,self.h
        cx=w*(.70 if self.fmt=='short' else .72);cy=h*(.40 if self.fmt=='short' else .46)
        s=1 if self.fmt=='short' else 1.22
        bob=5*math.sin(age*2.8)
        cy+=bob
        d=self.Draw.Draw(image)
        def rect(box,color): self.rect(image,box,color)
        def label(text,y=0,color='#fff1cf',size=31):
            self.card(image,text,(cx-135*s,cy-55*s+y,cx+135*s,cy+30*s+y),color,round(size*s))
        if scene in {'offer','reward','balance72','three','zero','winner','countdown'}:
            value={'offer':'$100,000,000','reward':'WIN $1 BILLION','balance72':'$72,000,000','three':'$3 LEFT','zero':'$0 LEFT','winner':'$1,000,000,000','countdown':'00:07'}[scene]
            # Big balance at top, leaving character and captions clear.
            self.card(image,value,(w*.08,h*.225,w*.92,h*.315),'#f4d78f' if scene not in {'zero','winner'} else '#b9d5b1',34 if self.fmt=='short' else 48)
            if scene in {'zero','winner'}:
                label('KEEP NOTHING',105*s,size=22)
            else:
                rect((cx-70*s,cy-70*s,cx+70*s,cy+145*s),'#36444b')
                rect((cx-56*s,cy-53*s,cx+56*s,cy+114*s),'#b1c8b9')
                self.text(image,'24h' if scene in {'offer','reward'} else '$3',(cx,cy+30*s),round(40*s))
        elif scene=='rules':
            for i,txt in enumerate(['NO GIFTS','KEEP NOTHING','24 HOURS']):label(txt,i*102*s,size=25)
        elif scene=='house':
            rect((cx-110*s,cy-25*s,cx+110*s,cy+130*s),'#d4ad7a')
            self.cut(image,[(cx-142*s,cy-25*s),(cx,cy-150*s),(cx+142*s,cy-25*s)],'#a76448')
            rect((cx-26*s,cy+50*s,cx+26*s,cy+130*s),'#597f83')
        elif scene in {'car','stunt'}:
            move=math.sin(age*2.1)*65*s if scene=='stunt' else 0
            yy=-abs(math.sin(age*2.1))*80*s if scene=='stunt' else 0
            cx+=move;cy+=yy
            self.cut(image,[(cx-145*s,cy+50*s),(cx-102*s,cy-10*s),(cx+12*s,cy-40*s),(cx+80*s,cy+10*s),(cx+140*s,cy+26*s),(cx+145*s,cy+80*s),(cx-145*s,cy+80*s)],'#d77750')
            for x in [cx-90*s,cx+85*s]:d.ellipse((x-27*s,cy+55*s,x+27*s,cy+109*s),fill='#353737',outline='#c8c2b0',width=6)
            if scene=='stunt':self.cut(image,[(cx+70*s,cy+175*s),(cx+165*s,cy+110*s),(cx+165*s,cy+175*s)],'#aa815b')
        elif scene=='jewel':
            self.cut(image,[(cx-90*s,cy),(cx-50*s,cy-70*s),(cx+50*s,cy-70*s),(cx+90*s,cy),(cx,cy+140*s)],'#86b8b5')
        elif scene in {'jet','flight'}:
            offset=35*math.sin(age*1.4)
            cx+=offset
            self.cut(image,[(cx-160*s,cy),(cx-115*s,cy-30*s),(cx-25*s,cy-32*s),(cx+20*s,cy-125*s),(cx+64*s,cy-125*s),(cx+42*s,cy-28*s),(cx+139*s,cy-13*s),(cx+165*s,cy+12*s),(cx+37*s,cy+30*s),(cx-4*s,cy+100*s),(cx-50*s,cy+105*s),(cx-46*s,cy+26*s),(cx-139*s,cy+31*s)],'#f5e7c9')
            for i in range(4):d.ellipse((cx-90*s+i*35*s,cy-15*s,cx-77*s+i*35*s,cy-2*s),fill='#5a858b')
        elif scene in {'billboard','ad-message','big-face'}:
            rect((cx-12*s,cy+90*s,cx+12*s,cy+250*s),'#675f51')
            rect((cx-150*s,cy-100*s,cx+150*s,cy+110*s),'#405c65')
            if scene=='big-face':self.rig.paste(image,0,(cx,cy),130*s,130*s)
            else:
                for i,txt in enumerate(['A VERY','EXPENSIVE','DAY']):self.text(image,txt,(cx,cy-45*s+i*50*s),round(27*s),'#f5e5c8')
        elif scene in {'arena','arena-empty','alone'}:
            if scene=='arena':label('ARENA RENTAL',size=23)
            else:
                for i in range(3):rect((cx-120*s+i*90*s,cy+30*s,cx-55*s+i*90*s,cy+165*s),'#9b604c')
                if scene=='alone':label('ONE TICKET',-100*s,size=23)
        elif scene in {'show','show-contract'}:
            if scene=='show-contract':label('$11,999,997',size=27)
            else:
                for i in range(3):
                    x=cx-100*s+i*90*s
                    d.ellipse((x-15*s,cy-60*s,x+15*s,cy-30*s),fill='#efdab8')
                    d.line((x,cy-30*s,x,cy+55*s),fill='#313b40',width=12)
                    d.line((x,cy,x+40*s*math.sin(age*4+i),cy-20*s),fill='#313b40',width=8)
                    self.text(image,'♪',(x+20*s,cy+70*s+8*math.sin(age*3+i)),round(40*s),'#e7c477')
        elif scene in {'cup','stop'}:
            self.cut(image,[(cx-67*s,cy-90*s),(cx+67*s,cy-90*s),(cx+48*s,cy+75*s),(cx-48*s,cy+75*s)],'#e4c9a1')
            d.ellipse((cx-70*s,cy-105*s,cx+70*s,cy-75*s),fill='#5b3b29',outline='#f3dfb9',width=6)
            self.card(image,'YOU OWN THIS',(cx-150*s,cy+120*s,cx+150*s,cy+180*s),'#e4a28a',round(21*s))
        elif scene in {'mug','drink','return-mug','morning'}:
            if scene=='drink':cx=w*(.38 if self.fmt=='short' else .27);cy=h*(.43 if self.fmt=='short' else .40)
            if scene=='return-mug':cx=w*.65;cy=h*.55
            d.ellipse((cx+42*s,cy-32*s,cx+100*s,cy+45*s),outline='#577e82',width=14)
            rect((cx-65*s,cy-50*s,cx+60*s,cy+70*s),'#7da6a4')
            d.ellipse((cx-65*s,cy-65*s,cx+60*s,cy-32*s),fill='#67472f',outline='#d0dfcb',width=5)
            if scene!='return-mug':
                for i in range(3):
                    xx=cx-35*s+i*30*s
                    d.arc((xx-10*s,cy-120*s-8*math.sin(age*3+i),xx+13*s,cy-65*s),90,270,fill='#e9e7d8',width=4)
            if scene=='mug':self.card(image,'CAFE OWNS THE MUG',(w*.09,h*.225,w*.91,h*.31),size=28 if self.fmt=='short' else 38)
        elif scene in {'return','souvenir','no-tip'}:
            label({'return':'RENTED. RETURNED.','souvenir':'SOUVENIR?','no-tip':'NO TIPS = NO GIFTS'}[scene],size=20)
        elif scene in {'idea','reaction','run','cafe'}:
            label({'idea':'BUY EXPERIENCES','reaction':'READ THE RULES','run':'00:59','cafe':'$3 LEFT'}[scene],size=22)
        if scene in {'house','car','jewel','souvenir','no-tip','stop'}:
            # Animated paper cross makes the ownership trap unambiguous.
            pop=ease(age/.28)
            self.Draw.Draw(image).line((cx-100*s,cy-110*s,cx-100*s+200*s*pop,cy-110*s+220*s*pop),fill='#bf593d',width=12)
            self.Draw.Draw(image).line((cx+100*s,cy-110*s,cx+100*s-200*s*pop,cy-110*s+220*s*pop),fill='#bf593d',width=12)

    def draw(self,t):
        index=max(0,bisect.bisect_right(self.starts,t)-1)
        shot=self.shots[index];age=t-shot['start'];scene=shot['scene']
        image=self.background(scene)
        self.character(image,t,scene,age)
        self.object(image,scene,t,age)
        # Gentle optical push-in is interrupted by real scene cuts above.
        zoom=1+.026*ease((age%5)/5)
        cw,ch=self.w/zoom,self.h/zoom
        image=image.crop(((self.w-cw)/2,(self.h-ch)/2,(self.w+cw)/2,(self.h+ch)/2)).resize((self.w,self.h),self.Image.Resampling.BICUBIC)
        d=self.Draw.Draw(image)
        self.card(image,'SPEND $100M. KEEP NOTHING.',(self.w*.065,self.h*.075,self.w*.935,self.h*.15),'#f6e7c9',27 if self.fmt=='short' else 34)
        # Progress is editorial playback, not a misleading real-time challenge clock.
        d.rectangle((self.w*.07,self.h*.166,self.w*.93,self.h*.171),fill='#c4b69b')
        d.rectangle((self.w*.07,self.h*.166,self.w*(.07+.86*t/self.seconds),self.h*.171),fill='#59817e')
        ci=bisect.bisect_right(self.capstarts,t)-1
        if ci>=0 and t<self.caps[ci]['end']:
            import textwrap
            lines=textwrap.wrap(self.caps[ci]['text'],width=25 if self.fmt=='short' else 48)
            size=36 if self.fmt=='short' else 38
            top=self.h*(.81 if self.fmt=='short' else .83)
            for i,line in enumerate(lines[:2]):
                font=self.font(size);box=d.textbbox((0,0),line,font=font)
                tw=box[2]-box[0];yy=top+i*(size+13)
                d.rounded_rectangle((self.w/2-tw/2-17,yy-10,self.w/2+tw/2+17,yy+size+13),radius=11,fill='#302d28')
                d.text((self.w/2,yy),line,font=font,anchor='mt',fill='#fff2d6')
        self.text(image,'STICKTWIST  /  FICTION',(self.w*.08,self.h*.945),17 if self.fmt=='short' else 19,anchor='lm')
        return image.convert('RGB')


def source_audio(gh,out,fmt):
    names=[f'{fmt}-timeline.json','02-short-working-mix.mp3' if fmt=='short' else '03-long-voice.mp3']
    release=next((r for r in gh.releases() if r.get('draft') and r['target_commitish']==AUDIO_COMMIT and r['name']=='StickTwist — Spend $100m / narrated script drafts'),None)
    if release is None:
        raise RuntimeError('Approved narration draft not found at exact source commit')
    assets=gh.request(f'releases/{release["id"]}/assets')
    for name in names:
        asset=next((a for a in assets if a['name']==name),None)
        if asset is None:raise RuntimeError('Missing approved audio asset '+name)
        gh.download(asset,out/name)
        if digest(out/name)!=AUDIO_HASHES[name]:raise RuntimeError('Approved audio hash mismatch '+name)
    return out/names[1],json.loads((out/names[0]).read_text())


def long_mix(voice,out,seconds,shots):
    import numpy as np
    import soundfile as sf
    from .audio_auditions import SR,music,effect,mix
    bed=music(seconds,'suspense')
    # Quiet spaces around the lonely arena and a warmer, lighter final cafe.
    for shot in shots:
        a,b=round(shot['start']*SR),min(len(bed),round(shot['end']*SR))
        if shot['scene'] in {'alone','arena-empty','stop'}:bed[a:b]*=.25
    sf.write(out/'music.wav',bed,SR)
    track=np.zeros(len(bed),dtype=np.float32)
    for shot in shots:
        if shot['scene'] not in {'offer','cup','zero','winner','jet','return'}:continue
        sound=effect('notification' if shot['scene'] in {'offer','winner','zero'} else 'paper')*.50
        at=round((shot['start']+.12)*SR);count=min(len(sound),len(track)-at)
        if count>0:track[at:at+count]+=sound[:count]
    sf.write(out/'effects.wav',track,SR)
    target=out/'long-mix.mp3';mix(voice,out/'music.wav',out/'effects.wav',target,seconds)
    return target


def main():
    cloud_only()
    from .github import GitHub
    from .audio_auditions import duration,command
    fmt=os.environ.get('FILM_FORMAT','short')
    if fmt not in {'short','long'}:raise ValueError('Unknown film format')
    gh=GitHub();out=Path(f'build/spend100m-{fmt}');out.mkdir(parents=True,exist_ok=True)
    voice,timeline=source_audio(gh,out,fmt)
    seconds=duration(voice)
    film=Film(fmt,timeline,seconds)
    write_json(out/'shot-plan.json',film.shots);write_json(out/'captions.json',film.caps)
    (out/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(film.caps))+'\n',encoding='utf-8')
    video=out/f'StickTwist-100M-{fmt}.mp4'
    target=(1080,1920) if fmt=='short' else (1920,1080)
    # 12 distinct cutout poses per second, each held for two frames in a 24fps file.
    frames=math.ceil(seconds*12)
    cmd=['ffmpeg','-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{film.w}x{film.h}','-framerate','12','-i','pipe:0','-i',str(voice),'-map','0:v:0','-map','1:a:0','-vf',f'scale={target[0]}:{target[1]}:flags=lanczos,fps=24','-t',str(seconds),'-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(video)]
    thumbw,thumbh=(240,427) if fmt=='short' else (384,216)
    contact=film.Image.new('RGB',(thumbw*3,thumbh*3),'#e5d2b0')
    for i in range(9):
        at=seconds*(i+.45)/9
        contact.paste(film.draw(at).resize((thumbw,thumbh)),((i%3)*thumbw,(i//3)*thumbh))
    contact.save(out/'review.jpg',quality=91)
    film.draw(2.5).save(out/'poster.jpg',quality=92)
    stage=os.environ.get('FILM_STAGE','boards')
    if stage not in {'boards','render'}:raise ValueError('Unknown production stage')
    if stage=='boards':
        release=gh.draft(f'spend100m-boards-{fmt}-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}',f'StickTwist — Spend $100m / {fmt} storyboard',
            'UNPUBLISHED visual storyboard. Not a video. No publishing approval.\n\n'
            f'{len(film.shots)} shots mapped to the approved narration. Caption and scene layout inspection before video rendering.')
        for name in ['review.jpg','poster.jpg','shot-plan.json','captions.json','captions.srt']:gh.upload(release,out/name)
        print('BOARD_REVIEW_URL='+release['html_url'],flush=True)
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(f'[Open {fmt} storyboard]({release["html_url"]})\n')
        return
    audio=voice if fmt=='short' else long_mix(voice,out,seconds,film.shots)
    # The audio input is resolved after boards, so long-form sound is never built for a still preview.
    cmd[cmd.index(str(voice))]=str(audio)
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        try:
            for n in range(frames):
                proc.stdin.write(film.draw(n/12).tobytes())
                if n%240==0:print(f'RENDER_PROGRESS={n}/{frames}',flush=True)
            proc.stdin.close()
            if proc.wait()!=0:raise RuntimeError('Cloud render failed')
        except BaseException:
            proc.kill();raise
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
    vs=next(s for s in probe['streams'] if s['codec_type']=='video');au=next(s for s in probe['streams'] if s['codec_type']=='audio')
    if (vs['width'],vs['height'],vs['codec_name'],vs['pix_fmt'],vs['r_frame_rate'])!=(*target,'h264','yuv420p','24/1') or au['codec_name']!='aac':raise RuntimeError('Unexpected media streams')
    if abs(float(probe['format']['duration'])-seconds)>.20:raise RuntimeError('Narration ending truncated')
    command(['ffmpeg','-v','error','-i',str(video),'-f','null','-'])
    manifest={'episode':'spend-100m-in-one-day','format':fmt,'seconds':seconds,'width':target[0],'height':target[1],
        'fps':24,'distinct_animation_poses_per_second':12,'shots':len(film.shots),'source_commit':os.environ['GITHUB_SHA'],
        'audio_source_commit':AUDIO_COMMIT,'audio_source_sha256':digest(voice),'video_sha256':digest(video),
        'fiction':True,'publishing_approved':False,'owner_approved_script_and_audio':True,
        'caption_timing':'native Kokoro token estimates; review synchronization before publishing',
        'checks':['H264/AAC','full cloud decode','duration preserves complete narration','approved audio hash','1080 output','24fps']}
    write_json(out/'manifest.json',manifest)
    release=gh.draft(f'spend100m-{fmt}-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}',f'StickTwist — Spend $100m / {fmt} paper film',
        'UNPUBLISHED OWNER REVIEW. Complete fictional paper-cutout film.\n\nNo YouTube upload or publication approval.\n\n'
        f'Format: {fmt}. Duration: {seconds:.2f}s. Shots: {len(film.shots)}.\n\nVideo SHA256: `{digest(video)}`.\n\n'
        'Narration reuses the owner-approved exact audio. Captions use native token timing estimates. Review the MP4, not only the contact sheet.')
    for file in [video,out/'review.jpg',out/'poster.jpg',out/'captions.srt',out/'shot-plan.json',out/'captions.json',out/'manifest.json']:gh.upload(release,file)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(f'## {fmt.title()} paper film\n\n[Open unpublished film]({release["html_url"]})\n\n{seconds:.2f} seconds. {len(film.shots)} narrative shots.\n')
    print('FILM_REVIEW_URL='+release['html_url'],flush=True)


if __name__=='__main__':main()
