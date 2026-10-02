"""Mini-T driving, disc launcher, and turret control."""
import time
import __main__ as receiver

VERSION = '2.1.1'
SPEED = 1024
LEFT_SPEED = 840  # Motor 2 drives the left track.
FIRE_ANGLE = 150
RESET_ANGLE = 86
TURRET_SPEED = 45

class TankApp:
    def __init__(self):
        self.version = VERSION
        self.drive_percent = 100
        self.servos = None
        self.firing = False
        self.aim = 0
        self.aux_deadline = time.ticks_ms()
        self.moves = {
            b'W': (SPEED, -LEFT_SPEED), b'S': (-SPEED, LEFT_SPEED),
            b'A': (SPEED, SPEED), b'D': (-SPEED, -SPEED),
            b'X': (0, 0),
        }

    def command(self, key):
        # Validation calls this before activation, so it must not touch hardware
        # or register extensions until this is the active confirmed app.
        if getattr(receiver,'app',None) is self and getattr(receiver,'candidate_id',None) is None:
            self.register_extensions()
        values = self.moves.get(key, (0, 0))
        return tuple(int(v*self.drive_percent/100) for v in values)

    def register_extensions(self):
        # Compatibility adapter for the already installed wireless service.
        # Leave its update, rollback, and motor watchdog handlers intact.
        if hasattr(receiver,'_base_update_handler'):
            return
        receiver._base_update_handler = receiver.handle_update

        def dispatch(packet):
            body = packet[:-16]
            if len(packet)<25 or receiver.tag(body)!=packet[-16:]:
                return
            kind, ident, payload = body[4:5], body[5:9], body[9:]
            active = receiver.app
            if kind in (b'B',b'R',b'Z'):
                reset = getattr(active,'reset_aux',None)
                if reset is not None:
                    reset()
            if kind in (b'L',b'V'):
                try:
                    if receiver.upload is not None or receiver.candidate_id is not None:
                        raise ValueError('Application update in progress')
                    action = getattr(active,'extension',None)
                    if action is None:
                        raise ValueError('Launcher not installed')
                    receiver.reply(kind,ident,action(kind,payload))
                except Exception as error:
                    reset = getattr(active,'reset_aux',None)
                    if reset is not None:
                        reset()
                    receiver.reply(b'E',ident,str(error).encode()[:100])
            else:
                receiver._base_update_handler(packet)

        receiver.handle_update = dispatch

    def ensure_servos(self):
        if self.servos is not None:
            return
        from servos import ServosController
        from machine import Timer
        self.servos = ServosController()
        self.servos.set_angle(2,RESET_ANGLE)
        self.servos.set_speed(1,0)

        def aux_watchdog(timer):
            active = receiver.app
            watchdog = getattr(active,'check_aux_timeout',None)
            if watchdog is not None:
                watchdog()

        receiver._aux_timer = Timer(1)
        receiver._aux_timer.init(period=50,mode=Timer.PERIODIC,callback=aux_watchdog)

    def reset_aux(self):
        if self.servos is not None:
            if self.firing:
                self.servos.set_angle(2,RESET_ANGLE)
            if self.aim:
                self.servos.set_speed(1,0)
        self.firing = False
        self.aim = 0

    def check_aux_timeout(self):
        if (self.firing or self.aim) and time.ticks_diff(time.ticks_ms(),self.aux_deadline)>=0:
            self.reset_aux()

    def aux_status(self):
        angle = FIRE_ANGLE if self.firing else RESET_ANGLE
        if self.servos is None:
            return ('%d|0|off|off' % angle).encode()
        return ('%d|%d' % (angle,self.aim)).encode()

    def extension(self,kind,payload):
        if kind==b'V':
            return self.aux_status()
        if len(payload) not in (2,3) or payload[0] not in (0,1) or payload[1] not in (0,1,2):
            raise ValueError('Invalid launcher command')
        percent = payload[2] if len(payload)==3 else 100
        if percent not in (40,100):
            raise ValueError('Invalid driving speed')
        self.drive_percent = percent
        self.ensure_servos()
        firing, aim = bool(payload[0]),payload[1]-1
        self.aux_deadline = time.ticks_add(time.ticks_ms(),500)
        if firing!=self.firing:
            self.servos.set_angle(2,FIRE_ANGLE if firing else RESET_ANGLE)
        if aim!=self.aim:
            self.servos.set_speed(1,aim*TURRET_SPEED)
        self.firing, self.aim = firing,aim
        return self.aux_status()
