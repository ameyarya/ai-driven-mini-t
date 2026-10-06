# Bullseye alignment calibration

Physical dashboard test, 2026-10-06. No firing or forward movement.

Baseline Align accepted 3.3% left offset because final tolerance was ±5%. The current bullseye final tolerance is ±1%; other target regressions retain their previous tolerance. Approach remains coarse far away and tightens at the final setpoint.

| Left turn | Before x | After x | Change |
| --- | ---: | ---: | ---: |
| 50 ms (earlier run) | 43.30% | 46.70% | +3.40% |
| 32 ms (calibrated run) | 46.70% | 48.75% | +2.05% |
| 20 ms (calibrated run) | 48.75% | 50.50% | +1.75% |

The measured initial left-turn gain is 0.068 percentage points/ms. In-run feedback continues to update the duration estimate. Reference-matched bullseyes allow 20 ms minimum turns, avoiding the previous 50 ms minimum near the center. An unmeasured reverse direction uses a conservative error-dependent seed and reversal halving; it is not claimed calibrated.

The browser-run test finished at **0.5% right**, step 3/40. Repeating Align finished at the same 0.5% right, step 1/40, without another movement. 82 host tests pass, including precise-target tolerance and sub-50 ms correction regression.

[Numeric calibration](alignment-calibration.json). This calibration applies to the current speed, surface and camera setup; right-turn response, other starting angles and launcher aim remain unverified. It measures image centering, not physical degrees or camera-to-launcher registration. Match scores are correlations, not probabilities.
