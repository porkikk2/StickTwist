"""Offline story grammar, no paid API. No silent script recycling."""
import argparse
import datetime as dt
import hashlib
import json
from zoneinfo import ZoneInfo
from .core import ROOT, validate, write_json


def story_from_rows(identifier, title, rows):
    scenes = ['shock', 'room', 'phone', 'deal', 'receipt', 'reveal', 'ending']
    return validate({'id': identifier, 'title': title, 'language': 'en', 'fiction': True,
                     'beats': [dict(text=r[0], label=r[1], prop=r[2], scene=s)
                               for s, r in zip(scenes, rows)]})


def candidates():
    yield from json.loads((ROOT/'stories/launch.json').read_text(encoding='utf-8-sig'))
    items = [('camera','box'), ('guitar','box'), ('bike','key'), ('keyboard','box'),
             ('headphones','box'), ('skateboard','box'), ('tablet','phone'), ('projector','box')]
    people = [('Roommate','roommate'), ('Cousin','cousin'), ('Neighbor','neighbor')]
    for item, prop in items:
        for title, person in people:
            yield story_from_rows(f'{person}-rented-{item}', f'My {title} Rented Out My {item.title()}', [
                (f'My {person} rented out my {item} while I was away. Then asked me to deliver it.', 'DELIVERY FOR WHO?', prop),
                ('I came home to an empty shelf and a message saying we were finally starting a business.', 'EMPTY SHELF', prop),
                (f'Apparently, I supplied the {item}. My {person} supplied the confidence. Nobody had supplied my permission.', 'ZERO PERMISSION', 'phone'),
                ('I contacted the customer and explained everything. They had already paid a deposit and wanted a refund.', 'THE CUSTOMER', 'cash'),
                ('Then they sent me the listing. The collection address was our apartment. The contact number was mine.', 'MY NUMBER?', 'note'),
                (f'I got my {item} back and helped the customer cancel. My {person} complained that I had ruined the business.', 'BUSINESS CLOSED', prop),
                ('So I handed over an invoice for using my shelf. Suddenly, charging people without asking was a terrible idea.', 'FUNNY HOW THAT WORKS', 'note')])


def week_start(value=None):
    day = dt.date.fromisoformat(value) if value else dt.datetime.now(ZoneInfo('Europe/London')).date()
    return day-dt.timedelta(days=day.weekday())


def make_queue(week, state):
    key = week.isoformat()
    if key in state['weeks']:
        return state['weeks'][key]
    used = set(state['used'])
    selected = [s for s in candidates() if s['id'] not in used][:5]
    if len(selected) != 5:
        raise RuntimeError('Story bank exhausted. Add original scripts; recycling is disabled.')
    entries = []
    for offset, story in enumerate(selected):
        validate(story)
        fingerprint = hashlib.sha256(json.dumps(story, sort_keys=True).encode()).hexdigest()
        slot = dt.datetime.combine(week+dt.timedelta(days=offset), dt.time(17), ZoneInfo('Europe/London'))
        entries.append({'story': story, 'script_sha256': fingerprint,
                        'suggested_slot': slot.isoformat(), 'status': 'awaiting_render_and_owner_approval'})
    queue = {'week': key, 'timezone': 'Europe/London', 'auto_publish': False, 'episodes': entries}
    state['used'].extend(s['id'] for s in selected)
    state['weeks'][key] = queue
    return queue


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--week')
    p.add_argument('--output', default='build/queue.json')
    args = p.parse_args()
    path = ROOT/'queue/state.json'
    state = json.loads(path.read_text(encoding='utf-8-sig'))
    queue = make_queue(week_start(args.week), state)
    write_json(path, state)
    write_json(args.output, queue)
    print(f"Prepared five stories for {queue['week']}")


if __name__ == '__main__':
    main()
