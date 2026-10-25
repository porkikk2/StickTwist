import datetime as dt
import json
import os
import re
from pathlib import Path
from .core import cloud_only, write_json
from .approval import verify_approval, unpack_verified
from .github import GitHub


def main():
    cloud_only()
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    if event.get('sender',{}).get('login') != os.environ['GITHUB_REPOSITORY_OWNER']:
        raise ValueError('Owner-authored workflow dispatch is required')
    inputs = event['inputs']
    episode, sha, visibility = inputs['episode_id'], inputs['bundle_sha256'], inputs['visibility']
    verify_approval(episode,sha,visibility,inputs['confirmation'],
                    os.environ['GITHUB_ACTOR'],os.environ['GITHUB_REPOSITORY_OWNER'])
    tag = inputs['preview_tag']
    if not re.fullmatch(r'preview-\d{4}-\d{2}-\d{2}-\d+-\d+',tag):
        raise ValueError('Invalid preview tag')
    gh = GitHub()
    release = next((r for r in gh.releases() if r['tag_name'] == tag and r['draft']),None)
    if release is None:
        raise ValueError('An unpublished owner-review draft is required')
    assets = gh.request(f'releases/{release["id"]}/assets?per_page=100')
    asset = next((a for a in assets if a['name'] == episode+'.zip'),None)
    if asset is None:
        raise ValueError('Episode bundle not found')
    folder = Path('build/approved')
    folder.mkdir(parents=True,exist_ok=True)
    bundle = folder/'approved.zip'
    gh.download(asset,bundle)
    metadata = unpack_verified(bundle,sha,episode,folder)
    # Check channel before creating a durable upload claim.
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = Credentials.from_authorized_user_info(json.loads(os.environ['YOUTUBE_TOKEN_JSON']))
    youtube = build('youtube','v3',credentials=creds,cache_discovery=False)
    channel = youtube.channels().list(part='id',mine=True).execute(num_retries=0)
    ids = [c['id'] for c in channel.get('items',[])]
    if ids != [os.environ['YOUTUBE_CHANNEL_ID']]:
        raise ValueError('OAuth account does not match the intended YouTube channel')
    ledger = gh.draft('sticktwist-upload-ledger','PRIVATE DRAFT — upload ledger',
                      'Do not publish. Durable upload claims prevent accidental duplicate uploads.')
    existing = gh.request(f'releases/{ledger["id"]}/assets?per_page=100')
    # Paginate: a growing ledger must never miss an earlier upload claim.
    page = 2
    while len(existing) >= (page-1)*100:
        batch = gh.request(f'releases/{ledger["id"]}/assets?per_page=100&page={page}')
        existing.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    if any(a['name'] in {f'{episode}.pending.json', f'{episode}.uploaded.json'} for a in existing):
        raise ValueError('Upload already claimed or completed; inspect YouTube Studio before any recovery')
    record = {'episode_id':episode,'bundle_sha256':sha,'visibility':visibility,
              'approved_by':os.environ['GITHUB_ACTOR'],'run_id':os.environ['GITHUB_RUN_ID'],
              'time_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    pending = folder/f'{episode}.pending.json'
    write_json(pending,record)
    gh.upload(ledger,pending)  # Claim FIRST; a crash now blocks all automatic retries.
    metadata['status']['privacyStatus'] = visibility
    response = youtube.videos().insert(part='snippet,status',body=metadata,notifySubscribers=False,
        media_body=MediaFileUpload(str(folder/'video.mp4'),mimetype='video/mp4',resumable=True)).execute(num_retries=0)
    record['video_id'] = response['id']
    record['actual_visibility'] = response.get('status',{}).get('privacyStatus','unknown')
    receipt = folder/f'{episode}.uploaded.json'
    write_json(receipt,record)
    gh.upload(ledger,receipt)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
        summary.write(f'## Owner-approved upload\n\nVideo id: `{response["id"]}`\n\n'
                      f'Requested visibility: {visibility}. Actual visibility: {record["actual_visibility"]}.\n')
    print('Upload completed; receipt stored in unpublished ledger draft')


if __name__ == '__main__':
    main()
