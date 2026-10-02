"""Stable ESP-NOW motor watchdog and authenticated application updater."""
import sys
import os
import time
import struct
import hashlib
import espnow
from machine import Timer
sys.path.append('/bbl')
from motors import MotorsController

TRANSMITTER = bytes.fromhex('206ef1450f1c')
SECRET = open('tank_update.key', 'rb').read()
PREFIX = b'CBU1'
DRIVE = b'cbdrive1:'
APP = 'tank_app.py'
PREVIOUS = 'tank_app.previous.py'
STAGING = 'tank_app.next.py'
TRIAL = 'tank_app.trial'
MAX_SIZE = 32768
m = MotorsController()
motor_update = getattr(m, 'motors_period_cb', lambda: None)
running = False
deadline = time.ticks_ms()
upload = None
candidate_id = None
last_commit = None
last_confirm = None

def stop():
    global running
    m.stop(1)
    m.stop(2)
    running = False

stop()

def exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def copy_file(source, dest):
    with open(source, 'rb') as src, open(dest, 'wb') as dst:
        while True:
            chunk = src.read(256)
            if not chunk:
                break
            dst.write(chunk)

def tag(body):
    key = SECRET + b'\x00' * (64-len(SECRET))
    inner = bytes(x ^ 0x36 for x in key)
    outer = bytes(x ^ 0x5c for x in key)
    return hashlib.sha256(outer + hashlib.sha256(inner + body).digest()).digest()[:16]

def load_app(source):
    namespace = {'__name__': 'tank_motor_app'}
    exec(source, namespace)
    result = namespace['TankApp']()
    if not isinstance(result.version, str) or len(result.version)>48:
        raise ValueError('Invalid application version')
    for key in (b'W', b'A', b'S', b'D', b'X'):
        values = result.command(key)
        if len(values)!=2 or any(not isinstance(x,int) or abs(x)>2048 for x in values):
            raise ValueError('Invalid motor mapping')
        if key==b'X' and values!=(0,0):
            raise ValueError('Stop must stop both motors')
    return result

def rollback():
    stop()
    if exists(PREVIOUS):
        copy_file(PREVIOUS, APP)
    if exists(TRIAL):
        os.remove(TRIAL)

# A power interruption or reset before confirmation restores the old app.
if exists(TRIAL):
    rollback()
try:
    app = load_app(open(APP).read())
except Exception:
    rollback()
    app = load_app(open(APP).read())

def tick(timer):
    if running and time.ticks_diff(time.ticks_ms(), deadline)>=0:
        stop()
    motor_update()

e = espnow.ESPNow()
e.active(True)
try:
    e.add_peer(TRANSMITTER)
except OSError:
    pass
timer = Timer(0)
timer.init(period=1, mode=Timer.PERIODIC, callback=tick)

def reply(kind, ident, payload=b''):
    body = PREFIX + kind + ident + payload
    e.send(TRANSMITTER, body + tag(body), False)

def abort_upload():
    global upload
    stop()
    if upload is not None:
        upload['file'].close()
        upload = None

def handle_update(packet):
    global upload, app, candidate_id, last_commit, last_confirm
    if len(packet)<25 or not packet.startswith(PREFIX):
        return
    body, signature = packet[:-16], packet[-16:]
    if tag(body)!=signature:
        return
    kind, ident, data = body[4:5], body[5:9], body[9:]
    try:
        if kind==b'P':
            reply(b'P', ident, app.version.encode()+b'|'+str(int(running)).encode())
        elif kind==b'B':
            stop()
            if candidate_id is not None:
                raise ValueError('Confirm or rollback pending app first')
            if len(data)!=36:
                raise ValueError('Invalid manifest')
            size = struct.unpack('>I', data[:4])[0]
            if not 0<size<=MAX_SIZE:
                raise ValueError('App too large')
            if upload is not None and upload['id']==ident:
                upload['last'] = time.ticks_ms()
            else:
                abort_upload()
                upload = {'id':ident, 'size':size, 'hash':data[4:], 'offset':0,
                          'last':time.ticks_ms(), 'file':open(STAGING,'wb')}
            reply(b'A', ident, struct.pack('>I',upload['offset']))
        elif kind==b'D':
            if upload is None or upload['id']!=ident or len(data)<5:
                raise ValueError('No matching upload')
            offset = struct.unpack('>I', data[:4])[0]
            chunk = data[4:]
            upload['last'] = time.ticks_ms()
            if offset==upload['offset']:
                if offset+len(chunk)>upload['size']:
                    raise ValueError('Upload exceeds manifest')
                upload['file'].write(chunk)
                upload['offset'] += len(chunk)
            elif offset+len(chunk)!=upload['offset']:
                raise ValueError('Wrong chunk offset')
            reply(b'A',ident,struct.pack('>I',upload['offset']))
        elif kind==b'F':
            stop()
            if ident==last_commit:
                reply(b'F',ident,app.version.encode())
                return
            if upload is None or upload['id']!=ident:
                raise ValueError('No matching upload')
            state = upload
            upload = None
            state['file'].close()
            if state['offset']!=state['size']:
                raise ValueError('Incomplete upload')
            source = open(STAGING,'rb').read()
            if hashlib.sha256(source).digest()!=state['hash']:
                raise ValueError('Hash mismatch')
            candidate = load_app(source.decode())
            copy_file(APP, PREVIOUS)
            with open(TRIAL,'wb') as marker:
                marker.write(ident)
            copy_file(STAGING, APP)
            app = candidate
            candidate_id = ident
            last_commit = ident
            reply(b'F',ident,app.version.encode())
        elif kind==b'G':
            if ident==last_confirm:
                reply(b'G',ident,app.version.encode())
                return
            if candidate_id!=ident:
                raise ValueError('No matching candidate')
            os.remove(TRIAL)
            candidate_id = None
            last_confirm = ident
            reply(b'G',ident,app.version.encode())
        elif kind==b'R':
            abort_upload()
            rollback()
            app = load_app(open(APP).read())
            candidate_id = None
            last_commit = None
            last_confirm = None
            reply(b'R',ident,app.version.encode())
        elif kind==b'Z':
            abort_upload()
            if candidate_id==ident:
                rollback()
                app = load_app(open(APP).read())
                candidate_id = None
                last_commit = None
            reply(b'Z',ident)
    except Exception as error:
        stop()
        if kind==b'F' and exists(TRIAL):
            rollback()
            app = load_app(open(APP).read())
            candidate_id = None
            last_commit = None
        reply(b'E',ident,str(error).encode()[:100])

print('WIRELESS UPDATE SERVICE READY', app.version)
try:
    while True:
        host, packet = e.recv(0)
        if host==TRANSMITTER and packet:
            if packet.startswith(PREFIX):
                handle_update(packet)
            elif packet.startswith(DRIVE) and upload is None and candidate_id is None:
                key = packet[len(DRIVE):]
                if key in (b'W',b'A',b'S',b'D',b'X'):
                    try:
                        a,b = app.command(key)
                        if any(not isinstance(x,int) or abs(x)>2048 for x in (a,b)):
                            raise ValueError('Invalid motor speed')
                        deadline = time.ticks_add(time.ticks_ms(),500)
                        if key==b'X':
                            stop()
                            e.send(TRANSMITTER,DRIVE+b'ACK',False)
                        else:
                            m.set_speed(1,a)
                            m.set_speed(2,b)
                            running = bool(a or b)
                    except Exception:
                        stop()
                        rollback()
                        app = load_app(open(APP).read())
            elif packet==DRIVE+b'X':
                stop()
                e.send(TRANSMITTER,DRIVE+b'ACK',False)
        if upload is not None and time.ticks_diff(time.ticks_ms(),upload['last'])>3000:
            abort_upload()
        time.sleep_ms(2)
finally:
    abort_upload()
    timer.deinit()
