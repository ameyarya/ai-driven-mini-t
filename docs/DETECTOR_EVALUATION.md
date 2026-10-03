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


### Exact labeled vision input
Independent YOLO-World measures each captured frame and Python labels it before
Qwen inference. One dashboard view shows exactly that JPEG, with SHA-256
verification, frame age, and inference state. It remains frozen until the next
observation. Qwen also receives measured changes after previous actions.
A saved-frame check proposed 500 ms after ineffective 50 ms turns; real-world
improvement remains unverified. Controller and labeled-input tests: 22 passed.


Centering stop diagnosis: Qwen mislabeled unfinished centering as uncertainty. Exact progress-only statements are filtered for centering; genuine warnings remain blocking and raw model output remains preserved. Stop messages now include the actual warning. Regression suite: 23 passed. Logged LEFT moved target from 42.35% to 29.25%; direction mismatch guard retained pending physical verification.


Dashboard now has two explicitly separate views: live camera on top and the hash-verified labeled Qwen input underneath. Both fit alongside the control column within the viewport. The labeled view remains frozen during inference, with frame age and status.


### Qwen planner + fast visual feedback controller
Qwen translates a centering or explicit image-height approach goal once. Python
uses detector measurements after each stopped movement, learns response per ms,
and adapts pulse duration (50–1000 ms). Initial gain probes: 150 ms turn / 250 ms
forward. Center tolerance: 5 percentage points; height tolerance: 1 point.
Target loss or three stalled corrections asks Qwen to review while stationary,
with at most two reviews. Unsupported missions fail explicitly. No obstacle
avoidance or autonomous firing is added. Watchdog, direction guard, fresh-frame
checks, Stop, settling wait, and 40-step bound remain.
Bottom pane identifies Qwen planner input vs controller-only input truthfully,
with byte-hash verification in both cases. Saved-frame planner call: 9.76 s;
four warm detector/controller observations: 32–34 ms excluding capture. Live
benchmark was blocked by an offline camera stream. 34 unit tests pass; actual
driving performance remains unverified.

After livestream restoration, one live capture + labeling + controller decision took 2.55 s (detector 212.9 ms), with no Qwen call and no motor command. Settling wait and movement duration are additional per-cycle costs.


### Find target by rotating in place
Added Qwen find-mode planning, followed by detector-only right-turn search
(500 ms pulses, stop and fresh observation between pulses). A candidate stops
rotation immediately and needs a second stationary detection before success.
Target absence is expected during search; ambiguous detections stop. No forward
travel, automatic centering, or firing is added to this goal. Exact 360 requires
measured motor-time calibration via ROOK_FULL_TURN_MS at current speed/surface.
Default is explicitly labeled uncalibrated, bounded at 19.5 seconds motor-on
rotation / 40 observations; it never claims a measured full turn. Saved absent-
target Qwen planning succeeded without movement. 41 tests pass; physical search
performance awaits user testing.


### Search completion and pivot correction
A user search run completed at x=98.15% with a clipped can. Find now centers
the detected candidate and requires it to be fully visible in two stationary
frames before completion. Centered but vertically clipped targets stop with
a clear warning. No extra centering phrase is required.
Receiver A/D mappings already command both motors: (1024,1024) / (-1024,-1024).
Because motors are mirrored, these signs mean opposite track directions.
Autonomous pivots now use 100% instead of 40% power to address possible low-
power stalling; physical confirmation that both tracks move is still needed.
Search pulses shortened to 250 ms at this higher power; uncalibrated search
budget is 9.75 s motor-on / 40 observations. Existing timed calibration must
be remeasured at 100% turn power. Approach speed remains 40%. 43 tests pass.


Physical validation update (2026-10-02): user confirmed the corrected turn-in-place find-and-center use case works. Full-power pivots and fully visible, centered target completion are now user-tested. Exact 360-degree coverage remains uncalibrated; no heading-accuracy claim is made.


### Combined search → center → approach goal
Added find_approach_size planning and stage transitions. Search confirms a fully
visible centered target twice, then transitions while stopped; a fresh frame
precedes approach. The search stage no longer prematurely completes a combined
mission. Explicit search and image-height requests constrain planner output
to the correct mission mode and setpoint. Real Qwen initially returned find
only; allowed-schema constraints address that omission. Failed planner output
is now retained in local plan logs for diagnosis. Missing/clipped target cannot
advance. Global stop, step, search, watchdog, and direction bounds remain.
46 tests pass; physical combined-goal test pending.
