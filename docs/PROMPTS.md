# Rover prompts

## Center a visible target

> Position red can in center

## Search in place, then center

> Find the red can by doing 360 turn in place

Search is bounded; exact 360° coverage is uncalibrated. The standalone search
finishes with the can fully visible and centered.

## Approach a visible target

> Move closer to the red can until it occupies roughly 50% of the image height.
> Keep it centered, then stop.

## Search and approach in one mission

> Find the red can by turning in place. Center it, then move closer until it
> occupies roughly 50% of the image height. Keep it centered, then stop.

Combined missions are implemented but still undergoing physical testing.
Distant targets can be roughly aligned before approaching; alignment tightens
as the target grows. Missed detections stop movement before retry/reacquisition.

## Planned: firing

> Shoot at the can

Autonomous firing is not implemented. This prompt currently fails explicitly;
launcher aiming/calibration and a controlled firing stage remain future work.

The original unedited prompt list is preserved in the Git-ignored local archive.
