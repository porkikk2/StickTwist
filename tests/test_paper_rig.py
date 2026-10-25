import math
import unittest
from sticktwist.paper_motion import ik,hero_pose,friend_pose,camera,FPS,SECONDS


class PaperRigTests(unittest.TestCase):
    def test_two_bone_joint_keeps_both_segment_lengths(self):
        for target in [(30,140),(-120,30),(500,0),(0,0)]:
            elbow,wrist=ik((0,0),target,82,85)
            self.assertAlmostEqual(math.dist((0,0),elbow),82,places=5)
            self.assertAlmostEqual(math.dist(elbow,wrist),85,places=5)

    def test_story_action_changes_position_expression_and_gesture(self):
        entry,shock,angry=hero_pose(.1),hero_pose(2.8),hero_pose(5.5)
        self.assertLess(entry['x'],shock['x']-100)
        self.assertEqual([entry['head'],shock['head'],angry['head']],[0,1,2])
        self.assertLess(shock['right_hand'][1],entry['right_hand'][1]-100)
        self.assertNotEqual(friend_pose(1)['head'],friend_pose(6)['head'])

    def test_all_frames_have_bounded_camera_and_finite_rig(self):
        self.assertEqual(FPS*SECONDS,192)
        for n in range(FPS*SECONDS):
            t=n/FPS
            for pose in [hero_pose(t),friend_pose(t)]:
                self.assertTrue(math.isfinite(pose['x']) and math.isfinite(pose['y']))
                self.assertTrue(400<pose['y']<650)
            zoom,cx,cy=camera(t)
            self.assertTrue(1<=zoom<=1.3)
            self.assertTrue(0<cx<720 and 0<cy<1280)
