import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENES = {'shock', 'room', 'phone', 'deal', 'receipt', 'reveal', 'ending'}
PROPS = {'console', 'phone', 'box', 'ticket', 'key', 'note', 'cash'}


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def validate(story):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', story['id']):
        raise ValueError('Invalid episode id')
    if not 1 <= len(story['title']) <= 90:
        raise ValueError('Invalid title length')
    if story.get('fiction') is not True or story.get('language') != 'en':
        raise ValueError('Only labelled English fiction')
    if not 6 <= len(story['beats']) <= 9:
        raise ValueError('Expected six to nine beats')
    words = 0
    for beat in story['beats']:
        if beat['scene'] not in SCENES or beat['prop'] not in PROPS:
            raise ValueError('Unknown scene or prop')
        if not beat['text'].strip() or not 1 <= len(beat['label']) <= 35:
            raise ValueError('Empty text or invalid label')
        words += len(beat['text'].split())
    if not 85 <= words <= 145:
        raise ValueError(f'Narration outside editorial range: {words} words')
    return story


def caption_chunks(text, start, duration, group=5):
    # Phrase estimates, not forced alignment; owner reviews sync before approval.
    words = text.split()
    weights = [max(1, len(re.sub(r'\W', '', w))) for w in words]
    total, elapsed, result = sum(weights), 0, []
    for i in range(0, len(words), group):
        weight = sum(weights[i:i+group])
        result.append({'start': start + duration * elapsed / total,
                       'end': start + duration * (elapsed + weight) / total,
                       'text': ' '.join(words[i:i+group])})
        elapsed += weight
    return result


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def cloud_only():
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
        os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted' or
        os.environ.get('RUNNER_OS') != 'Linux'):
        raise RuntimeError('Media processing requires GitHub-hosted Linux; local rendering is prohibited')
