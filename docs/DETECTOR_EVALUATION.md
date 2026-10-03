# Independent detector: saved-frame evaluation

Date: 2026-10-02. Offline only; no motor commands, training, or live-loop changes.

## Setup

YOLO-World `yolov8s-worldv2.pt`, Apple MPS on the development M4 Mac, input size
640, confidence cutoff 0.10. Python 3.12.14, Ultralytics 8.4.171, PyTorch 2.14.1,
TorchVision 0.29.1, CLIP commit d05afc436d78f1c48dc0dbf8e5980a9d471f35f6.
All inference was local. Weights and dependencies downloaded; camera frames were
not uploaded.

## Results

A fixed manifest of 196 saved frames was rerun with `red soda can` and explicit
MPS synchronization. 186 frames produced at least one candidate. This is a
**detection count, not an accuracy score**: the entire set has not been independently
annotated and many frames are highly correlated.

Steady-state median detection latency: **18.8 ms**; p95: **25.3 ms**. Initialization:
2.242 s; warm-up: 1.077 s. An earlier cold/download run had higher setup/warm-up
costs and a 27.8 ms median. Timings exclude annotation rendering, file saving,
camera capture, and Qwen inference. They do not predict end-to-end navigation
latency with both models active.

Three prompts were compared on the same 196 common frames (two later captures
in the other runs were excluded):

| Prompt | Frames detected at 0.10 | Frames detected at 0.25 |
| --- | ---: | ---: |
| red soda can | 186 | 177 |
| soda can | 177 | 160 |
| Coca-Cola can | 175 | 72 |

More detections alone do not prove greater accuracy. Visual spot-checks favored
`red soda can` for this particular object/environment. This is prompt selection
on development images, not a held-out benchmark.

## Manually reviewed cases

Seven visible-target cases and three absent-target cases were checked. At cutoff
0.10 all seven produced target boxes and all three absent cases produced no box.
The floor can, thin edge sliver, and pushing-run close-up fall below 0.25 and would
be missed at that cutoff. These ten cases are not enough to establish reliability.

| Frame | Case | Confidence | Horizontal centre | Visible image height | Touches edge |
| --- | --- | ---: | ---: | ---: | --- |
| frame-20261001-183746.jpg | No can | None | — | — | — |
| frame-20261001-192642.jpg | Clutter, no can | None | — | — | — |
| frame-20261001-201426.jpg | Lost target, no can | None | — | — | — |
| frame-20261001-184553.jpg | Floor can | 0.1104 | 52.09% | 36.6% | No |
| frame-20261001-194614.jpg | Near centre | 0.7909 | 45.82% | 63.23% | No |
| frame-20261001-194745.jpg | Left / bottom edge | 0.8516 | 34.05% | 66.29% | Yes |
| frame-20261001-201408.jpg | Thin sliver at left edge | 0.1019 | 2.61% | 81.02% | Yes |
| frame-20261002-164253.jpg | Moderate size | 0.6039 | 38.86% | 38.27% | No |
| frame-20261002-165028.jpg | Pushing-run close-up | 0.1887 | 27.3% | 94.87% | Yes |
| frame-20261002-171532.jpg | Smaller can | 0.643 | 40.03% | 34.24% | No |

The close-up measurement is about 95% image height with edge contact, directly
contradicting the prior Qwen decision that the can was smaller than 40%.
Edge-touch is a geometric flag derived from the box; it does not guarantee that
every form of occlusion or clipping is recognized. Detector scores are not
calibrated probabilities. Measurements refer to visible image bounds, not
physical centimetres or unseen portions of the object.

## Decision

Promising enough to prototype as independent measurement input to Qwen, but not
integrated into control yet. Keep weak detections explicit as uncertain candidates,
check target continuity, and stop or reobserve when target identity/visibility is
ambiguous. Before treating low-confidence candidates as control measurements,
add diverse no-target/red-distractor cases and a held-out annotated frame set.

The annotated JPEGs and full per-frame reports remain in local `detector-output/`;
images are not published. Reproduce with [the offline runner](../experiments/README.md).

Model documentation: https://docs.ultralytics.com/models/yolo-world/
