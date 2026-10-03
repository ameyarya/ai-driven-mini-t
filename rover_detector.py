"""Local persistent detector and numeric image labeling; no motor control."""
import argparse
import json
import hashlib
from pathlib import Path
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parent


def target_description(goal):
    # The current POC target. Other descriptions are passed through, not silently
    # replaced with the can; their detection quality has not been validated.
    import re
    return 'red soda can' if re.search(r'\bcan\b|coca.?cola', goal, re.I) else goal


def progress(measurement, history):
    if not history:
        return None
    previous = history[-1]
    x, old_x = measurement.get('target_x'), previous.get('target_x_before')
    height, old_height = measurement.get('target_height'), previous.get('target_height_before')
    return {'action': previous.get('action'), 'duration_ms': previous.get('duration_ms'),
            'center_before_percent': old_x, 'center_after_percent': x,
            'center_change_percent': round(x-old_x, 2) if isinstance(x, (int, float)) and isinstance(old_x, (int, float)) else None,
            'height_before_percent': old_height, 'height_after_percent': height,
            'height_change_percent': round(height-old_height, 2) if isinstance(height, (int, float)) and isinstance(old_height, (int, float)) else None}


class Detector:
    def __init__(self, weights, device):
        import torch
        from ultralytics import YOLOWorld
        self.torch = torch
        self.device = device
        self.model = YOLOWorld(weights)
        self.description = 'red soda can'
        self.model.set_classes([self.description])
        import numpy as np
        self.model.predict(np.zeros((360,640,3),dtype=np.uint8),device=device,imgsz=640,conf=.10,verbose=False)
        if device == 'mps':
            self.torch.mps.synchronize()

    def prepare(self, frame, goal, history):
        import cv2
        description = target_description(goal)
        if description != self.description:
            self.model.set_classes([description])
            self.description = description
        start = time.perf_counter()
        prediction = self.model.predict(str(frame), device=self.device, imgsz=640, conf=.10, verbose=False)[0]
        if self.device == 'mps':
            self.torch.mps.synchronize()
        candidates = []
        h, w = prediction.orig_shape
        for box in prediction.boxes:
            xy = box.xyxy[0].cpu().tolist()
            candidates.append({'confidence': round(float(box.conf[0]), 4),
                               'bbox': [round(xy[0]/w*1000), round(xy[1]/h*1000), round(xy[2]/w*1000), round(xy[3]/h*1000)]})
        candidates.sort(key=lambda c: c['confidence'], reverse=True)
        # Several separate candidates cannot establish target identity.
        selected = candidates[0] if len(candidates) == 1 else None
        bbox = selected['bbox'] if selected else None
        measurement = {'source': 'YOLO-World', 'target_description': description,
                       'target_visible': selected is not None, 'target_bbox': bbox,
                       'target_confidence': selected['confidence'] if selected else None,
                       'candidate_count': len(candidates), 'candidates': candidates,
                       'target_x': (bbox[0]+bbox[2])/20 if bbox else None,
                       'target_height': (bbox[3]-bbox[1])/10 if bbox else None,
                       'target_clipped': bool(bbox and (bbox[0]<=3 or bbox[1]<=6 or bbox[2]>=997 or bbox[3]>=994)),
                       'detector_ms': round((time.perf_counter()-start)*1000, 1)}
        feedback = progress(measurement, history)
        image = cv2.imread(str(frame))
        if image is None:
            raise ValueError('Cannot read captured frame')
        grid = image.copy()
        for i in range(1, 10):
            cv2.line(grid,(w*i//10,0),(w*i//10,h),(230,230,230),1)
            cv2.line(grid,(0,h*i//10),(w,h*i//10),(230,230,230),1)
        image = cv2.addWeighted(grid,.22,image,.78,0)
        cv2.line(image,(w//2,0),(w//2,h),(255,255,255),1)
        cv2.drawMarker(image,(w//2,h//2),(255,255,255),cv2.MARKER_CROSS,22,1)
        for i in range(1,10):
            cv2.putText(image,str(i*10)+'%',(w*i//10+2,h-5),cv2.FONT_HERSHEY_SIMPLEX,.30,(255,255,255),1,cv2.LINE_AA)
        trail = [entry['target_x_before'] for entry in history if isinstance(entry.get('target_x_before'),(int,float))]
        if bbox:
            x1,y1,x2,y2=[round(bbox[0]*w/1000),round(bbox[1]*h/1000),round(bbox[2]*w/1000),round(bbox[3]*h/1000)]
            cv2.rectangle(image,(x1,y1),(x2,y2),(100,240,150),2)
            center=(round(measurement['target_x']*w/100),(y1+y2)//2)
            cv2.circle(image,center,4,(100,240,150),-1)
            cv2.line(image,(w//2,center[1]),center,(100,240,150),1)
            trail.append(measurement['target_x'])
        for old,new in zip(trail,trail[1:]):
            cv2.line(image,(round(old*w/100),h//2),(round(new*w/100),h//2),(90,200,240),2)
        labels=['SOURCE IMAGE: width/height normalized 0-100%; center=50%']
        if bbox:
            labels += [f"TARGET x={measurement['target_x']:.1f}% offset={measurement['target_x']-50:+.1f}%",
                       f"HEIGHT={measurement['target_height']:.1f}% score={measurement['target_confidence']:.2f} clipped={measurement['target_clipped']}"]
        else:
            labels += ['TARGET NOT LOCATED' if not candidates else 'AMBIGUOUS TARGETS: '+str(len(candidates))]
        if feedback:
            labels += [f"LAST {feedback['action']} {feedback['duration_ms']}ms dx={feedback['center_change_percent']}% dh={feedback['height_change_percent']}%"]
        # Keep the measurement label outside the target where possible.
        left = w-345 if bbox and measurement['target_x'] < 50 else 0
        panel = image.copy()
        cv2.rectangle(panel,(left,0),(w if left else 345,len(labels)*17+8),(12,18,24),-1)
        image = cv2.addWeighted(panel,.85,image,.15,0)
        for i,label in enumerate(labels):
            cv2.putText(image,label,(left+5,16+i*17),cv2.FONT_HERSHEY_SIMPLEX,.34,(220,245,230),1,cv2.LINE_AA)
        ok, encoded = cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,94])
        if not ok:
            raise ValueError('Cannot encode labeled frame')
        content = encoded.tobytes()
        digest = hashlib.sha256(content).hexdigest()
        labeled = frame.with_name(frame.stem+'-labeled-'+digest[:16]+'.jpg')
        labeled.write_bytes(content)
        return {'model_frame': str(labeled), 'measurement': measurement, 'movement_feedback': feedback}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--weights',default=str(ROOT/'tools/yolov8s-worldv2.pt'))
    parser.add_argument('--device',default='mps')
    args=parser.parse_args()
    detector=Detector(args.weights,args.device)
    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,data):
            body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            self.reply(200,{'ready':True}) if self.path=='/health' else self.reply(404,{'error':'Not found'})
        def do_POST(self):
            try:
                if self.path!='/prepare':return self.reply(404,{'error':'Not found'})
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<=65536:raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(size))
                frame=Path(data['frame']).resolve()
                if frame.parent!=(ROOT/'vision-output').resolve() or frame.suffix!='.jpg' or not frame.is_file():
                    raise ValueError('Frame must be a saved vision-output JPEG')
                result=detector.prepare(frame,data['goal'],data.get('history',[]))
                self.reply(200,result)
            except Exception as e:self.reply(400,{'error':str(e)})
        def log_message(self,*args):pass
    print('DETECTOR READY',flush=True)
    HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__':main()
