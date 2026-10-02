"""Bounded turn/observe controller for the first can-centering experiment."""
import threading
import time

GOAL = 'Turn to centre the Coca-Cola can in the camera image, then stop.'


class CenteringController:
    def __init__(self, observe, drive):
        self.observe, self.drive = observe, drive
        self.lock = threading.RLock()
        self.state = {'state': 'idle', 'goal': GOAL}
        self.cancelled = threading.Event()
        self.lease = 0

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def active(self):
        return self.snapshot()['state'] in ('observing', 'turning', 'settling')

    def heartbeat(self):
        with self.lock:
            self.lease = time.monotonic() + 5

    def cancel(self, reason='Stopped by user'):
        with self.lock:
            self.cancelled.set()
            if self.active():
                self.state.update(state='stopped', message=reason)
                self.drive('X')

    def start(self):
        with self.lock:
            if self.active():
                raise ValueError('Autonomous goal already running')
            token = threading.Event()
            self.cancelled = token
            self.heartbeat()
            self.drive('X')
            self.state = {'state': 'observing', 'goal': GOAL, 'step': 0,
                          'message': 'Looking for the can'}
            threading.Thread(target=self.run, args=(token,), daemon=True).start()

    def valid(self, token):
        return token is self.cancelled and not token.is_set() and time.monotonic() < self.lease

    def run(self, token):
        try:
            for step in range(1, 9):
                with self.lock:
                    if not self.valid(token):
                        break
                    self.state.update(state='observing', step=step, message='Looking for the can')
                result = self.observe(GOAL, centering=True)
                with self.lock:
                    if not self.valid(token):
                        break
                    self.state['result'] = result
                    assessment = result['assessment']
                    position = assessment.get('target_position')
                    if time.time() - result['captured_at'] > 25:
                        self.state.update(state='stopped', message='Assessment too old; stopped')
                        break
                    if position == 'centre' and not assessment.get('uncertainties'):
                        self.state.update(state='complete', message='Can centred — goal complete')
                        break
                    if position not in ('left', 'right') or assessment.get('uncertainties'):
                        self.state.update(state='stopped', message='Can missing or uncertain; stopped')
                        break
                    if assessment.get('suggested_action') != position:
                        self.state.update(state='stopped', message='Model position and action disagree; stopped')
                        break
                    self.state.update(state='turning', message='Short turn ' + position)
                    self.drive('A' if position == 'left' else 'D')
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
