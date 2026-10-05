"""Obstacle navigation tests: ideal map/ranges, independent contact checks."""
import math
import unittest
import obstacle_navigation as nav
from rover_sim import RoverSim


class ObstacleTests(unittest.TestCase):
    def setUp(self):self.sim=RoverSim(render=False)
    def tearDown(self):self.sim.close()

    def test_route_chooses_only_open_side(self):
        for scene,sign in [('left_open',1),('right_open',-1)]:
            obstacles=nav.preset(scene);path=nav.route((0,0),(.85,0),obstacles)
            self.assertIsNotNone(path)
            self.assertTrue(any(sign*y>.4 for x,y in path))
            self.assertTrue(all(nav.segment_safe(a,b,obstacles) for a,b in zip(path,path[1:])))

    def test_enclosed_robot_stops_without_motion_or_firing(self):
        self.sim.reset(distance=1.2,obstacle_scene='blocked');self.sim.start_avoidance()
        self.assertIsNone(self.sim.plan);self.assertEqual(self.sim.status,'Stopped: no clear route')
        self.assertEqual((self.sim.x,self.sim.y),(0,0));self.assertFalse(self.sim.shots)

    def test_long_manual_drive_cannot_tunnel_through_block(self):
        self.sim.reset(distance=1.2,obstacle_scene='block')
        for _ in range(10):self.sim.move('forward',1000)
        self.assertGreater(self.sim.guard_stops,0)
        self.assertGreaterEqual(nav.clearance(self.sim.x,self.sim.y,self.sim.obstacles),nav.MARGIN-1e-9)
        self.assertEqual(self.sim.obstacle_contacts,0)

    def test_backward_guard_and_turning_footprint(self):
        self.sim.reset(obstacles=[dict(x=-.35,y=0,hx=.05,hy=.1)])
        self.assertFalse(self.sim.move('backward',1000));self.assertEqual(self.sim.obstacle_contacts,0)
        before=(self.sim.x,self.sim.y);self.sim.move('left',1000)
        self.assertEqual((self.sim.x,self.sim.y),before);self.assertEqual(self.sim.obstacle_contacts,0)

    def test_simulated_ranges_track_orientation(self):
        self.sim.reset(distance=1.2,obstacle_scene='block')
        initial=self.sim.obstacle_state()['ranges_m']
        self.assertAlmostEqual(initial['0'],.3);self.assertEqual(initial['90'],2.5)
        self.sim.heading=math.pi/2;self.sim._pose()
        self.assertAlmostEqual(self.sim.obstacle_state()['ranges_m']['-90'],.3)

    def test_bad_obstacles_rejected_without_resetting_scene(self):
        for obstacles in [[dict(x=0,y=0,hx=.1,hy=.1)],
                          [dict(x=1,y=0,hx=-1,hy=.1)],
                          [dict(x=float('nan'),y=0,hx=.1,hy=.1)]]:
            with self.assertRaises(ValueError):self.sim.reset(obstacles=obstacles)
        with self.assertRaises(ValueError):self.sim.reset(obstacle_scene='unknown')
        self.assertEqual(self.sim.obstacle_scene,'clear')

    def test_goal_inside_inflated_obstacle_fails_closed(self):
        self.assertIsNone(nav.route((0,0),(.55,0),nav.preset('block')))
        self.assertIsNone(nav.route((0,0),(5,0),[]))

    def test_starting_avoidance_does_not_reload_ammunition(self):
        self.sim.fire();shots=list(self.sim.shots)
        self.sim.start_avoidance()
        self.assertEqual(self.sim.shots,shots)

    def test_contact_monitor_detects_forced_overlap_at_far_end_of_wall(self):
        self.sim.reset(distance=1.2,obstacle_scene='left_open')
        # Bypass the guard to verify contact evidence is independently sensitive.
        self.sim.x=.55;self.sim.y=.28;self.sim._pose();self.sim.advance(.01)
        self.assertGreater(self.sim.obstacle_contacts,0)

    def test_100_varied_obstacle_missions(self):
        reached=blocked=0
        for i in range(100):
            scene=('block','left_open','right_open','wall','blocked')[i%5]
            self.sim.reset(distance=1.2+(i%4)*.1,lateral=((i//5)%3-1)*.1,
                           heading=((i%3)-1)*.5,obstacle_scene=scene)
            self.sim.start_avoidance()
            for _ in range(121):
                if not self.sim.plan:break
                self.sim.step_goal()
                self.assertGreaterEqual(nav.clearance(self.sim.x,self.sim.y,self.sim.obstacles),nav.MARGIN-1e-9)
            self.assertIsNone(self.sim.plan,f'case {i}');self.assertEqual(self.sim.obstacle_contacts,0,f'case {i}')
            self.assertFalse(self.sim.shots)
            if scene=='blocked':
                self.assertEqual(self.sim.status,'Stopped: no clear route');blocked+=1
            else:
                self.assertEqual(self.sim.status,'Obstacle goal achieved',f'case {i}: {self.sim.status}');reached+=1
        self.assertEqual((reached,blocked),(80,20))


if __name__=='__main__':unittest.main()
