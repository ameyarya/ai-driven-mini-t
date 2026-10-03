# Offline detector evaluation

This experiment runs YOLO-World on saved JPEG frames. It does not import the
rover server, open a serial port, or issue movement commands. It does not train
the model or change the live camera/Qwen loop.

Use Python 3.12 and install `experiments/requirements.txt` in an isolated virtual
environment. CLIP encodes the target description; YOLO-World then detects it in
images. Both model weights download on first use.

```sh
python experiments/detector_eval.py \
  --frames-dir ../vision-output \
  --output-dir ../detector-output/red-soda-can \
  --weights ../tools/yolov8s-worldv2.pt \
  --prompt 'red soda can' \
  --device mps
```

`--device cpu` is also supported. `--confidence` defaults to 0.10 for exploratory
candidate collection, not a validated motor-control threshold. `--manifest`
accepts a JSON list of JPEG basenames to freeze the input set between runs.
`--limit` selects an initial subset for a smoke test.

The output contains annotated images and `results.json` with per-frame boxes,
confidence, image-relative center/height, edge-touch flags, timing, and package
versions. MPS is explicitly synchronized before recording detection latency.
Model initialization and warm-up are reported separately. Detection timings
exclude rendering/saving annotated images, camera capture, and Qwen inference.
Raw images and model weights are ignored by Git; do not publish camera captures
as part of benchmark code changes.

See [the initial evaluation](../docs/DETECTOR_EVALUATION.md) for results and limits.

## Offline playground checks

From the repository root, with the offline playground running at port 8001:

```sh
node experiments/playground_browser_test.mjs
python3 experiments/playground_controller_replay.py
```

The browser runner uses installed macOS Google Chrome and Node's built-in
WebSocket support (Node 22+), with an isolated headless profile. It clicks the
actual UI for 28 real-Qwen scene/goal combinations and checks loading, disabled
states, stale results and HTTP error handling. It never approves training data.
Screenshots and detailed reports stay private in `playground-data/browser-tests`.
Only its own Chrome process is closed at the end.

The replay checks bounded actions, forward-motion prerequisites, uncertainty
stops and completion conditions on all recorded scenes across four controller
modes. It is an invariant check, not a physics simulation or accuracy benchmark.
