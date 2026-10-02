import threading
import time
import unittest
from unittest.mock import patch
from rover_autonomy import NavigationController


def result(position, uncertainty=None):
    return {'captured_at': time.time(), 'assessment': {
        'goal_achieved': position == 'centre', 'suggested_action': position if position in ('forward', 'backward', 'left', 'right') else 'stop',
        'uncertainties': uncertainty or []}}


class ControllerTests(unittest.TestCase):
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
