# AI-Driven Mini-T project workflow

- This repository is the canonical working folder. Do not recreate active
  source files or runtime data in the parent `Code` directory.
- Keep README, docs/STATUS.md, and relevant progress documentation current as
  features are completed. Maintain docs/PROMPTS.md and docs/IDEAS.md when needed.
- The user authorized committing and pushing completed project changes.
- Preserve private camera images, logs, signing keys, hardware backups, local
  notes, and archived experiments locally; do not add them to Git.
- The full ongoing plan is local-notes/rook-home-rover-plan.md.
- CyberBrick firmware is locked: never flash it with third-party tools. Use
  the existing Python application update/rollback protocol when required.
- Thonny must be closed while the server owns the serial port. Do not run
  archived hardware diagnostics as part of normal tests.
- Verify navigation changes with:
  `python3 -m unittest test_rover_autonomy test_rover_vision_labeled test_rover_fast_navigation test_rover_playground test_rover_training`
- Shooting changes also require `test_rover_shooting` and `test_rover_elevation`; simulation checks run in
  `.sim-venv` with `cd simulation && ../.sim-venv/bin/python -m unittest test_sim test_obstacles`.
- Simulator preview is not Qwen inference or physical validation. Keep oracle
  measurements and contact ground truth explicitly labeled; never claim a real
  hit from an acknowledged fire command. Existing adapter-v1 rejects firing.
- Do not start physical autonomous tests without the user starting the goal
  or explicitly requesting that hardware test.

- Keep saved-frame training sessions separate from validation/test sessions.
  Private datasets and adapters stay in ignored `playground-data/`. Run GPU
  training and inference sequentially on the 16 GB development Mac.
