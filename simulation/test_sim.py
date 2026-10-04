import unittest
import math
import numpy as np
from rover_sim import RoverSim


class ProjectileTests(unittest.TestCase):
    def setUp(self):self.sim=RoverSim(render=False)
    def tearDown(self):self.sim.close()

    def test_contact_ground_truth_distinguishes_hit_and_miss(self):
        self.assertTrue(self.sim.fire()['contact_hit'])
        self.sim.reset(lateral=.3)
        self.assertFalse(self.sim.fire()['contact_hit'])

    def test_six_shots_then_reload(self):
        for _ in range(6):self.sim.fire()
        with self.assertRaises(ValueError):self.sim.fire()
        self.sim.reset();self.assertTrue(self.sim.fire()['contact_hit'])

    def test_pivot_stays_in_place_and_reverse_reverses(self):
        self.sim.move('right',500)
        self.assertEqual((self.sim.x,self.sim.y),(0,0))
        self.assertLess(self.sim.heading,0)
        self.sim.move('forward',500);x,y=self.sim.x,self.sim.y
        self.sim.move('backward',500)
        self.assertAlmostEqual(self.sim.x,0);self.assertAlmostEqual(self.sim.y,0)
        self.assertGreater(x,0);self.assertLess(y,0)

    def test_100_deterministic_shot_scenarios(self):
        # Half aligned, half laterally displaced. Compare actual projectile-can
        # contacts, not can motion or a planner's claimed success.
        for i in range(100):
            lateral=0 if i%2==0 else .25
            self.sim.reset(distance=.4+(i%10)*.02,lateral=lateral)
            self.assertEqual(self.sim.fire()['contact_hit'],i%2==0, f'case {i}')

    def test_up_down_changes_elevation_without_driving(self):
        self.sim.launcher('up',250)
        self.assertAlmostEqual(self.sim.elevation,7.5)
        self.assertEqual((self.sim.x,self.sim.y,self.sim.heading),(0,0,0))
        axis=self.sim.data.body('launcher').xmat.reshape(3,3)[:,0]
        self.assertAlmostEqual(axis[2],math.sin(math.radians(7.5)))
        self.sim.launcher('down',250)
        self.assertAlmostEqual(self.sim.elevation,0)

    def test_limits_stop_and_reset(self):
        for _ in range(3):self.sim.launcher('up',1000)
        self.assertEqual(self.sim.elevation,45)
        self.sim.launcher('stop',1000);self.assertEqual(self.sim.elevation,45)
        for _ in range(3):self.sim.launcher('down',1000)
        self.assertEqual(self.sim.elevation,-10)
        self.sim.reset();self.assertEqual(self.sim.elevation,0)

    def test_invalid_launcher_commands_preserve_pose(self):
        for action,duration in [('spin',250),('up',-1),('down',1001),('up',True),('up',2.5)]:
            with self.assertRaises(ValueError):self.sim.launcher(action,duration)
            self.assertEqual(self.sim.elevation,0)

    def test_shot_uses_current_elevation_and_lowering_recovers_hit(self):
        self.sim.launcher('up',1000)
        shot=self.sim.fire()
        self.assertAlmostEqual(shot['elevation'],30)
        self.assertFalse(shot['contact_hit'])
        self.sim.launcher('down',1000)
        self.assertTrue(self.sim.fire()['contact_hit'])

    def test_100_elevated_shot_scenarios(self):
        # Same near-range scenes, half level hits and half raised misses.
        # Exercise the launcher commands, not only fire(elevation=...).
        for i in range(100):
            self.sim.reset(distance=.4+(i%10)*.02)
            self.sim.launcher('up',1000)
            if i%2==0:self.sim.launcher('down',1000)
            shot=self.sim.fire()
            self.assertEqual(shot['contact_hit'],i%2==0,f'elevation case {i}')

    def test_projectile_and_barrel_share_elevation_and_heading(self):
        self.sim.move('left',500);self.sim.launcher('up',500)
        direction=self.sim.data.body('launcher').xmat.reshape(3,3)[:,0].copy()
        captured=[]
        original=self.sim.advance
        self.sim.advance=lambda seconds:captured.append(self.sim.data.qvel[self.sim.ball_velocity:self.sim.ball_velocity+3].copy())
        try:self.sim.fire()
        finally:self.sim.advance=original
        np.testing.assert_allclose(captured[0],direction*6,atol=1e-10)


if __name__=='__main__':unittest.main()
