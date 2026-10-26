import copy
import json
import unittest
from sticktwist.core import ROOT
from sticktwist.story_audio import validate_story


class SpendingStoryTests(unittest.TestCase):
    def setUp(self):
        self.story=json.loads((ROOT/'stories/spend100m.json').read_text(encoding='utf-8-sig'))

    def test_exact_budget_and_three_dollar_finale(self):
        validate_story(self.story)
        self.assertEqual(sum(x['dollars'] for x in self.story['spending_ledger']),100000000)
        self.assertEqual(sum(x['dollars'] for x in self.story['spending_ledger'][:-1]),99999997)
        self.assertEqual(self.story['rules']['reward_dollars'],1000000000)

    def test_changed_cost_is_rejected(self):
        changed=copy.deepcopy(self.story)
        changed['spending_ledger'][0]['dollars']+=1
        with self.assertRaises(ValueError):
            validate_story(changed)

    def test_unapproved_voice_is_rejected(self):
        self.story['voice']='af_heart'
        with self.assertRaises(ValueError):
            validate_story(self.story)

    def test_both_formats_have_complete_scripts_without_publication_approval(self):
        validate_story(self.story)
        self.assertFalse(self.story['finished_script_owner_approved'])
        self.assertIn('One billion dollars.',self.story['short']['beats'][-1]['text'])
        self.assertIn('The challenge had ended.',self.story['long']['chapters'][-1]['text'])
