import json
import os
from pathlib import Path
from .core import digest
from .github import GitHub


def main():
    gh = GitHub()
    queue = json.loads(Path('build/queue.json').read_text())
    tag = f'preview-{queue["week"]}-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}'
    notes = ['# StickTwist — owner review only', '',
             'UNPUBLISHED DRAFT. Do not publish this release: videos have not been approved.',
             'Download each ZIP, watch video.mp4, inspect captions.srt, review.jpg and metadata.json.',
             'No YouTube upload has happened. Suggested slots are editorial suggestions only.', '',
             '| Episode | Bundle SHA256 |', '|---|---|']
    bundles = sorted(Path('build/previews').glob('*.zip'))
    for bundle in bundles:
        notes.append(f'| {bundle.stem} | `{digest(bundle)}` |')
    notes.extend(['', 'To authorize a YouTube upload, use Actions → Approve YouTube upload.',
                  'Approval includes the exact ZIP SHA256, episode id and chosen visibility.',
                  'TTS captions use approximate phrase timing. Check pronunciation and sync.',
                  'All characters/events are fictional. No paid APIs or local video processing.'])
    body = '\n'.join(notes)
    release = gh.draft(tag, f'StickTwist review — {queue["week"]}',body)
    for bundle in bundles:
        gh.upload(release,bundle)
        gh.upload(release,bundle.with_suffix('.sha256'))
    gh.upload(release,Path('build/queue.json'))
    url = release['html_url']
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
        summary.write(f'## Owner review\n\n[Open unpublished draft]({url})\n\n'+body+'\n')
    print(f'Preview stored as unpublished draft: {url}')


if __name__ == '__main__':
    main()
