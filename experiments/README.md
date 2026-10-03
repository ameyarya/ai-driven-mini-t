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

## Apple Silicon planner fine-tuning

See [the local QLoRA experiment](../docs/FINE_TUNING.md). Install
`experiments/training-requirements.txt` into a separate `.training-venv`, then
prepare the local split and run base evaluation → training → adapter evaluation
**sequentially**. Concurrent training and inference exhausted Metal memory on
the 16 GB development Mac. Neither the detector environment nor Ollama weights
are modified by this workflow.

```sh
python3 experiments/prepare_planner_training.py
.training-venv/bin/python experiments/train_planner_mlx.py base-eval
.training-venv/bin/python experiments/train_planner_mlx.py train --iters 80
.training-venv/bin/python experiments/train_planner_mlx.py adapter-eval
```

The scripts consume existing private saved scenes. They do not create a physics
simulator, issue motor commands, or upload a dataset. The dataset and adapter
are excluded from Git. Test the semantic label rules with `test_rover_training`.

To repeat the browser matrix with the trained model server running:

```sh
ROOK_PLAYGROUND_BACKEND=mlx node experiments/playground_browser_test.mjs
```
# Full saved-frame comparison

`experiments/full_planner_comparison.py` runs all 21 goal templates against
every verified saved observation using both the unchanged MLX model and the
trained adapter, sequentially. It uses identical images, production prompts,
JSON schemas and decoding. Stop the MLX planner service and unload Ollama
before starting to avoid GPU memory contention.

```sh
HF_HOME="$PWD/tools/hf-training-cache" .training-venv/bin/python -u \
  experiments/full_planner_comparison.py
```

Private results are flushed after every call to
`playground-data/full-comparison/results.jsonl`; `summary.json` records progress.
Restarting resumes completed calls and rejects changed inputs. Scores use the
existing agent-authored contracts and unverified detector labels. Training,
validation, selected test and other frames are reported separately; other
frames can share training sessions and are not an independent held-out set.
Timing excludes loading the model. This tests planning, not physical movement.
The October 3 full run has started; aggregate results are pending.
