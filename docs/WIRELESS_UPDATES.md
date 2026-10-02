# Wireless application updates

The Mini-T receiver supports signed application updates through the USB
transmitter. Its USB cable is only needed for recovery or changes to the update
service itself. This transfers Python application files, not firmware.

Keep the tank's battery and switch on. Run from the repository directory:

    python3 -u server_tank.py

The hold-to-drive page is http://localhost:8000. In another terminal:

    python3 wireless_update.py --status
    python3 wireless_update.py tank_app.py
    python3 wireless_update.py --rollback

Drive with the arrow keys. Launcher controls: hold Space to fire, release to reset; hold 1/2 to move the
launcher up/down. Escape stops driving, resets firing, and stops launcher motion.
The app uses the saved S2 angles of 150 degrees for fire and 86 degrees for reset.
S1 uses the stock 45-percent continuous-servo speed for launcher elevation.
An independent 500 ms heartbeat timeout resets the launcher on connection loss.
The app registers its signed launcher protocol extension when it becomes the
active app; application validation does not fire or initialize the servos.

Edit tank_app.py to change the application. TankApp.command(key) returns the
two motor speeds, each between -2048 and 2048. X must return (0, 0). Give each
revision a VERSION string. Application code is trusted Python and must not block
the receiver loop. The uploader validates syntax, hash, the motor mappings, and
the stopped state before confirmation. The receiver retains the previous app.
An unconfirmed update resets to the previous app on startup.

Motors stop during uploads. An interrupted upload times out after three seconds.
Lost drive commands stop the motors after 500 ms. The updater checks complete
files before replacing the active app. Neither drive firmware nor the USB
transmitter firmware is flashed.

Keep .tank_update.key beside the server and uploader. It is the local signing
key and must not be shared or removed. Uploaded applications can access the
receiver's hardware and files; only upload code you trust.

Recovery copies are in the local receiver backup directory (not included in Git). The root backup contains the
original factory app and rc_config; before-wireless-updates contains a copy of
the wireless receiver program. To restore the original remote-control setup,
stop the server, connect the receiver by USB, and restore boot.py from the root
backup. The original app/bbl files and rc_config were retained on the receiver.

Changing tank_wireless_service.py or its startup code currently requires USB.
Wireless updates are for tank_app.py, and do not include firmware replacement.
