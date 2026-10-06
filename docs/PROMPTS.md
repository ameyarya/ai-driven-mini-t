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
