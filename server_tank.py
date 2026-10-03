"""Local web page -> USB transmitter -> ESP-NOW motor receiver.

Setup:  pip3 install pyserial
Run:    python3 server_tank.py   then open http://localhost:8000
Notes:  close Thonny first (it holds the serial port), battery connected.
"""
import threading
import time
import json
from pathlib import Path
import rover_vision
import rover_fast_navigation
import rover_autonomy
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import serial
import wireless_update

PORT = "/dev/cu.usbmodem1101"   # USB transmitter, MAC 206ef1450f1c
SPEED = 1024

MOVES = {
    "W": (SPEED, -SPEED),      # forward
    "S": (-SPEED, SPEED),      # back
    "A": (-SPEED, -SPEED),     # left
    "D": (SPEED, SPEED),       # right
    "X": (0, 0),               # stop
}

BOARD_CODE = 'import espnow\nimport network\nimport time\ne = espnow.ESPNow()\ne.active(True)\npeer = bytes.fromhex("206ef1497d7c")\ntry:\n e.add_peer(peer)\nexcept OSError:\n pass\ndef wire(c):\n for attempt in range(3):\n  if e.send(peer,b"cbdrive1:"+c.encode()):\n   return\n  time.sleep_ms(10)\n raise OSError("Receiver unavailable")\nconfirmed = False\nfor attempt in range(5):\n try:\n  wire("X")\n  ack = e.recv(150)\n  if ack[0] == peer and ack[1] == b"cbdrive1:ACK":\n   confirmed = True\n   break\n except OSError:\n  pass\n time.sleep_ms(20)\nif not confirmed:\n raise OSError("Receiver did not acknowledge stop")\nprint("WIRELESS HOLD CONTROL READY")\nimport ubinascii\ndef ota(raw):\n packet = bytes.fromhex(raw)\n e.send(peer,packet,False)\n start = time.ticks_ms()\n while time.ticks_diff(time.ticks_ms(),start)<280:\n  host,msg = e.recv(0)\n  if host==peer and msg and msg.startswith(b"CBU1"):\n   print("OTA",ubinascii.hexlify(msg).decode())\n   return\n  time.sleep_ms(2)\n print("OTA NONE")\n'
SETUP = 'exec(%r)\r\n' % BOARD_CODE

lock = threading.RLock()
ser = serial.Serial()
ser.port = PORT
ser.baudrate = 115200
ser.timeout = 0.1
ser.dtr = False                         # avoid resetting the board on open
ser.rts = False
ser.open()


def drain(label=""):
    data = ser.read(ser.in_waiting or 1)
    if data:
        print(label, data.decode(errors="replace").strip()[-300:])


def send(line):
    with lock:
        ser.write(line.encode() + b"\r\n")
        response = bytearray()
        until = time.monotonic() + 0.3
        while time.monotonic() < until:
            response.extend(ser.read(ser.in_waiting or 1))
            if response.endswith(b'>>> '):
                break
        if b'Traceback' in response or not response.endswith(b'>>> '):
            raise RuntimeError(response.decode(errors='replace'))


def init_board():
    time.sleep(2)                       # let any boot finish
    for _ in range(5):                  # interrupt boot.py app -> REPL
        ser.write(b"\x03")
        time.sleep(0.3)
    drain("after Ctrl-C:")
    ser.write(SETUP.encode())
    response = bytearray()
    until = time.monotonic()+8
    while time.monotonic()<until:
        response.extend(ser.read(ser.in_waiting or 1))
        if response.endswith(b'>>> '):
            break
    print(response.decode(errors='replace')[-400:], flush=True)
    if b'WIRELESS HOLD CONTROL READY\r\n' not in response or b'Traceback' in response:
        raise RuntimeError('Wireless setup failed')


PAGE = """<!doctype html><meta charset="utf-8"><meta name=viewport content="width=device-width,initial-scale=1">
<title>Wireless motor control</title>
<style>
body{font-family:system-ui;text-align:center;margin-top:40px}
.g{display:grid;grid-template-columns:repeat(3,90px);gap:10px;justify-content:center}
button{height:90px;font-size:28px;border-radius:12px;border:1px solid #888;background:#eee;touch-action:none;user-select:none}
button:active{background:#ccc}
.camera{max-width:800px;margin:20px auto}
video{width:100%;max-height:450px;background:#111;border-radius:12px;object-fit:contain}
.camera button{height:40px;font-size:16px;padding:0 16px}
select{max-width:300px;padding:10px}
</style>
<h2>Wireless motor control</h2>
<div class="camera">
<iframe src="http://localhost:8889/live/tank/?autoplay=true&muted=true&controls=false" title="Wireless DJI camera" tabindex="-1" style="width:100%;height:450px;border:0;border-radius:12px;background:#111;pointer-events:none"></iframe>
<p>Wireless DJI video · about 1 second behind. Use short taps while testing.</p>
</div>
<div class=g>
<span></span><button data-key="W">↑</button><span></span>
<button data-key="A">←</button><span></span><button data-key="D">→</button>
<span></span><button data-key="S">↓</button><span></span>
</div>
<p>Hold arrow keys or a button to drive. Release to stop. Escape = stop all.</p>
<div style="display:flex;gap:10px;justify-content:center;margin-top:20px">
<button data-key="Q" style="width:130px;font-size:18px">Up (1)</button>
<button data-key="F" style="width:130px;font-size:18px">Fire (Space)</button>
<button data-key="E" style="width:130px;font-size:18px">Down (2)</button>
</div>
<p>Hold Space to fire; release to reset. Hold 1/2 for launcher up/down.</p>
<p id="status">Stopped</p>
<script>
let wanted='X', fire=0, aim=0, busy=false, last='X|0|0';
const held=new Set();
const keyMap={ArrowUp:'W',ArrowLeft:'A',ArrowDown:'S',ArrowRight:'D','1':'Q','2':'E',' ':'F',Escape:'X'};
function state(){return wanted+'|'+fire+'|'+aim}
async function pump(){
 if(busy || (state()==='X|0|0' && last===state()))return;
 busy=true;
 const sent=state(), k=wanted, f=fire, a=aim;
 try{
  const r=await fetch('/control?c='+k+'&fire='+f+'&aim='+a+'&speed='+100,{cache:'no-store',signal:AbortSignal.timeout(700)});
  if(!r.ok)throw Error('Command failed');
  last=sent;
  document.querySelector('#status').textContent=[k==='X'?'':('Driving '+k),f?'Firing':'',a?'Moving launcher':''].filter(Boolean).join(' · ')||'Stopped';
 }catch(e){wanted='X';fire=0;aim=0;held.clear();document.querySelector('#status').textContent='Connection lost';}
 finally{busy=false;if(state()!==sent)pump();}
}
function update(){
 const keys=[...held];
 wanted=keys.filter(k=>'WASD'.includes(k)).at(-1)||'X';
 fire=held.has('F')?1:0;
 const q=keys.filter(k=>k==='Q'||k==='E').at(-1);
 aim=q==='Q'?-1:q==='E'?1:0;
 pump();
}
function stop(){held.clear();update()}
setInterval(pump,100);
addEventListener('keydown',e=>{
  const k=keyMap[e.key];
  if(!k)return;
  e.preventDefault();
  if(e.repeat)return;
  if(k==='X'){stop();return;}
  held.delete(k);held.add(k);update();
});
addEventListener('keyup',e=>{
 const k=keyMap[e.key];
 if(held.delete(k))update();
});
addEventListener('blur',stop);
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
document.querySelectorAll('button[data-key]').forEach(b=>{
 b.addEventListener('pointerdown',e=>{e.preventDefault();b.setPointerCapture(e.pointerId);held.add(b.dataset.key);update()});
 const release=()=>{held.delete(b.dataset.key);update()};
 b.addEventListener('pointerup',release);
 b.addEventListener('pointercancel',release);
 b.addEventListener('lostpointercapture',release);
});
</script>"""


vision_lock = threading.Lock()
vision_state = {'state': 'idle'}


def autonomous_drive(key):
    if key != 'X':
        paths = rover_vision.read_json('http://127.0.0.1:9997/v3/paths/list')['items']
        if not any(p['name'] == 'live/tank' and p['ready'] for p in paths):
            raise RuntimeError('Camera stream lost; autonomous turn cancelled')
    with lock:
        # Full-power pivots drive both tracks; approach retains reduced speed.
        # Keep launcher idle and stop before configuring the next movement.
        send("wire('X')")
        wireless_update.exchange(ser, b'L', wireless_update.secrets.token_bytes(4), bytes((0, 1, rover_autonomy.autonomous_speed(key))))
        send('wire(%r)' % key)


def autonomous_refresh(key):
    # Renew the receiver's 500 ms motor watchdog without stop/reconfiguration.
    with lock:
        send('wire(%r)' % key)


autonomy = rover_autonomy.NavigationController(rover_vision.assess, autonomous_drive, autonomous_refresh,
    planner=rover_fast_navigation.plan_goal, fast_observe=rover_fast_navigation.observe_goal)


def analyze_frame(goal):
    global vision_state
    try:
        result = rover_vision.assess(goal)
        with vision_lock:
            vision_state = {'state': 'done', 'result': result}
    except Exception as error:
        with vision_lock:
            vision_state = {'state': 'error', 'error': str(error)}


class Handler(BaseHTTPRequestHandler):
    def text_result(self, status, message):
        body = message.encode()
        self.send_response(status)
        self.send_header('Content-Type','text/plain; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global vision_state
        if self.headers.get('Origin') not in (None,'http://localhost:8000','http://127.0.0.1:8000'):
            self.send_error(403)
            return
        if urlparse(self.path).path in ('/autonomy/start', '/autonomy/stop', '/autonomy/heartbeat'):
            try:
                path = urlparse(self.path).path
                if path == '/autonomy/start':
                    paths = rover_vision.read_json('http://127.0.0.1:9997/v3/paths/list', timeout=1)['items']
                    if not any(p['name'] == 'live/tank' and p['ready'] for p in paths):
                        raise ValueError('Camera offline — restart the Mimo livestream')
                    with vision_lock:
                        if vision_state['state'] == 'running':
                            raise ValueError('Wait for the current analysis to finish')
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 4096:
                        raise ValueError('Invalid goal request')
                    goal = json.loads(self.rfile.read(length)).get('goal', '')
                    autonomy.start(goal)
                elif path == '/autonomy/stop':
                    autonomy.cancel()
                else:
                    autonomy.heartbeat()
                self.text_result(200, json.dumps(autonomy.snapshot()))
            except Exception as error:
                self.text_result(503, str(error))
            return
        if urlparse(self.path).path == '/vision/analyze':
            try:
                if autonomy.active():
                    raise ValueError('Stop autonomous control before manual analysis')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Invalid request size')
                goal = json.loads(self.rfile.read(length)).get('goal', '')
                if not isinstance(goal, str) or not goal.strip() or len(goal) > 1000:
                    raise ValueError('Enter a goal under 1000 characters')
                with vision_lock:
                    if vision_state['state'] == 'running':
                        self.text_result(409, 'Analysis already running')
                        return
                    vision_state = {'state': 'running', 'started_at': time.time()}
                threading.Thread(target=analyze_frame, args=(goal,), daemon=True).start()
                self.text_result(202, 'Analysis started')
            except Exception as error:
                self.text_result(400, str(error))
            return
        if self.headers.get('Content-Type')!='application/octet-stream':
            self.send_error(415)
            return
        path = urlparse(self.path).path
        if path not in ('/update','/rollback'):
            self.send_error(404)
            return
        autonomy.cancel('Stopped for application update')
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0<=length<=32768:
                raise ValueError('Invalid update size')
            source = self.rfile.read(length)
            with lock:
                if path=='/update':
                    version = wireless_update.update_app(ser,source)
                    message = 'Wireless update verified: '+version
                else:
                    message = 'Rolled back to: '+wireless_update.rollback(ser)
            self.text_result(200,message)
        except Exception as error:
            self.text_result(503,str(error))

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/camera/status':
            try:
                paths = rover_vision.read_json('http://127.0.0.1:9997/v3/paths/list', timeout=1)['items']
                live = any(p['name'] == 'live/tank' and p['ready'] for p in paths)
                self.text_result(200, json.dumps({'live': live}))
            except Exception:
                self.text_result(200, json.dumps({'live': False}))
            return
        if url.path == '/autonomy/status':
            self.text_result(200, json.dumps(autonomy.snapshot()))
            return
        if url.path == '/vision/input':
            self.text_result(200, json.dumps(rover_vision.input_snapshot()))
            return
        if url.path == '/vision/status':
            with vision_lock:
                body = json.dumps(vision_state)
            self.text_result(200, body)
            return
        if url.path == '/vision/frame':
            params = parse_qs(url.query)
            with vision_lock:
                filename = vision_state.get('result', {}).get('frame')
            if params.get('source') == ['autonomy']:
                filename = autonomy.snapshot().get('result', {}).get('frame')
            # Pin overlays to the analyzed image, even when the next result arrives.
            requested = params.get('file', [None])[0]
            if requested is not None:
                if not requested.startswith('frame-') or Path(requested).name != requested or not requested.endswith('.jpg'):
                    self.send_error(400)
                    return
                selected = Path(__file__).resolve().parent / 'vision-output' / requested
                if not selected.is_file():
                    self.send_error(404)
                    return
                filename = str(selected)
            if not filename:
                self.send_error(404)
                return
            body = Path(filename).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path=='/tank-status':
            try:
                with lock:
                    result = wireless_update.status(ser)
                self.text_result(200,result)
            except Exception as error:
                self.text_result(503,str(error))
            return
        if url.path in ('/control','/launcher','/launcher-status'):
            params = parse_qs(url.query)
            try:
                if url.path=='/launcher-status':
                    with lock:
                        result=wireless_update.exchange(ser,b'V',wireless_update.secrets.token_bytes(4)).decode()
                    self.text_result(200,result)
                    return
                if autonomy.active():
                    self.text_result(409, 'Autonomous goal running; use Stop to cancel')
                    return
                fire=int(params.get('fire',['0'])[0])
                aim=int(params.get('aim',['0'])[0])
                if fire not in (0,1) or aim not in (-1,0,1):
                    raise ValueError('Invalid launcher state')
                percent=int(params.get('speed',['100'])[0])
                if percent not in (40,100):
                    raise ValueError('Invalid driving speed')
                if url.path=='/control':
                    key=params.get('c',['X'])[0].upper()
                    if key not in MOVES:
                        raise ValueError('Invalid direction')
                with lock:
                    result=wireless_update.exchange(ser,b'L',wireless_update.secrets.token_bytes(4),bytes((fire,aim+1,percent))).decode()
                if url.path=='/control':
                    send('wire(%r)' % key)
                self.text_result(200,result)
            except Exception as error:
                self.text_result(503,str(error))
            return
        if url.path == "/cmd":
            if autonomy.active():
                self.text_result(409, 'Autonomous goal running; use Stop to cancel')
                return
            key = parse_qs(url.query).get("c", [""])[0].upper()
            if key in MOVES:
                try:
                    send("wire(%r)" % key)
                except Exception as error:
                    print(error, flush=True)
                    self.send_error(503, "Wireless command failed")
                    return
            else:
                self.send_error(400, "Unknown direction")
                return
            self.send_response(204)
            self.end_headers()
            return
        body = Path(__file__).with_name('rover_dashboard.html').read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    init_board()
    print("Open http://localhost:8000  (Ctrl-C to quit)")
    try:
        HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
    finally:
        try:
            send("wire('X')")
            with lock:
                wireless_update.exchange(ser,b'L',wireless_update.secrets.token_bytes(4),bytes((0,1)))
        finally:
            ser.close()
