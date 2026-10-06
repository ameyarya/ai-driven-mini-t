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
import obstacle_navigation as avoidance


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
        self.tank_bodies={self.model.body('tank').id,self.model.body('launcher').id}
        self.tank_geoms={i for i in range(self.model.ngeom) if self.model.geom_bodyid[i] in self.tank_bodies}
        self.reset()

    def reset(self, distance=.65, lateral=0, heading=0, obstacle_scene='clear', obstacles=None):
        if not .25 <= distance <= 3 or abs(lateral)>2:
            raise ValueError('Distance must be .25..3 m; lateral -2..2 m')
        selected=avoidance.preset(obstacle_scene) if obstacles is None else obstacles
        if not isinstance(selected,list) or len(selected)>12:
            raise ValueError('At most twelve obstacles required')
        selected=[dict(o) for o in selected]
        for o in selected:
            if set(o)!=set(('x','y','hx','hy')) or not all(type(v) in (int,float) and math.isfinite(v) for v in o.values()) or o['hx']<=0 or o['hy']<=0:
                raise ValueError('Invalid obstacle rectangle')
        if not avoidance.safe(0,0,selected):raise ValueError('Obstacle overlaps start footprint')
        self.obstacles=selected;self.obstacle_scene=obstacle_scene
        self.obstacle_geoms={self.model.geom(f'obstacle_{i}').id for i in range(len(selected))}
        self.route=[];self.waypoint=0;self.avoidance_steps=0;self.guard_stops=0;self.obstacle_contacts=0
        for i in range(12):
            geom=self.model.geom(f'obstacle_{i}')
            if i<len(selected):
                o=selected[i];geom.pos[:]=[o['x'],o['y'],.12];geom.size[:]=[o['hx'],o['hy'],.12]
            else:geom.pos[:]=[0,0,-5]
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
            # Mocap/static pairs are excluded from automatic contact generation.
            # Query MuJoCo's actual narrow-phase geometry independently of our disk guard.
            for obstacle in self.obstacle_geoms:
                for tank in self.tank_geoms:
                    if mujoco.mj_geomDistance(self.model,self.data,obstacle,tank,0.,None)<0:
                        self.obstacle_contacts+=1
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
                x=self.x+math.cos(self.heading)*speed*dt
                y=self.y+math.sin(self.heading)*speed*dt
                if not avoidance.safe(x,y,self.obstacles):
                    self.guard_stops+=1;self.status='Stopped: obstacle clearance guard';return False
                self.x,self.y=x,y
            self._pose();self.advance(dt)
        return True

    def start_avoidance(self):
        target=self.data.body('can').xpos[:2]
        # Target position and obstacle map are simulator oracles, not inferred.
        goal=(float(target[0])-.35,float(target[1]))
        self.route=avoidance.route((self.x,self.y),goal,self.obstacles)
        self.waypoint=1;self.avoidance_steps=0;self.history=[]
        if not self.route:
            self.route=[];self.plan=None;self.status='Stopped: no clear route';return
        self.plan={'mode':'obstacle_route'};self.goal='Avoid obstacles, approach can, then stop'
        self.status='Obstacle route started (known simulation map)'

    def step_avoidance(self):
        self.avoidance_steps+=1
        if self.avoidance_steps>120:
            self.plan=None;self.status='Stopped: obstacle step limit';return {'suggested_action':'stop'}
        while self.waypoint<len(self.route) and math.dist((self.x,self.y),self.route[self.waypoint])<.012:
            self.waypoint+=1
        finished=self.waypoint>=len(self.route)
        target=self.data.body('can').xpos[:2] if finished else self.route[self.waypoint]
        dx,dy=target[0]-self.x,target[1]-self.y
        error=(math.atan2(dy,dx)-self.heading+math.pi)%(2*math.pi)-math.pi
        if abs(error)>.02:
            action='left' if error>0 else 'right';duration=max(1,min(400,round(abs(error)/1.5*1000)))
        elif finished:
            self.plan=None;self.status='Obstacle goal achieved';return {'suggested_action':'stop','goal_achieved':True}
        else:
            action='forward';duration=max(1,min(400,round(math.hypot(dx,dy)/.25*1000)))
        if not self.move(action,duration):self.plan=None
        else:self.status=f'Avoidance {action} · waypoint {self.waypoint}/{len(self.route)-1}'
        self.history.append(dict(action=action,duration_ms=duration,phase='obstacle_route'))
        return dict(suggested_action=action,duration_ms=duration,goal_achieved=False)

    def obstacle_state(self):
        readings=avoidance.ranges(self.x,self.y,self.heading,self.obstacles)
        return dict(scene=self.obstacle_scene,ranges_m=readings,
                    source='SIM ORACLE: known rectangle map + ideal laser fan; not camera detection',
                    route=self.route,waypoint=self.waypoint,pose=[self.x,self.y,self.heading],
                    clearance_m=None if not self.obstacles else avoidance.clearance(self.x,self.y,self.obstacles),
                    guard_stops=self.guard_stops,obstacle_contacts=self.obstacle_contacts)

    def overview(self):
        camera=mujoco.MjvCamera();camera.lookat[:]=[.65,0,0];camera.distance=2.8
        camera.azimuth=90;camera.elevation=-90
        self.renderer.update_scene(self.data,camera=camera)
        image=Image.fromarray(self.renderer.render().copy())
        draw=ImageDraw.Draw(image);draw.text((10,10),'SIM KNOWN-MAP VIEW: blue obstacles; no real sensors',fill='white',stroke_width=1,stroke_fill='black')
        out=io.BytesIO();image.save(out,format='JPEG',quality=90);return out.getvalue()

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
        if self.obstacles:
            readings=avoidance.ranges(self.x,self.y,self.heading,self.obstacles)
            draw.text((12,12),f"SIM RANGE front={readings['0']:.2f}m left={readings['90']:.2f}m right={readings['-90']:.2f}m",fill='white',stroke_width=1,stroke_fill='black')
        return rgb,image,m

    def step_goal(self):
        if not self.plan:raise ValueError('Start a mission first')
        if self.plan.get('mode')=='obstacle_route':return self.step_avoidance()
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
            if not self.move(action,duration):
                self.plan=None
                return dict(suggested_action='stop',goal_achieved=False,reason=self.status)
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
