"""One bounded launcher command, durable attempt accounting, no impact claims."""
import json
import os
from pathlib import Path
import threading
import time
import uuid


class ShotController:
    def __init__(self, set_fire, directory, record=None, pulse_ms=350):
        if type(pulse_ms) is not int or not 100 <= pulse_ms <= 450:
            raise ValueError('Fire pulse must be 100..450 ms, below receiver watchdog')
        self.set_fire, self.record = set_fire, record
        self.directory = Path(directory)
        self.pulse_ms = pulse_ms
        self.lock = threading.Lock()

    def fire_once(self, token):
        with self.lock:
            if token.is_set():
                raise ValueError('Shot cancelled before command')
            self.directory.mkdir(parents=True, exist_ok=True)
            ledger = self.directory/'ledger.json'
            state = json.loads(ledger.read_text()) if ledger.exists() else {'attempts':[]}
            if len(state['attempts']) >= 6:
                raise ValueError('Six automatic fire attempts used; reload and explicitly reset ledger')
            attempt = dict(id=uuid.uuid4().hex, time=time.time(), fire_command_sent=False,
                shot_fired='unconfirmed', hit='unconfirmed', pulse_ms=self.pulse_ms)
            # Reserve BEFORE transmission. A lost acknowledgment never causes a retry.
            state['attempts'].append(attempt)
            self._save(ledger,state)
            try:
                if self.record:
                    attempt['evidence'] = self.record(attempt['id'], token)
                if token.is_set():
                    raise ValueError('Shot cancelled')
                attempt['fire_command_sent'] = 'unconfirmed'
                self._save(ledger,state)
                self.set_fire(True, token)
                attempt['fire_command_sent'] = True
                self._save(ledger,state)
                token.wait(self.pulse_ms/1000)
            except Exception as error:
                attempt['error'] = str(error)
                raise
            finally:
                try:
                    self.set_fire(False, token)
                    attempt['reset_acknowledged'] = True
                except Exception as error:
                    attempt['reset_error'] = str(error)
                self._save(ledger,state)
            if attempt.get('reset_error'):
                raise RuntimeError('Launcher reset acknowledgment failed: '+attempt['reset_error'])
            attempt['remaining_automatic_attempts'] = 6-len(state['attempts'])
            return attempt

    @staticmethod
    def _save(path, state):
        temporary = path.with_suffix('.tmp')
        with temporary.open('w') as handle:
            json.dump(state,handle,indent=2); handle.flush(); os.fsync(handle.fileno())
        temporary.replace(path)

    def acknowledge_reload(self):
        if not self.lock.acquire(blocking=False):
            raise ValueError('Wait for the shot command to finish before reloading')
        try:
            self.directory.mkdir(parents=True,exist_ok=True)
            ledger=self.directory/'ledger.json'
            if ledger.exists():
                ledger.replace(self.directory/('ledger-before-reload-'+uuid.uuid4().hex+'.json'))
            self._save(ledger,{'attempts':[], 'reload_acknowledged_at':time.time()})
        finally:self.lock.release()
