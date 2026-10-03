"""Exercise the running localhost:8002 simulator; no Qwen or hardware calls."""
import json
import argparse
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'playground-data/simulation/http-matrix.json'
URL='http://127.0.0.1:8002'
GOALS=[
    ('center','Center the red can, then stop.'),
    ('find','Find the red can by turning in place, center it, then stop.'),
    ('approach','Approach the red can until 50% of image height, then stop.'),
    ('shoot','Center the red can, then shoot once.'),
    ('combined_shoot','Find the red can, approach until 50% of image height, then shoot once.'),
]


def post(path,body):
    req=urllib.request.Request(URL+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=180))


def status():return json.load(urllib.request.urlopen(URL+'/status',timeout=30))


def main():
    report=dict(started=time.time(),backend='scripted; Qwen not called',cases=[],checks=[])
    def save():OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+'\n')
    for index in range(20):
        distance=.55+(index%5)*.15
        lateral=[-.30,-.15,0,.15,.30][index%5]
        behind=index>=10
        for kind,goal in GOALS:
            post('/reset',dict(distance=distance,lateral=lateral))
            if behind:
                post('/move',dict(action='left',duration_ms=1000))
                post('/move',dict(action='left',duration_ms=1000))
            initial=status()
            post('/goal',dict(goal=goal,backend='scripted'))
            start=time.monotonic()
            for observation in range(81):
                current=status()
                if not current['running']:break
                post('/step',{})
            final=status()
            shooting=kind in ('shoot','combined_shoot')
            fired=bool(final['shots'])
            checks=dict(terminated=not final['running'],
                at_most_one_shot=len(final['shots'])<=1,
                no_unrequested_fire=shooting or not fired,
                step_bound=final['steps']<=80,
                absent_nonsearch_stops=(kind not in ('center','approach','shoot') or
                    initial['measurement']['target_visible'] or final['steps']==0 and not fired))
            case=dict(scene=index,kind=kind,goal=goal,distance=distance,lateral=lateral,behind=behind,
                initial=initial['measurement'],final=final['measurement'],status=final['status'],
                steps=final['steps'],observations=observation,shots=final['shots'],checks=checks,
                invariant_passed=all(checks.values()),seconds=round(time.monotonic()-start,2))
            report['cases'].append(case);save()
            print(f"{len(report['cases'])}/100 {kind} scene {index}: {final['status']}",flush=True)
    for name,path,body in [
        ('Unknown movement rejected','/move',dict(action='fly',duration_ms=250)),
        ('Unbounded pulse rejected','/move',dict(action='forward',duration_ms=2000)),
        ('Physical distance rejected','/goal',dict(goal='Approach red can to 20 centimeters',backend='scripted')),
        ('Repeated firing mission rejected','/goal',dict(goal='Shoot red can six times',backend='scripted')),
        ('Unnamed target rejected','/goal',dict(goal='Shoot it',backend='scripted')),
        ('Blank goal rejected','/goal',dict(goal='',backend='scripted')),
    ]:
        try:post(path,body);passed=False
        except urllib.error.HTTPError as error:passed=error.code==400
        report['checks'].append(dict(name=name,passed=passed))
    post('/reset',{})
    for _ in range(6):post('/fire',{})
    try:post('/fire',{});passed=False
    except urllib.error.HTTPError as error:passed=error.code==400
    report['checks'].append(dict(name='Seventh shot rejected',passed=passed))
    post('/reset',{})
    post('/goal',dict(goal='Find the red can and shoot once',backend='scripted'))
    post('/stop',{})
    report['checks'].append(dict(name='Stop cancels without shooting',passed=not status()['running'] and not status()['shots']))
    post('/reset',{})
    report['finished']=time.time()
    report['summary']=dict(cases=len(report['cases']),invariants_passed=sum(c['invariant_passed'] for c in report['cases']),
        checks_passed=sum(c['passed'] for c in report['checks']),checks_total=len(report['checks']),
        by_kind={kind:dict(total=sum(c['kind']==kind for c in report['cases']),
            goals_completed=sum(c['kind']==kind and c['status']=='Goal achieved' for c in report['cases']),
            fired=sum(c['kind']==kind and bool(c['shots']) for c in report['cases']),
            contact_hits=sum(c['kind']==kind and any(s['contact_hit'] for s in c['shots']) for c in report['cases']),
            stops=sum(c['kind']==kind and c['status'] not in ('Goal achieved','Simulated contact HIT','Simulated MISS') for c in report['cases'])) for kind,_ in GOALS})
    save();print(json.dumps(report['summary'],indent=2),flush=True)
    if report['summary']['invariants_passed']!=100 or report['summary']['checks_passed']!=len(report['checks']):
        raise SystemExit('Invariant or HTTP check failed')


def qwen_smoke():
    results=[]
    goals=[
        'Center the red can, then shoot once.',
        'Find the red can by turning in place, center it, then shoot once.',
        'Approach the red can until 50% of image height, keep it centered, then shoot once.',
        'Find the red can, approach until 50% of image height, keep it centered, then shoot once.',
    ]
    for goal in goals:
        post('/reset',dict(distance=.8,lateral=.15))
        start=time.monotonic()
        try:
            post('/goal',dict(goal=goal,backend='ollama'))
            planner_seconds=time.monotonic()-start
            for _ in range(81):
                state=status()
                if not state['running']:break
                post('/step',{})
            state=status()
            result=dict(goal=goal,planner_seconds=round(planner_seconds,2),status=state['status'],
                steps=state['steps'],shots=state['shots'],passed=len(state['shots'])==1 and state['shots'][0]['contact_hit'])
        except urllib.error.HTTPError as error:
            result=dict(goal=goal,passed=False,error=error.read().decode())
        results.append(result)
        (OUT.parent/'qwen-smoke.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    post('/reset',{})
    if not all(r['passed'] for r in results):raise SystemExit('Qwen mission check failed; see saved results')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--qwen-smoke',action='store_true')
    args=parser.parse_args()
    qwen_smoke() if args.qwen_smoke else main()
