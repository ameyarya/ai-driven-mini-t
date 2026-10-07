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

## Physical bullseye standoff update

Physical Approach now targets 20% image height; goals above 20% are rejected,
forward pulses are capped at 250 ms, and observations at 25% or larger stop
all physical bullseye missions. These limits are image-size proxies for this
stand, not calibrated centimeters or general obstacle avoidance. A shooting
setup must be saved at 20% or less. Complete mission requires the saved setup.
The former 50% physical approach was too close in a real browser test and was
stopped without firing. Historical can/simulation setpoints remain unchanged.

The setup dialog groups reference, adjustment, test/save and enabling into four steps. Height pulse timing changes elevation; the separate 350 ms firing pulse remains unchanged. Testing firing duration against range is future work and should hold height and distance constant.

Upright stream (rotation 0): the sensor streams upright 720×960 portrait, verified from an unfiltered RTMP snapshot on 2026-10-06, so no rotation is applied. Live view needs no CSS rotation; snapshots and shot clips stay 640×854 upright. Rotation remains configured in camera-orientation.json.

Upright standoff preserves the same physical stand distance (72 px target height): Approach uses 8.43% image height, with a 10.54% stop limit. Saved setups were rescaled ×0.7494 on 2026-10-06 (preset 10.4% → 7.79%) without moving the tank; confirm with one test shot before trusting the converted preset.
