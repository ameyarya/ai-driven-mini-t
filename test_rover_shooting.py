import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import rover_fast_navigation as fast
from rover_autonomy import NavigationController
from rover_shooting import ShotController


def measurement(x=50, visible=True, clipped=False):
    return dict(target_visible=visible,target_x=x,target_height=50,
                target_clipped=clipped,candidate_count=int(visible))


class ShootingTests(unittest.TestCase):
    def test_shooting_schema_cannot_name_overlay_text_as_target(self):
        request=fast.planner_request('Center red can then shoot once',b'image',measurement())
        self.assertEqual(request['format']['properties']['target']['enum'],['soda can'])
        legacy=fast.planner_request('Center red can then shoot once',b'image',measurement(),shooting_enabled=False)
        self.assertNotIn('enum',legacy['format']['properties']['target'])
    def test_shooting_contract_preserves_search_approach_and_explicit_intent(self):
        p=dict(mode='find_approach_shoot',target='red can',height_percent=50,uncertainties=[])
        goal='Find red can, approach until 50% image height, then shoot'
        fast.validate_plan(p,goal)
        for changes in ({'mode':'approach_shoot'},{'mode':'find_shoot'},{'height_percent':40},{'target':'person'}):
            with self.assertRaises(ValueError):fast.validate_plan(dict(p,**changes),goal)
        with self.assertRaises(ValueError):fast.validate_plan(p,'Find can and approach until 50% image height')

    def test_no_shot_for_absent_clipped_or_ambiguous_target(self):
        p=dict(mode='shoot',target='red can',height_percent=0)
        for m in (measurement(visible=False),measurement(clipped=True),dict(measurement(),candidate_count=2)):
            self.assertNotEqual(fast.control_decision(p,m,[])['suggested_action'],'fire')

    def test_mission_cannot_hide_multiple_shots_or_unnamed_target(self):
        p=dict(mode='shoot',target='red can',height_percent=0,uncertainties=[])
        for goal in ('Shoot it','Fire six shots at red can','Shoot red can until hit'):
            with self.assertRaises(ValueError):fast.validate_plan(p,goal)

    def test_inverse_height_gain_limits_nonlinear_approach(self):
        # Pinhole target goes 20% -> 25% after 250 ms. Reaching 50% from
        # 25% requires 500 ms at the same translation speed, not 1250 ms.
        h=[dict(action='forward',duration_ms=250,target_height_before=20)]
        duration=fast.movement_duration('forward',25,measurement() | {'target_height':25},h)
        self.assertEqual(duration,325)  # 65% of the estimated 500 ms translation.

    def test_find_shoot_confirmation_does_not_loop_or_repeat(self):
        p=dict(mode='find_shoot',target='red can',height_percent=0)
        history=[]
        for _ in range(5):
            a=fast.control_decision(p,measurement(),history)
            if a['suggested_action']=='fire':break
            self.assertTrue(a.get('observe_again'))
            history.append(dict(action='stop',phase=a['phase'],target_x_before=50,target_height_before=50))
        self.assertEqual(a['suggested_action'],'fire')
        history.append({'action':'fire'})
        self.assertNotEqual(fast.control_decision(p,measurement(),history)['suggested_action'],'fire')

    def test_durable_limit_and_lost_ack_never_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            token=threading.Event();calls=[]
            def send(fire,token):
                calls.append(fire)
                if fire:raise RuntimeError('Acknowledgment lost')
            controller=ShotController(send,folder)
            for _ in range(6):
                with self.assertRaises(RuntimeError):controller.fire_once(token)
            self.assertEqual(calls,[True,False]*6)
            restarted=ShotController(send,folder)
            with self.assertRaises(ValueError):restarted.fire_once(token)
            self.assertEqual(len(json.loads((Path(folder)/'ledger.json').read_text())['attempts']),6)

    def test_cancelled_before_fire_and_during_pulse(self):
        with tempfile.TemporaryDirectory() as folder:
            token=threading.Event();token.set();calls=[]
            c=ShotController(lambda state,event:calls.append(state),folder)
            with self.assertRaises(ValueError):c.fire_once(token)
            self.assertEqual(calls,[])
            token.clear()
            def send(state,event):
                calls.append(state)
                if state:event.set()
            c.set_fire=send
            result=c.fire_once(token)
            self.assertEqual(calls,[True,False]);self.assertEqual(result['hit'],'unconfirmed')

    def test_reset_failure_does_not_report_finished_and_reload_preserves_history(self):
        with tempfile.TemporaryDirectory() as folder:
            def send(state,event):
                if state:event.set()
                else:raise RuntimeError('Reset ack lost')
            c=ShotController(send,folder)
            with self.assertRaisesRegex(RuntimeError,'reset acknowledgment'):c.fire_once(threading.Event())
            c.acknowledge_reload()
            self.assertEqual(json.loads((Path(folder)/'ledger.json').read_text())['attempts'],[])
            self.assertEqual(len(list(Path(folder).glob('ledger-before-reload-*.json'))),1)

    def test_controller_fires_once_and_does_not_claim_hit_or_goal_success(self):
        plan=dict(mode='shoot',target='red can',height_percent=0,uncertainties=[])
        calls=[];moves=[]
        def observe(goal,plan,history):
            return dict(captured_at=time.time(),assessment=fast.control_decision(plan,measurement(),history))
        controller=NavigationController(None,moves.append,planner=lambda *a,**k:plan,
            fast_observe=observe,fire=lambda token:calls.append('fire') or {'hit':'unconfirmed'})
        controller.state['goal']='Center can then shoot once'
        controller.run(controller.cancelled)
        self.assertEqual(calls,['fire']);self.assertEqual(controller.snapshot()['state'],'stopped')
        self.assertIn('unconfirmed',controller.snapshot()['message'])
        self.assertTrue(all(move=='X' for move in moves))


if __name__=='__main__':unittest.main()
