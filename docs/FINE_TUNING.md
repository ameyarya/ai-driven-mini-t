# Local planner fine-tuning experiment

Rook now has an Apple Silicon QLoRA training path using
[MLX-VLM](https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/LORA.MD).
Qwen's official CUDA trainer remains available as a separate prepared option.
No paid GPU service or private-image upload is used.

## What is trained

This page describes **adapter-v1 and its pre-shooting contract**. The host now
has one-shot mission support, but this adapter has not been retrained for it.
The ongoing full-frame benchmark uses a frozen copy of the pre-shooting
planner prompt. [Shooting and simulation status](SHOOTING_SIMULATION.md).

The model maps a user goal and a labeled camera observation to the existing
planner JSON contract: mission mode, target, requested image-height setpoint,
short reason and uncertainty. The base is a local 4-bit MLX conversion of
`Qwen3-VL-4B-Instruct`, not the Ollama GGUF file currently used by the rover.
A small trainable LoRA adapter is saved separately; the vision stack and base
weights remain frozen.

The goal classes are center, approach-to-image-size, find, find-then-approach,
and refusal of shooting, moving away and physical-distance requests. This
experiment does not implement those unsupported actions or train motor timing.
Python still chooses repeated movements from detector measurements.

## Data and labels

The preparation script uses 24 saved frames with three goal phrasings per class
for **504 training examples**. Six frames from the next recording session form
**126 validation examples**. Four frames from the final recording session
(target left/right/center/missing) form **28 held-out tests**.

A gap greater than 120 seconds defines a recording session. Entire sessions are
kept in separate splits, and identical raw-image hashes cannot cross splits.
Test prompts reuse the goal templates; this checks held-out observations, not
unseen language or completely new rooms. The small sample is not a reliability
claim across environments.

Labels are agent-authored capability/goal contracts, with target visibility and
clipping taken from recorded detector output. They are not independent human
vision annotations or verified path-clearance labels. No previous incorrect
Qwen answer is automatically accepted as ground truth. Frames, manifests,
model weights, checkpoints and detailed model outputs remain Git-ignored.

## Reproduce on Apple Silicon

```sh
python3.12 -m venv .training-venv
.training-venv/bin/python -m pip install -r experiments/training-requirements.txt
# Download mlx-community/Qwen3-VL-4B-Instruct-4bit locally into
# tools/qwen3-vl-4b-mlx. Experiment revision:
# 2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b
python3 experiments/prepare_planner_training.py
HF_HOME="$PWD/tools/hf-training-cache" .training-venv/bin/python \
  experiments/train_planner_mlx.py base-eval
HF_HOME="$PWD/tools/hf-training-cache" .training-venv/bin/python \
  experiments/train_planner_mlx.py train --iters 80
HF_HOME="$PWD/tools/hf-training-cache" .training-venv/bin/python \
  experiments/train_planner_mlx.py adapter-eval
```

The experiment uses rank 8 / alpha 16, batch size 1, learning rate 5e-5,
completion-only loss, gradient checkpointing and 80 iterations. It updates
about 16.5 million adapter parameters. Validation loss is sampled on four
validation batches at iterations 1, 40 and 80. The held-out generation
test is separate from that loss calculation.

The training script records actual adapter weight changes, file hash, memory,
training duration, base revision and library versions alongside the adapter.
The adapter is under `playground-data/planner-training/adapter-v1/`.

## Fair comparison

Both base and adapted models receive the same saved image, production prompt,
JSON schema, greedy decoding and 160-token budget in MLX. A pass requires the
correct mission and setpoint, expected output fields, target name, short reason
and appropriate uncertainty. For a refused goal, image height has no operational
meaning and is not required to equal a supported-goal setpoint.

An initial unconstrained-output diagnostic omitted schema decoding and is
retained privately; it is not used as a performance baseline. Comparing that
run's output format against a schema-constrained adapter would be misleading.
The earlier Ollama browser score is also a different backend/quantization and
is not the fine-tuning before/after baseline.

Fine-tuned weights are staged locally. They do not automatically replace the
rover's Ollama model. Conversion/deployment and fresh physical validation are
separate steps; do not claim a trained planner fixes detector or control errors.

Run inference and training sequentially on this 16 GB Mac. The first attempt
ran the baseline concurrently and exhausted Metal GPU memory; that incomplete
run is retained privately and is not counted as a completed training run.

## Completed first run — October 3, 2026

| Measure | Result |
| --- | --- |
| Unchanged MLX model | 12/28 held-out contracts passed |
| 80-step adapter | 25/28 passed |
| Training time | 819.63 seconds (13.7 minutes) |
| Peak GPU allocation | 6.723 GB |
| Changed adapter tensors | 504/504 |
| Validation loss, iteration 1 → 80 | 3.687 → 0.067 |

The remaining failures are all on the missing-target scene: centering and
approach are proposed despite absence, and a search-and-shoot request drops
the then-unsupported shooting part. Mission-omission validation and missing-target
controller checks remain necessary. The 40-step validation loss was 0.051;
this experiment reports the final 80-step checkpoint and does not pick a
checkpoint using held-out test results.

[Aggregate machine-readable results](fine-tuning-results.json) contain no
private camera frames. The previous 0/28 unconstrained diagnostic is excluded
from this comparison because its output schema was not supplied to decoding.

## Try the trained model in the playground

```sh
# Run sequentially after training/evaluation finishes:
.training-venv/bin/python -u rover_mlx_planner_server.py
# Another terminal:
python3 rover_playground.py
```

Open localhost:8001 and select **Fine-tuned Qwen · MLX adapter**. The option
becomes available when the local adapter server is ready and is selected by
default at page load. **Original Qwen · Ollama** remains available for comparison.
Both paths send the displayed recorded labeled JPEG and use the same production
planner prompt/schema. Their original run logs are preserved. This selection
does not replace the hardware dashboard model or issue motor commands.

Browser integration was verified in isolated headless Chrome after fixing MLX
thread ownership and waiting for model readiness: 37/37 UI checks passed, and
the actual browser reproduced the same 25/28 planner result. All 69 Python
tests and 784 controller invariant replays passed. Integration-error runs are
retained privately and excluded from the model comparison.
