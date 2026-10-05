"""Local MuJoCo playground. Single thread keeps OpenGL on its creating thread."""
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import uuid
from pathlib import Path
from rover_sim import RoverSim, ROOT, navigation


def benchmark_busy():
    directory=ROOT/'playground-data/full-comparison'
    if not (directory/'summary.json').exists():return False
    summary=json.loads((directory/'summary.json').read_text())
    total=json.loads((directory/'specification.json').read_text())['total_calls']
    return sum(v['completed'] for v in summary.values())<total


def serve(port=8002):
    sim=RoverSim()
    class Handler(BaseHTTPRequestHandler):
        def reply(self,code,body,kind='application/json'):
            if isinstance(body,(dict,list)):body=json.dumps(body).encode()
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            path=self.path.split('?')[0]
            if path=='/':self.reply(200,Path(__file__).with_name('index.html').read_bytes(),'text/html; charset=utf-8')
            elif path in ('/camera.jpg','/labeled.jpg'):
                self.reply(200,sim.image(path=='/labeled.jpg'),'image/jpeg')
            elif path=='/overview.jpg':self.reply(200,sim.overview(),'image/jpeg')
            elif path=='/status':
                _,_,measurement=sim.observation()
                self.reply(200,dict(status=sim.status,running=sim.plan is not None,shots=sim.shots,
                    measurement=measurement,benchmark_busy=benchmark_busy(),steps=len(sim.history),
                    launcher_elevation=sim.elevation,launcher_limits=[sim.MIN_ELEVATION,sim.MAX_ELEVATION],
                    obstacles=sim.obstacle_state()))
            else:self.reply(404,{'error':'Unknown endpoint'})

        def do_POST(self):
            if self.headers.get('Origin') not in (None,f'http://localhost:{port}',f'http://127.0.0.1:{port}'):
                self.reply(403,{'error':'Invalid origin'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if self.headers.get('Content-Type')!='application/json' or not 0<length<=4096:
                    raise ValueError('JSON request required, at most 4096 bytes')
                body=json.loads(self.rfile.read(length))
                if self.path=='/reset':sim.reset(float(body.get('distance',.65)),float(body.get('lateral',0)),
                    obstacle_scene=body.get('obstacle_scene','clear'))
                elif self.path=='/avoid':sim.start_avoidance()
                elif self.path=='/move':
                    sim.plan=None;sim.move(body['action'],body.get('duration_ms',250))
                elif self.path=='/launcher':
                    sim.plan=None;sim.launcher(body['action'],body.get('duration_ms',250))
                    sim.status=f'Launcher {sim.elevation:.1f} degrees (simulated)'
                elif self.path=='/fire':
                    sim.plan=None;shot=sim.fire();sim.status='Contact HIT' if shot['contact_hit'] else 'MISS'
                elif self.path=='/stop':sim.plan=None;sim.status='Stopped by user'
                elif self.path=='/step':sim.step_goal()
                elif self.path=='/goal':
                    goal=body.get('goal','')
                    if not isinstance(goal,str) or not goal.strip() or len(goal)>1000:raise ValueError('Enter a goal')
                    backend=body.get('backend','scripted')
                    _,_,measurement=sim.observation()
                    image=sim.image(True)
                    if backend=='scripted':
                        if not re.search(r'\bcan\b',goal,re.I):
                            raise ValueError('Controller preview supports explicitly named can targets only')
                        requested=navigation.vision.requested_height(goal)
                        searching=navigation.search_goal(goal);shooting=navigation.shooting_goal(goal)
                        if shooting:mode=('find_approach_shoot' if searching else 'approach_shoot') if requested else ('find_shoot' if searching else 'shoot')
                        else:mode=('find_approach_size' if searching else 'approach_size') if requested else ('find' if searching else 'center')
                        plan=dict(mode=mode,target='red can',height_percent=requested or 0,reason='Scripted contract preview; Qwen not called',uncertainties=[])
                    elif backend=='ollama':
                        if benchmark_busy():raise ValueError('Wait for the all-frame GPU benchmark to finish before Qwen inference')
                        request=navigation.planner_request(goal,image,measurement)
                        response=navigation.vision.read_json('http://127.0.0.1:11434/api/chat',request,timeout=120)
                        if response.get('done_reason')=='length':raise ValueError('Planner output truncated')
                        plan=json.loads(response['message']['content'])
                        out=ROOT/'playground-data/simulation'/uuid.uuid4().hex;out.mkdir(parents=True)
                        (out/'input.jpg').write_bytes(image)
                        (out/'planner.json').write_text(json.dumps(dict(goal=goal,request=request,response=response),indent=2))
                    else:raise ValueError('Unknown planner backend')
                    navigation.validate_plan(plan,goal)
                    sim.goal=goal;sim.plan=plan;sim.history=[];sim.status='Mission started ('+backend+')'
                else:raise ValueError('Unknown action')
                self.reply(200,{'status':sim.status})
            except Exception as error:self.reply(400,{'error':str(error)})
    server=HTTPServer(('127.0.0.1',port),Handler)
    print(f'MuJoCo playground http://localhost:{port} — no hardware access',flush=True)
    try:server.serve_forever()
    finally:sim.close();server.server_close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8002)
    serve(parser.parse_args().port)
