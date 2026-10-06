"""Human shot outcomes and asynchronous bounded calibration; never fires."""
import json
import math
from pathlib import Path
import threading
import time


def validate_feedback(body):
    if body.get('outcome') not in ('hit','miss','unknown'):
        raise ValueError('Choose hit, miss or unsure')
    if not isinstance(body.get('shot_id'),str) or not body['shot_id']:
        raise ValueError('A recorded shot is required')
    if body['outcome']=='miss':
        for key in ('dx','dy'):
            value=body.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>2:
                raise ValueError('Miss offset must be within two target radii')
        if max(abs(body['dx']),abs(body['dy']))<.05:
            raise ValueError('Mark where the projectile missed the target')
    return dict(body)


def validate_correction(result, feedback):
    delta=result.get('height_delta_ms');bias=result.get('aim_offset_delta_percent')
    if type(delta) is not int or abs(delta)>100:
        raise ValueError('Height correction must be an integer within ±100 ms')
    if type(bias) not in (int,float) or not math.isfinite(bias) or abs(bias)>3:
        raise ValueError('Aim offset correction must be within ±3 percentage points')
    if not isinstance(result.get('uncertainties'),list) or result['uncertainties']:
        raise ValueError('Qwen is uncertain; adjustment not applied')
    if feedback['dy']*delta>0:
        raise ValueError('Height correction contradicts the marked miss')
    if feedback['dx']*bias<0:
        raise ValueError('Horizontal correction contradicts the marked miss')
    if abs(feedback['dy'])<.05 and delta:
        raise ValueError('No vertical miss was reported')
    if abs(feedback['dx'])<.05 and bias:
        raise ValueError('No horizontal miss was reported')
    return result


class ShotFeedback:
    def __init__(self,path,infer,apply,save_hit):
        self.path=Path(path);self.infer=infer;self.apply=apply;self.save_hit=save_hit
        self.lock=threading.RLock();self.token=threading.Event()
        self.state={'state':'idle','message':'Feedback waits for a shot'}
        self.records=json.loads(self.path.read_text()) if self.path.exists() else []
    def snapshot(self):
        with self.lock:return dict(self.state)
    def active(self):return self.snapshot()['state'] in ('analyzing','adjusting')
    def cancel(self):self.token.set()
    def start(self,body,shot):
        body=validate_feedback(body)
        if body['shot_id']!=shot.get('id'):raise ValueError('Shot changed; review the latest shot')
        if shot.get('fire_command_sent') is not True or shot.get('reset_acknowledged') is not True:
            raise ValueError('Shot/reset sequence must finish before feedback')
        with self.lock:
            if self.active():raise ValueError('Feedback analysis is already running')
            if any(r['shot_id']==shot['id'] for r in self.records):raise ValueError('Feedback for this shot was already submitted')
            self.token=threading.Event();token=self.token
            self.state={'state':'analyzing','shot_id':shot['id'],'message':'Comparing shot frame, settings and your feedback'}
            threading.Thread(target=self.run,args=(body,json.loads(json.dumps(shot)),token),daemon=True).start()
    def run(self,body,shot,token):
        try:
            if body['outcome']=='hit':
                if token.is_set():raise ValueError('Feedback cancelled')
                self.save_hit(shot);result={'message':'Confirmed hit saved as shooting setup'}
            elif body['outcome']=='unknown':result={'message':'Unsure recorded; no adjustment'}
            else:
                result=validate_correction(self.infer(shot,body,self.records[-6:]),body)
                if token.is_set():raise ValueError('Feedback cancelled')
                with self.lock:self.state.update(state='adjusting',message='Applying bounded height correction and next-shot aim offset')
                result.update(self.apply(shot,result,token))
            record=dict(body,time=time.time(),shot=shot,result=result)
            with self.lock:
                self.records.append(record);self.path.parent.mkdir(parents=True,exist_ok=True)
                tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.records,indent=2)+'\n');tmp.replace(self.path)
                self.state.update(state='complete',message=result.get('message',result.get('reason','Feedback applied; ready for next test')),result=result)
        except Exception as error:
            with self.lock:self.state.update(state='error',message=str(error))
