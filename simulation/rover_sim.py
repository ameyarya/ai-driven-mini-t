"""Mac-compatible toy projectile simulation; kinematic tracks, contact truth."""
import io
import math
from pathlib import Path
import sys
import numpy as np
import mujoco
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import rover_fast_navigation as navigation


class RoverSim:
    MIN_ELEVATION = -10.
    MAX_ELEVATION = 45.
    ELEVATION_RATE = 30.  # Illustrative degrees/sec, not calibrated servo motion.

    def __init__(self, render=True):
        self.model=mujoco.MjModel.from_xml_path(str(Path(__file__).with_name('tank.xml')))
        self.data=mujoco.MjData(self.model)
        self.renderer=mujoco.Renderer(self.model,height=360,width=640) if render else None
        self.can_joint=self.model.joint('can_free').qposadr[0]
        self.ball_joint=self.model.joint('projectile_free').qposadr[0]
        self.ball_velocity=self.model.joint('projectile_free').dofadr[0]
        self.can_geom=self.model.geom('can_geom').id
        self.can_geoms={self.model.geom(name).id for name in ('can_geom','can_top','can_bottom')}
        self.ball_geom=self.model.geom('projectile_geom').id
        self.reset()

    def reset(self, distance=.65, lateral=0, heading=0):
        if not .25 <= distance <= 3 or abs(lateral)>2:
            raise ValueError('Distance must be .25..3 m; lateral -2..2 m')
        mujoco.mj_resetData(self.model,self.data)
        self.data.qpos[self.can_joint:self.can_joint+3]=[distance,lateral,.061]
        self.x=self.y=0.;self.heading=float(heading);self.elevation=0.
        self.shots=[];self.history=[];self.plan=None;self.goal='';self.status='Ready';self.projectile_active=False
        self._pose();self.advance(.1)

    def _pose(self):
        self.data.mocap_pos[0]=[self.x,self.y,.045]
        self.data.mocap_quat[0]=[math.cos(self.heading/2),0,0,math.sin(self.heading/2)]
        angle=math.radians(self.elevation)
        self.model.body_quat[self.model.body('launcher').id]=[math.cos(angle/2),0,-math.sin(angle/2),0]
        mujoco.mj_forward(self.model,self.data)

    def launcher(self, action, duration_ms=250):
        if action not in ('up','down','stop') or type(duration_ms) is not int or not 0<=duration_ms<=1000:
            raise ValueError('Invalid simulated launcher movement')
        if action=='stop':return self.elevation
        change=(1 if action=='up' else -1)*self.ELEVATION_RATE*self.model.opt.timestep
        for _ in range(round(duration_ms/1000/self.model.opt.timestep)):
            self.elevation=max(self.MIN_ELEVATION,min(self.MAX_ELEVATION,self.elevation+change))
            if abs(self.elevation)<1e-10:self.elevation=0.
            self._pose();self.advance(self.model.opt.timestep)
        return self.elevation

    def advance(self, seconds):
        for _ in range(round(seconds/self.model.opt.timestep)):
            mujoco.mj_step(self.model,self.data)
            if self.shots and self.projectile_active:
                for contact in self.data.contact:
                    if (int(contact.geom1) in self.can_geoms and int(contact.geom2)==self.ball_geom or
                        int(contact.geom2) in self.can_geoms and int(contact.geom1)==self.ball_geom):
                        self.shots[-1]['contact_hit']=True

    def move(self, action, duration_ms):
        if action not in ('forward','backward','left','right','stop') or type(duration_ms) is not int or not 0<=duration_ms<=1000:
            raise ValueError('Invalid simulated movement')
        dt=self.model.opt.timestep
        for _ in range(round(duration_ms/1000/dt)):
            if action in ('left','right'):
                self.heading+=(1 if action=='left' else -1)*1.5*dt
            elif action in ('forward','backward'):
                speed=(1 if action=='forward' else -1)*.25
                self.x+=math.cos(self.heading)*speed*dt
                self.y+=math.sin(self.heading)*speed*dt
            self._pose();self.advance(dt)

    def fire(self, speed=6., elevation=None):
        if len(self.shots)>=6:
            raise ValueError('Six simulated shots used; reset scene to reload')
        elevation=self.elevation if elevation is None else elevation
        if not math.isfinite(speed) or not math.isfinite(elevation) or not 1<=speed<=12 or not self.MIN_ELEVATION<=elevation<=self.MAX_ELEVATION:
            raise ValueError('Invalid projectile launch parameters')
        self.elevation=float(elevation);self._pose()
        angle=math.radians(elevation)
        direction=np.array([math.cos(self.heading)*math.cos(angle),math.sin(self.heading)*math.cos(angle),math.sin(angle)])
        start=np.array([self.x,self.y,.10])+.145*direction
        self.data.qpos[self.ball_joint:self.ball_joint+7]=[*start,1,0,0,0]
        self.data.qvel[self.ball_velocity:self.ball_velocity+6]=[*(direction*speed),0,0,0]
        before=self.data.body('can').xpos.copy()
        shot=dict(command_sent=True,shot_fired=True,contact_hit=False,
                  speed=speed,elevation=elevation,simulation_only=True)
        self.shots.append(shot);mujoco.mj_forward(self.model,self.data)
        self.projectile_active=True
        self.advance(.8)
        self.projectile_active=False
        shot['can_displacement_m']=float(np.linalg.norm(self.data.body('can').xpos-before))
        return shot

    def observation(self):
        if self.renderer is None:
            raise ValueError('Rendering disabled')
        self.renderer.update_scene(self.data,camera='rover')
        rgb=self.renderer.render().copy()
        self.renderer.enable_segmentation_rendering()
        try:
            self.renderer.update_scene(self.data,camera='rover')
            segments=self.renderer.render()
            mask=np.isin(segments[:,:,0],list(self.can_geoms))&(segments[:,:,1]==mujoco.mjtObj.mjOBJ_GEOM)
        finally:
            self.renderer.disable_segmentation_rendering()
        ys,xs=np.where(mask)
        m=dict(target_visible=bool(len(xs)),candidate_count=int(bool(len(xs))),
               target_x=None,target_height=None,target_clipped=None,
               measurement_source='MuJoCo segmentation oracle; not real detector')
        image=Image.fromarray(rgb);draw=ImageDraw.Draw(image)
        for x in range(64,640,64):draw.line((x,0,x,360),fill=(120,120,120),width=1)
        draw.line((320,0,320,360),fill='white',width=2)
        if len(xs):
            box=(int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max()))
            m.update(target_x=(box[0]+box[2])/2/640*100,target_height=(box[3]-box[1]+1)/360*100,
                     target_clipped=box[0]==0 or box[2]==639 or box[1]==0 or box[3]==359)
            draw.rectangle(box,outline='lime',width=3)
            draw.text((12,338),f"SIM ORACLE x={m['target_x']:.1f}% height={m['target_height']:.1f}%",fill='white',stroke_width=1,stroke_fill='black')
        else:draw.text((12,338),'SIM ORACLE: target absent',fill='white')
        return rgb,image,m

    def step_goal(self):
        if not self.plan:raise ValueError('Start a mission first')
        _,_,measurement=self.observation()
        decision=navigation.control_decision(self.plan,measurement,self.history)
        action=decision['suggested_action']
        if decision.get('uncertainties') or decision.get('needs_replan'):
            self.status='Stopped: '+decision.get('reason','uncertain');self.plan=None
        elif action=='fire':
            shot=self.fire()
            self.status='Simulated contact HIT' if shot['contact_hit'] else 'Simulated MISS'
            self.plan=None
        elif decision['goal_achieved']:
            self.status='Goal achieved';self.plan=None
        elif decision.get('observe_again') or action!='stop':
            duration=0 if decision.get('observe_again') else decision['duration_ms']
            self.move(action,duration)
            self.history.append(dict(action=action,duration_ms=duration,phase=decision.get('phase'),
                target_x_before=measurement['target_x'],target_height_before=measurement['target_height']))
            self.status=decision['reason']
        else:self.status=decision['reason'];self.plan=None
        if len(self.history)>=80 and self.plan:
            self.status='Stopped: simulation step limit';self.plan=None
        return decision

    def image(self,labeled=False):
        rgb,image,_=self.observation()
        output=io.BytesIO()
        (image if labeled else Image.fromarray(rgb)).save(output,format='JPEG',quality=90)
        return output.getvalue()

    def close(self):
        if self.renderer:self.renderer.close()
