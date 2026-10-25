"""Cloud-only Kokoro voice auditions and original procedural sound design."""
import json
import os
import subprocess
import wave
from pathlib import Path
from .core import cloud_only,digest,write_json

SR=24000
DEMO_TEXT=("At six o'clock, my phone showed me a photograph that hadn't been taken yet. "
           "Same room. Same red box. But the person opening it was wearing my face. "
           "I had twenty minutes to stop him. Then a message appeared. "
           "Don't trust the voice you're hearing right now.")
VOICES=[('01-american-male','a','am_michael',.98),
        ('02-british-male','b','bm_george',1.0),
        ('03-american-female','a','af_heart',1.0)]


def command(args):
    subprocess.run(args,check=True)


def duration(path):
    result=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(path)]))
    return float(result['format']['duration'])


def mp3(source,target):
    command(['ffmpeg','-y','-v','error','-i',str(source),'-c:a','libmp3lame','-b:a','192k',str(target)])


def music(seconds,kind):
    cloud_only()
    import numpy as np
    n=round(seconds*SR)
    result=np.zeros(n,dtype=np.float32)
    tempo=88 if kind=='suspense' else 104
    beat=60/tempo
    def note(at,frequency,length,level):
        start=round(at*SR);count=min(round(length*SR),n-start)
        if count<=0:
            return
        t=np.arange(count)/SR
        attack=np.minimum(t/.025,1)
        env=attack*np.exp(-t/(.48 if kind=='suspense' else .20))
        tone=np.sin(2*np.pi*frequency*t)+.18*np.sin(2*np.pi*frequency*2*t)
        result[start:start+count]+=level*env*tone
    pitches=[146.83,220,261.63,220,164.81,246.94,293.66,246.94] if kind=='suspense' else [261.63,329.63,392,329.63,293.66,349.23,440,349.23]
    for i in range(int(seconds/(beat/2))+1):
        note(i*beat/2,pitches[i%len(pitches)],beat*.85,.055)
        if i%4==0:
            note(i*beat/2,pitches[i%len(pitches)]/2,beat*2,.035)
    fade=np.minimum(np.arange(n)/(SR*.7),1)*np.minimum((n-1-np.arange(n))/(SR*.9),1)
    return result*fade


def effect(kind):
    cloud_only()
    import numpy as np
    rng=np.random.default_rng({'paper':2,'whoosh':3,'step':4,'notification':5,'reveal':6}[kind])
    lengths={'paper':.45,'whoosh':.4,'step':.17,'notification':.55,'reveal':1.1}
    t=np.arange(round(lengths[kind]*SR))/SR
    if kind=='paper':
        noise=rng.normal(0,1,len(t));noise=np.diff(noise,prepend=0)
        return (.10*noise*np.sin(np.pi*t/lengths[kind])**2).astype(np.float32)
    if kind=='whoosh':
        noise=rng.normal(0,1,len(t))
        return (.13*noise*np.sin(np.pi*t/lengths[kind])**3).astype(np.float32)
    if kind=='step':
        return (.14*np.sin(2*np.pi*(95*t-65*t*t))*np.exp(-t*32)+.025*rng.normal(0,1,len(t))*np.exp(-t*60)).astype(np.float32)
    if kind=='notification':
        return (.13*(np.sin(2*np.pi*880*t)+.45*np.sin(2*np.pi*1320*t))*np.exp(-t*9)).astype(np.float32)
    return (.14*(np.sin(2*np.pi*73.42*t)+.3*np.sin(2*np.pi*146.83*t))*np.exp(-t*5)).astype(np.float32)


def effect_timeline(seconds):
    cloud_only()
    import numpy as np
    track=np.zeros(round(seconds*SR),dtype=np.float32)
    events=[(.4,'step'),(.9,'step'),(3.0,'notification'),(6.6,'paper'),(10.6,'whoosh'),(max(12,seconds-3),'reveal')]
    for at,kind in events:
        start=round(at*SR);sound=effect(kind)
        count=min(len(sound),len(track)-start)
        if count>0:
            track[start:start+count]+=sound[:count]
    return track,events


def mix(narration,bed,sfx,destination,seconds):
    # Voice is the sidechain key: music ducks further whenever narration is present.
    filters=("[0:a]asplit=2[voice][key];"
             "[1:a]volume=0.30[music];"
             "[music][key]sidechaincompress=threshold=0.015:ratio=6:attack=15:release=300[duck];"
             "[2:a]volume=0.35[fx];"
             "[voice][duck][fx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.89:level=false[out]")
    command(['ffmpeg','-y','-v','error','-i',str(narration),'-i',str(bed),'-i',str(sfx),
             '-filter_complex',filters,'-map','[out]','-t',str(seconds),'-c:a','libmp3lame','-b:a','192k',str(destination)])


def main():
    cloud_only()
    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KPipeline,KModel
    from .github import GitHub
    torch.set_num_threads(2)
    out=Path('build/audio-auditions');out.mkdir(parents=True,exist_ok=True)
    model=KModel(repo_id='hexgrad/Kokoro-82M').to('cpu').eval()
    pipelines={code:KPipeline(lang_code=code,repo_id='hexgrad/Kokoro-82M',model=model) for code in ['a','b']}
    manifest={'script':DEMO_TEXT,'model':'hexgrad/Kokoro-82M','model_license':'Apache-2.0',
              'source':'https://huggingface.co/hexgrad/Kokoro-82M','sample_rate':SR,
              'source_commit':os.environ['GITHUB_SHA'],'voices':[],'files':{}}
    for label,code,voice,speed in VOICES:
        parts=[]
        for gs,ps,audio in pipelines[code](DEMO_TEXT,voice=voice,speed=speed,split_pattern=r'\n+'):
            if audio is not None:
                parts.append(audio.detach().cpu().numpy() if hasattr(audio,'detach') else np.asarray(audio))
        if not parts:
            raise RuntimeError('TTS produced no audio')
        audio=np.concatenate(parts)
        raw=out/f'{label}-raw.wav'
        sf.write(raw,audio,SR,subtype='PCM_16')
        clean=out/f'{label}.wav'
        command(['ffmpeg','-y','-v','error','-i',str(raw),'-af','loudnorm=I=-16:TP=-2:LRA=7',
                 '-ar',str(SR),'-ac','1','-c:a','pcm_s16le',str(clean)])
        mp3(clean,out/f'{label}.mp3')
        seconds=duration(clean)
        if not 12<=seconds<=40:
            raise RuntimeError(f'Unexpected audition duration: {seconds}')
        manifest['voices'].append({'label':label,'voice':voice,'speed':speed,'seconds':seconds})
    voice=out/'01-american-male.wav'
    seconds=duration(voice)
    fx,events=effect_timeline(seconds)
    sf.write(out/'sfx-timeline.wav',fx,SR,subtype='PCM_16')
    for kind,label in [('suspense','04-suspense-mix'),('comedy','05-comedy-mix')]:
        bed=music(seconds,kind)
        bedpath=out/f'music-{kind}.wav'
        sf.write(bedpath,bed,SR,subtype='PCM_16')
        mix(voice,bedpath,out/'sfx-timeline.wav',out/f'{label}.mp3',seconds)
        mp3(bedpath,out/f'music-{kind}.mp3')
    # A separate effects reel with gaps makes each reusable effect easy to evaluate.
    reel=np.zeros(SR*9,dtype=np.float32)
    for i,kind in enumerate(['step','paper','whoosh','notification','reveal']):
        snd=effect(kind);start=round((.3+i*1.6)*SR)
        reel[start:start+len(snd)]+=snd
        sf.write(out/f'sfx-{kind}.wav',snd,SR,subtype='PCM_16')
    sf.write(out/'sfx-reel.wav',reel,SR,subtype='PCM_16')
    mp3(out/'sfx-reel.wav',out/'06-effects-reel.mp3')
    # Check both duration and actual samples; fail rather than publishing a silent/clipped demo.
    for file in out.glob('*.mp3'):
        checked=subprocess.check_output(['ffmpeg','-v','error','-i',str(file),'-f','f32le','-ac','1','-ar',str(SR),'pipe:1'])
        samples=np.frombuffer(checked,dtype='<f4')
        rms=float(np.sqrt(np.mean(samples*samples)))
        peak=float(np.max(np.abs(samples)))
        if not .0001<rms or peak>=1 or not len(samples):
            raise RuntimeError(f'Invalid audio samples in {file.name}: rms={rms},peak={peak}')
        manifest['files'][file.name]={'sha256':digest(file),'seconds':duration(file),'rms':rms,'peak':peak}
    manifest['music']='Original procedural note sequences, no sampled soundtrack or paid service'
    manifest['sfx']='Original synthesized paper/whoosh/step/notification/reveal; no sampled recordings'
    manifest['demo_events']=events
    write_json(out/'audio-manifest.json',manifest)
    notes=['# StickTwist audio auditions','',
           'UNPUBLISHED DRAFT. No video render and no YouTube upload.',
           '01 / 02 / 03 are dry voices reading exactly the same script.',
           '04 / 05 use voice 01 with original suspense / comedy music and effects.',
           '06 is an isolated effects reel. music-* files let you judge the two beds separately.',
           'Music ducks under speech. These are auditions, not an approved production voice.',
           '',DEMO_TEXT,'','Kokoro model and weights: https://huggingface.co/hexgrad/Kokoro-82M (Apache-2.0).',
           'All synthesis and mixing ran on this standard GitHub-hosted CPU runner.']
    gh=GitHub();tag=f'audio-audition-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}'
    release=gh.draft(tag,'StickTwist — voice, music and SFX auditions','\n\n'.join(notes))
    for file in sorted(out.glob('*.mp3')):
        gh.upload(release,file)
    gh.upload(release,out/'audio-manifest.json')
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
        summary.write(f'## Voice and sound auditions\n\n[Open unpublished audio samples]({release["html_url"]})\n\n'
                      '3 dry voices, 2 full mixes, 2 original music beds, 1 effects reel. No video render.\n')
    print('AUDIO_REVIEW_URL='+release['html_url'])


if __name__=='__main__':
    main()
