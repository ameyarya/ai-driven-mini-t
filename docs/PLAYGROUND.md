# Offline playground and Qwen fine-tuning preparation

The rover can stay powered off. The playground runs at **localhost:8001**,
independently of the hardware dashboard at port 8000.

```sh
cd /Users/am3yarya/Documents/Github/rook
python3 rover_playground.py
```

For the original model, keep Ollama running with `qwen3-vl:4b-instruct` installed.
For the trained model, run `.training-venv/bin/python rover_mlx_planner_server.py`
and select **Fine-tuned Qwen · MLX adapter** in the playground. No camera stream,
serial port or detector worker is required. The UI uses existing saved labeled
JPEGs and their recorded detector measurements. It verifies saved image hashes
and resolves older log paths after the workspace move.

## Workflow

1. Select a saved scene. The displayed labeled JPEG is the image sent to Qwen.
2. Enter a goal and test local Qwen. This uses the production planner prompt,
   structured schema and semantic validation with either selected local backend;
   it never issues movement commands.
3. Inspect the plan and correct its JSON. Approve only examples you have checked.
   Rejected/truncated/unsupported model outputs are retained for diagnosis.
4. Export approved examples. Local `playground-data/dataset/train.json` and
   `validation.json` contain the upstream `image` + `conversations` format.
   Images, results, reviewed labels and checkpoints remain Git-ignored.

The exported assistant answer is the reviewed **plan**, not a motor action.
The human turn uses the exact planner prompt, including the numeric measurements.
An unsupported shooting request should be labeled `unsupported`; this dataset
cannot introduce a shooting capability into the current controller.

No model output is automatically treated as ground truth. A deterministic 80/20
split groups identical raw image bytes together, including differently labeled
versions. Small datasets may have an empty split. Adjacent frames from one run
remain correlated: before claiming generalization, make a separate holdout from
new sessions/rooms rather than relying solely on this initial frame split.

## Official fine-tuning source

[Qwen’s training framework](https://github.com/QwenLM/Qwen3-VL/tree/main/qwen-vl-finetune)
is checked out locally under `tools/qwen3-vl/qwen-vl-finetune` at revision
`96588727e44c78b25ba03ea03b8e12f7e64fd0da`. It is not vendored into Rook’s Git repo.
To reproduce the checkout:

```sh
git clone --filter=blob:none --sparse https://github.com/QwenLM/Qwen3-VL.git tools/qwen3-vl
cd tools/qwen3-vl
git checkout 96588727e44c78b25ba03ea03b8e12f7e64fd0da
git sparse-checkout set qwen-vl-finetune
```

The upstream entry point defaults to FlashAttention 2 and uses a CUDA-oriented
training stack. Its listed dependencies include DeepSpeed, FlashAttention,
Triton, Transformers and PEFT. That stock recipe is **not configured for this
16 GB MacBook Air**. We have downloaded the source and prepared data tooling,
not installed CUDA dependencies. A separate Apple Silicon MLX training route
is now implemented; see [the local fine-tuning experiment](FINE_TUNING.md).

When ready, use a separate Linux NVIDIA/CUDA machine with a compatible isolated
training environment installed according to the pinned upstream README. Transfer
only data you intend to train on, keeping household frames private. No paid GPU
has been provisioned. The memory requirements for our configuration have not
been benchmarked.

```sh
# On that training machine, from the Rook checkout:
bash scripts/train_qwen_rook_lora.sh
```

The launcher requires nonempty approved data, registers `rook_train` in the
ignored upstream checkout, and uses Qwen3-VL-4B-Instruct with LoRA rank 16,
batch size 1 and gradient accumulation 8. This is a starting configuration,
not a validated training run. It saves local checkpoints and disables remote
experiment reporting. Validation data is kept separate; held-out evaluation and
adapter conversion/deployment into Ollama remain follow-up work.

## What these tests can tell us

Saved images let us inspect goal interpretation, missing-target responses,
unsupported requests, structured output and latency without draining batteries.
They do **not** model how a new turn changes the camera view, predict collisions,
prove approach success or measure learned behavior after training. Training the
planner also will not fix a controller/detector error: Python still determines
repeated actions and movement timing.

Verified checks:

```sh
python3 -m unittest test_rover_playground test_rover_autonomy \
  test_rover_vision_labeled test_rover_fast_navigation
```

The new tests check exact image bytes passed to Qwen, preservation of original
logs, hash rejection, approved-only export, upstream format, grouped splitting,
and rejection of corrections that silently omit a requested search.

Initial local smoke test indexed 196 hash-verified observations and called the
real Qwen model. On a centering-only goal, Qwen incorrectly proposed
`find_approach_size`; the production validator rejected it for lacking an
explicit size goal. The failed output was retained locally without approval.
This establishes the testing path, not a passing model-quality benchmark.

## Automated browser and controller checks

See [the offline testing results](PLAYGROUND_TESTING.md) and
[reproducible commands](../experiments/README.md#offline-playground-checks).
