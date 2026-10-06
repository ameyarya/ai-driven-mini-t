"""Timed launcher elevation relative to a user-confirmed reference, not degrees."""
import json
import math
from pathlib import Path
import threading
import time

class ElevationCalibration:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=threading.RLock()
        self.position=None
        self.enabled=False
        self.data=json.loads(self.path.read_text()) if self.path.exists() else {'points':[]}
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps(self.data,indent=2)+'\n');temporary.replace(self.path)
    def snapshot(self):
        with self.lock:return {'reference_confirmed':self.position is not None,'position_ms':self.position,'enabled':self.enabled,'points':self.data['points']}
    def confirm_reference(self):
        with self.lock:self.position=0;self.enabled=False
    def invalidate(self):
        with self.lock:self.position=None;self.enabled=False
    def desired(self,height):
        if type(height) not in (float,int) or not math.isfinite(height):raise ValueError('Invalid target height')
        points=sorted(self.data['points'],key=lambda p:p['height_percent'])
        if any(right['height_percent']-left['height_percent']<.5 for left,right in zip(points,points[1:])):
            raise ValueError('Calibration samples too close or ambiguous; collect distinct target sizes')
        if len(points)<2 or points[-1]['height_percent']-points[0]['height_percent']<3:
            raise ValueError('Save hits at two target sizes at least 3 percentage points apart')
        if not points[0]['height_percent']<=height<=points[-1]['height_percent']:
            raise ValueError('Target size outside calibrated range; no extrapolation or shot')
        for left,right in zip(points,points[1:]):
            if left['height_percent']<=height<=right['height_percent']:
                fraction=(height-left['height_percent'])/(right['height_percent']-left['height_percent'])
                return round(left['position_ms']+fraction*(right['position_ms']-left['position_ms']))
        raise ValueError('No usable elevation calibration interval')
    def enable(self):
        with self.lock:
            if self.position is None:raise ValueError('Restore reference height and confirm it first')
            points=self.data['points'];self.desired(sum(p['height_percent'] for p in points)/len(points) if points else 0)
            self.enabled=True
    def move(self,destination,set_aim,token):
        with self.lock:
            if self.position is None:raise ValueError('Confirm physical reference height first')
            if type(destination) is not int or not -600<=destination<=600:raise ValueError('Elevation offset must stay within ±600 ms of reference')
            delta=destination-self.position
            try:
                while delta:
                    if token.is_set():raise ValueError('Elevation cancelled; restore reference height')
                    pulse=min(abs(delta),100);direction=-1 if delta>0 else 1
                    set_aim(direction)
                    cancelled=token.wait(pulse/1000)
                    set_aim(0)
                    if cancelled:raise ValueError('Elevation cancelled; restore reference height')
                    self.position+=pulse if delta>0 else -pulse
                    delta=destination-self.position
            except Exception:
                self.invalidate();raise
            finally:
                try:set_aim(0)
                except Exception:self.invalidate();raise
    def save_hit(self,shot):
        with self.lock:
            aiming=shot.get('elevation',{})
            if not shot.get('fire_command_sent') is True or not shot.get('reset_acknowledged') is True:
                raise ValueError('Need a completed recorded shot')
            if aiming.get('reference_confirmed') is not True or aiming.get('position_ms') is None:
                raise ValueError('Shot was made without a confirmed reference')
            if aiming.get('target')!='bullseye target':raise ValueError('Only bullseye shots calibrate this profile')
            height=aiming.get('height_percent');position=aiming.get('position_ms')
            if type(height) not in (float,int) or not 0<height<100 or type(position) is not int or not -600<=position<=600:raise ValueError('Invalid calibration measurement')
            if any(p['shot_id']==shot['id'] for p in self.data['points']):raise ValueError('Shot already saved')
            if any(abs(p['height_percent']-height)<.5 for p in self.data['points']):
                raise ValueError('A sample already covers this target size; move the target to a distinct distance')
            self.data['points'].append({'shot_id':shot['id'],'height_percent':height,'position_ms':position,'confirmation':'user-confirmed hit','time':time.time()})
            self.enabled=False;self.save()
