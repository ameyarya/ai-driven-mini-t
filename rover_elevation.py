"""Timed launcher elevation relative to a user-confirmed reference, not degrees."""
import json
import math
from pathlib import Path
import threading
import time
from camera_orientation import standoff_limit

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
        with self.lock:return {'reference_confirmed':self.position is not None,'position_ms':self.position,'enabled':self.enabled,'points':self.data['points'],'preset':self.data.get('preset'),'aim_offset_percent':self.data.get('aim_offset_percent',0)}
    def confirm_reference(self):
        with self.lock:self.position=0;self.enabled=False
    def invalidate(self):
        with self.lock:self.position=None;self.enabled=False
    def desired(self,height):
        if type(height) not in (float,int) or not math.isfinite(height):raise ValueError('Invalid target height')
        preset=self.data.get('preset')
        if not preset:raise ValueError('Save one confirmed successful shot first')
        if abs(height-preset['height_percent'])>3:
            raise ValueError('Target is outside saved shooting distance; approach before firing')
        return preset['position_ms']
    def enable(self):
        with self.lock:
            if self.position is None:raise ValueError('Restore reference height and confirm it first')
            preset=self.data.get('preset');self.desired(preset['height_percent'] if preset else 0)
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
            if height>standoff_limit():raise ValueError(f'Shooting setup must keep bullseye image height at most {standoff_limit()}%; move tank back')
            preset={'shot_id':shot['id'],'height_percent':height,'position_ms':position,'confirmation':'user-confirmed hit','time':time.time()}
            self.data['points'].append(preset)
            self.data['preset']=preset
            self.enabled=True;self.save()
