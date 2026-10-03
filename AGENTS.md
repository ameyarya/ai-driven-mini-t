# Rook project workflow

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
  `python3 -m unittest test_rover_autonomy test_rover_vision_labeled test_rover_fast_navigation`
- Do not start physical autonomous tests without the user starting the goal
  or explicitly requesting that hardware test.
