# Project status

Updated 2026-10-01.

## Active platform

CyberBrick Mini-T tank with DJI Action 5 Pro video and local Qwen3-VL 4B
Instruct on an M4 Mac. Focus is a working vision/navigation POC, with camera
hardware changes and convenience improvements deferred.

## Completed

- Hold-to-drive arrows, stop on release, corrected turning directions.
- Ground-tested track compensation: left track approximately 18% slower during
  forward/reverse. Full requested drive speed retained.
- ESP-NOW link from Mac USB transmitter to battery-powered tank receiver.
- Manual launcher controls: 1/2 elevation, Space fire, Escape stop/reset.
- Signed wireless Python application updates and rollback.
- DJI Mimo RTMP stream into MediaMTX and embedded browser video.
- Local model installation and real camera-frame question answering.
- Dashboard direct answer, scene, movement advice, uncertainty, and snapshot age.

## Latest experiment

A Coca-Cola can was placed to the right of the tank camera. The initial movement
schema biased the response toward FORWARD. Added a direct answer field and prompt
instructions that distinguish image position from movement. Repeating the same
question returned **right**, with movement suggestion **stop**, in 10.57 seconds.
No model-triggered movement or firing occurred.

## Next

1. Check target recognition and left/centre/right consistency across views.
2. Measure analysis latency and stale-frame behavior.
3. Add bounded target-centering turns with stop and manual override.
4. Add obstacle-aware navigation toward a simple goal.
5. Consider launcher aiming only after camera/launcher alignment is calibrated.

## Paused investigations

**HAIBOXING 18859 truck:** steering servo works with spare CyberBrick at tested
±30° travel. Drive remains disabled. CyberBrick shield per-port current limits
and the truck's 380 motor startup/stall current are unverified. No motor wires
cut. A more capable MCU does not replace a suitably rated motor driver.

**Ascend ASC-2600 drone camera:** electrical/protocol compatibility for standalone
reuse remains unknown. No camera transplant performed.

**Phone-free DJI streaming:** USB webcam mode works, but the POC retains Mimo
wireless streaming to avoid introducing another hardware project.

## Limits

The model advises by default. The new can-centering goal can execute bounded
turns when started. General navigation, automatic firing, and obstacle avoidance
are not implemented. Video delay is about one second; initial model responses
are around 10–12 seconds. Single images do not establish accurate range or
collision clearance. Hardware backups, signing keys, captured frames, and personal
images remain outside the public repository.

## Laya suitability review

Reviewed https://github.com/NandhaKishorM/laya . Laya is a local text-based
System 1 decision engine with typed choices/scores/yes-no outputs, not a camera
vision replacement. Could consume a scene description or detector output, but
adding it after Qwen would not remove the existing image-analysis latency. Its
advertised 33 ms is a project benchmark, not a measured rover/M4 result.
No installation or integration performed. Keep current POC until a concrete
decision-layer need emerges; can-centering from measured image coordinates can
also use direct control rules.

## First autonomous goal implemented

Goal: turn until the Coca-Cola can is centred in the camera image, then stop.
Dashboard Start goal/Stop goal controls activate a background turn/observe loop.
Qwen supplies target_position and suggested_action; controller checks agreement
and executes only left/right, with 150 ms host pulses at 40% drive setting.
Explicit stop and 1.5 second settling wait separate observations. Centre is
prompted as the middle 10% of image width. No forward, backward, or automatic
launcher commands. Manual controls retain full requested speed.

Manual commands/Escape cancel the goal. Browser blur/hide/close requests stop;
a five-second heartbeat lease blocks subsequent turns after disconnection.
Stops on missing/uncertain target, position/action disagreement, assessment age
over 25 seconds, camera stream loss, errors, or eight-observation limit. Existing
receiver 500 ms watchdog remains the independent fallback. A frozen-but-connected
video source is not yet detected. No arbitrary autonomous goals supported yet.

Seven controller tests passed: centred completion, missing/uncertain stop, turn
then centre, manual cancellation during inference, step cap, stale frame rejection,
and browser lease expiry. Python/JavaScript syntax checked. Physical centering
accuracy awaits user-initiated dashboard test; no autonomous test movement issued
by the development agent.

## Dashboard simplified and camera battery limit

Simplified the default page to live video, fixed can-centering goal Start/Stop,
one autonomy status, and compact manual driving controls. Launcher, visual
questions, snapshot, and detailed model output are collapsed by default.
DOM IDs and JavaScript syntax verified; no controller behavior changed.
User reports DJI battery died during livestream testing. Controller status was
"Camera stream lost; autonomous turn cancelled" at step 1. Recharge camera and
restart Mimo stream before continuing physical centering tests. External USB
power is a possible longer-test option, not yet tested on the rover.

Dashboard now uses the browser viewport height: smaller adaptive camera feed,
compact controls, and expanded detail panels overlay the sidebar instead of
increasing page height. Page-level scrolling is disabled; long optional model
details can scroll inside their overlay. Controller behavior is unchanged.

## User-defined navigation goals

Replaced fixed can-centering goal with an empty Navigation goal input passed to
Qwen. General controller supports forward/backward/left/right/stop. Each model
response includes goal_achieved; loop uses recent executed actions, sends one
150 ms movement pulse, stops, waits for video, and analyzes again. Completes
only when Qwen reports goal achieved without blocking uncertainty. Stops on
explicit STOP, uncertainty, invalid output, stale assessment, lost camera/browser,
manual override, errors, or a 40-observation cap. Short autonomous moves remain
at 40%; manual speed remains 100%. Launcher remains manual. Nine tests pass,
including all four movement mappings and empty-goal rejection. General navigation
on hardware remains unverified; camera battery recharge is pending.

Aligned camera frame and control column to the same viewport-constrained height;
video-delay caption overlays the camera instead of adding height below it.

Manual driving/launcher widgets hidden from the dashboard; keyboard driving,
launcher shortcuts, and Escape override remain available.

Removed the Launcher section from the dashboard markup.

## Camera availability and clearer progress

Added /camera/status to report MediaMTX stream readiness. Dashboard shows
Camera live/offline; Start remains disabled while offline, and server rejects
starts without a live source. Camera status polling requests cancellation when
the source disappears. This detects stream availability, not a frozen image.
Run status now explicitly shows analyzing, moving, waiting for video, completion,
stopped, or error, with the most recent action retained between observations.
Latest model decision and reason are visible without opening detailed results.
Viewport-sized layout and hidden manual widgets are preserved. Nine controller
tests and JavaScript/Python syntax checks passed.

Moved camera questions to an empty text box in the top toolbar. Detailed model
results now open in a separate overlay; right column stays focused on navigation.
JavaScript syntax and required element IDs verified.

Removed the camera question input and Ask action from the page; navigation goal
and model results remain. Standalone backend analysis is retained for later use.

Removed Model results button and expandable panel. Latest decision remains
visible; detailed renderer fields are hidden to preserve existing polling.

## Runs persist independently of browser focus

User requested autonomous goals continue when leaving the tab and ignore arrow
keys. Removed browser heartbeat expiry as a cancellation condition; blur, hiding,
closing, and UI polling failures no longer cancel autonomous goals. Manual
commands are rejected while a goal is active; keyboard inputs are ignored during
autonomy. Stop button cancels. Goal completion, uncertainty, camera loss, errors,
and the 40-observation limit still stop the controller. Nine tests pass, including
continued navigation after browser lease expiry and explicit cancellation.

## Target POC mission: find, approach, aim, and shoot

User-defined end-to-end goal:

1. Quickly scan the surroundings through a full 360° tank rotation to locate a
   Coca-Cola can. The goal is fast target acquisition rather than waiting for
   a long model response after every tiny search turn.
2. Once found, turn toward the can and advance toward it.
3. Centre the can in the camera view and position the tank for shooting. Camera
   centering alone does not establish launcher aim; camera-to-launcher alignment,
   useful shooting distance, and launcher elevation need physical calibration.
4. Fire at the can and observe the result.
5. Shooting has **six turns**, as specified by the user. Meaning pending: six
   firing attempts, six available projectiles, or another six-turn mechanism.
   Do not silently interpret this as six confirmed shots or automatic refills.

This is the desired POC, not a claim about current capabilities. Current
autonomy supports bounded navigation actions and visual reassessment, but does
not autonomously fire, measure a full 360° rotation, estimate calibrated shooting
distance, or verify projectile hits. No code/control changes made during the
current running test.

The control interface should support these mission stages and their required
actions rather than constrain every task to one narrow centering response. A
structured response can remain extensible (stage, next action, target observation,
completion, and reason); short output need not restrict the mission itself.
Firing control and its six-turn interpretation must be added explicitly later.
