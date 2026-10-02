"""Capture one live DJI frame and ask local Qwen for navigation advice.

Run: python3 rover_vision.py [--goal 'Find a clear path ahead']
This script only observes; it does not send motor commands.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
import urllib.request


def read_json(url, body=None, timeout=5):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def assess(goal):
    paths = read_json('http://127.0.0.1:9997/v3/paths/list')['items']
    if not any(p['name'] == 'live/tank' and p['ready'] for p in paths):
        raise RuntimeError('DJI stream is offline. Start the Mimo livestream first.')
    output = Path(__file__).resolve().parent / 'vision-output'
    output.mkdir(exist_ok=True)
    frame = output / ('frame-' + time.strftime('%Y%m%d-%H%M%S') + '.jpg')
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-rw_timeout', '15000000',
        '-i', 'rtmp://192.168.1.192:1935/live/tank', '-an', '-frames:v', '1',
        '-vf', 'scale=640:-2', '-q:v', '3', '-y', str(frame),
    ], check=True, timeout=25)
    captured_at = time.time()
    prompt = (
        'Answer the user question directly using this camera image. '
        'For left/centre/right questions, use horizontal position in the IMAGE, '
        'not a movement direction. If asked for a location, put that location '
        'first in answer. Do not turn an observation question into a driving goal. '
        'Assess only visible evidence. Do not invent distances, hidden obstacles, '
        'or a target that is not visible. A single image cannot prove clearance. '
        'The feed has approximately one second of delay. '
        'If the image is blurred, obstructed, not facing the driving surface, '
        'or too uncertain to assess, suggest stop. '
        'Return a concise JSON object with answer (direct response to the question), '
        'scene, obstacles (list), '
        'suggested_action (forward/backward/left/right/stop), reason, and '
        'uncertainties (list). Set suggested_action to stop unless the user '
        'explicitly requests navigation advice or movement. The suggestion is '
        'advisory only. User question or goal: ' + goal
    )
    start = time.monotonic()
    response = read_json('http://127.0.0.1:11434/api/chat', {
        'model': 'qwen3-vl:4b-instruct', 'stream': False,
        'format': {'type': 'object', 'properties': {
            'answer': {'type': 'string', 'maxLength': 240},
            'scene': {'type': 'string', 'maxLength': 180},
            'obstacles': {'type': 'array', 'maxItems': 4, 'items': {'type': 'string', 'maxLength': 80}},
            'suggested_action': {'type': 'string', 'enum': ['forward', 'backward', 'left', 'right', 'stop']},
            'reason': {'type': 'string', 'maxLength': 180},
            'uncertainties': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'maxLength': 80}},
        }, 'required': ['answer', 'scene', 'obstacles', 'suggested_action', 'reason', 'uncertainties'],
                   'additionalProperties': False},
        'messages': [{'role': 'user', 'content': prompt,
                      'images': [base64.b64encode(frame.read_bytes()).decode()]}],
        'options': {'num_ctx': 4096, 'num_predict': 800, 'temperature': 0},
    }, timeout=120)
    if response.get('done_reason') == 'length':
        raise RuntimeError('Model output was truncated; no usable assessment.')
    assessment = json.loads(response['message']['content'])
    if assessment.get('suggested_action') not in ('forward', 'backward', 'left', 'right', 'stop'):
        raise RuntimeError('Model returned an invalid action; no usable assessment.')
    result = {'model': response['model'], 'frame': str(frame),
              'captured_at': captured_at, 'goal': goal,
              'inference_seconds': round(time.monotonic() - start, 2),
              'assessment': assessment, 'motor_commands_sent': False}
    frame.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goal', default='Find a clear path ahead.')
    args = parser.parse_args()
    try:
        print(json.dumps(assess(args.goal), indent=2))
    except Exception as error:
        parser.exit(1, 'Vision assessment failed: ' + str(error) + '\n')
