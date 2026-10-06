# Launcher height calibration workflow

The receiver exposes launcher elevation **speed**, not its angle. Automatic
vertical aiming is therefore an experimental timed-offset lookup, relative to
a reference height you physically restore and confirm. It is not a measured
servo angle or a ballistic model.

## Collect a profile

1. Open **Launcher height calibration** on the physical dashboard.
2. Physically restore a repeatable reference launcher height, with the same
   camera/launcher mounting, then press **Confirm reference height**. This
   declares the current height to be zero; it does not move or home the servo.
3. Use **Up / Down · 50 ms** to adjust height while observing the mechanism.
4. Press **Test shot at current height**. It aligns horizontally and attempts
   one bounded shot at the selected height, recording video and ammunition use.
5. Only if you observe the target falling or lying on the floor, press
   **Save last shot as confirmed hit**. Misses are not calibration samples.
6. At a different distance/target image size, repeat. Restore the target after
   a hit. At least two successful sizes, separated by three image-height
   percentage points, are required. Keep the same physical target and reference.
7. Press **Enable auto aim**. Shoot then aligns, interpolates the timed height
   offset, adjusts it, captures a fresh frame and rechecks visibility, center
   and target size before one shot.

Auto aim refuses to extrapolate outside the successful sample range. If a
height adjustment fails or is cancelled, the reference is invalidated. Moving
height through legacy keyboard/manual controls also invalidates it. The existing
Stop, six-attempt ledger, recording and shot-reset safeguards remain.

Samples are saved privately in `playground-data/elevation-calibration.json`.
Each records a completed shot ID, apparent target height and timed elevation
offset. Samples persist; reference confirmation and auto aim do **not** persist
across server restart. Restore the same reference physically before re-enabling.
If mounting, target dimensions, actuator speed or reference height change,
existing samples are no longer applicable; collect a new profile.

The camera size measurement covers the matched bullseye square, not the stand.
The control uses 100 ms maximum elevation chunks, and limits offsets to ±600 ms
from reference. These are host motion bounds, not measured mechanical endpoints.
Do not continue nudging at a physical travel stop.

**I reloaded six projectiles** acknowledges an actual physical reload and resets
the attempt ledger. It does not sense ammunition. The panel shows attempts left.
Do not use that acknowledgment merely to clear a limit without reloading.

## Verification and limits

Seven unit tests cover interpolation/range rejection, required reference and
samples, restart behavior, bounded movement, cancellation, command failures and
confirmed-shot validation. The full host suite passes 89 tests. UI inspection
verified the controls and that movement/test-shot controls are disabled before
reference confirmation. No shots were fired while implementing this workflow.

Two successful points enable interpolation but do not establish reliability.
Backlash, battery/surface changes and timed servo drift remain unmeasured;
physical automatic elevation acceptance is pending. Existing first physical
bullseye hit used the previous unchanged height and is **not** silently imported
as a calibration point. Hit confirmation here is explicitly supplied by the
user; automatic visual impact classification remains unimplemented.
