import unittest
from unittest.mock import patch
from sticktwist.spend_movie import captions,phrase_time,shot_plan,Film,check_film_report

class FilmPlanTests(unittest.TestCase):
    def test_native_caption_times_preserve_words_and_do_not_overlap(self):
        tokens=[{'text':w,'start':i*.3,'end':i*.3+.28} for i,w in enumerate(['The','cafe','owns','the','mug','.'])]
        result=captions([{'tokens':tokens}],2)
        self.assertEqual(' '.join(c['text'] for c in result),'The cafe owns the mug.')
        self.assertTrue(all(a['end']<=b['start'] for a,b in zip(result,result[1:])))
    def test_phrase_uses_actual_spoken_timestamp(self):
        beat={'start':0,'tokens':[{'text':'Twenty-four','start':1,'end':2},{'text':'hours','start':2,'end':3}]}
        self.assertEqual(phrase_time(beat,'Twenty-four hours'),1)
        with self.assertRaises(ValueError):phrase_time(beat,'twenty five')
    def test_changed_narrative_structure_fails_before_media(self):
        with self.assertRaises(ValueError):shot_plan([], 'short',54)
    def test_local_media_processing_refused(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(RuntimeError):Film('short',[],54)

    def test_decoded_stream_report_rejects_wrong_dimensions_and_frame_rate(self):
        report='Stream #0:0: Video: h264 (High), yuv420p, 1080x1920, 24 fps\nStream #0:1: Audio: aac (LC), 24000 Hz, mono'
        check_film_report(report,(1080,1920))
        for changed in [report.replace('24 fps','124 fps'),report.replace('1080x1920','1080x19200'),report.replace('Audio: aac','Audio: mp3')]:
            with self.assertRaises(RuntimeError):check_film_report(changed,(1080,1920))
