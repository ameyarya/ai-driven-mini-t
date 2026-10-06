# AI-Driven Mini-T feature checklist

An AI brain for a mini toy tank.

Updated: 2026-10-04. Edit this file to add, remove, or reprioritize features.
Checked items are implemented; validation notes distinguish physical tests
from simulation or software tests. Unchecked items remain unfinished.

## Tank controls

- [x] Wireless control: Mac → USB CyberBrick transmitter → ESP-NOW tank receiver.
- [x] Hold arrow keys to drive; release to stop. Physically tested.
- [x] Correct left/right directions and 18% left-track speed compensation. Physically tested.
- [x] Manual launcher up/down with keys 1/2. Physically tested.
- [x] Manual fire/reset with Space. Physically tested.
- [x] Signed wireless receiver application updates and rollback.
- [x] Receiver watchdogs and bounded movement/launcher commands.

## Camera and interface

- [x] DJI/Mimo live camera feed through MediaMTX.
- [x] Compact dashboard with an editable goal and Start/Stop controls.
- [x] Separate live view and exact labeled image supplied to the planner/controller.
- [x] Independent can detector: bounding box, position, image-height percentage,
  clipping and ambiguity checks.
- [x] Image labels/grid, frame age, movement duration and decision status.
- [x] Autonomous run continues when the browser tab loses focus.
- [ ] Calibrated physical distance and angle measurements.

## Autonomous navigation

- [x] Local Qwen3-VL 4B goal planning with validated structured output.
- [x] Python move → stop → observe feedback loop using fresh detections.
- [x] Adaptive turn and approach timing rather than one fixed pulse length.
- [x] Center the can. Physically tested.
- [x] Approach to a requested percentage of image height. Physically tested;
  the latest inverse-height timing change still needs a physical retest.
- [x] Turn-in-place search for the can. Physically tested; exact 360° coverage is uncalibrated.
- [x] Combined search → approximate alignment → approach → final alignment.
  Implemented and simulation-tested; physical runs have not yet completed reliably.
- [x] Bounded target-loss recovery, stale-frame checks, Stop and step/search limits.
- [ ] Calibrate search rotation and verify full 360° coverage.
- [x] Simulation-only obstacle avoidance using a known map, A* routes and a footprint guard.
  100 scenarios: 80 reached, 20 blocked stops, zero obstacle contacts.
- [ ] Real obstacle sensing and avoidance on the physical tank.

## Autonomous shooting

- [x] One-shot stage after alignment, with bounded fire/reset commands.
  Implemented and simulation-tested; automatic physical firing is untested.
- [x] Persistent limit of six automatic attempts before explicit reload acknowledgment.
- [x] Record shot evidence without claiming that a command acknowledgment proves a hit.
- [ ] Automatic launcher elevation/aiming.
- [ ] Calibrate physical firing range, elevation and firing duration.
- [ ] Detect actual projectile release from camera evidence.
- [ ] Classify hit, miss or uncertain from camera evidence.
- [ ] Automatic retry strategy within the remaining ammunition budget.

## Testing and simulation

- [x] Saved-frame offline playground, independent of physical hardware.
- [x] Local MLX QLoRA planner adapter experiment and original/adapter comparison.
  Adapter-v1 still refuses firing and has recorded regressions; it is not deployed on the tank.
- [x] Full saved-frame benchmark: 8,232 calls, results published.
- [x] MuJoCo tank, camera, can and projectile-contact simulation.
- [x] Scripted controller and optional original-Qwen planner backends.
- [x] Simulated launcher up/down, visible barrel angle and matching shot trajectory.
- [x] Simulation launcher buttons and keys 1/2, angle limits and reset.
- [x] Ten physics tests covering 200 deterministic projectile scenarios.
- [x] 100 scripted mission regression cases and eight existing API guards.
- [x] Twelve launcher API checks and thirteen scripted browser checks.
- [x] Four original-Qwen shooting plans tested in simulation on one initial scene.
- [x] 79 host tests.
- [x] GIF/MP4 simulation demonstrations and public result summaries in the README.
- [ ] Simulator calibration against real track and launcher measurements.
- [x] Obstacle scenarios, ideal range readings, blocked-route stops and browser controls.
  Ten obstacle tests plus the existing ten physics tests pass; 19 browser checks pass.
- [x] Scripted combined search/alignment/avoidance/approach/shot regression: 31 cases,
  24 simulated contact hits and seven expected stops/cancellations; perfect-map inputs.
- [ ] Broader Qwen-driven simulation testing across varied scenes and target positions.

## Physical acceptance tests still pending

- [ ] Retest approach timing after the latest controller change.
- [ ] Reliably complete search → align → approach on the real tank.
- [ ] Supervised automatic single-shot firing test.
- [ ] Complete find → approach → aim → shoot on the real tank.
- [ ] Verify real-world Stop, target-loss and stale-video behavior for the complete mission.
- [ ] Record a real-tank demonstration and publish its results.

## Scope decisions / future projects

These are not requirements for finishing the current tank mission.

- [ ] Decide whether general-object navigation belongs in AI-Driven Mini-T.
- [ ] Decide whether a Mac/phone-free tank is a future AI-Driven Mini-T milestone.
- [ ] Muse charm — separate project.
- [ ] Wheeled desk buddy with camera/speaker/display — separate project.
- [ ] Home rover for the dog — separate project.

## Your additions and priorities

- [ ] 

Evidence and limitations: [status](docs/STATUS.md),
[simulation tests](docs/SHOOTING_SIMULATION.md),
[launcher results](docs/launcher-simulation-results.json),
[planner comparison](docs/FULL_PLANNER_COMPARISON.md).
