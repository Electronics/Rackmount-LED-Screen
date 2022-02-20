#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run an OSC server with asynchroneous I/O handling via the uasync framwork.
"""

import sys
import logging
import socket

import uasyncio
#from uasyncio import IOQueue, coroutine, get_event_loop, sleep

# from uosc.socketutil import get_hostport
from uosc.server import handle_osc

MAX_DGRAM_SIZE = 1472
log = logging.getLogger("uosc.async_server")


async def run_server(host, port, **params):
    log.debug("run_server(%s, %s)", host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))

    try:
        while True:
            if __debug__: log.debug("run_server: Before IORead")
            yield uasyncio.core._io_queue.queue_read(sock)
            if __debug__: log.debug("run_server: Before recvfrom")
            data, caddr = sock.recvfrom(MAX_DGRAM_SIZE)
            if __debug__: log.debug("RECV %i bytes from %s",
                                    len(data), str(caddr))
            handle_osc(data, caddr, **params)
    finally:
        sock.close()
        log.info("Bye!")


def oscCallback(t, msg):
    # t = timestamp?
    print("OSC msg: "+str(msg))
    (oscaddr, tags, args, src) = msg # oscaddr=OSC path, tags = i/s/etc, args=tuple(values, src=(ip, port)
    if oscaddr is "/display" and tags is "s":
        print("Set display to "+args[0])


async def main():
    # asyncio wants to call the main proc itself first before spawning coroutines
    log.debug("Starting asyncio event loop")
    uasyncio.create_task(run_server("0.0.0.0", 9001, dispatch=oscCallback))

    loop = uasyncio.get_event_loop()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

if __name__ == '__main__':
    import time
    logging.basicConfig(level=logging.DEBUG) #  if '-v' in sys.argv[1:] else logging.INFO

    uasyncio.run(main())
    
