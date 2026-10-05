# Combined mission simulation regression

A 31-case headless MuJoCo matrix exercises **find → align → obstacle-aware
approach → final visual alignment/approach → one shot**. All 31 checks passed:
24 reachable missions produced projectile–can contact, and seven negative
cases stopped without a new shot. There were zero tank/launcher–obstacle
geometry overlaps across the matrix.

The test harness chains existing controllers without resetting the scene
between stages. This is not a new integrated dashboard goal mode. Search and
final firing use the production visual controller with ideal segmentation;
avoidance uses the existing perfect-map A* controller and perfect pose. Qwen
is not called. Launcher elevation stays at its initial 0°; automatic ballistic
or elevation aiming is not tested or implemented by this suite.

## Cases and evidence

| Cases | Expected result | Observed |
| --- | --- | --- |
| 24 reachable detours | One projectile contact each | 24 hits |
| Enclosed tank and occluding wall | Bounded search stop, no firing | 2 stops |
| Destination inside inflated obstacle | Route rejection, no firing | 1 stop |
| Cancel during search, avoidance, final shot stage | No later movement or firing | 3 cancellations |
| Six prior attempt fixtures | Reject another shot | 1 rejection |

Reachable cases vary target distance (1.2–1.5 m), left/right offsets (±0.7 m),
and headings initially facing away from the can. Twelve include a second
static obstacle. Every case records stage decisions, positions, observations,
terminal status, clearance, overlaps and new shots in the
[public report](combined-simulation-results.json).

The cancellation cases apply the same `plan=None` state change as the HTTP
Stop handler and verify that a stale step cannot move or fire. They are
controller-state tests, not browser race or HTTP transport checks. The ammo
case seeds six prior attempts without launching six projectiles; it verifies
the simulator's shot limit and preservation across stage transitions, not the
physical receiver or host's durable shot ledger.

Obstacle overlaps use the simulator's independent `mj_geomDistance` monitor,
including tank and launcher geometry. The clearance summary samples stage
steps; the existing movement guard additionally checks each translation
substep. The suite does not substitute automatic MuJoCo contact counts for
mocap/static collision evidence.

## Reproduce in cloud

From the repository root, with `.sim-venv` installed:

```sh
mkdir -p /workspace/.cache/mesa
MUJOCO_GL=egl MESA_SHADER_CACHE_DIR=/workspace/.cache/mesa \
  .sim-venv/bin/python simulation/combined_matrix.py
```

On a Mac, use `.sim-venv/bin/python simulation/combined_matrix.py` with the
normal graphics backend. No running simulation server is needed: the runner
owns a separate scene. It exits nonzero if any checked case fails. By default,
results go to ignored `playground-data/simulation/combined-matrix.json`.
To deliberately refresh the public report, pass
`--output docs/combined-simulation-results.json`.

Related regressions:

```sh
.venv/bin/python -m unittest test_rover_autonomy test_rover_vision_labeled \
  test_rover_fast_navigation test_rover_playground test_rover_training test_rover_shooting
(cd simulation && ../.sim-venv/bin/python -m unittest test_sim test_obstacles)
```

The cloud rerun passed 79 host and 20 simulator tests. Existing browser and
HTTP matrices were not rerun for this addition; their prior results remain
separate evidence.

## Limits

These are selected deterministic synthetic cases with static rectangles,
perfect localization and segmentation, and uncalibrated kinematic tracks and
projectile physics. They do not test obstacle perception, localization noise,
moving obstacles, learned planning, real Qwen inference or physical reliability.
Search is bounded rather than a calibrated full 360° rotation. Full integrated
mission support and physical acceptance remain separate work.
