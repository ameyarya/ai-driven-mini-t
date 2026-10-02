"""Bounded move/observe controller for user-supplied navigation goals."""
import threading
import time

ACTIONS = {'forward': 'W', 'backward': 'S', 'left': 'A', 'right': 'D', 'stop': 'X'}
MAX_STEPS = 40


class NavigationController:
    def __init__(self, observe, drive):
        self.observe, self.drive = observe, drive
        self.lock = threading.RLock()
        self.state = {'state': 'idle', 'goal': ''}
        self.cancelled = threading.Event()
        self.lease = 0

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def active(self):
        return self.snapshot()['state'] in ('observing', 'moving', 'settling')

    def heartbeat(self):
        with self.lock:
            self.lease = time.monotonic() + 5

    def cancel(self, reason='Stopped by user'):
        with self.lock:
            self.cancelled.set()
            if self.active():
                self.state.update(state='stopped', message=reason)
                self.drive('X')

    def start(self, goal):
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 1000:
            raise ValueError('Enter a navigation goal under 1000 characters')
        with self.lock:
            if self.active():
                raise ValueError('Autonomous goal already running')
            token = threading.Event()
            self.cancelled = token
            self.heartbeat()
            self.drive('X')
            self.state = {'state': 'observing', 'goal': goal.strip(), 'step': 0,
                          'message': 'Analyzing the goal'}
            threading.Thread(target=self.run, args=(token,), daemon=True).start()

    def valid(self, token):
        return token is self.cancelled and not token.is_set() and time.monotonic() < self.lease

    def run(self, token):
        try:
            with self.lock:
                goal = self.state['goal']
            history = []
            for step in range(1, MAX_STEPS + 1):
                with self.lock:
                    if not self.valid(token):
                        break
                    self.state.update(state='observing', step=step, message='Analyzing the goal')
                result = self.observe(goal, autonomous=True, history=history[-6:])
                with self.lock:
                    if not self.valid(token):
                        break
                    self.state['result'] = result
                    assessment = result['assessment']
                    action = assessment.get('suggested_action')
                    if time.time() - result['captured_at'] > 25:
                        self.state.update(state='stopped', message='Assessment too old; stopped')
                        break
                    if not isinstance(assessment.get('goal_achieved'), bool):
                        raise ValueError('Model did not report goal completion')
                    if assessment.get('goal_achieved') and not assessment.get('uncertainties'):
                        self.state.update(state='complete', message='Qwen reports goal achieved — stopped')
                        break
                    if action not in ACTIONS or assessment.get('uncertainties'):
                        self.state.update(state='stopped', message='Uncertain observation or invalid action; stopped')
                        break
                    if action == 'stop':
                        self.state.update(state='stopped', message='Qwen chose stop: ' + assessment.get('reason', ''))
                        break
                    self.state.update(state='moving', message='Short move ' + action)
                    self.drive(ACTIONS[action])
                    history.append({'step': step, 'action': action, 'answer': assessment.get('answer', '')})
                # One 150 ms pulse, followed by explicit stop. Firmware watchdog
                # remains a separate 500 ms fallback if the host fails.
                token.wait(0.15)
                with self.lock:
                    if token is not self.cancelled or token.is_set():
                        return
                    self.drive('X')
                    self.state.update(state='settling', message='Stopped; waiting for fresh video')
                if token.wait(1.5):
                    return
            with self.lock:
                if token is self.cancelled and not token.is_set():
                    if self.active():
                        self.state.update(state='stopped', message='Browser disconnected or step limit reached')
                    self.drive('X')
        except Exception as error:
            with self.lock:
                if token is self.cancelled and not token.is_set():
                    self.state.update(state='error', message=str(error))
                    try:
                        self.drive('X')
                    except Exception:
                        pass
