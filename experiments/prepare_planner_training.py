"""Build local goal-contract examples, split by recording session, without motors."""
import datetime
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rover_playground import catalog
from rover_fast_navigation import planner_request

OUT = ROOT / 'playground-data' / 'planner-training'
GOALS = {
    'center': ['Center the red can in the image, then stop.', 'Position the red can in the center.', 'Keep the red can in the middle of the camera image.'],
    'approach_size': ['Move closer to the red can until it occupies roughly 50% of the image height. Keep it centered, then stop.', 'Approach the red can until it fills 40% of the image height. Center it, then stop.', 'Move closer until the red can occupies 60% of the image height. Keep it centered.'],
    'find': ['Find the red can by doing a 360 turn in place. Center it, then stop.', 'Search for the red can by turning in place, center it, then stop.', 'Scan for the red can, center it in the image, then stop.'],
    'find_approach_size': ['Find the red can by turning in place, then move closer until it occupies roughly 50% of the image height. Keep it centered, then stop.', 'Search for the red can, then approach until it fills 40% of the image height. Keep it centered.', 'Find and center the red can, then approach until it occupies 60% of the image height.'],
    'shoot': ['Find the red can and shoot it.', 'Fire at the red can.', 'Aim the launcher at the red can and fire.'],
    'away': ['Move farther away from the red can.', 'Drive backward away from the red can.', 'Move away from the red can, then stop.'],
    'physical_distance': ['Move within 20 centimeters of the red can.', 'Approach the red can to a distance of 30 cm.', 'Stop 10 inches from the red can.'],
}


def expected_plan(kind, goal, measurement):
    """Labels reflect existing capability, not unimplemented shooting behavior."""
    target = 'red soda can'
    result = dict(mode=kind,target=target,height_percent=0,reason='',uncertainties=[])
    if kind in ('shoot','away','physical_distance'):
        return dict(result,mode='unsupported',reason={'shoot':'Firing is not supported by this controller.','away':'Moving away is not supported by this controller.','physical_distance':'Physical distances require calibration; only image size is supported.'}[kind])
    if measurement.get('candidate_count',0)>1:
        return dict(result,mode='unsupported',reason='Multiple target candidates; cannot choose reliably.',uncertainties=['Ambiguous target'])
    if kind in ('center','approach_size') and not measurement.get('target_visible'):
        return dict(result,mode='unsupported',reason='Target not visible; cannot perform this non-search goal.',uncertainties=['Target not visible'])
    if kind=='approach_size' and measurement.get('target_clipped'):
        return dict(result,mode='unsupported',reason='Target clipped; full image height is unavailable.',uncertainties=['Target clipped'])
    if 'size' in kind:
        result['height_percent']=float(re.search(r'(\d+)\s*%',goal).group(1))
    result['reason']={'center':'Center the target, then stop.','approach_size':'Approach to the requested image height while centered.','find':'Search in place, center and confirm the target, then stop.','find_approach_size':'Search, align, approach to requested image height, then stop.'}[kind]
    return result


def sessions(items):
    groups=[]
    for item in sorted(items,key=lambda x:x['id']):
        match=re.search(r'frame-(\d{8})-(\d{6})',item['id'])
        timestamp=datetime.datetime.strptime(' '.join(match.groups()),'%Y%m%d %H%M%S').timestamp()
        if not groups or timestamp-groups[-1]['end']>120:
            groups.append(dict(end=timestamp,items=[]))
        groups[-1]['end']=timestamp;groups[-1]['items'].append(item)
    return groups


def select(items, count):
    unique={hashlib.sha256(i['raw'].read_bytes()).hexdigest():i for i in items}
    values=list(unique.values())
    if len(values)<=count:return values
    return [values[round(i*(len(values)-1)/(count-1))] for i in range(count)]


def main():
    groups=sessions(catalog().values())
    if len(groups)<3:raise ValueError('Need at least three distinct recording sessions')
    train=select([i for g in groups[:-2] for i in g['items']],24)
    validation=select(groups[-2]['items'],6)
    latest=groups[-1]['items']
    predicates=[lambda m:m.get('target_visible') and m['target_x']<35 and not m.get('target_clipped'),
                lambda m:m.get('target_visible') and m['target_x']>65 and not m.get('target_clipped'),
                lambda m:m.get('target_visible') and abs(m['target_x']-50)<3 and not m.get('target_clipped'),
                lambda m:not m.get('target_visible') and m.get('candidate_count',0)==0]
    test=[next(i for i in reversed(latest) if predicate(i['measurement'])) for predicate in predicates]
    selections={'train':train,'validation':validation,'test':test}
    hashes={name:{hashlib.sha256(i['raw'].read_bytes()).hexdigest() for i in values} for name,values in selections.items()}
    for a,b in [('train','validation'),('train','test'),('validation','test')]:
        if hashes[a]&hashes[b]:raise ValueError('Identical raw image crosses splits')
    (OUT/'images').mkdir(parents=True,exist_ok=True)
    manifest=[];counts={}
    for split,items in selections.items():
        examples=[];official=[]
        for item in items:
            image=OUT/'images'/(item['sha256']+'.jpg');shutil.copy2(item['image'],image)
            variants=1 if split=='test' else 3
            for kind,goals in GOALS.items():
                for goal in goals[:variants]:
                    answer=expected_plan(kind,goal,item['measurement'])
                    request=planner_request(goal,image.read_bytes(),item['measurement'])
                    prompt=request['messages'][0]['content']
                    examples.append(dict(images=[str(image)],messages=[
                        dict(role='user',content=[dict(type='image',image=str(image)),dict(type='text',text=prompt)]),
                        dict(role='assistant',content=[dict(type='text',text=json.dumps(answer,separators=(',',':')))])],
                        goal=goal,kind=kind,expected=answer,schema=request['format'],frame=item['id']))
                    official.append(dict(image='images/'+image.name,conversations=[
                        {'from':'human','value':'<image>\n'+prompt},{'from':'gpt','value':json.dumps(answer,separators=(',',':'))}]))
            manifest.append(dict(split=split,frame=item['id'],raw_sha256=hashlib.sha256(item['raw'].read_bytes()).hexdigest(),labeled_sha256=item['sha256']))
        if split=='train':random.Random(20261003).shuffle(examples)
        (OUT/(split+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in examples))
        (OUT/(split+'-qwen.json')).write_text(json.dumps(official,indent=2)+'\n')
        counts[split]=len(examples)
    metadata=dict(label_source='Agent-authored goal/capability contracts; recorded detector visibility is unverified, not human grounding labels',
        split_policy='Latest recording session held out for test; previous session validation; earlier sessions train. Gap >120s defines session.',
        counts=counts,frames={k:len(v) for k,v in selections.items()},manifest=manifest)
    (OUT/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({k:metadata[k] for k in ('counts','frames','label_source')},indent=2))


if __name__=='__main__':main()
