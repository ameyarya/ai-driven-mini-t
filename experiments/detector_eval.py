"""Offline YOLO-World evaluation. Never imports the motor-control server."""
import argparse
import json
import statistics
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--weights', default='yolov8s-worldv2.pt')
    parser.add_argument('--prompt', default='red soda can')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--confidence', type=float, default=.10)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--manifest', type=Path, help='JSON list of saved filenames for repeatable comparisons')
    args = parser.parse_args()
    import torch
    import ultralytics
    from ultralytics import YOLOWorld
    names = json.loads(args.manifest.read_text()) if args.manifest else None
    if names is not None and any(Path(name).name != name or not name.endswith('.jpg') for name in names):
        raise SystemExit('Manifest must contain JPEG basenames only')
    frames = [args.frames_dir/name for name in names] if names is not None else sorted(p for p in args.frames_dir.glob('*.jpg') if '-labeled' not in p.stem)
    if args.limit:
        frames = frames[:args.limit]
    if not frames:
        raise SystemExit('No JPEG frames found')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    model = YOLOWorld(args.weights)
    model.set_classes([args.prompt])
    setup_seconds = time.perf_counter()-start
    # Warm-up is excluded from steady-state timings, reported separately.
    start = time.perf_counter()
    model.predict(str(frames[0]), device=args.device, imgsz=640,
                  conf=args.confidence, verbose=False)
    warmup_seconds = time.perf_counter()-start
    rows = []
    for i, frame in enumerate(frames):
        start = time.perf_counter()
        result = model.predict(str(frame), device=args.device, imgsz=640,
                               conf=args.confidence, verbose=False)[0]
        if args.device.startswith('mps'):
            torch.mps.synchronize()
        elapsed = time.perf_counter()-start
        h, w = result.orig_shape
        detections = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
            detections.append({'confidence': round(float(box.conf[0]), 4),
                'bbox_pixels': [round(v, 2) for v in [x1, y1, x2, y2]],
                'bbox_normalized': [round(x1/w*1000), round(y1/h*1000), round(x2/w*1000), round(y2/h*1000)],
                'center_x_percent': round((x1+x2)/2/w*100, 2),
                'height_percent': round((y2-y1)/h*100, 2),
                'touches_image_edge': x1 <= 2 or y1 <= 2 or x2 >= w-2 or y2 >= h-2})
        detections.sort(key=lambda x: x['confidence'], reverse=True)
        row = {'frame': frame.name, 'seconds': round(elapsed, 4), 'detections': detections}
        rows.append(row)
        result.save(filename=str(args.output_dir/frame.name))
        if (i+1)%20 == 0 or i+1 == len(frames):
            print(f'{i+1}/{len(frames)} frames processed', flush=True)
    timings = [r['seconds'] for r in rows]
    report = {'model': args.weights, 'prompt': args.prompt, 'device': args.device,
              'confidence_threshold': args.confidence, 'imgsz': 640,
              'torch': torch.__version__, 'ultralytics': ultralytics.__version__,
              'setup_seconds': round(setup_seconds, 3), 'warmup_seconds': round(warmup_seconds, 3),
              'frames': len(rows), 'frames_with_detection': sum(bool(r['detections']) for r in rows),
              'median_seconds': round(statistics.median(timings), 4),
              'p95_seconds': sorted(timings)[max(0, int(.95*len(timings))-1)],
              'results': rows}
    (args.output_dir/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2),flush=True)


if __name__ == '__main__':
    main()
