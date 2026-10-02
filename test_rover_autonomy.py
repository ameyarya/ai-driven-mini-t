import threading
import time
import unittest
from unittest.mock import patch
from rover_autonomy import NavigationController, AdaptiveTurn
from rover_vision import centering_decision, is_centering_goal


def result(position, uncertainty=None):
    return {'captured_at': time.time(), 'assessment': {
        'goal_achieved': position == 'centre', 'suggested_action': position if position in ('forward', 'backward', 'left', 'right') else 'stop',
        'uncertainties': uncertainty or []}}


class ControllerTests(unittest.TestCase):
    def test_coordinates_override_wrong_turn_and_complete(self):
        for x, action, achieved in [(34, 'left', False), (46, 'stop', True), (72, 'right', False)]:
            a = centering_decision({'target_visible': True, 'target_x': x, 'uncertainties': []})
            self.assertEqual(a['suggested_action'], action)
            self.assertEqual(a['goal_achieved'], achieved)

    def test_complex_mission_is_not_reduced_to_centering(self):
        self.assertTrue(is_centering_goal('position red can in center'))
        self.assertFalse(is_centering_goal('scan 360, approach the can, centre it and shoot'))
        for goal in [
            'Move closer to the red can until it occupies roughly 40% of the image height. Keep it centered, then stop.',
            'Move away from the can and keep it in the center',
            'Keep the can centered and make it fill half the image',
        ]:
            with self.subTest(goal=goal):
                self.assertFalse(is_centering_goal(goal))

    def test_worsening_turn_stops(self):
        answers = iter([centering_decision({'target_visible': True, 'target_x': x, 'uncertainties': []}) for x in (34, 25)])
        def observe(*a, **k):
            return {'captured_at': time.time(), 'assessment': next(answers)}
        c, moves = self.controller(observe)
        with patch.object(c.cancelled, 'wait', return_value=False):
            c.run(c.cancelled)
        self.assertEqual(moves, ['A', 'X', 'X'])
        self.assertIn('wrong way', c.snapshot()['message'])

    def test_missing_coordinates_stop(self):
        a = centering_decision({'target_visible': False, 'target_x': None, 'uncertainties': []})
        self.assertEqual(a['suggested_action'], 'stop')
        self.assertFalse(a['goal_achieved'])

    def test_overshoot_reverses_and_halves_duration(self):
        turn = AdaptiveTurn()
        self.assertEqual(turn.next_duration(70), .15)
        self.assertAlmostEqual(turn.next_duration(40), .075)
        self.assertEqual(centering_decision({'target_visible': True, 'target_x': 40, 'uncertainties': []})['suggested_action'], 'left')

    def test_turn_time_adapts_to_observed_motion(self):
        turn = AdaptiveTurn()
        turn.next_duration(80)
        duration = turn.next_duration(70)
        self.assertGreater(duration, .15)
        self.assertLessEqual(duration, .30)

    def controller(self, observe):
        moves = []
        c = NavigationController(observe, moves.append)
        c.state['goal'] = 'Centre a test target'
        c.heartbeat()
        return c, moves

    def test_centred_finishes_without_turn(self):
        c, moves = self.controller(lambda *a, **k: result('centre'))
        c.run(c.cancelled)
        self.assertEqual(c.snapshot()['state'], 'complete')
        self.assertEqual(moves, ['X'])

    def test_missing_and_uncertain_stop(self):
        for position, uncertainty in [('not_visible', []), ('left', ['blur'])]:
            c, moves = self.controller(lambda *a, **k: result(position, uncertainty))
            c.run(c.cancelled)
            self.assertEqual(c.snapshot()['state'], 'stopped')
            self.assertEqual(moves, ['X'])

    def test_left_then_centre(self):
        answers = iter([result('left'), result('centre')])
        c, moves = self.controller(lambda *a, **k: next(answers))
        with patch.object(c.cancelled, 'wait', return_value=False):
            c.run(c.cancelled)
        self.assertEqual(moves, ['A', 'X', 'X'])
        self.assertEqual(c.snapshot()['state'], 'complete')

    def test_manual_cancel_discards_late_model_result(self):
        entered, release = threading.Event(), threading.Event()
        def observe(*a, **k):
            entered.set()
            release.wait(2)
            return result('right')
        c, moves = self.controller(observe)
        worker = threading.Thread(target=c.run, args=(c.cancelled,))
        worker.start()
        self.assertTrue(entered.wait(1))
        c.cancel('Manual control')
        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(moves, ['X'])
        self.assertEqual(c.snapshot()['state'], 'stopped')

    def test_step_limit(self):
        c, moves = self.controller(lambda *a, **k: result('right'))
        with patch.object(c.cancelled, 'wait', return_value=False):
            c.run(c.cancelled)
        self.assertEqual(moves.count('D'), 40)
        self.assertEqual(moves[-1], 'X')
        self.assertEqual(c.snapshot()['state'], 'stopped')

    def test_all_navigation_actions(self):
        for action, key in [('forward', 'W'), ('backward', 'S'), ('left', 'A'), ('right', 'D')]:
            answers = iter([result(action), result('centre')])
            c, moves = self.controller(lambda *a, **k: next(answers))
            with patch.object(c.cancelled, 'wait', return_value=False):
                c.run(c.cancelled)
            self.assertEqual(moves, [key, 'X', 'X'])

    def test_translation_renews_watchdog_for_one_second(self):
        for action in ('forward', 'backward'):
            answers = iter([result(action), result('centre')])
            c, moves = self.controller(lambda *a, **k: next(answers))
            renewed = []
            c.refresh = renewed.append
            with patch.object(c.cancelled, 'wait', return_value=False) as wait:
                c.run(c.cancelled)
            self.assertEqual([call.args[0] for call in wait.call_args_list], [.25]*4 + [1.5])
            self.assertEqual(renewed, [moves[0]]*3)

    def test_short_turn_does_not_renew_watchdog(self):
        answers = iter([result('right'), result('centre')])
        c, moves = self.controller(lambda *a, **k: next(answers))
        renewed = []
        c.refresh = renewed.append
        with patch.object(c.cancelled, 'wait', return_value=False) as wait:
            c.run(c.cancelled)
        self.assertEqual([call.args[0] for call in wait.call_args_list], [.15, 1.5])
        self.assertEqual(renewed, [])

    def test_empty_goal_rejected(self):
        c, moves = self.controller(lambda *a, **k: result('centre'))
        with self.assertRaises(ValueError):
            c.start('   ')
        self.assertEqual(moves, [])

    def test_stale_assessment_cannot_move(self):
        r = result('right')
        r['captured_at'] -= 30
        c, moves = self.controller(lambda *a, **k: r)
        c.run(c.cancelled)
        self.assertEqual(moves, ['X'])

    def test_browser_disconnect_does_not_cancel(self):
        answers = iter([result('right'), result('centre')])
        c, moves = self.controller(lambda *a, **k: next(answers))
        c.lease = 0
        with patch.object(c.cancelled, 'wait', return_value=False):
            c.run(c.cancelled)
        self.assertEqual(moves, ['D', 'X', 'X'])
        self.assertEqual(c.snapshot()['state'], 'complete')


if __name__ == '__main__':
    unittest.main()
