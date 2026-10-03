# Project status

Updated 2026-10-02.

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
source is downloaded locally; a CUDA LoRA launcher is prepared. No weights have
been trained. This is recorded-scene testing, not a physics simulator.
See [setup and limitations](PLAYGROUND.md).

## Bounds and remaining work

- Exact 360° coverage remains uncalibrated; search has explicit time/step bounds.
- No obstacle avoidance, calibrated physical ranging, or autonomous firing yet.
- Receiver watchdog, Stop, stale-frame checks, clipping/ambiguity checks,
  wrong-way turn checks, and 40-step limit remain active.
- Live capture plus controller observation was around two seconds in recorded
  tests; the 1.5-second settling wait and movement time are additional.
- 56 navigation/vision/playground tests pass. Hardware behavior still needs physical
  checks; unit tests are not a substitute for successful tank runs.

## Workspace

All project source, private runtime data, environments, and preserved historical
files now live inside this repo folder. Private assets remain Git-ignored.
See [workspace layout](WORKSPACE.md), [prompts](PROMPTS.md), and [ideas](IDEAS.md).

Truck steering, the drone camera transplant, and phone-free DJI streaming remain
paused investigations; their scripts and backups were preserved in the local archive.
