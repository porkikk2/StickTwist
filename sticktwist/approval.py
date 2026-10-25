"""Fail-closed approval and exact bundle integrity checks; no media work."""
import json
import re
import zipfile
from pathlib import Path
from .core import digest, validate


def verify_approval(episode, sha, visibility, confirmation, actor, owner):
    if actor != owner:
        raise ValueError('Only the repository owner may approve')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}',episode):
        raise ValueError('Invalid episode')
    if not re.fullmatch(r'[0-9a-f]{64}',sha):
        raise ValueError('Expected SHA256')
    if visibility not in {'private','unlisted','public'}:
        raise ValueError('Invalid visibility')
    expected = f'APPROVE {episode} {sha} {visibility}'
    if confirmation != expected:
        raise ValueError('Confirmation must exactly match episode, bundle SHA256 and visibility')


def unpack_verified(bundle, expected_sha, episode, destination):
    if digest(bundle) != expected_sha:
        raise ValueError('Bundle changed since approval')
    required = {'video.mp4','captions.srt','story.json','metadata.json','review.jpg','manifest.json'}
    with zipfile.ZipFile(bundle) as z:
        if len(z.namelist()) != len(required) or set(z.namelist()) != required:
            raise ValueError('Unexpected or unsafe ZIP contents')
        if sum(x.file_size for x in z.infolist()) > 150*1024*1024:
            raise ValueError('Oversized bundle')
        z.extractall(destination)
    folder = Path(destination)
    manifest = json.loads((folder/'manifest.json').read_text())
    if manifest['episode_id'] != episode or set(manifest['files']) != required-{'manifest.json'}:
        raise ValueError('Manifest does not match episode')
    for name, sha in manifest['files'].items():
        if digest(folder/name) != sha:
            raise ValueError(f'Asset hash mismatch: {name}')
    story = validate(json.loads((folder/'story.json').read_text()))
    if story['id'] != episode:
        raise ValueError('Story episode mismatch')
    metadata = json.loads((folder/'metadata.json').read_text())
    if 'privacyStatus' in metadata['status'] or 'publishAt' in metadata['status']:
        raise ValueError('Visibility must come from explicit approval')
    return metadata
