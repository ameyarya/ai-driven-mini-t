# Rover ideas

These are project ideas, not claims about implemented capabilities.

- **Tank POC:** find the red soda can and shoot it. Search, centering, and approach
  work in the controller; a one-shot stage is implemented but not physically
  tested. Visual shot/hit verification and launcher calibration remain next.
- **Desk companion:** nudge me to stand up or drink water, and move around.
  [Muse Gadget SDK](https://github.com/facebookincubator/muse-gadget-sdk)
  evaluated on 2026-10-03 as an optional companion interface. Its Linux SDK
  supports custom commands and proactive messages to Muse; a separate Linux
  host with Bluetooth LE could bridge bounded commands to Rook's Mac HTTP API.
  This is a proposed integration, not implemented or tested. The supported
  setup requires the Muse phone app and an SDK token; it is not a standalone
  local-Qwen framework. The ESP32 SDK requires replacement ESP-IDF firmware
  and must not be flashed onto the locked CyberBrick boards. The user's updated
  target is an untethered camera-and-screen Muse companion mounted on the tank;
  the Mac should not be required at runtime. See the
  [standalone companion plan](DESK_COMPANION.md). Hardware inventory and the
  camera/movement integration are still to be established.
- **Dog monitor:** find my dog, log activities and water/walk breaks, and send
  reports to me.

Keep the current tank POC focused before expanding into companion or monitoring
features. The original unedited idea list is preserved in the local archive.
