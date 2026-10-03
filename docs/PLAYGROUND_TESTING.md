# Offline headless testing results

Tested October 2, 2026, on the development Mac using installed Google Chrome
in headless mode, an isolated browser profile, and real local Qwen3-VL 4B.
No camera, serial port, or physical motor commands were used.

## Results after fixes

| Layer | Coverage | Result |
| --- | --- | --- |
| Python tests | Navigation, image identity, playground review/export and request isolation | 60/60 passed |
| Headless Chrome | Catalog/image loading, button states, stale result clearing, invalid requests, browser exceptions | 37/37 passed |
| Recorded-scene controller replay | 196 recorded frames × 4 controller modes | 784/784 invariant checks passed |
| Real Qwen planner | 4 scene types × 7 goal types | 12/28 met the expected planning contract |

Scene types were target left, right, centered, and missing. Goal types were
center, approach to 50% image height, find, find-then-approach, shoot, move away,
and physical distance. The missing-target approach correctly returned an
explicit refusal and counts as a pass; refusal does not require a 50% setpoint.

The browser matrix ran twice, before and after fixes (56 real Qwen calls total).
The final run’s median end-to-end inference was approximately 3.75 seconds on
this warmed local model. This is not directly comparable with live capture/drive
latency or the older whole-mission benchmarks.

## Model findings

- Visible-target approach, search, and combined goal modes were interpreted
  correctly, as were missing-target search and combined goals.
- All four centering-only goals were incorrectly translated into search or
  search-and-approach modes.
- Shooting, moving away and physical-distance requests were not explicitly
  labeled unsupported by Qwen in these cases. Python rejected them instead.
- The remaining 16 incorrect plans were blocked after the validator fixes.
  That demonstrates rejection behavior, not an improvement in model reasoning.
- Some generated explanations falsely described off-center targets as centered.
  The mode/setpoint checks do not score explanation accuracy or vision quality.

## Bugs fixed during testing

1. Reject a planner changing a centering-only goal into another mission.
2. Reject requests expressed in physical distance units regardless of the
   mission mode Qwen proposes. Image-height approach remains supported.
3. Resolve the playground’s model transport and persist its result while holding
   the request lock, avoiding nested patched transports between concurrent tests.

Regression tests cover these checks. Original saved frames and camera logs were
preserved. No generated output was approved as training ground truth.

## Reproduce

```sh
python3 rover_playground.py
# In a second terminal:
node experiments/playground_browser_test.mjs
python3 experiments/playground_controller_replay.py
python3 -m unittest test_rover_playground test_rover_autonomy \
  test_rover_vision_labeled test_rover_fast_navigation
```

Detailed reports, model outputs and screenshots are stored locally under
`playground-data/` and excluded from Git. The runner uses Node 22+ and the
installed macOS Chrome executable. Only its isolated test browser is closed.

This is a broad regression suite, not “all possible” prompts or a trained-model
benchmark. Controller replay checks bounds and prerequisites; it does not
simulate how motors change future images or prove physical mission completion.
The recorded labels are detector outputs, not independently verified ground truth.
