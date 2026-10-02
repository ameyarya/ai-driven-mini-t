"""Upload tank_app.py through the running localhost transmitter server."""
import argparse
import hashlib
import hmac
import secrets
import struct
import time
from pathlib import Path
from urllib.request import Request, urlopen

KEY_PATH = Path(__file__).with_name('.tank_update.key')
PREFIX = b'CBU1'

def exchange(ser, kind, ident, payload=b''):
    secret = KEY_PATH.read_bytes()
    body = PREFIX + kind + ident + payload
    packet = body + hmac.new(secret,body,hashlib.sha256).digest()[:16]
    for attempt in range(5):
        ser.write(('ota(%r)\r\n' % packet.hex()).encode())
        response = bytearray()
        end = time.monotonic()+1
        while time.monotonic()<end:
            response.extend(ser.read(ser.in_waiting or 1))
            if response.endswith(b'>>> '):
                break
        if b'Traceback' in response:
            raise RuntimeError('Transmitter rejected the update packet')
        for line in response.decode(errors='replace').splitlines():
            if not line.startswith('OTA ') or line=='OTA NONE':
                continue
            reply = bytes.fromhex(line[4:])
            if len(reply)<25:
                continue
            signed = reply[:-16]
            if not hmac.compare_digest(reply[-16:],hmac.new(secret,signed,hashlib.sha256).digest()[:16]):
                continue
            if signed[:4]!=PREFIX or signed[5:9]!=ident:
                continue
            result_kind, result = signed[4:5],signed[9:]
            if result_kind==b'E':
                raise RuntimeError('Receiver: '+result.decode(errors='replace'))
            expected = b'A' if kind in (b'B',b'D') else kind
            if result_kind==expected:
                return result
    raise TimeoutError('Tank did not acknowledge the wireless packet')

def status(ser):
    return exchange(ser,b'P',secrets.token_bytes(4)).decode()

def rollback(ser):
    return exchange(ser,b'R',secrets.token_bytes(4)).decode()

def update_app(ser, source):
    if not 0<len(source)<=32768:
        raise ValueError('App must contain 1–32768 bytes')
    compile(source,'tank_app.py','exec')
    ident = secrets.token_bytes(4)
    offset = 0
    try:
        result = exchange(ser,b'B',ident,struct.pack('>I',len(source))+hashlib.sha256(source).digest())
        if struct.unpack('>I',result)[0]!=0:
            raise RuntimeError('Unexpected initial upload offset')
        while offset<len(source):
            chunk = source[offset:offset+160]
            result = exchange(ser,b'D',ident,struct.pack('>I',offset)+chunk)
            offset += len(chunk)
            if struct.unpack('>I',result)[0]!=offset:
                raise RuntimeError('Receiver upload offset mismatch')
        version = exchange(ser,b'F',ident).decode()
        reported = status(ser)
        if reported!=version+'|0':
            raise RuntimeError('Updated app failed its stopped-state check')
        exchange(ser,b'G',ident)
        return version
    except Exception:
        # Abort also rolls back this transfer's unconfirmed candidate, but
        # never rolls back an unrelated, previously confirmed application.
        try:
            exchange(ser,b'Z',ident)
        except Exception:
            pass
        raise

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',nargs='?',type=Path)
    parser.add_argument('--status',action='store_true')
    parser.add_argument('--rollback',action='store_true')
    args = parser.parse_args()
    if args.status:
        request = Request('http://localhost:8000/tank-status')
    elif args.rollback:
        request = Request('http://localhost:8000/rollback',data=b'',method='POST',headers={'Content-Type':'application/octet-stream'})
    elif args.source:
        request = Request('http://localhost:8000/update',data=args.source.read_bytes(),method='POST',headers={'Content-Type':'application/octet-stream'})
    else:
        parser.error('Provide a Python source file, --status, or --rollback')
    with urlopen(request,timeout=120) as response:
        print(response.read().decode())
