"""Resumable all-saved-frame/all-template comparison; no hardware access."""
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rover_playground import catalog
from rover_fast_navigation import planner_request
from experiments.prepare_planner_training import GOALS, expected_plan
from experiments.train_planner_mlx import MODEL, ADAPTER, score

OUT = ROOT / 'playground-data/full-comparison'


def summarize(results):
    summary = {}
    for backend in ('base', 'adapter'):
        selected = [r for r in results if r['backend'] == backend]
        times = sorted(r['seconds'] for r in selected if 'seconds' in r)
        summary[backend] = dict(completed=len(selected), passed=sum(r['passed'] for r in selected),
            median_seconds=statistics.median(times) if times else None,
            by_split={split: dict(total=sum(r['split'] == split for r in selected),
                passed=sum(r['split'] == split and r['passed'] for r in selected))
                for split in ('train', 'validation', 'test', 'other')},
            by_kind={kind: dict(total=sum(r['kind'] == kind for r in selected),
                passed=sum(r['kind'] == kind and r['passed'] for r in selected)) for kind in GOALS})
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def main():
    import mlx.core as mx
    from mlx_vlm import load, generate
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.structured import build_json_schema_logits_processor
    OUT.mkdir(parents=True, exist_ok=True)
    items = list(catalog().values())
    manifest = json.loads((ROOT / 'playground-data/planner-training/manifest.json').read_text())
    splits = {r['raw_sha256']: r['split'] for r in manifest['manifest']}
    specification = dict(frames=[dict(id=i['id'], sha256=i['sha256']) for i in items],
        goals=GOALS, adapter_sha256=hashlib.sha256((ADAPTER/'adapters.safetensors').read_bytes()).hexdigest(),
        decoding='MLX JSON schema, greedy, 160 tokens', total_calls=len(items)*sum(map(len,GOALS.values()))*2)
    spec_path = OUT/'specification.json'
    if spec_path.exists() and json.loads(spec_path.read_text()) != specification:
        raise ValueError('Comparison inputs changed; preserve prior results and choose a new output directory')
    spec_path.write_text(json.dumps(specification, indent=2)+'\n')
    log = OUT/'results.jsonl'
    results = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    done = {(r['backend'], r['frame'], r['goal']) for r in results}
    for backend in ('base', 'adapter'):
        if all((backend,i['id'],goal) in done for i in items for goals in GOALS.values() for goal in goals):
            continue
        model, processor = load(str(MODEL), adapter_path=str(ADAPTER) if backend=='adapter' else None)
        for item in items:
            image = item['image'].read_bytes()
            if hashlib.sha256(image).hexdigest() != item['sha256']:
                raise ValueError('Saved image changed')
            split = splits.get(hashlib.sha256(item['raw'].read_bytes()).hexdigest(), 'other')
            for kind, goals in GOALS.items():
                for goal in goals:
                    if (backend,item['id'],goal) in done:
                        continue
                    expected = expected_plan(kind,goal,item['measurement'])
                    request = planner_request(goal,image,item['measurement'])
                    messages = [dict(role='user',content=[dict(type='image',image=str(item['image'])),
                        dict(type='text',text=request['messages'][0]['content'])])]
                    prompt = apply_chat_template(processor,model.config,messages,num_images=1)
                    start = time.monotonic()
                    constraint = build_json_schema_logits_processor(processor.tokenizer,request['format'])
                    generated = generate(model,processor,prompt,image=[str(item['image'])],max_tokens=160,
                        temperature=0,verbose=False,logits_processors=[constraint])
                    seconds = time.monotonic()-start
                    try:
                        plan = json.loads(generated.text)
                        failures = score(plan,expected)
                    except ValueError:
                        plan = None
                        failures = ['Invalid or truncated JSON']
                    result = dict(backend=backend,frame=item['id'],goal=goal,kind=kind,split=split,
                        input_sha256=item['sha256'],plan=plan,text=generated.text,expected=expected,
                        failures=failures,passed=not failures,seconds=round(seconds,3))
                    with log.open('a') as handle:
                        handle.write(json.dumps(result)+'\n'); handle.flush(); os.fsync(handle.fileno())
                    results.append(result)
                    summarize(results)
                    print(f'{len(results)}/{specification["total_calls"]} {backend} {kind} {seconds:.2f}s {"PASS" if not failures else "FAIL"}',flush=True)
                    mx.clear_cache()
        del model, processor
        gc.collect(); mx.clear_cache()
    print('COMPLETE',json.dumps(summarize(results)),flush=True)


if __name__ == '__main__':
    main()
