"""Record a known-map avoidance run and a blocked-route stop, no hardware."""
import json
import subprocess
from record_demo import RecordedSim, ROOT


def main():
    output=ROOT/'docs/assets/obstacle-avoidance-simulation.mp4'
    sim=RecordedSim(output);results=[]
    try:
        sim.title='AI-Driven Mini-T | Obstacle avoidance (known-map oracle)'
        for scene in ('left_open','blocked'):
            sim.reset(distance=1.2,obstacle_scene=scene);sim.next_frame=sim.data.time
            sim.action=scene+' | map, position and target location are simulator oracles'
            sim.hold(1.5);sim.start_avoidance()
            for _ in range(121):
                if not sim.plan:break
                sim.action=f'Known-map avoidance | step {sim.avoidance_steps+1} | clearance guard active'
                sim.hold(.2);sim.step_goal()
            sim.action=sim.status+' | contacts: '+str(sim.obstacle_contacts)
            sim.hold(2)
            expected='Stopped: no clear route' if scene=='blocked' else 'Obstacle goal achieved'
            if sim.status!=expected or sim.obstacle_contacts or sim.shots:
                raise RuntimeError('Obstacle demo failed acceptance checks')
            results.append(dict(scene=scene,status=sim.status,steps=sim.avoidance_steps,
                                contacts=sim.obstacle_contacts))
        output.with_suffix('.json').write_text(json.dumps(dict(results=results,frames=sim.frames,
            fps=10,simulation_only=True,backend='Known-map controller; no Qwen',
            limitations=['Perfect map and pose','Static obstacles','Uncalibrated tracks']),indent=2)+'\n')
    finally:sim.finish()
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(output),'-filter_complex',
        'fps=6,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',
        '-loop','0',str(output.with_suffix('.gif'))],check=True)
    print(json.dumps(results))


if __name__=='__main__':main()
