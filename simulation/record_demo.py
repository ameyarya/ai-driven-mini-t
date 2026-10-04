"""Record a fresh scripted simulation mission; never accesses physical hardware."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import mujoco
from PIL import Image, ImageDraw, ImageFont
from rover_sim import RoverSim, ROOT


class RecordedSim(RoverSim):
    def __init__(self, output):
        self.recording = False
        super().__init__()
        self.output = output
        self.action = 'Ready'
        self.title = 'Rook | Find, align, approach, shoot'
        self.frames = 0
        self.next_frame = 0
        self.encoder = subprocess.Popen([
            'ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt',
            'rgb24', '-s', '1280x480', '-r', '10', '-i', '-', '-an',
            '-c:v', 'libx264', '-crf', '23', '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart', str(output)], stdin=subprocess.PIPE)
        self.overview = mujoco.MjvCamera()
        self.overview.lookat[:] = [.45, 0, .03]
        self.overview.distance = 1.6
        self.overview.azimuth = 150
        self.overview.elevation = -65
        self.font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 20)
        self.recording = True

    def capture(self):
        _, labeled, measurement = self.observation()
        self.renderer.update_scene(self.data, camera=self.overview)
        external = Image.fromarray(self.renderer.render().copy())
        frame = Image.new('RGB', (1280, 480), '#101820')
        frame.paste(labeled, (0, 65))
        frame.paste(external, (640, 65))
        draw = ImageDraw.Draw(frame)
        draw.text((16, 8), self.title, font=self.font, fill='white')
        draw.text((16, 36), 'Tank camera + segmentation oracle', font=self.font, fill='#a8dbba')
        draw.text((656, 36), 'External simulation view', font=self.font, fill='#a8dbba')
        draw.text((16, 432), self.action[:105], font=self.font, fill='white')
        draw.text((16, 457), 'SCRIPTED CONTROLLER | No Qwen call | Uncalibrated physics | Simulation only', fill='#a8dbba')
        self.encoder.stdin.write(frame.tobytes())
        self.frames += 1
        return measurement

    def hold(self, seconds):
        for _ in range(round(seconds * 10)):
            self.capture()

    def advance(self, seconds):
        if not self.recording:
            return super().advance(seconds)
        for _ in range(round(seconds / self.model.opt.timestep)):
            super().advance(self.model.opt.timestep)
            if self.data.time >= self.next_frame:
                self.capture()
                self.next_frame = self.data.time + .1

    def finish(self):
        self.encoder.stdin.close()
        if self.encoder.wait() != 0:
            raise RuntimeError('Video encoder failed')
        self.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'docs/assets/rook-simulation.mp4')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sim = RecordedSim(args.output)
    try:
        sim.reset(distance=.8, lateral=.15, heading=3)
        sim.next_frame = sim.data.time
        sim.goal = 'Find the red can, approach until 50% of image height, then shoot once.'
        sim.plan = dict(mode='find_approach_shoot', target='red can', height_percent=50,
                        reason='Scripted controller demonstration', uncertainties=[])
        sim.action = 'Goal: search in place, approach to 50% image height, fire once'
        sim.hold(1.5)
        decisions = []
        for step in range(80):
            if not sim.plan:
                break
            _, _, measurement = sim.observation()
            import rover_fast_navigation as navigation
            decision = navigation.control_decision(sim.plan, measurement, sim.history)
            sim.action = f"Step {step+1}: {decision['suggested_action'].upper()} | {decision.get('duration_ms', 0)} ms"
            sim.hold(.4)
            decisions.append(sim.step_goal())
        sim.action = sim.status + ' | One simulated shot; contact checked by MuJoCo'
        sim.hold(2)
        if sim.plan or len(sim.shots) != 1 or not sim.shots[0]['contact_hit']:
            raise RuntimeError('Demo mission did not complete with one contact hit')
        report = dict(backend='scripted; no Qwen inference', fresh_recording=True,
                      initial_scene=dict(distance=.8, lateral=.15, heading=3),
                      goal=sim.goal, status=sim.status, shots=sim.shots,
                      steps=len(decisions), frames=sim.frames, fps=10,
                      limitations=['Segmentation oracle', 'Uncalibrated kinematic tracks and launcher',
                                   'Not a recording of historical benchmark runs'])
        args.output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    finally:
        sim.finish()
    gif = args.output.with_suffix('.gif')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(args.output),
                    '-filter_complex', 'fps=6,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',
                    '-loop', '0', str(gif)], check=True)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
