"""Animated procedural stickmen. Called only from the guarded cloud renderer."""
import math
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
BG, INK, MINT, PINK = '#101729', '#f5f4ee', '#87f5bd', '#ff6e86'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def font(size):
    return ImageFont.truetype(FONT, size)


def lines(draw, text, size, max_width):
    result, line = [], ''
    for word in text.split():
        trial = (line+' '+word).strip()
        if draw.textlength(trial, font=font(size)) > max_width and line:
            result.append(line)
            line = word
        else:
            line = trial
    if line:
        result.append(line)
    return result


def centered(draw, text, y, size, color=INK, width=600):
    wrapped = lines(draw, text, size, width)
    for i, line in enumerate(wrapped):
        x = (W-draw.textlength(line, font=font(size)))/2
        draw.text((x,y+i*(size+10)), line, font=font(size), fill=color)
    return len(wrapped)*(size+10)


def actor(d, x, y, t, color, mood='neutral', pointing=False):
    bob = math.sin(t*5)*4
    y += bob
    # Shadow, body, limbs: independently animated hands, steps and expressions.
    d.ellipse((x-58,y+274,x+58,y+292), fill='#080e1c')
    d.ellipse((x-38,y-38,x+38,y+38), fill=BG, outline=color, width=9)
    d.line([(x,y+38),(x,y+154)], fill=color, width=10)
    step = math.sin(t*4)*12
    d.line([(x,y+154),(x-42-step,y+278)], fill=color, width=10)
    d.line([(x,y+154),(x+42+step,y+278)], fill=color, width=10)
    hand = 25*math.sin(t*3)
    d.line([(x,y+75),(x-49,y+112),(x-65,y+80+hand)], fill=color, width=9)
    d.line([(x,y+75),(x+45,y+104),(x+84,y+(50 if pointing else 144)+hand)], fill=color, width=9)
    for ex in [-13,13]:
        d.ellipse((x+ex-3,y-8,x+ex+3,y-2),fill=INK)
    if mood == 'shock':
        d.ellipse((x-8,y+9,x+8,y+25),outline=INK,width=3)
        d.line((x-24,y-22,x-7,y-27),fill=color,width=4)
    elif mood == 'sad':
        d.arc((x-15,y+12,x+15,y+37),190,350,fill=INK,width=3)
    else:
        d.arc((x-16,y-2,x+16,y+25),5,175,fill=INK,width=3)


def prop(d, kind, x, y, scale=1):
    if kind == 'console':
        d.polygon([(x-32,y-67),(x+20,y-77),(x+36,y+65),(x-28,y+72)], fill=INK)
        d.rounded_rectangle((x-9,y-65,x+10,y+66),radius=4,fill='#263653')
        d.line((x+13,y-61,x+27,y+60),fill=MINT,width=3)
    elif kind == 'phone':
        d.rounded_rectangle((x-42,y-70,x+42,y+70),radius=13,fill=INK)
        d.rounded_rectangle((x-34,y-57,x+34,y+48),radius=5,fill='#263653')
        for off in [-32,-8,16]:
            d.line((x-24,y+off,x+24,y+off),fill=MINT,width=5)
    elif kind == 'cash':
        for i in range(3):
            d.rounded_rectangle((x-63+i*6,y-33-i*10,x+54+i*6,y+27-i*10),radius=5,fill=MINT,outline=BG,width=3)
        d.text((x-13,y-48),'$',font=font(35),fill=BG)
    elif kind == 'key':
        d.ellipse((x-58,y-30,x-5,y+23),outline=MINT,width=10)
        d.line((x-5,y-4,x+62,y-4),fill=MINT,width=10)
        d.line((x+45,y-4,x+45,y+20),fill=MINT,width=9)
    elif kind in {'note','ticket'}:
        d.rounded_rectangle((x-70,y-52,x+70,y+52),radius=6,fill=INK)
        for i in range(3):
            d.line((x-47,y-25+i*22,x+44,y-25+i*22),fill='#263653',width=5)
    else:
        d.rectangle((x-66,y-47,x+66,y+57),fill='#e7b77b',outline=BG,width=4)
        d.rectangle((x-12,y-47,x+12,y+57),fill='#c58d56')


def frame(story, beat, index, t, progress, caption):
    im = Image.new('RGB',(W,H),BG)
    d = ImageDraw.Draw(im)
    # Quiet graphic grid, consistent channel identity, caption-safe vertical layout.
    for x in range(0,W,60):
        d.line((x,0,x,H),fill='#172238')
    d.rounded_rectangle((44,60,255,105),radius=18,fill=MINT)
    d.text((61,68),'STICKTWIST',font=font(23),fill=BG)
    d.text((490,75),'FICTION',font=font(19),fill='#a2aec5')
    title_size = 36 if len(story['title']) < 38 else 30
    centered(d,story['title'].upper(),151,title_size,width=620)
    d.rounded_rectangle((54,285,666,373),radius=18,fill='#243049')
    centered(d,beat['label'],303,25,color=MINT,width=575)
    scene = beat['scene']
    d.rounded_rectangle((75,755,645,801),radius=12,fill='#293955')
    d.line((0,849,W,849),fill='#34445c',width=3)
    left_x = 195 + math.sin(t*1.5)*8
    right_x = 513 - math.sin(t*1.5)*8
    actor(d,left_x,543,t,MINT,'shock' if scene in {'shock','receipt'} else 'neutral',scene in {'phone','ending'})
    actor(d,right_x,543,t+.7,PINK,'sad' if scene in {'reveal','ending'} else 'neutral',scene == 'deal')
    if scene == 'room':
        # Deliberately empty shelf communicates the missing possession.
        d.rectangle((292,580,430,592),fill=INK)
        d.line((355,593,355,651,375,665),fill='#a2aec5',width=4)
        centered(d,'GONE',430,43,color=PINK)
    else:
        # Object travels between the characters; reveal uses a glowing spotlight.
        x = 355 + (55*math.sin(min(t,1.2)*1.2) if scene == 'deal' else 0)
        y = 662 + 7*math.sin(t*2)
        if scene in {'reveal','receipt'}:
            d.ellipse((x-100,y-100,x+100,y+100),outline=MINT,width=3)
        prop(d,beat['prop'],x,y)
    d.rounded_rectangle((55,923,665,1093),radius=22,fill='#080d18')
    centered(d,caption,949,34,width=565)
    d.text((58,1141),f'{index+1:02} / {len(story["beats"]):02}',font=font(20),fill='#a2aec5')
    d.rounded_rectangle((55,1190,665,1198),radius=4,fill='#293955')
    d.rounded_rectangle((55,1190,max(63,55+610*progress),1198),radius=4,fill=MINT)
    return im
