"""Bounded move/observe controller for user-supplied navigation goals."""
import threading
import time
import rover_vision

ACTIONS = {'forward': 'W', 'backward': 'S', 'left': 'A', 'right': 'D', 'stop': 'X'}
MAX_STEPS = 40


def autonomous_speed(key):
    # Pivot both tracks at full power; low-duty reverse can stall a track.
    return 100 if key in ('A','D','X') else 40



class NavigationController:
    def __init__(self, observe, drive, refresh=None, planner=None, fast_observe=None):
        self.observe, self.drive = observe, drive
        self.refresh = refresh
        self.planner, self.fast_observe = planner, fast_observe
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
            plan = self.planner(goal, history=[]) if self.planner else None
            replans = 0
            for step in range(1, MAX_STEPS + 1):
                with self.lock:
                    if not self.valid(token):
                        break
                    self.state.update(state='observing', step=step, message='Measuring target' if plan else 'Analyzing the goal', plan=plan)
                result = (self.fast_observe(goal, plan, history) if plan
                          else self.observe(goal, autonomous=True, history=history[-6:]))
                if plan and result['assessment'].get('needs_replan'):
                    with self.lock:
                        if not self.valid(token):
                            break
                        self.state.update(result=result, message='Stopped; Qwen reviewing lost target or stalled progress')
                        self.drive('X')
                    if replans >= 2:
                        raise ValueError('Planner review limit reached; target lost or progress stalled')
                    plan = self.planner(goal, history=history[-6:])
                    replans += 1
                    history=[]
                    previous_x=previous_action=None
                    continue
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
                        self.state.update(state='complete', message='Measured goal achieved — stopped' if plan else 'Qwen reports goal achieved — stopped')
                        break
                    if action not in ACTIONS or assessment.get('uncertainties'):
                        self.state.update(state='stopped', message=('Uncertain observation: ' + '; '.join(map(str, assessment['uncertainties'])) if assessment.get('uncertainties') else 'Invalid action: ' + str(action)) + '; stopped')
                        break
                    if assessment.get('observe_again'):
                        self.drive('X')
                        history.append({'action':'stop','duration_ms':0,
                                        'phase':assessment.get('phase'),
                                        'target_x_before':assessment.get('target_x'),
                                        'target_height_before':assessment.get('target_height')})
                        self.state.update(state='settling',message=assessment.get('reason','Confirming target'))
                        continue
                    if action == 'stop':
                        self.state.update(state='stopped', message=('Controller chose stop: ' if plan else 'Qwen chose stop: ') + assessment.get('reason', ''))
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
                                    'reason': assessment.get('reason', ''),
                                    'phase': assessment.get('phase')})
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
