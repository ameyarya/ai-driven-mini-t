#!/usr/bin/env bash
# Linux/CUDA only. Keep images and checkpoints private.
set -euo pipefail
rook_root="$(cd "$(dirname "$0")/.." && pwd)"
rook_source="$rook_root/tools/qwen3-vl/qwen-vl-finetune"
rook_dataset="$rook_root/playground-data/dataset"
command -v nvidia-smi >/dev/null || { echo 'This upstream trainer requires a CUDA training machine.'; exit 1; }
python3 - "$rook_source" "$rook_dataset" <<'PY'
import json, pathlib, sys
source, dataset = map(pathlib.Path, sys.argv[1:])
rows = json.loads((dataset / 'train.json').read_text())
if not rows:
    raise SystemExit('No approved training examples. Review and export first.')
config = source / 'qwenvl/data/__init__.py'
text = config.read_text()
marker = '\n# Rook local dataset registration\n'
text = text.split(marker)[0]
text += marker + 'data_dict["rook_train"] = ' + repr(dict(annotation_path=str(dataset / 'train.json'), data_path=str(dataset))) + '\n'
config.write_text(text)
PY
cd "$rook_source"
torchrun --nproc_per_node="${NPROC_PER_NODE:-1}" qwenvl/train/train_qwen.py \
  --model_name_or_path Qwen/Qwen3-VL-4B-Instruct \
  --dataset_use rook_train --data_flatten True \
  --lora_enable True --lora_r 16 --lora_alpha 32 --lora_dropout 0.05 \
  --bf16 True --gradient_checkpointing True \
  --per_device_train_batch_size 1 --gradient_accumulation_steps 8 \
  --num_train_epochs 1 --learning_rate 0.00001 --model_max_length 4096 \
  --max_pixels 262144 --min_pixels 784 \
  --logging_steps 1 --save_strategy epoch --report_to none \
  --output_dir "$rook_root/playground-data/checkpoints"
