# Untethered Muse desk companion

User direction, 2026-10-03: a self-contained Muse personal assistant with a
camera and screen, mounted on the existing CyberBrick tank so it can move.
The Mac is a development tool, not a required runtime host. No hardware has
been selected or purchased, and no Muse integration has been implemented.

## Separation of responsibilities

- Muse service: conversation, personal-assistant requests, and high-level intent.
- Onboard gadget: display, camera capture, optional voice input/output, local
  movement controller, and a battery power supply appropriate to that hardware.
- Existing CyberBrick receiver: motor actuation, watchdogs and signed commands.

The Muse Gadget SDK supplies device integration; it does not supply a local
offline Muse model. Its documented setup requires an SDK token and initial
pairing through the Muse phone app. ESP32 gadgets then join Wi-Fi and connect
to Muse. A Mac-free device is feasible as a design goal, but internet access
and Muse service availability remain dependencies.

## Hardware paths to evaluate

**Linux computer mounted on the tank:** a supported Raspberry Pi with camera,
small screen and suitable regulated/battery power. Plug the existing
CyberBrick transmitter into the Pi over USB. This reuses our current USB →
ESP-NOW receiver link and keeps Python controller work portable. The Linux
SDK supports custom commands and proactive messages, but a companion display
UI and camera-to-Muse command need development. Local Qwen performance is not
assumed; the assistant brain here is Muse.

**SenseCAP Watcher head:** an integrated ESP32-S3 gadget supported by Muse with
screen, microphone/speaker hardware and optional camera support. The SDK's
camera flag is disabled by default. Enabling it adds preview and
`camera.capture`, which returns a JPEG as base64. Photo attachments to voice
messages are not included. The supported default interaction is push-to-talk
with text replies; spoken replies need separate TTS integration.

Watcher is a compact candidate, not a verified rover controller. Removing the
Mac would require custom movement transport, such as ESP-NOW to the existing
receiver. Peer identity, signed-packet compatibility and Wi-Fi/ESP-NOW channel
coexistence must be tested before selecting this route. Existing CyberBrick
boards must retain their locked firmware. Do not flash Muse firmware onto them.

Hardware selection must account for the Mini-T's mounting space, payload,
power and runtime. Check the user's existing devices before buying components.

## First milestones

1. Stationary companion: pair with Muse, show replies on screen, take a camera
   snapshot via a custom command and verify Muse can use its result.
2. Mac-free movement: implement bounded forward/turn/stop commands and run
   them through the existing receiver watchdog. Keep companion movement
   commands separate from the experimental firing capability.
3. Combine conversation and perception: requests such as "come closer" or
   "look at my desk," using a local feedback loop and clear stop conditions.
4. Proactive assistant behavior: reminders, configurable routines, and later
   navigation around obstacles. Desk-edge detection is a required part of
   free movement on a raised desk; current can-centering tests do not provide it.

Sources checked on 2026-10-03:

- [Muse SDK overview](https://github.com/facebookincubator/muse-gadget-sdk)
- [Linux SDK and extension commands](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux)
- [Supported ESP32 devices and Watcher camera](https://github.com/facebookincubator/muse-gadget-sdk/blob/main/esp32/devices/README.md#watcher-camera)
- [ESP32 interaction and text/TTS replies](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/esp32)
