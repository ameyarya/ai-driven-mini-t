# One-distance shooting setup

Open **Shooting setup**. Physically restore a repeatable launcher reference and
confirm it. This button declares the current position; it does not home the servo.
Adjust Up/Down, then use **Test shot at current height** (horizontal alignment
and one shot). Only after observing a hit, choose **Save successful shooting setup**.
This saves target image height and timed launcher offset, and enables the setup.

**Aim & shoot** approaches that saved apparent target size, centers the bullseye,
restores the saved launcher offset, checks a fresh image, and fires once. It pauses
for human confirmation afterward; automatic fall/hit recognition is not implemented.
It never retries a shot automatically. The durable six-attempt limit remains;
**I reloaded six projectiles** requires an actual reload.

Only one successful shot is required. Saving another replaces the active preset.
The final size must be within three percentage points of the saved size. This is
an image-based shooting distance proxy, not physical range or ballistic prediction.
Keep the same target, camera mounting and launcher reference.

Saved settings persist privately in playground-data/elevation-calibration.json.
After restart, physically restore and confirm the same reference, then choose
**Use saved setup**. Manual height controls, cancelled or failed movements invalidate
the reference. Servo timing drift and backlash remain unmeasured. Height moves
are bounded to ±600 ms from reference, in chunks up to 100 ms.

No physical shots were fired to implement this simplified workflow.
