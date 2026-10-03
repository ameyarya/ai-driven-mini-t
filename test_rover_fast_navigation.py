import base64
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import rover_fast_navigation as fast
from rover_autonomy import NavigationController

PLAN={'mode':'approach_size','target':'red soda can','height_percent':50,'uncertainties':[],'reason':'Approach and center'}


def measurement(x=50,height=30,visible=True,clipped=False):
    return {'target_visible':visible,'target_x':x,'target_height':height,'target_clipped':clipped}


class FastNavigationTests(unittest.TestCase):
    def test_planner_and_controller_display_roles_are_truthful(self):
        with tempfile.TemporaryDirectory() as d:
            frame=Path(d)/'frame-test.jpg';frame.write_bytes(b'raw image')
            labeled=Path(d)/'frame-labeled.jpg';labeled.write_bytes(b'exact labeled image')
            prepared={'model_frame':str(labeled),'measurement':measurement()}
            def response(url,body,timeout):
                self.assertEqual(base64.b64decode(body['messages'][0]['images'][0]),labeled.read_bytes())
                return {'model':'test','message':{'content':json.dumps(PLAN)}}
            with patch.object(fast.vision,'capture_frame',return_value=frame),patch.object(fast.vision,'prepare_detector_image',return_value=prepared),patch.object(fast.vision,'read_json',side_effect=response) as chat:
                plan=fast.plan_goal('Approach red can to 50% of image height')
                self.assertEqual(fast.vision.input_snapshot()['result']['input_role'],'qwen_planner')
                result=fast.observe_goal('Approach red can to 50% of image height',plan,[])
                self.assertEqual(chat.call_count,1)
                self.assertEqual(result['input_role'],'controller')
                self.assertEqual(result['input_sha256'],hashlib.sha256(labeled.read_bytes()).hexdigest())
                self.assertEqual(fast.vision.input_snapshot()['state'],'controller')

    def test_find_rotates_without_advancing_when_target_absent(self):
        plan=dict(PLAN,mode='find',height_percent=0,search_direction='right',full_turn_ms=None)
        fast.validate_plan(plan,'Find the red can by doing 360 turn in place')
        a=fast.control_decision(plan,measurement(visible=False),[])
        self.assertEqual(a['suggested_action'],'right')
        self.assertEqual(a['duration_ms'],500)
        self.assertFalse(a.get('needs_replan',False))
        self.assertFalse(a['heading_calibrated'])

    def test_find_requires_two_stationary_detections_then_stops(self):
        plan=dict(PLAN,mode='find',height_percent=0)
        first=fast.control_decision(plan,measurement(x=25),[])
        self.assertTrue(first['observe_again'])
        h=[{'action':'stop','duration_ms':0,'phase':'find_confirmation','target_x_before':25}]
        confirmed=fast.control_decision(plan,measurement(x=26),h)
        self.assertTrue(confirmed['goal_achieved'])
        self.assertEqual(confirmed['suggested_action'],'stop')
        lost=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(lost['suggested_action'],'right')

    def test_find_ambiguous_target_stops(self):
        plan=dict(PLAN,mode='find',height_percent=0)
        a=fast.control_decision(plan,dict(measurement(visible=False),candidate_count=2),[])
        self.assertEqual(a['suggested_action'],'stop')
        self.assertTrue(a['uncertainties'])

    def test_find_timed_limit_uses_full_history_and_stops_without_success(self):
        plan=dict(PLAN,mode='find',height_percent=0,full_turn_ms=4000)
        h=[{'action':'right','phase':'search','duration_ms':500}]*8
        a=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(a['suggested_action'],'stop')
        self.assertFalse(a['goal_achieved'])
        a=fast.control_decision(dict(plan,full_turn_ms=4100),measurement(visible=False),h)
        self.assertEqual(a['duration_ms'],100)

    def test_uncalibrated_search_exhausts_without_claiming_360_or_success(self):
        plan=dict(PLAN,mode='find',height_percent=0)
        h=[{'action':'right','phase':'search','duration_ms':500}]*39
        a=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(a['suggested_action'],'stop')
        self.assertFalse(a['goal_achieved'])
        self.assertIn('360 not calibrated',a['reason'])

    def test_find_controller_confirms_candidate_without_extra_turn(self):
        plan=dict(PLAN,mode='find',height_percent=0)
        frames=iter([measurement(visible=False),measurement(x=25),measurement(x=26)])
        moves=[]
        def observe(goal,plan,history):return {'captured_at':time.time(),'assessment':fast.control_decision(plan,next(frames),history)}
        c=NavigationController(None,moves.append,planner=lambda *a,**k:plan,fast_observe=observe)
        c.state['goal']='Find red can by rotating in place'
        with patch.object(c.cancelled,'wait',return_value=False):c.run(c.cancelled)
        self.assertEqual(moves,['D','X','X','X'])
        self.assertEqual(c.snapshot()['state'],'complete')

    def test_find_mission_cannot_silently_drop_approach(self):
        with self.assertRaises(ValueError):fast.validate_plan(dict(PLAN,mode='find'),'Find red can, then approach it')
        with self.assertRaises(ValueError):fast.validate_plan(PLAN,'Find red can by rotating 360')

    def test_alignment_before_approach_and_complete(self):
        for x,h,action,complete in [(30,30,'left',False),(70,30,'right',False),(50,30,'forward',False),(50,50.1,'stop',True),(30,51,'left',False)]:
            a=fast.control_decision(PLAN,measurement(x,h),[])
            self.assertEqual(a['suggested_action'],action)
            self.assertEqual(a['goal_achieved'],complete)

    def test_missing_target_and_clipping_never_advance(self):
        for m in [measurement(visible=False),measurement(clipped=True),measurement(height=None)]:
            a=fast.control_decision(PLAN,m,[])
            self.assertEqual(a['suggested_action'],'stop')
            self.assertFalse(a['goal_achieved'])

    def test_duration_learns_gain_and_shortens_near_goal(self):
        history=[{'action':'forward','duration_ms':250,'target_height_before':20}]
        far=fast.movement_duration('forward',20,measurement(height=25),history)
        near=fast.movement_duration('forward',2,measurement(height=25),history)
        self.assertGreater(far,near)
        self.assertLessEqual(far,1000)
        self.assertGreaterEqual(near,50)

    def test_overshoot_reverse_halves_previous_duration(self):
        h=[{'action':'left','duration_ms':100,'target_x_before':40}]
        self.assertEqual(fast.movement_duration('right',10,measurement(x=60),h),50)

    def test_stall_requires_planner_review(self):
        h=[{'action':'left','duration_ms':150,'target_x_before':30}]*3
        a=fast.control_decision(PLAN,measurement(x=30.1),h)
        self.assertTrue(a['needs_replan'])
        self.assertEqual(a['suggested_action'],'stop')

    def test_unsupported_or_uncertain_plan_rejected(self):
        for changes in [{'mode':'unsupported'},{'height_percent':0},{'uncertainties':['Path obstructed']},{'target':''}]:
            with self.assertRaises(ValueError):fast.validate_plan(dict(PLAN,**changes))

    def test_plan_cannot_drop_shooting_or_change_explicit_setpoint(self):
        for goal in ['Center can then shoot','Approach can to 40% of image height']:
            with self.assertRaises(ValueError):fast.validate_plan(PLAN,goal)

    def test_one_planner_call_for_multiple_control_steps(self):
        moves=[];calls=[];answers=iter([measurement(30),measurement(48),measurement(49,50)])
        def planner(goal,history):calls.append(goal);return PLAN
        def observe(goal,plan,history):
            return {'captured_at':time.time(),'assessment':fast.control_decision(plan,next(answers),history)}
        c=NavigationController(None,moves.append,planner=planner,fast_observe=observe)
        c.state['goal']='Approach red can to 50% image height'
        with patch.object(c.cancelled,'wait',return_value=False):c.run(c.cancelled)
        self.assertEqual(len(calls),1)
        self.assertEqual(moves,['A','X','W','X','X'])
        self.assertEqual(c.snapshot()['state'],'complete')

    def test_lost_target_review_is_bounded_without_moves(self):
        moves=[];calls=[]
        def planner(goal,history):calls.append(goal);return PLAN
        def observe(goal,plan,history):return {'captured_at':time.time(),'assessment':fast.control_decision(plan,measurement(visible=False),history)}
        c=NavigationController(None,moves.append,planner=planner,fast_observe=observe)
        c.state['goal']='Center red can'
        c.run(c.cancelled)
        self.assertEqual(len(calls),3)
        self.assertTrue(all(m=='X' for m in moves))
        self.assertIn('review limit',c.snapshot()['message'])

    def test_stop_during_planning_does_not_move(self):
        moves=[]
        def planner(goal,history):c.cancel();return PLAN
        c=NavigationController(None,moves.append,planner=planner,fast_observe=lambda *a: self.fail('Observed after Stop'))
        c.state['state']='observing';c.state['goal']='Center red can'
        c.run(c.cancelled)
        self.assertEqual(moves,['X'])


if __name__=='__main__':unittest.main()
