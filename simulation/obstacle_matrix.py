"""Publish a deterministic 100-case known-map avoidance evaluation, no Qwen."""
import json
from rover_sim import RoverSim, ROOT
import obstacle_navigation as nav


def run():
    sim=RoverSim(render=False);cases=[]
    try:
        for i in range(100):
            scene=('block','left_open','right_open','wall','blocked')[i%5]
            distance=1.2+(i%4)*.1;lateral=((i//5)%3-1)*.1;heading=((i%3)-1)*.5
            sim.reset(distance=distance,lateral=lateral,heading=heading,obstacle_scene=scene)
            sim.start_avoidance();minimum=nav.clearance(sim.x,sim.y,sim.obstacles)
            for _ in range(121):
                if not sim.plan:break
                sim.step_goal();minimum=min(minimum,nav.clearance(sim.x,sim.y,sim.obstacles))
            success=sim.status==('Stopped: no clear route' if scene=='blocked' else 'Obstacle goal achieved')
            checks=dict(expected_terminal_state=success,no_contacts=sim.obstacle_contacts==0,
                        clearance_kept=minimum>=nav.MARGIN-1e-9,no_firing=not sim.shots,
                        bounded=sim.avoidance_steps<=120)
            cases.append(dict(scene=scene,distance=distance,lateral=lateral,initial_heading=heading,
                status=sim.status,steps=sim.avoidance_steps,minimum_clearance_m=round(minimum,4),
                guard_stops=sim.guard_stops,contacts=sim.obstacle_contacts,checks=checks,
                passed=all(checks.values())))
    finally:sim.close()
    summary=dict(cases=len(cases),passed=sum(c['passed'] for c in cases),
                 reached=sum(c['status']=='Obstacle goal achieved' for c in cases),
                 blocked_stops=sum(c['status']=='Stopped: no clear route' for c in cases),
                 contacts=sum(c['contacts'] for c in cases),
                 guard_stops=sum(c['guard_stops'] for c in cases))
    report=dict(date='2026-10-04',backend='Known-map A* and footprint guard; no Qwen',
                sensing='Ideal rectangle map, pose and can-location oracle; displayed ideal laser fan',
                summary=summary,cases=cases,
                limitations=['Not sensor-only navigation','No learned obstacle detection or fine-tuning',
                             'Kinematic tracks, static rectangular obstacles, perfect localization',
                             'Fixed bounded workspace; no physical tank tests'])
    out=ROOT/'docs/obstacle-simulation-results.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if summary['passed']!=100:raise SystemExit(1)


if __name__=='__main__':run()
