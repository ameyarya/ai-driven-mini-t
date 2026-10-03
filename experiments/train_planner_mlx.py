"""Train/evaluate a private MLX QLoRA planner experiment on Apple Silicon."""
import argparse
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DATA=ROOT/'playground-data/planner-training'
MODEL=ROOT/'tools/qwen3-vl-4b-mlx'
ADAPTER=DATA/'adapter-v1'


def rows(split):
    return [json.loads(line) for line in (DATA/(split+'.jsonl')).read_text().splitlines()]


def score(plan, expected):
    failures=[]
    if not isinstance(plan,dict):return ['Output is not a JSON object']
    if set(plan)!={'mode','target','height_percent','reason','uncertainties'}:failures.append('Incorrect output fields')
    if plan.get('mode')!=expected['mode']:failures.append('Wrong mission mode')
    if type(plan.get('height_percent')) not in (int,float) or (expected['mode']!='unsupported' and plan['height_percent']!=expected['height_percent']):failures.append('Wrong image-height setpoint')
    if not isinstance(plan.get('target'),str) or not re.search(r'\bcan\b',plan['target'],re.I):failures.append('Target omitted/incorrect')
    if not isinstance(plan.get('reason'),str) or len(plan['reason'])>120:failures.append('Invalid/overlong reason')
    uncertainties=plan.get('uncertainties')
    if not isinstance(uncertainties,list) or any(not isinstance(x,str) for x in uncertainties) or len(uncertainties)>3 or bool(uncertainties)!=bool(expected['uncertainties']):failures.append('Incorrect uncertainty contract')
    return failures


def evaluate(adapter=None,split='test',limit=None):
    import mlx.core as mx
    from mlx_vlm import load,generate
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.structured import build_json_schema_logits_processor
    model,processor=load(str(MODEL),adapter_path=str(adapter) if adapter else None)
    selected=rows(split)[:limit]
    results=[]
    for index,row in enumerate(selected,1):
        image=Path(row['images'][0])
        image_hash=hashlib.sha256(image.read_bytes()).hexdigest()
        if image.stem!=image_hash:
            raise ValueError('Evaluation image differs from the prepared dataset')
        prompt=apply_chat_template(processor,model.config,row['messages'][:1],num_images=1)
        start=time.monotonic()
        constraint=build_json_schema_logits_processor(processor.tokenizer,row['schema'])
        generated=generate(model,processor,prompt,image=row['images'],max_tokens=160,temperature=0,verbose=False,logits_processors=[constraint])
        text=generated.text
        try:
            plan=json.loads(text);failures=score(plan,row['expected'])
        except ValueError:
            plan=None;failures=['Invalid or truncated JSON']
        result=dict(kind=row['kind'],frame=row['frame'],goal=row['goal'],expected=row['expected'],
                    text=text,plan=plan,input_sha256=image_hash,passed=not failures,failures=failures,seconds=round(time.monotonic()-start,2))
        results.append(result)
        print(f'{index}/{len(selected)} {row["kind"]}: {"PASS" if result["passed"] else "FAIL"} {result["seconds"]}s',flush=True)
        mx.clear_cache()
    summary=dict(backend='MLX greedy JSON-schema decoding; production schema, fixed 160-token budget',split=split,
                 adapter=str(adapter) if adapter else None,total=len(results),passed=sum(r['passed'] for r in results),
                 peak_memory_gb=round(mx.get_peak_memory()/1e9,3),
                 dataset_manifest_sha256=hashlib.sha256((DATA/'manifest.json').read_bytes()).hexdigest(),results=results)
    output=DATA/(('adapter-v1' if adapter else 'base')+'-'+split+'-evaluation.json')
    output.write_text(json.dumps(summary,indent=2)+'\n')
    print('EVALUATION',summary['passed'],'/',summary['total'],flush=True)
    return summary


def train_model(iters):
    import mlx.core as mx
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten
    from mlx_vlm import load
    from mlx_vlm.lora import setup_model_for_training
    from mlx_vlm.trainer.datasets import VisionDataset
    from mlx_vlm.trainer.sft_trainer import train,TrainingArgs
    from mlx_vlm.trainer.utils import print_trainable_parameters
    from datasets import Dataset
    mx.random.seed(20261003)
    model,processor=load(str(MODEL))
    config=model.config.__dict__
    train_data=VisionDataset(Dataset.from_list(rows('train')),config,processor,train_on_completions=True)
    val_data=VisionDataset(Dataset.from_list(rows('validation')),config,processor,train_on_completions=True)
    settings=SimpleNamespace(full_finetune=False,train_vision=False,lora_rank=8,lora_alpha=16,lora_dropout=0.0)
    model=setup_model_for_training(model,settings)
    print_trainable_parameters(model)
    ADAPTER.mkdir(parents=True,exist_ok=True)
    initial={name:float(mx.sum(mx.abs(value)).item()) for name,value in tree_flatten(model.trainable_parameters())}
    args=TrainingArgs(batch_size=1,iters=iters,val_batches=4,steps_per_report=5,steps_per_eval=40,
        steps_per_save=40,max_seq_length=2048,adapter_file=str(ADAPTER/'adapters.safetensors'),
        grad_checkpoint=True,learning_rate=0.00005,grad_clip=1.0,gradient_accumulation_steps=1)
    start=time.monotonic()
    train(model,optim.Adam(learning_rate=args.learning_rate),train_data,val_data,args,
          train_on_completions=True)
    final={name:float(mx.sum(mx.abs(value)).item()) for name,value in tree_flatten(model.trainable_parameters())}
    changed=sum(initial[name]!=final[name] for name in initial)
    metadata=dict(iters=iters,settings=vars(settings),training_args=vars(args),
        training_seconds=round(time.monotonic()-start,2),peak_memory_gb=round(mx.get_peak_memory()/1e9,3),
        changed_trainable_tensors=changed,total_trainable_tensors=len(initial),
        adapter_sha256=hashlib.sha256((ADAPTER/'adapters.safetensors').read_bytes()).hexdigest(),
        model_revision=(ROOT/'playground-data/mlx-model-revision.txt').read_text().strip(),
        dataset_manifest_sha256=hashlib.sha256((DATA/'manifest.json').read_bytes()).hexdigest(),
        versions={name:importlib.metadata.version(name) for name in ('mlx','mlx-vlm','transformers','datasets')},
        label_source='Agent-authored capability labels + unverified recorded detector visibility; no human grounding labels')
    (ADAPTER/'training-run.json').write_text(json.dumps(metadata,indent=2)+'\n')
    if not changed:raise RuntimeError('No adapter tensors changed')
    print('TRAINED:',changed,'changed adapter tensors; peak memory',metadata['peak_memory_gb'],'GB',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['base-eval','train','adapter-eval'])
    parser.add_argument('--iters',type=int,default=80)
    parser.add_argument('--split',choices=['validation','test'],default='test')
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    if args.mode=='train':train_model(args.iters)
    else:evaluate(ADAPTER if args.mode=='adapter-eval' else None,args.split,args.limit)


if __name__=='__main__':main()
