# One-shot missions and MuJoCo

## Physical tank support

The host mission controller now supports `shoot`, `find_shoot`,
`approach_shoot`, and `find_approach_shoot`. Each mission issues at most one
fire/reset command, after confirming one fully visible can in two stationary
observations. Approach still requires an explicit image-height percentage;
search and approach cannot be silently omitted. Automatic repeat-fire and
"keep shooting until hit" requests are rejected.

The existing signed CyberBrick launcher API is reused. No receiver firmware
update is needed. The tracks stop before firing. Launcher actuation defaults
to a 350 ms hold, configurable with `ROOK_FIRE_PULSE_MS=100..450`; this is an
unverified starting value, below the receiver's 500 ms auxiliary watchdog.
This holds the existing angular fire servo, then returns it to its reset angle.
It does not estimate elevation or ballistic range from the image.

Six automatic **attempts**, not six sensor-confirmed shots, are allowed before
explicit reload acknowledgment. Attempts are durably reserved before sending,
including uncertain transmissions; missing acknowledgments never trigger an
automatic retry. The ledger and six-second evidence clips stay private under
`playground-data/shots/`. An acknowledgment confirms the receiver's requested
servo state, not projectile release or impact. Manual commands are not included
in this automatic attempt counter, so it is not an ammunition sensor.

The controller reports **fire command finished; hit unconfirmed**, and stops.
It does not claim mission success from merely sending a fire command. The
recording starts before actuation; inspect its completion and contents before
using it as evidence. Automated visual shot/hit classification is not implemented
yet. Stop remains available during recording/actuation and resets the launcher.

After physically reloading, while autonomous control is stopped:

```sh
curl -X POST http://localhost:8000/shots/reloaded \
  -H 'Content-Type: application/json' -d '{"reloaded":true}'
```

The previous ledger is archived locally. No physical firing test was performed
during this implementation because the rover was unavailable. Launcher hold
time, elevation, alignment and real impact detection still require validation.

## MuJoCo playground

Open **http://localhost:8002**. Start the service with:

```sh
tools/detector-python/cpython-3.12-macos-aarch64-none/bin/python3.12 -m venv .sim-venv
.sim-venv/bin/python -m pip install -r simulation/requirements.txt
.sim-venv/bin/python simulation/server.py
```

The scene has a kinematically driven toy tank, onboard RGB camera, free-body
can and projectile, gravity, and collision detection. In-place rotation changes
heading without translation. Projectile–can contact is the hit ground truth;
can displacement alone is not used to claim a hit. Six simulated shots are
available per reset. Speed, mass, friction, dimensions, field of view and launch
angle are illustrative and have not been calibrated to the physical tank.

The default **Controller preview · no Qwen** translates supported goal keywords
to a mission and runs the same visual controller as the tank. It does not
exercise Qwen or train weights. The selectable **Original Qwen · Ollama** mode
uses the real production planner prompt, schema and labeled simulated image.
It is blocked until the all-frame benchmark finishes, to avoid competing model
allocations on the 16 GB Mac. No simulator code imports the serial server or
sends hardware commands.

Measurements come from ideal MuJoCo segmentation, explicitly labeled
**SIM ORACLE**, not YOLO or Qwen detection. Hit ground truth is withheld from
the planner. This separates controller/physics tests from perception tests;
it does not establish that the real detector recognizes rendered or real cans.
Qwen planner requests and exact input images are saved privately when used.

Example one-shot mission:

> Find the red can by turning in place, then approach until it occupies
> 50% of image height. Keep it centered, then shoot once.

## Verification

- 79 host unit tests pass, including cancellation, durable six-attempt limits,
  lost acknowledgments, one-shot execution and rejection of omitted missions.
- Four physics tests pass, including a 100-case aligned/misaligned projectile
  contact sweep. These are deterministic synthetic cases, not a reliability
  estimate in real rooms.
- Four scripted shooting missions reach contact in the initial off-center
  scene: center/fire (3 observations), find/fire (4), approach/fire (11),
  find/approach/fire (13). Qwen was not called in these mission checks.
- Six isolated headless Chrome checks pass: both camera views, laptop screen
  fit, firing/contact result, Stop, reset/reload, and no uncaught JS errors.

```sh
python3 -m unittest test_rover_shooting test_rover_autonomy \
  test_rover_vision_labeled test_rover_fast_navigation test_rover_playground test_rover_training
(cd simulation && ../.sim-venv/bin/python -m unittest test_sim)
node simulation/browser_test.mjs
```

Simulation exposed nonlinear approach overshoot: a linear image-height gain
made the tank advance too far near the can. Forward timing now estimates gain
in inverse apparent height, consistent with pinhole perspective. Turn timing
and pulse bounds are unchanged. This correction is verified in simulation and
unit tests; fresh physical navigation validation remains outstanding.

## Expanded localhost:8002 checks

The HTTP matrix now covers **100 missions** across 20 placements, including
initial headings facing away from the can. All 100 scenarios passed the
checked invariants: termination, step bound, at most one shot, no unrequested
fire and stopping on an absent target for goals without search. Eight HTTP
checks cover invalid actions/durations, unsupported goals, seventh-shot
rejection and Stop cancellation.

| Mission | Cases | Navigation completions | Shots / contact hits | Stops |
| --- | ---: | ---: | ---: | ---: |
| Center | 20 | 10 | 0 / 0 | 10 |
| Find then center | 20 | 20 | 0 / 0 | 0 |
| Approach to 50% height | 20 | 10 | 0 / 0 | 10 |
| Center then fire | 20 | — | 10 / 8 | 10 |
| Find, approach, fire | 20 | — | 20 / 20 | 0 |

The 30 stops occur when the target is behind the tank and the mission does not
request search. The two direct-fire misses expose uncalibrated range/aim; a
successful controller command is not automatically a successful shot.

**Real original-Qwen planning**, through the same HTTP service, also completes
all four firing mission types in the initial off-center scene, each issuing one
shot and producing simulator contact. These four cases are not diverse-scene
model validation. Qwen plans the mission; physics supplies the contact result.
The initial first request took 21.52 seconds including model startup; following
requests took 5.40–5.75 seconds. After the target-schema correction, the repeated
four mission requests took 3.84–4.33 seconds with the model already loaded.
These request times are not a controlled speed benchmark.

The broader tests found and fixed two bugs: find-and-center goals were treated
as center-only without the words search/360, and Qwen sometimes named the
"SIM ORACLE" overlay as the firing target. The latter was rejected before
firing. Shooting now constrains the target field to the supported red soda can;
unsupported/unnamed goals still fail validation. Both the scripted and real-Qwen
browser paths pass all six checks after correction.

```sh
python3 simulation/http_matrix.py
python3 simulation/http_matrix.py --qwen-smoke
ROOK_SIM_BACKEND=ollama node simulation/browser_test.mjs
```

Run sequentially: the matrix resets and mutates the shared simulator scene.
[Aggregate simulator results](simulation-results.json) omit captured images.

## Fine-tuning boundary

The current `adapter-v1` was trained to **refuse shooting**. It is not a
shooting-capable adapter, and this change does not retrain it. The all-frame
comparison continues with its frozen pre-shooting planner contract and labels.
Its benchmark scores should not be read as results for the new firing modes.

Next, collect rendered before/after sequences and contact ground truth, test
visual hit/miss/uncertain judgments independently, then build a separately
versioned shooting dataset. Keep held-out scenes and launch parameters outside
training. Simulation does not automatically fine-tune Qwen or replace physical
launcher and camera validation.
