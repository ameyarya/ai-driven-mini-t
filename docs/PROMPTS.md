# AI-Driven Mini-T prompts

Can missions use generic **can** detection and ignore color entirely.

## Center a visible target

> Position the can in the center

## Search in place, then center

> Find the can by doing 360 turn in place

Search is bounded; exact 360° coverage is uncalibrated. The standalone search
finishes with the can fully visible and centered.

## Approach a visible target

> Move closer to the can until it occupies roughly 50% of the image height.
> Keep it centered, then stop.

## Search and approach in one mission

> Find the can by turning in place. Center it, then move closer until it
> occupies roughly 50% of the image height. Keep it centered, then stop.

Combined missions are implemented but still undergoing physical testing.
Distant targets can be roughly aligned before approaching; alignment tightens
as the target grows. Missed detections stop movement before retry/reacquisition.

## One-shot firing (implemented, physical test pending)

> Center the can, then shoot once.

> Find the can by turning in place, then approach until it occupies
> 50% of image height. Keep it centered, then shoot once.

The host supports a single fire/reset command after stationary confirmation.
It records evidence and stops with **hit unconfirmed**. Elevation/range and
visual impact verification are not implemented. The current fine-tuned adapter
still refuses firing; use the original planner for these new missions.
See [shooting and simulation](SHOOTING_SIMULATION.md).

The original unedited prompt list is preserved in the Git-ignored local archive.

## Simulator launcher controls

At localhost:8002, use Launcher ↑/↓ or keys 1/2 before firing. Navigation
goals do not select elevation; shots use the current manual setting. Reset
returns to 0°. This is uncalibrated simulation, not physical aiming.

## Obstacle simulator

At localhost:8002, select an obstacle scene and press **Avoid & approach · map
oracle**. This dedicated button runs a fixed avoid/approach/stop task without
Qwen; the goal text box does not configure this controller. Start still runs
the existing mission planner and does not add obstacle route planning.
Use Stop to cancel, or select Clear and Reset to resume the usual missions.
See [obstacle avoidance](OBSTACLE_AVOIDANCE.md).

## Generic can: point and shoot

Find the can, center it, then shoot once and stop.

Can detection ignores color. This mission searches and aligns without approaching, then issues one fire command. It does not automatically adjust launcher elevation or confirm a physical hit.

## Dashboard action buttons

The physical dashboard replaces free text with Find, Align, Approach and Shoot. Each starts a separate mission and stops afterward. Find searches and centers, Align centers a visible can, Approach aligns and reaches 50% image height, Shoot aligns and fires once. Stop cancels. Buttons are disabled during a mission or camera outage; arrow keys remain available while idle.

## Complete mission button

Find the can by turning in place, then approach until it occupies 50% of image height. Keep it centered, then shoot once and stop.

Uses the existing combined search/approach/shoot controller. It does not add physical obstacle avoidance, automatic launcher elevation or confirmed-hit detection.

## Current dashboard target: bullseye

The physical action buttons now substitute **bullseye** for can in the above missions. Complete mission searches, approaches until the matched bullseye square occupies 50% of image height, aligns, then fires once. Historical can prompts and simulation fixtures remain for regression testing. Detection uses a private grayscale reference matcher rather than YOLO-World for this drawing.

## Shoot with calibrated height

Shoot also selects vertical height when auto aim is enabled in Launcher height calibration. It requires a confirmed reference and successful samples; unsupported target sizes stop without firing. Test shot uses the current manually nudged height with auto aim off. See [calibration workflow](ELEVATION_CALIBRATION.md).

## Physical bullseye standoff update

Physical Approach now targets 20% image height; goals above 20% are rejected,
forward pulses are capped at 250 ms, and observations at 25% or larger stop
all physical bullseye missions. These limits are image-size proxies for this
stand, not calibrated centimeters or general obstacle avoidance. A shooting
setup must be saved at 20% or less. Complete mission requires the saved setup.
The former 50% physical approach was too close in a real browser test and was
stopped without firing. Historical can/simulation setpoints remain unchanged.

Current physical UI: **Aim & shoot** uses a saved, user-confirmed successful
shooting setup (20% image height or less), approaches that size, restores timed
launcher height and fires once. Without a setup it stays disabled. **Test shot**
only aligns horizontally and fires at the selected height, without approaching.
