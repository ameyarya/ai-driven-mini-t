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
