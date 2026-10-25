"""Eight-second paper-puppet study. All image processing is cloud-only."""
import math
from .core import cloud_only, ROOT, digest, write_json

FPS, SECONDS, W, H = 24, 8, 720, 1280
ASSETS = ROOT / 'assets' / 'paper-test'


def ease(value):
    value = max(0.0,min(1.0,value))
    return value*value*(3-2*value)


def mix(a,b,t):
    return a+(b-a)*t


def point_mix(a,b,t):
    return (mix(a[0],b[0],t),mix(a[1],b[1],t))


def ik(root,target,l1,l2,bend=1):
    """Analytic two-bone joint, with a bounded reach and stable elbow bend."""
    dx,dy=target[0]-root[0],target[1]-root[1]
    distance=max(abs(l1-l2)+.001,min(math.hypot(dx,dy),l1+l2-.001))
    theta=math.atan2(dy,dx)
    offset=math.acos(max(-1,min(1,(l1*l1+distance*distance-l2*l2)/(2*l1*distance))))
    joint=(root[0]+l1*math.cos(theta+bend*offset),root[1]+l1*math.sin(theta+bend*offset))
    end=(root[0]+distance*math.cos(theta),root[1]+distance*math.sin(theta))
    return joint,end


def hero_pose(t):
    walk=ease(t/1.85)
    x=mix(35,222,walk)
    y=mix(570,535,walk)
    walking=t<1.85
    phase=t*7.7
    bounce=3*math.sin(phase*2) if walking else 1.2*math.sin(t*2)
    y+=bounce
    surprise=ease((t-2.05)/.38)
    anger=ease((t-4.65)/.35)
    left=point_mix((-62,258),(-128,88),surprise)
    right=point_mix((62,258),(133,78),surprise)
    left=point_mix(left,(-98,177),anger)
    right=point_mix(right,(143,113),anger)
    if walking:
        left=(left[0]-20*math.sin(phase),left[1]-12*math.sin(phase))
        right=(right[0]+20*math.sin(phase),right[1]+12*math.sin(phase))
    sway=4*math.sin(phase) if walking else 2*math.sin(t*2.2)
    return {'x':x,'y':y,'head':0 if t<2.10 else (1 if t<4.8 else 2),
            'left_hand':left,'right_hand':right,'walk':walking,'phase':phase,
            'head_angle':sway-7*surprise+4*anger,'torso_angle':sway*.35}


def friend_pose(t):
    shrink=ease((t-4.7)/.5)
    return {'x':535,'y':566+9*shrink+1.5*math.sin(t*2.1),'head':4 if t<4.8 else 5,
            'left_hand':(-89+18*shrink,142+21*shrink),
            'right_hand':(60-8*shrink,267-15*shrink),
            'walk':False,'phase':0,'head_angle':-4+9*shrink+math.sin(t*3),
            'torso_angle':-2-3*shrink}


def camera(t):
    if t<2.45:
        return (1+0.045*ease(t/2.45),360,665)
    if t<3.65:
        return (1.22+0.025*ease((t-2.45)/1.2),282,630)
    if t<4.65:
        return (1.22,445,655)
    if t<6.25:
        return (1.19,295,641)
    return (1.04,360,650)


class PaperStage:
    def __init__(self):
        cloud_only()
        from PIL import Image
        self.Image=Image
        self.room=Image.open(ASSETS/'room.png').convert('RGBA').resize((W,H),Image.Resampling.LANCZOS)
        atlas=Image.open(ASSETS/'puppet-atlas.png').convert('RGBA')
        if atlas.getchannel('A').getextrema()[0]!=0:
            raise ValueError('Puppet atlas must have actual transparency')
        self.parts=[]
        # The generated sheet has four columns, with optically spaced rows.
        rows=[(.025,.29),(.30,.535),(.545,.755),(.755,.99)]
        for top,bottom in rows:
            for col in range(4):
                cell=atlas.crop((round(atlas.width*col/4),round(atlas.height*top),
                                 round(atlas.width*(col+1)/4),round(atlas.height*bottom)))
                self.parts.append(self.clean(cell))
        self.cache={}

    def clean(self,cell):
        # Discard detached alpha noise, retaining head, eyebrows and paper edges.
        from collections import deque
        alpha=cell.getchannel('A')
        width,height=cell.size
        pixels=alpha.tobytes()
        seen=bytearray(width*height)
        components=[]
        for seed,a in enumerate(pixels):
            if a<128 or seen[seed]:
                continue
            seen[seed]=1
            todo=deque([seed]); component=[]
            while todo:
                at=todo.popleft(); component.append(at)
                x,y=at%width,at//width
                for nxt in ((at-1 if x else -1),(at+1 if x<width-1 else -1),
                            (at-width if y else -1),(at+width if y<height-1 else -1)):
                    if nxt>=0 and not seen[nxt] and pixels[nxt]>=128:
                        seen[nxt]=1;todo.append(nxt)
            components.append(component)
        if not components:
            raise ValueError('Empty puppet cell')
        cutoff=max(65,max(map(len,components))*.0025)
        keep=bytearray(width*height)
        for c in components:
            if len(c)>=cutoff:
                for at in c:
                    keep[at]=255
        mask=self.Image.frombytes('L',cell.size,bytes(keep))
        # A one-pixel expansion preserves the anti-aliased contour.
        from PIL import ImageFilter,ImageChops
        mask=mask.filter(ImageFilter.MaxFilter(3))
        cell.putalpha(ImageChops.multiply(alpha,mask))
        return cell.crop(cell.getbbox())

    def sprite(self,index,width,height,flip=False):
        key=(index,round(width),round(height),flip)
        if key not in self.cache:
            from PIL import ImageOps
            s=self.parts[index].resize((key[1],key[2]),self.Image.Resampling.LANCZOS)
            if flip:
                s=ImageOps.mirror(s)
            self.cache[key]=s
        return self.cache[key]

    def paste(self,canvas,index,center,width,height,angle=0,flip=False):
        s=self.sprite(index,width,height,flip)
        if abs(angle)>.3:
            s=s.rotate(angle,resample=self.Image.Resampling.BICUBIC,expand=True)
        pos=(round(center[0]-s.width/2),round(center[1]-s.height/2))
        # Actual layer shadows rather than a simulated texture on a flat icon.
        from PIL import ImageFilter
        shadow=self.Image.new('RGBA',s.size,(35,22,12,0))
        shadow.putalpha(s.getchannel('A').point(lambda a:round(a*.23)).filter(ImageFilter.GaussianBlur(1.2)))
        canvas.alpha_composite(shadow,(pos[0]+3,pos[1]+4))
        canvas.alpha_composite(s,pos)

    def segment(self,canvas,index,a,b,width=16):
        length=math.dist(a,b)
        angle=math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))
        self.paste(canvas,index,((a[0]+b[0])/2,(a[1]+b[1])/2),width,length+5,angle)

    def puppet(self,canvas,pose,hero=True,t=0):
        from PIL import ImageDraw
        x,y=pose['x'],pose['y']
        d=ImageDraw.Draw(canvas)
        # Soft contact shadow keeps the paper feet on the ground.
        shadow_layer=self.Image.new('RGBA',canvas.size,(0,0,0,0))
        ImageDraw.Draw(shadow_layer).ellipse((x-66,y+466,x+75,y+484),fill=(37,26,17,42))
        from PIL import ImageFilter
        canvas.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(5)))
        for side in [-1,1]:
            hip=(x+side*20,y+233)
            if pose['walk']:
                phase=pose['phase']+(0 if side<0 else math.pi)
                foot=(x+side*19+31*math.sin(phase),y+473-17*max(0,math.cos(phase)))
            else:
                foot=(x+side*40,y+473)
            knee,ankle=ik(hip,foot,123,123,bend=side)
            self.segment(canvas,10,hip,knee,18)
            self.segment(canvas,11,knee,ankle,16)
            self.paste(canvas,13,(ankle[0]+7,ankle[1]+6),63,25,flip=side<0)
        # Rear arm and sleeve, then torso, then foreground arm.
        for side,key in [(-1,'left_hand'),(1,'right_hand')]:
            shoulder=(x+side*29,y+106)
            hand=(x+pose[key][0],y+pose[key][1])
            elbow,wrist=ik(shoulder,hand,82,85,bend=side)
            self.segment(canvas,8,shoulder,elbow,17)
            self.segment(canvas,9,elbow,wrist,15)
            self.paste(canvas,12,wrist,48,47,angle=side*25,flip=side<0)
        self.segment(canvas,8,(x,y+59),(x,y+106),18)
        self.paste(canvas,3 if hero else 7,(x,y+170),109,163,pose['torso_angle'])
        self.paste(canvas,pose['head'],(x,y),163,163,pose['head_angle'])
        if not hero:
            left=(x+pose['left_hand'][0],y+pose['left_hand'][1])
            right=(x+pose['right_hand'][0],y+pose['right_hand'][1])
            self.paste(canvas,14,(left[0],left[1]-33),96,100,angle=-8+3*math.sin(t*4))
            self.paste(canvas,15,(right[0]-12,right[1]-70),91,184,angle=4)
            self.paste(canvas,12,(left[0]+13,left[1]+3),43,43,angle=-35)
            self.paste(canvas,12,(right[0]+7,right[1]-4),42,42,angle=45)

    def draw(self,t):
        from PIL import ImageDraw,ImageFont
        image=self.room.copy()
        self.puppet(image,friend_pose(t),False,t)
        self.puppet(image,hero_pose(t),True,t)
        # Clean comic reaction strokes only during the discovery, not continuous waving.
        if 2.1<t<2.6:
            p=hero_pose(t); d=ImageDraw.Draw(image)
            for i in range(3):
                xx=p['x']-70+i*32
                d.line((xx,p['y']-116,xx-10,p['y']-146),fill='#d97042',width=7)
        if t>=6.35:
            d=ImageDraw.Draw(image)
            pop=ease((t-6.35)/.22)
            if pop>.01:
                bubble=self.Image.new('RGBA',(500,200),(0,0,0,0))
                bd=ImageDraw.Draw(bubble)
                bd.rounded_rectangle((8,8,490,157),radius=25,fill='#fff0d4',outline='#493629',width=3)
                bd.polygon([(90,155),(64,194),(156,155)],fill='#fff0d4')
                font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',44)
                for i,line in enumerate(['YOU SOLD','MY PS5?!']):
                    bbox=bd.textbbox((0,0),line,font=font)
                    bd.text(((500-(bbox[2]-bbox[0]))/2,24+i*55),line,font=font,fill='#29221c')
                bubble=bubble.resize((round(500*pop),round(200*pop)),self.Image.Resampling.LANCZOS)
                image.alpha_composite(bubble,(round(360-bubble.width/2),round(290-bubble.height/2)))
        zoom,cx,cy=camera(t)
        cw,ch=W/zoom,H/zoom
        left=max(0,min(W-cw,cx-cw/2));top=max(0,min(H-ch,cy-ch/2))
        image=image.crop((round(left),round(top),round(left+cw),round(top+ch))).resize((W,H),self.Image.Resampling.LANCZOS)
        return image.convert('RGB')


def main():
    cloud_only()
    import json,os,subprocess
    from pathlib import Path
    from .github import GitHub
    out=Path('build/paper-motion');out.mkdir(parents=True,exist_ok=True)
    stage=PaperStage()
    video=out/'StickTwist-paper-motion-test.mp4'
    cmd=['ffmpeg','-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}',
         '-framerate',str(FPS),'-i','pipe:0','-vf','scale=1080:1920:flags=lanczos',
         '-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
    sample_times=[.2,1.3,2.7,3.9,5.2,7.2]
    contact=stage.Image.new('RGB',(360*3,640*2),'#ead9bd')
    for i,t in enumerate(sample_times):
        contact.paste(stage.draw(t).resize((360,640)),((i%3)*360,(i//3)*640))
    contact.save(out/'paper-motion-contact.jpg',quality=90)
    stage.draw(7.2).save(out/'paper-motion-poster.jpg',quality=92)
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        try:
            for n in range(FPS*SECONDS):
                proc.stdin.write(stage.draw(n/FPS).tobytes())
            proc.stdin.close()
            if proc.wait()!=0:
                raise RuntimeError('Cloud encoding failed')
        except BaseException:
            proc.kill();raise
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
    vs=next(s for s in probe['streams'] if s['codec_type']=='video')
    if (vs['width'],vs['height'],vs['codec_name'])!=(1080,1920,'h264') or abs(float(probe['format']['duration'])-SECONDS)>.1:
        raise RuntimeError('Unexpected test video format or duration')
    write_json(out/'motion-checks.json',{'duration_seconds':float(probe['format']['duration']),
        'frames':FPS*SECONDS,'fps':FPS,'source_commit':os.environ['GITHUB_SHA'],
        'video_sha256':digest(video),'audio':'none — visual movement study only',
        'motion':['two-bone arm/leg joints','foot lift and walking cycle','three hero expressions',
                  'guilty friend reaction','separate console and banknotes','four camera cuts'],
        'assets':{f:digest(ASSETS/f) for f in ['room.png','puppet-atlas.png']}})
    gh=GitHub()
    tag=f'paper-motion-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}'
    release=gh.draft(tag,'StickTwist — style 5 / 8-second movement test',
        'UNPUBLISHED DRAFT — visual movement test only, no audio, no YouTube upload.\n\n'
        'Paper puppet joints, walk, reaction and camera cuts. Not a completed story.\n\n'
        f'Video SHA256: `{digest(video)}`.\n\n'
        'Watch the MP4 before judging the movement; a contact sheet only shows selected poses.')
    for name in ['StickTwist-paper-motion-test.mp4','paper-motion-contact.jpg','paper-motion-poster.jpg','motion-checks.json']:
        gh.upload(release,out/name)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as s:
        s.write(f'## Paper cutout motion study\n\n8 seconds, 1080×1920, 24 fps. Silent.\n\n'
                f'[Open unpublished preview]({release["html_url"]})\n\nVideo SHA256: `{digest(video)}`\n')
    print('REVIEW_ONLY_URL='+release['html_url'])
    print('VIDEO_SHA256='+digest(video))


if __name__=='__main__':
    main()


