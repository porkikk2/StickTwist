import argparse
import json
import math
import subprocess
import wave
import zipfile
from pathlib import Path
from .core import ROOT, cloud_only, digest, validate, caption_chunks, srt_time, write_json

FPS = 24
VOICE = 'en_US-ljspeech-medium'


def run(args):
    subprocess.run(args, check=True)


def wav_seconds(path):
    with wave.open(str(path), 'rb') as w:
        return w.getnframes()/w.getframerate()


def verify_video(path, expected):
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    seconds = float(probe['format']['duration'])
    if (video['width'],video['height'],video['codec_name'],video['pix_fmt']) != (1080,1920,'h264','yuv420p'):
        raise ValueError('Unexpected output video format')
    if audio['codec_name'] != 'aac' or not 20 <= seconds <= 59.9 or abs(seconds-expected) > .2:
        raise ValueError(f'Invalid media duration/codec: {seconds}')
    return probe


def render(story, output):
    cloud_only()  # Before importing media libraries or opening any audio/video.
    from piper import PiperVoice, SynthesisConfig
    from PIL import Image, ImageDraw
    from .art import frame, W, H
    validate(story)
    folder = Path(output)/story['id']
    folder.mkdir(parents=True, exist_ok=True)
    model = ROOT/'models'/f'{VOICE}.onnx'
    if not model.exists():
        raise FileNotFoundError('Download the licensed LJ Speech model in the cloud setup step')
    voice = PiperVoice.load(str(model))
    audio_paths = []
    for i, beat in enumerate(story['beats']):
        path = folder/f'raw-{i}.wav'
        with wave.open(str(path),'wb') as w:
            voice.synthesize_wav(beat['text'], w, syn_config=SynthesisConfig(length_scale=.92))
        audio_paths.append(path)
    # Speed up only if needed; no truncation of narration.
    raw_total = sum(wav_seconds(p) for p in audio_paths)
    speed = max(1,raw_total/(57-len(audio_paths)*.18))
    if speed > 1.30:
        raise ValueError('Narration too long; edit script rather than making unintelligible speech')
    timeline, captions, cursor = [], [], 0
    audio = folder/'narration.wav'
    with wave.open(str(audio),'wb') as merged:
        merged.setparams((1,2,22050,0,'NONE','not compressed'))
        for i, (beat,path) in enumerate(zip(story['beats'],audio_paths)):
            processed = folder/f'voice-{i}.wav'
            run(['ffmpeg','-y','-v','error','-i',str(path),'-af',f'atempo={speed:.6f}',
                 '-ar','22050','-ac','1','-c:a','pcm_s16le',str(processed)])
            with wave.open(str(processed),'rb') as part:
                samples = part.readframes(part.getnframes())
            spoken = len(samples)/2/22050
            count = math.ceil((spoken+.18)*FPS)
            duration = count/FPS
            merged.writeframes(samples + b'\0'*(2*round(duration*22050)-len(samples)))
            cues = caption_chunks(beat['text'],cursor,spoken)
            captions.extend(cues)
            timeline.append({'start':cursor,'duration':duration,'frames':count,'captions':cues})
            cursor += duration
    srt = folder/'captions.srt'
    srt.write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}'
                              for i,c in enumerate(captions))+'\n',encoding='utf-8')
    mp4 = folder/'video.mp4'
    cmd = ['ffmpeg','-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}',
           '-framerate',str(FPS),'-i','pipe:0','-i',str(audio),'-vf','scale=1080:1920:flags=lanczos',
           '-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k',
           '-af','loudnorm=I=-16:TP=-1.5:LRA=11','-movflags','+faststart','-shortest',str(mp4)]
    sheet = Image.new('RGB',(W//3*4,H//3*2),'#101729')
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as ff:
        try:
            for i, (beat,timing) in enumerate(zip(story['beats'],timeline)):
                for n in range(timing['frames']):
                    t = n/FPS
                    now = timing['start']+t
                    cue = next((c['text'] for c in timing['captions'] if c['start'] <= now < c['end']), '')
                    image = frame(story,beat,i,t,now/cursor,cue)
                    ff.stdin.write(image.tobytes())
                    if n == timing['frames']//2:
                        sheet.paste(image.resize((W//3,H//3)),((i%4)*(W//3),(i//4)*(H//3)))
            ff.stdin.close()
            if ff.wait() != 0:
                raise RuntimeError('FFmpeg encoding failed')
        except BaseException:
            ff.kill()
            raise
    sheet.save(folder/'review.jpg',quality=88)
    probe = verify_video(mp4,cursor)
    write_json(folder/'story.json',story)
    metadata = {'snippet': {'title':story['title']+' #Shorts',
                'description': 'An original fictional StickTwist story. Characters and events are invented.\n'
                               '2D stickman animation with synthetic narration.\n#StickTwist #Stickman #Shorts',
                'tags':['StickTwist','stickman','fiction','animated stories','shorts'],
                'categoryId':'1','defaultLanguage':'en','defaultAudioLanguage':'en'},
                'status': {'selfDeclaredMadeForKids':False,'containsSyntheticMedia':True}}
    write_json(folder/'metadata.json',metadata)
    files = ['video.mp4','captions.srt','story.json','metadata.json','review.jpg']
    manifest = {'episode_id':story['id'],'files':{f:digest(folder/f) for f in files},
                'duration_seconds':float(probe['format']['duration']),
                'caption_timing':'phrase estimates within TTS beats; human review required',
                'tts':VOICE,'fps':FPS,'resolution':'1080x1920',
                'source_commit':__import__('os').environ.get('GITHUB_SHA','unknown')}
    write_json(folder/'manifest.json',manifest)
    bundle = Path(output)/f'{story["id"]}.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in files+['manifest.json']:
            z.write(folder/f,f)
    sha = digest(bundle)
    (Path(output)/f'{story["id"]}.sha256').write_text(sha+'\n',encoding='ascii')
    print(f'REVIEW ONLY: {bundle.name}  SHA256={sha}  duration={cursor:.2f}s')
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--queue',default='build/queue.json')
    p.add_argument('--limit',type=int,choices=[1,5],default=5)
    args = p.parse_args()
    cloud_only()
    queue = json.loads(Path(args.queue).read_text(encoding='utf-8-sig'))
    for episode in queue['episodes'][:args.limit]:
        render(episode['story'],'build/previews')


if __name__ == '__main__':
    main()
