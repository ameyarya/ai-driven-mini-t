"""Launcher API integration checks against the simulation server only."""
import json
import urllib.error
from http_matrix import post, status, ROOT


def main():
    checks=[]
    def check(name,passed):
        checks.append(dict(name=name,passed=bool(passed)))
        if not passed:raise AssertionError(name)
    try:
        post('/reset',{})
        post('/launcher',dict(action='up',duration_ms=250))
        check('Up changes reported elevation',abs(status()['launcher_elevation']-7.5)<1e-8)
        post('/launcher',dict(action='down',duration_ms=250))
        check('Down reverses elevation',status()['launcher_elevation']==0)
        for _ in range(3):post('/launcher',dict(action='up',duration_ms=1000))
        check('Upper limit enforced',status()['launcher_elevation']==45)
        post('/launcher',dict(action='stop',duration_ms=1000))
        check('Launcher stop preserves angle',status()['launcher_elevation']==45)
        for _ in range(3):post('/launcher',dict(action='down',duration_ms=1000))
        check('Lower limit enforced',status()['launcher_elevation']==-10)
        for name,body in [
            ('Unknown launcher action rejected',dict(action='spin')),
            ('Unbounded launcher duration rejected',dict(action='up',duration_ms=1001)),
            ('Negative launcher duration rejected',dict(action='down',duration_ms=-1))]:
            try:post('/launcher',body);accepted=True
            except urllib.error.HTTPError as e:accepted=e.code!=400
            check(name,not accepted and status()['launcher_elevation']==-10)
        post('/reset',{})
        check('Reset returns launcher to zero',status()['launcher_elevation']==0)
        post('/goal',dict(goal='Find the can and shoot once',backend='scripted'))
        post('/launcher',dict(action='up',duration_ms=1000))
        check('Manual launcher input cancels goal',not status()['running'])
        post('/fire',{})
        shot=status()['shots'][-1]
        check('Fire uses raised angle and misses',abs(shot['elevation']-30)<1e-8 and not shot['contact_hit'])
        post('/launcher',dict(action='down',duration_ms=1000));post('/fire',{})
        check('Lowering recovers level contact hit',status()['shots'][-1]['contact_hit'])
    finally:
        post('/reset',{})
        out=ROOT/'playground-data/simulation/launcher-http-checks.json'
        out.write_text(json.dumps(dict(checks=checks),indent=2)+'\n')
    print(json.dumps(checks))


if __name__=='__main__':main()
