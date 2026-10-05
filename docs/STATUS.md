# Project status

Updated 2026-10-04.

Editable scope and completion checklist: [FEATURES.md](../FEATURES.md).

Expanded simulator checks: 100 HTTP mission scenarios satisfy the tested
invariants and eight rejection/Stop checks pass. Find/approach/fire hits in
20/20 synthetic scenes; direct-fire hits in 8/10 fired cases, with two misses.
Thirty non-search missions stop on an absent target. Four real original-Qwen
shooting missions also pass the initial scene. No new fine-tuning occurred.

The full saved-frame comparison is complete: adapter-v1 scores 3,648/4,116
versus base 1,571/4,116, using the frozen pre-shooting contract. There are
31 paired regressions, including an approach-class aggregate regression.
See [full results and limitations](FULL_PLANNER_COMPARISON.md).

## Added: one-shot controller and MuJoCo

One-shot center/fire, find/fire, approach/fire and find/approach/fire missions
are implemented on the host, reusing the existing receiver launcher API.
Tracks stop and the can is confirmed stationary before a bounded fire/reset
command. Persistent accounting limits automatic attempts to six. Evidence is
recorded, but physical shot release and impact remain **unconfirmed**.
No physical firing test was performed. Current adapter-v1 still refuses firing.

MuJoCo runs locally at localhost:8002 with rendered camera views, an explicitly
labeled segmentation oracle and projectile-contact ground truth. The default
controller preview does not call Qwen; optional original-Qwen planning is available; the benchmark has finished. All four scripted shooting missions pass the initial
scene; 100 deterministic projectile cases, 79 host tests and six Chrome checks
pass. Inverse-image-height approach timing fixes simulated nonlinear overshoot;
fresh physical validation remains pending. See [details](SHOOTING_SIMULATION.md).

## Current platform

CyberBrick Mini-T tank, Mac USB transmitter → ESP-NOW receiver, DJI Action 5 Pro
via Mimo/MediaMTX, YOLO-World detector, and local Qwen3-VL 4B Instruct.

## Working and physically tested

- Hold-to-drive arrows, corrected turning directions, left-track 18% compensation.
- Manual launcher elevation and firing, plus signed wireless app updates/rollback.
- Local vision with live feed and a separate labeled planner/controller snapshot.
- Centering and approach to a requested percentage of image height.
- Turn-in-place search, followed by fully visible and centered target confirmation.
- Qwen plans once; Python adjusts movement duration from fresh detector feedback.
- Logged approach comparison: 346.43 → 69.15 seconds, 21 → 14 steps, 21 → 1
  Qwen calls. See [performance case study](PERFORMANCE.md) for limitations.

## Current work: combined search and approach

Search → approximate alignment → confirmation → approach → final centering/stop
is implemented. Alignment is loose for distant targets and tightens to ±5% near
the requested image size. Missed detections retry while stationary, with bounded
reacquisition that preserves the accepted mission.

Physical combined-goal validation is ongoing. An earlier run failed after a
missed small target and rejected replan; that handling was corrected. The latest
logged combined run reached the 40-step limit while still aligning a distant
can (12.7% image height). It is not yet reliably completing this mission.

## Offline playground

Saved-frame Qwen planning tests now run independently at localhost:8001, without
the rover, camera, detector worker, or motor server. Human-reviewed corrections
export to Qwen’s image/conversation dataset format. Official upstream training
source is downloaded locally; a CUDA LoRA launcher is prepared. A local MLX
QLoRA adapter has now completed 80 steps on the M4 Mac. Held-out planning
contracts improved from 12/28 to 25/28, with three missing-target failures
remaining. The trained model is selectable in the offline playground; the tank
runtime still uses the original Ollama model. See [fine-tuning results](FINE_TUNING.md). Headless Chrome goal-matrix testing exposes planner interpretation
errors; the validator now blocks centering-to-search substitutions and physical
distance requests. Concurrent playground requests also remain isolated. This is recorded-scene testing, not a physics simulator.
See [setup and limitations](PLAYGROUND.md).

## Bounds and remaining work

- Exact 360° coverage remains uncalibrated; search has explicit time/step bounds.
- No physical obstacle avoidance or calibrated physical ranging. Automatic firing is
  implemented but not physically validated.
- Receiver watchdog, Stop, stale-frame checks, clipping/ambiguity checks,
  wrong-way turn checks, and 40-step limit remain active.
- Live capture plus controller observation was around two seconds in recorded
  tests; the 1.5-second settling wait and movement time are additional.
- 79 host tests pass. Hardware behavior still needs physical
  checks; unit tests are not a substitute for successful tank runs.

## Workspace

All project source, private runtime data, environments, and preserved historical
files now live inside this repo folder. Private assets remain Git-ignored.
See [workspace layout](WORKSPACE.md), [prompts](PROMPTS.md), and [ideas](IDEAS.md).

Truck steering, the drone camera transplant, and phone-free DJI streaming remain
paused investigations; their scripts and backups were preserved in the local archive.

## Project name — 2026-10-04

The project is named **AI-Driven Mini-T**: an AI brain for a mini toy tank. The repository
and canonical workspace are `ai-driven-mini-t`. Existing `rover_*` Python module names
remain internal implementation identifiers.

## Workspace location — 2026-10-04

Canonical checkout moved to `/Users/am3yarya/Documents/Github/ai-driven-mini-t`.
Local datasets, models, environments and archives moved with the repository.

## Simulation recording — 2026-10-04

A fresh scripted combined-mission recording is embedded in the README with
an MP4 and result JSON. No new Qwen or physical hardware test is implied.

## Simulated launcher elevation — 2026-10-04

Up/down buttons and keys 1/2 now articulate the launcher and change shot
trajectory. Ten physics tests (200 shot scenarios), 79 host tests and
13 scripted browser checks pass. A separate GIF/MP4 demonstrates raised miss
and lowered hit. Limits/rate are uncalibrated; automatic elevation planning
and physical validation remain pending.

## Final project name — 2026-10-04

Name locked to **AI-Driven Mini-T** (`ai-driven-mini-t`). Historical recordings
retain their original Rook titles. Internal module names and asset filenames
are preserved for compatibility.

## Obstacle avoidance simulator — 2026-10-05

Known-map A* routing and a conservative footprint guard now run in MuJoCo.
Six selectable scenes include left/right detours and an enclosed tank. The
lower view shows the known obstacle map; ideal simulated range readings are
explicitly labeled. Avoidance stops near the can and never fires.

100/100 varied scenarios pass: 80 reach, 20 correctly stop without a route,
zero contacts. Ten obstacle tests and ten existing physics tests pass;
79 host tests and 19 scripted browser checks pass. Existing launcher and
mission HTTP regression results are recorded in the public obstacle report.
A fresh GIF/MP4 shows a detour and an enclosed stop. Browser Stop now ignores
stale step responses so cancellation status remains visible.

This is controller setup/testing, not training or camera obstacle detection.
The map, pose and target location are perfect simulator oracles. Real sensing,
localization, moving obstacles, unknown-map navigation and physical validation
remain pending. See [obstacle setup and results](OBSTACLE_AVOIDANCE.md).

## Combined simulation matrix — 2026-10-05

A new standalone harness chains existing search/alignment, known-map avoidance
and visual approach/one-shot controllers without resetting between stages.
All 31 cases pass: 24 reachable cases produce one simulated projectile contact,
two searches stop, one unsafe destination rejects routing, three stage
cancellations stop, and one exhausted-ammunition fixture rejects firing.
Zero obstacle overlaps; 79 host and 20 simulator regressions also pass.
This is scripted orchestration, not integrated dashboard mission support, Qwen
inference, automatic elevation aiming or physical validation. See
[methods and limitations](COMBINED_SIMULATION.md) and
[per-case results](combined-simulation-results.json).
