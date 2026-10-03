"""Offline frame review and Qwen training-data preparation. No hardware imports."""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import threading
import time
from unittest.mock import patch
import uuid

import rover_fast_navigation as navigation

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'playground-data'
LOCK = threading.Lock()
FIELDS = ('mode', 'target', 'height_percent', 'reason', 'uncertainties')


def catalog(frames=ROOT / 'vision-output'):
    items = {}
    for path in sorted(frames.glob('*.json')):
        try:
            record = json.loads(path.read_text())
            raw = frames / Path(record['frame']).name
            image = frames / Path(record['model_frame']).name
            measurement = record['detector']
            if not raw.is_file() or not image.is_file():
                continue
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            if digest != record.get('input_sha256'):
                continue
            items[path.name] = dict(id=path.name, raw=raw, image=image,
                                    measurement=measurement, sha256=digest,
                                    goal=record.get('goal', ''))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return items


def public_item(item):
    return {k: item[k] for k in ('id', 'measurement', 'sha256', 'goal')}


def infer(item, goal):
    """Reuse the production planner, but supply an immutable saved observation."""
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000:
        raise ValueError('Enter a goal (maximum 2000 characters)')
    run = DATA / 'runs' / uuid.uuid4().hex
    run.mkdir(parents=True)
    frame = run / 'frame.jpg'
    shutil.copy2(item['raw'], frame)
    prepared = dict(model_frame=str(item['image']), measurement=item['measurement'])
    captured_request = {}
    original_request = navigation.vision.read_json

    def request(url, body=None, timeout=5):
        captured_request.update(body or {})
        return original_request(url, body, timeout)

    start = time.monotonic()
    result = dict(id=run.name, source=item['id'], goal=goal,
                  image_sha256=item['sha256'], motor_commands_sent=False)
    # One server process, serialized calls. Never touch the live dashboard state
    # or original logs. No capture, camera, detector or serial connection needed.
    with LOCK, patch.object(navigation.vision, 'capture_frame', return_value=frame), \
            patch.object(navigation.vision, 'prepare_detector_image', return_value=prepared), \
            patch.object(navigation.vision, 'publish_input'), \
            patch.object(navigation.vision, 'read_json', side_effect=request):
        try:
            result['plan'] = navigation.plan_goal(goal)
        except Exception as error:
            result['error'] = str(error)
            saved = frame.with_suffix('.plan.json')
            if saved.exists():
                result['plan'] = json.loads(saved.read_text()).get('planner_decision')
    result['seconds'] = round(time.monotonic() - start, 2)
    if captured_request:
        result['prompt'] = captured_request['messages'][0]['content']
        result['schema'] = captured_request['format']
    (run / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def validate_label(plan, goal):
    if not isinstance(plan, dict) or set(plan) != set(FIELDS):
        raise ValueError('Expected exactly: ' + ', '.join(FIELDS))
    if not isinstance(plan['reason'], str) or len(plan['reason']) > 120:
        raise ValueError('Reason must be a string of at most 120 characters')
    if not isinstance(plan['target'], str) or len(plan['target']) > 80:
        raise ValueError('Target must be a string of at most 80 characters')
    if not isinstance(plan['uncertainties'], list) or len(plan['uncertainties']) > 3 or any(not isinstance(x, str) for x in plan['uncertainties']):
        raise ValueError('Uncertainties must be up to three strings')
    if type(plan['height_percent']) not in (int, float) or not 0 <= plan['height_percent'] <= 100:
        raise ValueError('Height must be numeric and in 0..100')
    if plan['mode'] != 'unsupported':
        navigation.validate_plan(plan, goal)


def review(run_id, plan):
    if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
        raise ValueError('Invalid run id')
    path = DATA / 'runs' / run_id / 'result.json'
    result = json.loads(path.read_text())
    validate_label(plan, result['goal'])
    if not result.get('prompt'):
        raise ValueError('No model prompt saved; cannot export this run')
    result.update(expected=plan, reviewed_at=time.time())
    path.write_text(json.dumps(result, indent=2) + '\n')
    return dict(reviewed=True, id=run_id)


def export_dataset(items):
    output = DATA / 'dataset'
    (output / 'images').mkdir(parents=True, exist_ok=True)
    splits = {'train': [], 'validation': []}
    manifest = []
    for path in sorted((DATA / 'runs').glob('*/result.json')):
        result = json.loads(path.read_text())
        if 'expected' not in result:
            continue
        item = items[result['source']]
        if result['image_sha256'] != item['sha256']:
            raise ValueError('Reviewed input changed')
        # All goals/overlays from an identical raw frame stay in one split.
        raw_hash = hashlib.sha256(item['raw'].read_bytes()).hexdigest()
        split = 'validation' if int(raw_hash[:8], 16) % 5 == 0 else 'train'
        filename = item['sha256'] + '.jpg'
        shutil.copy2(item['image'], output / 'images' / filename)
        splits[split].append(dict(image='images/' + filename, conversations=[
            dict(from_='human', value='<image>\n' + result['prompt']),
            dict(from_='gpt', value=json.dumps(result['expected'], separators=(',', ':')))]))
        manifest.append(dict(run=result['id'], split=split, raw_sha256=raw_hash,
                             labeled_sha256=item['sha256']))
    for name, examples in splits.items():
        # `from` is a Python keyword; serialize the official field name.
        for example in examples:
            for turn in example['conversations']:
                turn['from'] = turn.pop('from_')
        (output / (name + '.json')).write_text(json.dumps(examples, indent=2) + '\n')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return dict(path=str(output), **{k: len(v) for k, v in splits.items()})


class Handler(BaseHTTPRequestHandler):
    items = {}

    def reply(self, status, data, content_type='application/json'):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == '/':
            self.reply(200, (ROOT / 'rover_playground.html').read_bytes(), 'text/html; charset=utf-8')
        elif self.path == '/api/frames':
            self.reply(200, [public_item(item) for item in self.items.values()])
        elif self.path.startswith('/image/'):
            from urllib.parse import unquote
            item = self.items.get(unquote(self.path[len('/image/'):]))
            self.reply(200, item['image'].read_bytes(), 'image/jpeg') if item else self.reply(404, dict(error='Unknown frame'))
        else:
            self.reply(404, dict(error='Not found'))

    def do_POST(self):
        # JSON-only, same-origin requests; reject browser cross-origin writes.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.reply(403, dict(error='Cross-origin request rejected'))
        if self.headers.get('Content-Type') != 'application/json':
            return self.reply(415, dict(error='JSON required'))
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16384:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(size))
            if self.path == '/api/infer':
                result = infer(self.items[body['frame']], body['goal'])
            elif self.path == '/api/review':
                with LOCK:
                    result = review(body['run'], body['expected'])
            elif self.path == '/api/export':
                with LOCK:
                    result = export_dataset(self.items)
            else:
                return self.reply(404, dict(error='Not found'))
            self.reply(200, result)
        except (ValueError, KeyError, TypeError, OSError) as error:
            self.reply(400, dict(error=str(error)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    Handler.items = catalog()
    if args.export:
        print(json.dumps(export_dataset(Handler.items), indent=2))
        return
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Offline playground: http://localhost:{args.port} ({len(Handler.items)} verified frames)', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
