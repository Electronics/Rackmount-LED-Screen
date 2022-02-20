`asyncDisplay.py` is the main file

Push config.html and the "library" rackDisplay.py onto the ESP then run.

Some things that rely on other dependencies will give cryptic errors rather than saying they don't have the dependency. Also as all libraries via upip get installed to /lib/src, most libraries will never find the dependentcies even if they're installed.
Try adding:
```
import sys
sys.path.insert(1, "/lib/src")
```

adafruit-ampy on a host system is particularly useful for loading files and running programs without having to open/close serial things

OSC Server (https://github.com/SpotlightKid/micropython-osc/):
get rid of `from uosc.socketutil import get_hostport` and replace print's with str()

for async server, install uasyncio
	uasyncio changes IORead(<>) to uasyncio.core._io_queue.queue_read(<>)
	change yield to await in calling server
