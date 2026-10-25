import copy
import datetime as dt
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from sticktwist.core import ROOT, validate, cloud_only, caption_chunks, digest, write_json
from sticktwist.generate import candidates, make_queue, week_start
from sticktwist.approval import verify_approval, unpack_verified


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.story = next(candidates())
        self.sha = 'a'*64
        self.episode = self.story['id']
        self.confirm = f'APPROVE {self.episode} {self.sha} private'

    def test_entire_story_bank_is_valid_unique_english_fiction(self):
        bank = list(candidates())
        self.assertGreaterEqual(len(bank),25)
        self.assertEqual(len(bank),len({s['id'] for s in bank}))
        for story in bank:
            validate(story)

    def test_first_story_is_requested_ps5_story(self):
        self.assertEqual(self.story['title'],'My Best Friend Sold My PS5')

    def test_queue_has_five_unique_stories_and_never_auto_publishes(self):
        queue = make_queue(dt.date(2026,10,26),{'used':[],'weeks':{}})
        self.assertEqual(len({e['story']['id'] for e in queue['episodes']}),5)
        self.assertFalse(queue['auto_publish'])
        self.assertEqual(queue['episodes'][0]['suggested_slot'],'2026-10-26T17:00:00+00:00')

    def test_rerun_same_week_is_idempotent(self):
        state = {'used':[],'weeks':{}}
        queue = make_queue(dt.date(2026,10,26),state)
        self.assertEqual(make_queue(dt.date(2026,10,26),state),queue)
        self.assertEqual(len(state['used']),5)

    def test_next_week_does_not_recycle(self):
        state = {'used':[],'weeks':{}}
        a = make_queue(dt.date(2026,10,26),state)
        b = make_queue(dt.date(2026,11,2),state)
        self.assertFalse({e['story']['id'] for e in a['episodes']} & {e['story']['id'] for e in b['episodes']})

    def test_story_bank_exhaustion_fails_without_partial_state(self):
        state = {'used':[s['id'] for s in candidates()],'weeks':{}}
        before = copy.deepcopy(state)
        with self.assertRaises(RuntimeError):
            make_queue(dt.date(2030,1,7),state)
        self.assertEqual(state,before)

    def test_london_summer_slot_keeps_local_time(self):
        q = make_queue(dt.date(2027,6,7),{'used':[],'weeks':{}})
        self.assertEqual(q['episodes'][0]['suggested_slot'],'2027-06-07T17:00:00+01:00')

    def test_local_media_processing_is_rejected(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError):
                cloud_only()

    def test_self_hosted_runner_is_rejected(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux'},clear=True):
            with self.assertRaises(RuntimeError):
                cloud_only()

    def test_captions_are_contiguous_complete_and_within_speech(self):
        text = self.story['beats'][0]['text']
        cues = caption_chunks(text,3,7)
        self.assertEqual(' '.join(c['text'] for c in cues),text)
        self.assertEqual(cues[0]['start'],3)
        self.assertAlmostEqual(cues[-1]['end'],10)
        for a,b in zip(cues,cues[1:]):
            self.assertAlmostEqual(a['end'],b['start'])

    def test_owner_exact_approval_succeeds(self):
        verify_approval(self.episode,self.sha,'private',self.confirm,'owner','owner')

    def test_another_actor_cannot_approve(self):
        with self.assertRaises(ValueError):
            verify_approval(self.episode,self.sha,'private',self.confirm,'other','owner')

    def test_approval_cannot_change_video_or_visibility(self):
        for sha,visibility in [('b'*64,'private'),(self.sha,'public')]:
            with self.assertRaises(ValueError):
                verify_approval(self.episode,sha,visibility,self.confirm,'owner','owner')

    def test_unsafe_zip_and_wrong_bundle_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)/'unsafe.zip'
            with zipfile.ZipFile(bundle,'w') as z:
                z.writestr('../stolen.txt','no')
            with self.assertRaises(ValueError):
                unpack_verified(bundle,digest(bundle),self.episode,Path(tmp)/'out')
            with self.assertRaises(ValueError):
                unpack_verified(bundle,'0'*64,self.episode,Path(tmp)/'out')

    def test_manifest_detects_modified_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            files = {'video.mp4':b'data','captions.srt':b'data','review.jpg':b'data',
                     'story.json':json.dumps(self.story).encode(),
                     'metadata.json':b'{"status": {}}'}
            for name,data in files.items():
                (folder/name).write_bytes(data)
            manifest = {'episode_id':self.episode,'files':{n:digest(folder/n) for n in files}}
            (folder/'metadata.json').write_text('{"status":{"privacyStatus":"public"}}')
            bundle = folder/'test.zip'
            with zipfile.ZipFile(bundle,'w') as z:
                for name in files:
                    z.write(folder/name,name)
                z.writestr('manifest.json',json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                unpack_verified(bundle,digest(bundle),self.episode,folder/'out')


if __name__ == '__main__':
    unittest.main()
