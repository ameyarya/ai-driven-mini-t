"""One-time USB installation; only the identified Mini-T receiver is modified."""
import ast
import secrets
import time
from pathlib import Path
import serial

ROOT = Path(__file__).parent
secret_path = ROOT/'.tank_update.key'
if not secret_path.exists():
    secret_path.write_bytes(secrets.token_bytes(32))
    secret_path.chmod(0o600)
s = serial.Serial()
s.port = '/dev/cu.usbmodem1101'
s.baudrate = 115200
s.timeout = 0.05
s.dtr = False
s.rts = False
s.open()

def command(source, timeout=8, check=True):
    s.write((source+'\r\n').encode())
    data = bytearray()
    until = time.monotonic()+timeout
    while time.monotonic()<until:
        data.extend(s.read(s.in_waiting or 1))
        if data.endswith(b'>>> '):
            break
    if check and (b'Traceback' in data or not data.endswith(b'>>> ')):
        raise RuntimeError('Receiver USB command failed')
    return data

def result(source):
    output = command("print('RESULT',repr(%s))" % source)
    for line in output.decode().splitlines():
        if line.startswith('RESULT '):
            return ast.literal_eval(line[7:])
    raise RuntimeError('No board result')

def upload(path, data):
    command("f=open(%r,'wb')" % path)
    for offset in range(0,len(data),128):
        command('f.write(bytes.fromhex(%r))' % data[offset:offset+128].hex())
    command('f.close()')
    import hashlib
    actual = result("__import__('hashlib').sha256(open(%r,'rb').read()).digest()" % path)
    if actual!=hashlib.sha256(data).digest():
        raise RuntimeError('Uploaded file checksum mismatch')
    print('Installed and verified',path,flush=True)

try:
    time.sleep(2)
    for _ in range(30):
        s.write(b'\x03')
        time.sleep(0.3)
        data = s.read(s.in_waiting or 1)
        if data.endswith(b'>>> '):
            break
    command('import os,network')
    if result("network.WLAN(network.STA_IF).config('mac')")!=bytes.fromhex('206ef1497d7c'):
        raise RuntimeError('Wrong board; no receiver files changed')
    # Preserve the already working wireless startup and receiver code too.
    backup = ROOT/'tank-backup-206ef1497d7c'/'before-wireless-updates'
    backup.mkdir(parents=True,exist_ok=True)
    for name in ('boot.py','tank_receiver.py'):
        if not (backup/name).exists():
            content = result('open(%r,"rb").read()' % name)
            (backup/name).write_bytes(content)
    upload('tank_update.key',secret_path.read_bytes())
    upload('tank_app.py',(ROOT/'tank_app.py').read_bytes())
    upload('tank_wireless_service.py',(ROOT/'tank_wireless_service.py').read_bytes())
    boot = b"import rc_module\nrc_module.rc_slave_init()\nexec(open('tank_wireless_service.py').read(), globals())\n"
    upload('boot.py',boot)
    output = command('import machine; machine.reset()',timeout=10,check=False)
    print(output.decode(errors='replace')[-600:],flush=True)
    if b'WIRELESS UPDATE SERVICE READY' not in output or b'Traceback' in output:
        raise RuntimeError('Update service failed to start')
finally:
    s.close()
