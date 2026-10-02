"""Bounded move/observe controller for user-supplied navigation goals."""
import threading
import time
import rover_vision

ACTIONS = {'forward': 'W', 'backward': 'S', 'left': 'A', 'right': 'D', 'stop': 'X'}
MAX_STEPS = 40


class NavigationController:
    def __init__(self, observe, drive, refresh=None):
        self.observe, self.drive = observe, drive
        self.refresh = refresh
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
        return token is self.cancelled and not token.is_set()

    def run(self, token):
        try:
            with self.lock:
                goal = self.state['goal']
            history = []
            previous_x = None
            previous_action = None
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
                    x = assessment.get('target_x')
                    if isinstance(x, (int, float)) and previous_x is not None:
                        shift = x - previous_x
                        if (previous_action == 'left' and shift < -3) or (previous_action == 'right' and shift > 3):
                            raise ValueError('Turn moved target the wrong way; check motor/camera alignment')
                    previous_x = x if isinstance(x, (int, float)) else None
                    previous_action = action
                    duration_ms = assessment.get('duration_ms')
                    if type(duration_ms) is not int or not 1 <= duration_ms <= 1000:
                        raise ValueError('Model movement duration must be an integer from 1 to 1000 ms')
                    duration = duration_ms / 1000
                    self.state['turn_ms'] = round(duration * 1000)
                    self.state.update(state='moving', message='Move ' + action + ' for ' + str(round(duration*1000)) + ' ms')
                    self.drive(ACTIONS[action])
                    self.state['last_action'] = action
                    history.append({'step': step, 'action': action, 'duration_ms': duration_ms,
                                    'target_x_before': assessment.get('target_x'),
                                    'target_height_before': assessment.get('target_height'),
                                    'reason': assessment.get('reason', '')})
                # Bounded adaptive pulse, followed by explicit stop. Firmware watchdog
                # remains a separate 500 ms fallback if the host fails.
                remaining = duration
                while remaining > 0:
                    interval = min(.25, remaining)
                    if token.wait(interval):
                        return
                    remaining -= interval
                    if remaining > 0 and self.refresh is not None:
                        with self.lock:
                            if not self.valid(token):
                                return
                            self.refresh(ACTIONS[action])
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
                        self.state.update(state='stopped', message='Step limit reached')
                    self.drive('X')
        except Exception as error:
            with self.lock:
                if token is self.cancelled and not token.is_set():
                    self.state.update(state='error', message=str(error))
                    try:
                        self.drive('X')
                    except Exception:
                        pass
