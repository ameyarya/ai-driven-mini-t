"""Replay controller invariants on every recorded scene; no model or hardware."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rover_playground import catalog
from rover_fast_navigation import control_decision, alignment_tolerance


def run():
    cases = []
    for item in catalog().values():
        for mode in ('center', 'approach_size', 'find', 'find_approach_size'):
            plan = dict(mode=mode,target='red soda can',height_percent=50 if 'size' in mode else 0,
                        reason='Replay fixture',uncertainties=[],search_direction='right',
                        heading_calibrated=False,full_turn_ms=None)
            m = item['measurement']
            a = control_decision(plan, m, [])
            failures = []
            action = a['suggested_action']
            if action not in ('left','right','forward','stop'):
                failures.append('unsupported action')
            if not 50 <= a['duration_ms'] <= 1000:
                failures.append('duration outside bounds')
            if a.get('uncertainties') and action != 'stop':
                failures.append('movement under uncertainty')
            if action == 'forward':
                if not m.get('target_visible') or m.get('target_clipped') is not False:
                    failures.append('forward without fully measured target')
                if abs(m['target_x']-50) > alignment_tolerance(plan, m):
                    failures.append('forward while misaligned')
            if a.get('goal_achieved'):
                if not m.get('target_visible') or abs(m['target_x']-50)>5:
                    failures.append('completion without centered target')
                if 'size' in mode and (m.get('target_clipped') or m['target_height']<49):
                    failures.append('size completion before setpoint')
            cases.append(dict(frame=item['id'],mode=mode,action=action,passed=not failures,failures=failures))
    result = dict(kind='Controller invariant replay, not physical simulation',
                  total=len(cases),passed=sum(x['passed'] for x in cases),cases=cases)
    output = ROOT / 'playground-data' / 'controller-replay.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('kind','total','passed')},indent=2))
    return result


if __name__ == '__main__':
    result=run()
    raise SystemExit(0 if result['total']==result['passed'] else 1)
