# Color-free can detector comparison

2026-10-06: offline YOLO-World comparison, 640-pixel input, MPS, confidence 0.10. No tank commands or runtime setting changes.

35 shared saved frames: 25 recent captures and 10 historical examples (seven previously reviewed visible targets, three absent targets). Captures are correlated development images, not an independent accuracy benchmark. Counts below mean at least one candidate, not confirmed correct detection.

| Description | Recent frames with candidates /25 | Historical /10 | Latest placement /6 |
| --- | ---: | ---: | ---: |
| can | 6 | 5 | 6 |
| soda can | 0 | 4 | 0 |
| beverage can | 2 | 5 | 0 |
| aluminum can | 0 | 4 | 0 |

All four descriptions produced zero candidates on the three known absent historical frames. This small negative sample does not establish false-positive reliability.

Representative visual inspection confirms that `can` boxes the current target, with scores 0.498–0.574 across the six latest-placement frames. Two frames additionally box background clutter at 0.100–0.177. The production ambiguity rule would stop on those multiple candidates.

Re-filtering saved detections at 0.20 removes the extra candidates while retaining the target in all six latest frames. However, historical candidate-bearing frames fall from five to four. A global threshold increase therefore has a demonstrated detection-count tradeoff; it is not automatically an improvement.

Steady-state detector medians were 17.8–19.1 ms, excluding model setup, warm-up, labeling and Qwen. Full per-frame numeric evidence: [results](color-free-detector-results.json). Private annotated camera images remain local.

Next experiment: use the color-free description `can`, verify target continuity and ambiguity, and test difficult/absent scenes before choosing a threshold policy. Runtime switched to `can` after this comparison on 2026-10-06, retaining the 0.10 cutoff and the multiple-candidate ambiguity stop. Physical retest remains pending. No description is proven reliable for every can color or appearance.
