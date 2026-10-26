"""Narrated drafts of the owner-selected $100m story; no video render/upload."""
import json
import os
from pathlib import Path
from .core import ROOT,cloud_only,digest,write_json
from .audio_auditions import SR,music,effect,mix,mp3,duration,command


def validate_story(story):
    if story['id']!='spend-100m-in-one-day' or story.get('fiction') is not True:
        raise ValueError('Expected the owner-selected fictional challenge')
    if story['voice']!='am_michael' or not story['voice_owner_approved']:
        raise ValueError('Voice does not match owner selection 1')
    if sum(item['dollars'] for item in story['spending_ledger'])!=100000000:
        raise ValueError('Spending ledger must equal exactly $100 million')
    if story['spending_ledger'][-1]['dollars']!=3:
        raise ValueError('Final coffee payoff requires exactly three dollars')
    for fmt,key,low,high in [('short','beats',90,150),('long','chapters',900,1150)]:
        actual=sum(len(b['text'].split()) for b in story[fmt][key])
        if actual!=story[fmt]['word_count'] or not low<=actual<=high:
            raise ValueError(f'Unexpected {fmt} script length: {actual}')
    return story


def main():
    cloud_only()
    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KPipeline,KModel
    from .github import GitHub
    story=validate_story(json.loads((ROOT/'stories/spend100m.json').read_text(encoding='utf-8-sig')))
    torch.set_num_threads(2)
    out=Path('build/spend100m-audio');out.mkdir(parents=True,exist_ok=True)
    model=KModel(repo_id='hexgrad/Kokoro-82M').to('cpu').eval()
    pipeline=KPipeline(lang_code='a',repo_id='hexgrad/Kokoro-82M',model=model)
    manifest={'story_id':story['id'],'voice':'am_michael','voice_option':1,
              'source_commit':os.environ['GITHUB_SHA'],'fiction':True,
              'prices_are_invented':True,'publishing_approved':False,
              'working_music_not_owner_selected':True,'formats':{},'files':{}}
    normalized={}
    for fmt,key,label in [('short','beats','01-short-voice'),('long','chapters','03-long-voice')]:
        parts=[];timeline=[];clock=0
        for beat in story[fmt][key]:
            arrays=[];tokens=[];chunk_clock=0
            for result in pipeline(beat['text'],voice='am_michael',speed=.98,split_pattern=r'\n+'):
                gs,ps,audio=result
                if audio is None:
                    raise RuntimeError('Narration missing')
                arr=audio.detach().cpu().numpy() if hasattr(audio,'detach') else np.asarray(audio)
                seconds=len(arr)/SR
                for token in getattr(result,'tokens',None) or []:
                    start=getattr(token,'start_ts',None);end=getattr(token,'end_ts',None)
                    if start is not None and end is not None and end>start:
                        tokens.append({'text':token.text,'start':clock+chunk_clock+max(0,start),
                                       'end':clock+chunk_clock+min(seconds,end)})
                arrays.append(arr);chunk_clock+=seconds
            if not arrays:
                raise RuntimeError('Empty narrative beat')
            segment=np.concatenate(arrays)
            seconds=len(segment)/SR
            timeline.append({'title':beat['title'],'scene':beat['scene'],'text':beat['text'],
                             'start':clock,'spoken_seconds':seconds,'tokens':tokens})
            parts.extend([segment,np.zeros(round(.18*SR),dtype=np.float32)])
            clock+=seconds+.18
        raw=out/f'{fmt}-raw.wav'
        sf.write(raw,np.concatenate(parts),SR,subtype='PCM_16')
        clean=out/f'{fmt}-voice.wav'
        command(['ffmpeg','-y','-v','error','-i',str(raw),'-af','loudnorm=I=-16:TP=-2:LRA=7',
                 '-ar',str(SR),'-ac','1','-c:a','pcm_s16le',str(clean)])
        seconds=duration(clean)
        if (fmt=='short' and not 30<=seconds<=60) or (fmt=='long' and not 300<=seconds<=480):
            raise RuntimeError(f'Unexpected {fmt} narration duration: {seconds}; edit the draft before rendering')
        mp3(clean,out/f'{label}.mp3')
        write_json(out/f'{fmt}-timeline.json',timeline)
        normalized[fmt]=clean
        manifest['formats'][fmt]={'seconds':seconds,'word_count':story[fmt]['word_count'],
                                  'timing':'native Kokoro token duration estimates within narrative beats'}
        print(f'{fmt.upper()}_NARRATION_SECONDS={seconds:.3f}')
    seconds=duration(normalized['short'])
    sf.write(out/'short-music.wav',music(seconds,'suspense'),SR,subtype='PCM_16')
    sfx=np.zeros(round(seconds*SR),dtype=np.float32)
    timeline=json.loads((out/'short-timeline.json').read_text())
    events=[(.25,'notification'),(timeline[1]['start']+.1,'whoosh'),
            (timeline[2]['start']+.1,'paper'),(timeline[4]['start']+.1,'reveal'),
            (seconds-2.2,'notification')]
    for at,kind in events:
        start=round(at*SR);snd=effect(kind);count=min(len(snd),len(sfx)-start)
        if count>0:
            sfx[start:start+count]+=snd[:count]*.65
    sf.write(out/'short-effects.wav',sfx,SR,subtype='PCM_16')
    mix(normalized['short'],out/'short-music.wav',out/'short-effects.wav',out/'02-short-working-mix.mp3',seconds)
    for file in sorted(out.glob('*.mp3')):
        decoded=__import__('subprocess').check_output(['ffmpeg','-v','error','-i',str(file),'-f','f32le','-ac','1','-ar',str(SR),'pipe:1'])
        samples=np.frombuffer(decoded,dtype='<f4')
        peak=float(np.max(np.abs(samples)));rms=float(np.sqrt(np.mean(samples*samples)))
        if not .0001<rms or peak>=1:
            raise RuntimeError('Invalid narrated audio: '+file.name)
        manifest['files'][file.name]={'sha256':digest(file),'seconds':duration(file),'rms':rms,'peak':peak}
    write_json(out/'story-audio-manifest.json',manifest)
    write_json(out/'spend100m-script.json',story)
    gh=GitHub()
    tag=f'spend100m-audio-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}'
    body=('UNPUBLISHED DRAFT — owner-selected voice 1 and $100m challenge premise.\n\n'
          '01 is the short narration, 02 adds a provisional suspense score and effects, 03 is the complete long-form narrated draft.\n\n'
          'All prices are fictional. Exact spending total: $100,000,000. Final coffee: $3.\n\n'
          'No video render, no YouTube upload, no publishing approval. Working music is not yet owner-approved.\n\n'
          'Long-form narration is provided without a music bed so the complete script can be evaluated first.')
    release=gh.draft(tag,'StickTwist — Spend $100m / narrated script drafts',body)
    for file in sorted(out.iterdir()):
        if file.suffix in {'.mp3','.json'}:
            gh.upload(release,file)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
        summary.write(f'## Spend $100m narrated drafts\n\n[Open unpublished audio]({release["html_url"]})\n\n'
                      f'Shorts: {manifest["formats"]["short"]["seconds"]:.2f}s. Long draft: '
                      f'{manifest["formats"]["long"]["seconds"]:.2f}s. Voice: owner-selected option 1.\n')
    print('STORY_AUDIO_URL='+release['html_url'])


if __name__=='__main__':
    main()
