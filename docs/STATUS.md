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

The local model only advises. Automatic navigation, firing, and obstacle avoidance
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
