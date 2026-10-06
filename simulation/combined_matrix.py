"""Scripted multi-stage mission regression; perfect-map/segmentation oracles.

Stages are orchestrated here, not integrated into the dashboard goal planner.
No Qwen, hardware, learned sensing, or automatic elevation selection is used.
"""
import argparse
import json
import math
from pathlib import Path

from rover_sim import RoverSim, ROOT, navigation
import obstacle_navigation as avoidance

FIND = 'Find the can by turning in place, center it, then stop.'
SHOOT = 'Approach the can until 50% of image height, center it, then shoot once.'


def scenarios():
    cases = []
    for index in range(24):
        sign = 1 if index % 2 == 0 else -1
        cases.append(dict(name=f'detour-{index:02d}', distance=1.2 + .1*(index % 4),
                          lateral=sign*.7, heading=math.pi + .3*((index % 3)-1),
                          obstacles=[dict(x=.55, y=0, hx=.08, hy=.15)] +
                          ([dict(x=.85, y=-sign*.45, hx=.07, hy=.12)] if index >= 12 else []),
                          expected='hit'))
    cases.extend([
        dict(name='enclosed', distance=1.2, lateral=0, heading=math.pi,
             obstacle_scene='blocked', expected='search_stop'),
        dict(name='occluded-wall', distance=1.2, lateral=0, heading=math.pi,
             obstacle_scene='wall', expected='search_stop'),
        dict(name='unsafe-destination', distance=1.2, lateral=.7, heading=math.pi,
             obstacles=[dict(x=.85,y=.7,hx=.06,hy=.06)], expected='route_stop'),
    ])
    for stage in ('find', 'avoid', 'shoot'):
        cases.append(dict(name=f'cancel-{stage}', distance=1.2,lateral=.7,heading=math.pi,
                          obstacle_scene='block', cancel=stage,expected='cancelled'))
    cases.append(dict(name='exhausted-ammunition',distance=1.2,lateral=.7,heading=math.pi,
                      obstacle_scene='block', exhausted=True,expected='ammo_stop'))
    return cases


def run_case(sim, spec):
    sim.reset(**{k: spec[k] for k in ('distance','lateral','heading','obstacles','obstacle_scene') if k in spec})
    if spec.get('exhausted'):
        # Seed prior attempts without perturbing this scene with six projectiles.
        sim.shots = [dict(simulation_only=True, prior_attempt_fixture=True) for _ in range(6)]
    before_shots = len(sim.shots)
    result = dict(name=spec['name'], expected=spec['expected'], initial=spec,
                  stages=[], initial_measurement=sim.observation()[2])
    minimum = avoidance.clearance(sim.x,sim.y,sim.obstacles)
    outcome = None
    for stage, goal, mode in [('find',FIND,'find'),('avoid',None,None),('shoot',SHOOT,'approach_shoot')]:
        if stage == 'avoid':
            sim.start_avoidance()
        else:
            sim.goal=goal
            sim.plan=dict(mode=mode,target='can',height_percent=50 if stage=='shoot' else 0,
                          reason='Scripted matrix stage',uncertainties=[])
            navigation.validate_plan(sim.plan,goal)
            sim.history=[]
        trace=[]
        ammo_error=False
        for _ in range(121):
            if not sim.plan: break
            if spec.get('cancel')==stage and len(trace)==1:
                # Same cancellation state transition as simulation/server.py /stop.
                sim.plan=None;sim.status='Stopped by user'
                pose=(sim.x,sim.y,sim.heading);shots=len(sim.shots)
                try:
                    sim.step_goal()
                except ValueError:
                    pass
                else:
                    raise AssertionError('Cancelled mission accepted a stale step')
                assert pose==(sim.x,sim.y,sim.heading) and shots==len(sim.shots)
                outcome='cancelled';break
            try:
                decision=sim.step_goal()
            except ValueError as error:
                if str(error)!='Six simulated shots used; reset scene to reload': raise
                ammo_error=True;sim.plan=None;sim.status=str(error);break
            minimum=min(minimum,avoidance.clearance(sim.x,sim.y,sim.obstacles))
            trace.append(dict(action=decision.get('suggested_action'),phase=decision.get('phase'),
                              duration_ms=decision.get('duration_ms',0),pose=[sim.x,sim.y,sim.heading]))
        result['stages'].append(dict(stage=stage,status=sim.status,steps=len(trace),trace=trace,
                                     measurement=sim.observation()[2]))
        assert not sim.plan, 'Stage exceeded harness bound'
        if outcome: break
        if stage!='shoot':
            assert len(sim.shots)==before_shots,'Premature firing'
            wanted='Goal achieved' if stage=='find' else 'Obstacle goal achieved'
            if sim.status!=wanted:
                outcome='search_stop' if stage=='find' else 'route_stop';break
        else:
            outcome='ammo_stop' if ammo_error else ('hit' if len(sim.shots)>before_shots and sim.shots[-1]['contact_hit'] else 'miss_or_stop')
    new_shots=sim.shots[before_shots:]
    checks=dict(expected_outcome=outcome==spec['expected'], no_obstacle_overlaps=sim.obstacle_contacts==0,
                clearance_kept=minimum>=avoidance.MARGIN-1e-9,at_most_one_new_shot=len(new_shots)<=1,
                stopped=sim.plan is None, no_fire_on_stop=outcome=='hit' or not new_shots,
                stage_bounds=all(s['steps']<=120 if s['stage']=='avoid' else s['steps']<=81 for s in result['stages']))
    result.update(outcome=outcome,checks=checks,passed=all(checks.values()),new_shots=new_shots,
                  minimum_clearance_m=minimum if math.isfinite(minimum) else None,
                  obstacle_overlaps=sim.obstacle_contacts,guard_stops=sim.guard_stops)
    return result


def run(output):
    sim=RoverSim();cases=[]
    try:
        for spec in scenarios():
            case=run_case(sim,spec);cases.append(case)
            print(f"{case['name']}: {case['outcome']} {'PASS' if case['passed'] else 'FAIL'}",flush=True)
    finally:
        sim.close()
    outcomes={key:sum(c['outcome']==key for c in cases) for key in sorted({c['outcome'] for c in cases})}
    report=dict(backend='Scripted stage orchestration; Qwen not called',
                limitations=['Perfect map and pose; segmentation oracle','Static rectangles and kinematic tracks',
                             'Fixed zero-degree launcher elevation; no automatic ballistic aiming',
                             'Stage transitions supplied by harness, not a single dashboard mission',
                             'Selected deterministic scenes; no physical reliability claim'],
                summary=dict(cases=len(cases),passed=sum(c['passed'] for c in cases),outcomes=outcomes,
                             obstacle_overlaps=sum(c['obstacle_overlaps'] for c in cases)),cases=cases)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2))
    if not all(c['passed'] for c in cases): raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'playground-data/simulation/combined-matrix.json')
    run(parser.parse_args().output)
