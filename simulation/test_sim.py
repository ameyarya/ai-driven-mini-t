import unittest
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


if __name__=='__main__':unittest.main()
