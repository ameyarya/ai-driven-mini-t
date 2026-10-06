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

PLAN={'mode':'approach_size','target':'can','height_percent':50,'uncertainties':[],'reason':'Approach and center'}


def measurement(x=50,height=30,visible=True,clipped=False):
    return {'target_visible':visible,'target_x':x if visible else None,'target_height':height if visible else None,'target_clipped':clipped}


class FastNavigationTests(unittest.TestCase):
    def test_generic_can_and_centering_contract(self):
        from rover_detector import target_description
        for goal in ['Position orange can in center', 'Center the blue can', 'Find the silver can', 'Find the can', 'Find Coca-Cola']:
            self.assertEqual(target_description(goal), 'can')
        request=fast.planner_request('Position orange can in center', b'image', measurement())
        self.assertEqual(request['format']['properties']['mode']['enum'], ['center','unsupported'])
        request=fast.planner_request('Find the orange can, center it, then shoot once', b'image', measurement())
        self.assertEqual(request['format']['properties']['target']['enum'], ['can'])
        self.assertEqual(request['format']['properties']['mode']['enum'], ['find_shoot','unsupported'])

    def test_planner_and_controller_display_roles_are_truthful(self):
        with tempfile.TemporaryDirectory() as d:
            frame=Path(d)/'frame-test.jpg';frame.write_bytes(b'raw image')
            labeled=Path(d)/'frame-labeled.jpg';labeled.write_bytes(b'exact labeled image')
            prepared={'model_frame':str(labeled),'measurement':measurement()}
            def response(url,body,timeout):
                self.assertEqual(base64.b64decode(body['messages'][0]['images'][0]),labeled.read_bytes())
                return {'model':'test','message':{'content':json.dumps(PLAN)}}
            with patch.object(fast.vision,'capture_frame',return_value=frame),patch.object(fast.vision,'prepare_detector_image',return_value=prepared),patch.object(fast.vision,'read_json',side_effect=response) as chat:
                plan=fast.plan_goal('Approach can to 50% of image height')
                self.assertEqual(fast.vision.input_snapshot()['result']['input_role'],'qwen_planner')
                result=fast.observe_goal('Approach can to 50% of image height',plan,[])
                self.assertEqual(chat.call_count,1)
                self.assertEqual(result['input_role'],'controller')
                self.assertEqual(result['input_sha256'],hashlib.sha256(labeled.read_bytes()).hexdigest())
                self.assertEqual(fast.vision.input_snapshot()['state'],'controller')

    def test_find_rotates_without_advancing_when_target_absent(self):
        plan=dict(PLAN,mode='find',height_percent=0,search_direction='right',full_turn_ms=None)
        fast.validate_plan(plan,'Find the can by doing 360 turn in place')
        a=fast.control_decision(plan,measurement(visible=False),[])
        self.assertEqual(a['suggested_action'],'right')
        self.assertEqual(a['duration_ms'],250)
        self.assertFalse(a.get('needs_replan',False))
        self.assertFalse(a['heading_calibrated'])

    def test_find_requires_two_stationary_detections_then_stops(self):
        plan=dict(PLAN,mode='find',height_percent=0)
        first=fast.control_decision(plan,measurement(x=50),[])
        self.assertTrue(first['observe_again'])
        h=[{'action':'stop','duration_ms':0,'phase':'find_confirmation','target_x_before':50}]
        confirmed=fast.control_decision(plan,measurement(x=51),h)
        self.assertTrue(confirmed['goal_achieved'])
        self.assertEqual(confirmed['suggested_action'],'stop')
        lost=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(lost['suggested_action'],'right')

    def test_find_partial_edge_target_must_align_not_complete(self):
        plan=dict(PLAN,mode='find',height_percent=0)
        a=fast.control_decision(plan,measurement(x=98.15,clipped=True),[])
        self.assertEqual(a['suggested_action'],'right')
        self.assertFalse(a['goal_achieved'])
        a=fast.control_decision(plan,measurement(x=50,clipped=True),[])
        self.assertEqual(a['suggested_action'],'stop')
        self.assertFalse(a['goal_achieved'])
        self.assertTrue(a['uncertainties'])

    def test_turn_power_full_and_forward_reduced(self):
        from rover_autonomy import autonomous_speed
        self.assertEqual(autonomous_speed('A'),100)
        self.assertEqual(autonomous_speed('D'),100)
        self.assertEqual(autonomous_speed('W'),40)
        from tank_app import TankApp
        with patch('tank_app.time.ticks_ms',return_value=0,create=True):
            app=TankApp()
            self.assertEqual(app.command(b'A'),(1024,1024))
            self.assertEqual(app.command(b'D'),(-1024,-1024))

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
        h=[{'action':'right','phase':'search','duration_ms':250}]*39
        a=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(a['suggested_action'],'stop')
        self.assertFalse(a['goal_achieved'])
        self.assertIn('360 not calibrated',a['reason'])

    def test_find_controller_confirms_candidate_without_extra_turn(self):
        plan=dict(PLAN,mode='find',height_percent=0)
        frames=iter([measurement(visible=False),measurement(x=50),measurement(x=51)])
        moves=[]
        def observe(goal,plan,history):return {'captured_at':time.time(),'assessment':fast.control_decision(plan,next(frames),history)}
        c=NavigationController(None,moves.append,planner=lambda *a,**k:plan,fast_observe=observe)
        c.state['goal']='Find can by rotating in place'
        with patch.object(c.cancelled,'wait',return_value=False):c.run(c.cancelled)
        self.assertEqual(moves,['D','X','X','X'])
        self.assertEqual(c.snapshot()['state'],'complete')

    def test_find_mission_cannot_silently_drop_approach(self):
        fast.validate_plan(dict(PLAN,mode='find',height_percent=0),
                           'Find the can by turning in place, center it, then stop.')
        with self.assertRaises(ValueError):fast.validate_plan(dict(PLAN,mode='find'),'Find can, then approach it')
        with self.assertRaises(ValueError):fast.validate_plan(PLAN,'Find can by rotating 360')

    def test_combined_mission_searches_confirms_then_approaches(self):
        plan=dict(PLAN,mode='find_approach_size')
        goal='Find can, center it, then move closer until 50% of image height'
        fast.validate_plan(plan,goal)
        frames=iter([measurement(visible=False),measurement(x=98,clipped=True),
                     measurement(x=60),measurement(x=50),measurement(x=50),
                     measurement(x=50,height=31),measurement(x=50,height=49.5)])
        moves=[];plans=[];phases=[]
        def planner(*a,**k):plans.append(plan);return plan
        def observe(goal,plan,history):
            assessment=fast.control_decision(plan,next(frames),history)
            phases.append(assessment.get('phase'))
            return {'captured_at':time.time(),'assessment':assessment}
        c=NavigationController(None,moves.append,planner=planner,fast_observe=observe)
        c.state['goal']=goal
        with patch.object(c.cancelled,'wait',return_value=False):c.run(c.cancelled)
        self.assertEqual(len(plans),1)
        self.assertEqual(c.snapshot()['state'],'complete')
        self.assertEqual(phases,['search','find_align','find_align','find_confirmation','approach_ready','approach','approach'])
        self.assertEqual(moves.count('W'),1)
        self.assertEqual(moves[-1],'X')

    def test_combined_confirmation_is_not_mission_completion(self):
        plan=dict(PLAN,mode='find_approach_size')
        h=[{'action':'stop','duration_ms':0,'phase':'find_confirmation','target_x_before':50}]
        a=fast.control_decision(plan,measurement(),h)
        self.assertFalse(a['goal_achieved'])
        self.assertTrue(a['observe_again'])
        self.assertEqual(a['phase'],'approach_ready')
        h.append({'action':'stop','duration_ms':0,'phase':'approach_ready','target_x_before':50})
        a=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(a['suggested_action'],'stop')
        self.assertTrue(a['observe_again'])
        self.assertFalse(a.get('needs_replan',False))
        a=fast.control_decision(plan,measurement(x=50,clipped=True),h)
        self.assertEqual(a['suggested_action'],'stop')
        self.assertFalse(a['goal_achieved'])

    def test_combined_mission_requires_exact_requested_height(self):
        for height in (0,40):
            with self.assertRaises(ValueError):fast.validate_plan(dict(PLAN,mode='find_approach_size',height_percent=height),'Find can, then approach to 50% of image height')

    def test_far_target_can_advance_without_precise_centering(self):
        a=fast.control_decision(PLAN,measurement(x=40,height=10),[])
        self.assertEqual(a['suggested_action'],'forward')
        self.assertEqual(a['alignment_tolerance_percent'],13)
        a=fast.control_decision(PLAN,measurement(x=44.1,height=10.4),[])
        self.assertEqual(a['suggested_action'],'forward')
        a=fast.control_decision(PLAN,measurement(x=40,height=49),[])
        self.assertEqual(a['suggested_action'],'left')
        self.assertFalse(a['goal_achieved'])
        self.assertEqual(a['alignment_tolerance_percent'],5)

    def test_combined_retries_missed_frame_and_reacquires_with_original_goal(self):
        plan=dict(PLAN,mode='find_approach_size')
        h=[{'phase':'approach_ready','action':'stop','duration_ms':0,'target_x_before':40}]
        for _ in range(2):
            a=fast.control_decision(plan,measurement(visible=False),h)
            self.assertTrue(a['observe_again'])
            self.assertFalse(a.get('needs_replan',False))
            h.append({'phase':a['phase'],'action':'stop','duration_ms':0})
        a=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(a['suggested_action'],'left')
        self.assertEqual(a['phase'],'search_again')
        h.append({'phase':a['phase'],'action':'left','duration_ms':250})
        a=fast.control_decision(plan,measurement(visible=False),h)
        self.assertEqual(a['suggested_action'],'left')
        a=fast.control_decision(plan,measurement(x=40,height=10),h)
        self.assertTrue(a['observe_again'])
        self.assertEqual(a['phase'],'find_confirmation')

    def test_combined_transient_miss_does_not_call_planner_again(self):
        plan=dict(PLAN,mode='find_approach_size')
        frames=iter([measurement(x=40,height=10),measurement(x=40,height=10),
                     measurement(visible=False),measurement(x=40,height=11),measurement(x=50,height=49.5)])
        moves=[];calls=[]
        def planner(*a,**k):calls.append(plan);return plan
        def observe(goal,plan,history):return {'captured_at':time.time(),'assessment':fast.control_decision(plan,next(frames),history)}
        c=NavigationController(None,moves.append,planner=planner,fast_observe=observe)
        c.state['goal']='Find can, then approach to 50% of image height'
        with patch.object(c.cancelled,'wait',return_value=False):c.run(c.cancelled)
        self.assertEqual(len(calls),1)
        self.assertEqual(c.snapshot()['state'],'complete')
        self.assertEqual(moves.count('W'),1)
        self.assertFalse(any(m in ('A','D') for m in moves))

    def test_combined_ambiguity_does_not_resume_movement(self):
        h=[{'phase':'approach_ready'}]
        a=fast.control_decision(dict(PLAN,mode='find_approach_size'),dict(measurement(visible=False),candidate_count=2),h)
        self.assertEqual(a['suggested_action'],'stop')
        self.assertTrue(a['uncertainties'])
        self.assertFalse(a.get('observe_again',False))

    def test_unsupported_replan_reports_actual_reason(self):
        with self.assertRaisesRegex(ValueError,'Target not visible'):
            fast.validate_plan({'mode':'unsupported','reason':'Target not visible','uncertainties':[]},'Find can then approach to 50% of image height')

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
        c.state['goal']='Approach can to 50% image height'
        with patch.object(c.cancelled,'wait',return_value=False):c.run(c.cancelled)
        self.assertEqual(len(calls),1)
        self.assertEqual(moves,['A','X','W','X','X'])
        self.assertEqual(c.snapshot()['state'],'complete')

    def test_lost_target_review_is_bounded_without_moves(self):
        moves=[];calls=[]
        def planner(goal,history):calls.append(goal);return PLAN
        def observe(goal,plan,history):return {'captured_at':time.time(),'assessment':fast.control_decision(plan,measurement(visible=False),history)}
        c=NavigationController(None,moves.append,planner=planner,fast_observe=observe)
        c.state['goal']='Center can'
        c.run(c.cancelled)
        self.assertEqual(len(calls),3)
        self.assertTrue(all(m=='X' for m in moves))
        self.assertIn('review limit',c.snapshot()['message'])

    def test_stop_during_planning_does_not_move(self):
        moves=[]
        def planner(goal,history):c.cancel();return PLAN
        c=NavigationController(None,moves.append,planner=planner,fast_observe=lambda *a: self.fail('Observed after Stop'))
        c.state['state']='observing';c.state['goal']='Center can'
        c.run(c.cancelled)
        self.assertEqual(moves,['X'])


if __name__=='__main__':unittest.main()
