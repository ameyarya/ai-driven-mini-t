"""Record launcher up/down and contact truth, independent of Qwen and hardware."""
import json
import subprocess
from record_demo import RecordedSim, ROOT


def main():
    output=ROOT/'docs/assets/rook-launcher-simulation.mp4'
    sim=RecordedSim(output)
    try:
        sim.title='Rook | Launcher up/down and projectile trajectory'
        sim.reset()
        sim.next_frame=sim.data.time
        sim.action='Launcher level: 0 degrees'
        sim.hold(1)
        sim.action='UP: raise launcher to 30 degrees'
        sim.launcher('up',1000);sim.hold(1)
        sim.action='FIRE at 30 degrees: trajectory changes'
        raised=sim.fire();sim.hold(1)
        sim.action='Simulated MISS at 30 degrees (MuJoCo contact truth)';sim.hold(1)
        sim.action='DOWN: lower launcher to 0 degrees'
        sim.launcher('down',1000);sim.hold(1)
        sim.action='FIRE at 0 degrees'
        level=sim.fire();sim.hold(1)
        sim.action='Simulated contact HIT after lowering; not physical calibration';sim.hold(2)
        if raised['contact_hit'] or not level['contact_hit']:
            raise RuntimeError('Expected raised miss and level hit')
        report=dict(backend='scripted manual launcher demo; no Qwen',shots=sim.shots,
                    fps=10,frames=sim.frames,simulation_only=True,
                    limits_degrees=[sim.MIN_ELEVATION,sim.MAX_ELEVATION],
                    illustrative_rate_degrees_per_second=sim.ELEVATION_RATE)
        output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:sim.finish()
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(output),
                    '-filter_complex','fps=6,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',
                    '-loop','0',str(output.with_suffix('.gif'))],check=True)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
