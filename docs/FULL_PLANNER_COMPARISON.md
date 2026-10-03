# Completed saved-frame planner comparison

On October 3, 2026, both the unchanged model and adapter-v1 ran all
**196 saved observations × 21 goal templates**, for **8,232 calls**. Both used
MLX, identical labeled image bytes and production prompts, JSON-schema
decoding, greedy generation and a 160-token budget. The contract was frozen
before the new one-shot firing modes were introduced: shooting prompts in
this benchmark require refusal, not firing.

| Contract score | Unchanged model | Adapter-v1 |
| --- | ---: | ---: |
| All saved-frame/template pairs | 1,571/4,116 (38.2%) | 3,648/4,116 (88.6%) |
| Four selected held-out frames × 21 templates | 35/84 (41.7%) | 77/84 (91.7%) |
| Observed median generation time | 4.48 s | 4.92 s |

Of the 4,116 paired cases, 1,540 passed both, 2,108 improved from failure to
pass, **31 regressed from pass to failure**, and 437 failed both. The adapter
therefore improves the aggregate contract score but is not regression-free.

| Goal class (588 cases each) | Unchanged passes | Adapter passes |
| --- | ---: | ---: |
| Center | 170 | 418 |
| Approach to image size | **421** | **393** |
| Find | 496 | 586 |
| Find then approach | 482 | 588 |
| Refuse shooting (old contract) | 1 | 542 |
| Refuse moving away | 1 | 585 |
| Refuse physical distance | 0 | 536 |

The approach-size class regressed despite the overall improvement. Refusal
classes account for much of the gain. This is evidence for keeping the base
comparison and action/visibility guards rather than treating fine-tuning as a
blanket reliability improvement.

Labels are agent-authored capability contracts using unverified detector
visibility/clipping. The overall set includes training images and other images
from training sessions; it is not a held-out generalization score. The selected
test split has only four distinct observations, and its prompt phrasings also
occur in training. No physical task success or impact detection was measured.

Timing is descriptive, not a controlled speed experiment. Loading is excluded,
but thermal state and machine load vary, and MuJoCo rendering overlapped the
late adapter calls. The next speed work needs its own paired latency benchmark.

[Aggregate results](full-planner-comparison.json) contain no private images.
Detailed outputs remain local under `playground-data/full-comparison/`.
The resumable runner is `experiments/full_planner_comparison.py`;
it retains the run's original planner contract alongside private results.
