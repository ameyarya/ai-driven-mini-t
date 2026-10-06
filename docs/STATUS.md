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

## Physical test startup and orange target — 2026-10-06

The detector now preserves explicitly named can colors, including orange, rather than always searching for colored. Center-only goals constrain the planner to center or unsupported, preventing an absent target from silently changing the mission to search. Shooting plans preserve the requested can color. 80 host regression tests pass; orange detection and physical firing still require user validation. Startup accepts `TANK_SERIAL_PORT` for changed USB device paths.

## Generic soda-can target — 2026-10-06

Supersedes the color-specific update above: detector classes and planner targets now use `soda can`, ignoring color words entirely. This applies to centering, search, approach and shooting. Several detected cans remain ambiguous and stop rather than silently selecting one. 80 host tests pass; physical detection across colors and firing accuracy remain unvalidated.

## Repository-wide generic target cleanup — 2026-10-06

All active examples, training generators, simulation missions and test targets now omit can color. Historical result prompt wording is normalized for readability; previous timings/outcomes were not rerun and do not establish generic detection reliability. Existing archived media and private trained weights retain their original content. The detector uses open-vocabulary soda-can detection, not a color filter; all-color physical reliability is unverified.

## Color-free detector comparison — 2026-10-06

Offline comparison on 35 saved frames found `can` detects the latest-placement target in 6/6 frames while `soda can`, `beverage can` and `aluminum can` detect none in that six-frame group. Two `can` frames have extra low-score background candidates. Filtering at 0.20 removes those but loses one historical candidate-bearing frame. No runtime changes or physical commands; see [comparison](COLOR_FREE_DETECTOR.md).

## Runtime target switched to can — 2026-10-06

Detector vocabulary, warm-up class and production planner target now use `can`, based on the saved-image comparison. Confidence remains 0.10; multiple candidates still stop as ambiguous. 80 host regressions pass. Physical retest pending.

## Dashboard actions — 2026-10-06

Replaced the physical dashboard prompt box with Find, Align, Approach and Shoot plus Stop. Reuses existing validated goal/controller routes; Approach has a displayed 50% image-height setpoint and Shoot performs alignment then one bounded fire command. Browser verified all four buttons and no text field; no physical commands executed for this UI verification.

## Complete mission action — 2026-10-06

Added the Complete mission dashboard button, using existing find_approach_shoot planning with a 50% image-height goal and one shot. Uses the same camera, ambiguity, cancellation and shot-ledger checks as other actions. Physical combined acceptance remains pending; this is not real-world obstacle avoidance or automatic elevation aiming.

## Bullseye target — 2026-10-06

Switched physical buttons and planning to the hand-drawn bullseye. YOLO-World found no boxes for four descriptions on supplied photo/fresh frame. A multi-scale grayscale reference matcher detects the fresh camera target (0.9302 correlation), with zero matches on 42 earlier development frames. Synthetic checks cover three scales, absent target and duplicate-target ambiguity; 81 host tests pass. Reference remains private in vision-output; missing reference blocks operation. Match measures the square, not the stand. Physical acceptance, perspective robustness, elevation and impact verification remain pending.

## Physical Align calibration — 2026-10-06

Browser-run bullseye Align reduced offset from 3.3% left to 0.5% right using 32 ms and 20 ms left corrections; completed in 3 observations. Repeat completed in 1 observation at the same offset without motion. Bullseye final tolerance is now ±1%, with measured left-turn seed and 20 ms minimum precision corrections. 82 host tests pass. Right direction and launcher aim remain uncalibrated. See [calibration](ALIGNMENT_CALIBRATION.md).

## First visually confirmed physical shot — 2026-10-06

User-authorized browser trial started 31.8% left, Align completed at 0.5% right, then one shot knocked the bullseye onto the floor. Assistant reviewed recorded tipping/floor evidence; 1/6 attempts used, 5 remain. No search, approach or launcher elevation change. The current height worked in this one scene; automatic aiming and impact classification remain pending. Tilt-aware reference matching recovered the starting view without lowering the match cutoff. 82 host tests and 3 synthetic matcher tests pass. See [physical evidence summary](PHYSICAL_SHOOTING.md).

## Launcher elevation calibration workflow — 2026-10-06

Added reference confirmation, bounded Up/Down nudges, one calibration shot, user-confirmed successful samples, reload acknowledgment and remaining-attempt display. Superseded by the one-distance shooting setup below; multi-distance interpolation has been removed. Samples persist privately; startup and manual elevation invalidate reference assumptions. 89 host tests pass; browser controls verified without firing. Physical auto-elevation validation still requires user-collected samples. See [workflow](ELEVATION_CALIBRATION.md).

- Shooting setup simplified to one confirmed hit: Aim & shoot approaches the saved image size, restores launcher height, fires once and pauses for human confirmation. Physical acceptance pending.

## Physical bullseye standoff update

Physical Approach now targets 20% image height; goals above 20% are rejected,
forward pulses are capped at 250 ms, and observations at 25% or larger stop
all physical bullseye missions. These limits are image-size proxies for this
stand, not calibrated centimeters or general obstacle avoidance. A shooting
setup must be saved at 20% or less. Complete mission requires the saved setup.
The former 50% physical approach was too close in a real browser test and was
stopped without firing. Historical can/simulation setpoints remain unchanged.

## Browser hardware verification — 2026-10-06

- Align passed in 2 observations, ending 0.6% right of center (±1% tolerance).
- Reproduced Qwen listing measurement field names as uncertainties, and using
  current target height (11.4%) instead of the requested 50%. Prompt clarification
  and a single-valued setpoint enum passed saved-image inference checks.
- Old 50% approach brought the tank too close and was stopped. User moved it back.
  New physical standoff limits are regression tested; no further approach run yet.
- One authorized shot from 13.3% target height completed in 3 observations, with
  horizontal alignment only. Recorded target remained upright: no confirmed hit.
  One automatic attempt remains after a second test with +50 ms elevation. Both recorded targets remained upright; the first shot passed below according to the user, and the second flight could not be determined. No successful shooting setup saved.
- Fixed polling that re-enabled uncalibrated shooting buttons, stale decisions
  after planner failure, and misleading fire duration/action labels.
- 91 host tests and 20 simulation tests pass. Find/360 was not run because the
  camera is wired. Successful automatic elevation acceptance remains pending.

Shooting setup now opens in a wider dialog with four spaced steps, a status strip, and separate reload controls. Browser rendering verified. Final attempt left unused because the second projectile trajectory was unclear.

Calibration follow-up: frame-by-frame review of the +50 ms shot showed the blue projectile near the stand base, below the bullseye. A third test at +150 ms offset also left the target standing. Three attempts were used in this test session, taking the existing ledger from three remaining to zero. The tank did not approach during those shots. User took over physical calibration; no hit profile was saved. Current launcher offset remains +150 ms from the confirmed reference. Reload is required before further shots. UI now disables firing actions at zero attempts and serializes height adjustments.

Portrait camera: live feed rotates 90° clockwise and the two views sit side by side. Snapshots and shot clips use the same upright transform, at 360×640. Rotation is configured in camera-orientation.json. Changing camera orientation invalidates previous image-size shooting calibration; collect a new successful setup.

Portrait standoff preserves the previous target pixel size relative to the short edge: Approach uses 11.25% portrait height (equivalent to 20% landscape height), with a 14.06% portrait stop limit. Rotation does not permit approaching closer simply because the image is taller.

Shooting setup now expands within the right control column, with no centered popup or dimming over the cameras. The setup includes its own Stop button.
