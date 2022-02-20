#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run an OSC server with asynchroneous I/O handling via the uasync framwork.
"""
import sys
sys.path.insert(1, "/lib/src")

import logging
import socket
import micropython
import uasyncio
import machine
import time
#from uasyncio import IOQueue, coroutine, get_event_loop, sleep

# from uosc.socketutil import get_hostport
from uosc.server import handle_osc
from uosc.client import Client as OSCClient
from rackDisplay import *
from rackDisplay import _setDisplay, _setDisplay2

from microdot_asyncio import Microdot, send_file, redirect

import network
import machine as m
nl=network.LAN(mdc=m.Pin(23),mdio=m.Pin(18),power=m.Pin(16),id=0,phy_addr=1,phy_type=network.PHY_LAN8720)

interrupt = Pin(12, Pin.IN, Pin.PULL_UP)

micropython.alloc_emergency_exception_buf(100)

app = Microdot()

LONG_PRESS = 1000

MAX_DGRAM_SIZE = 1472
log = logging.getLogger("uosc.async_server")

buttonOSC = [["",9001,"","i",1]]*4  # IP, port, path, type, value
tallyBrightness = 5
displayBrightness = 3
defaultDisplay = ""
defaultDisplay2 = ""

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
        uasyncio.create_task(setDisplay(args[0]))
    if oscaddr is "/display2" and tags is "s":
        print("Set display2 to "+args[0])
        uasyncio.create_task(setDisplay2(args[0]))
    if oscaddr is "/tally" and tags is "i":
        if int(args[0]):
            print("Set tally on")
            setTallyState(1,1)
        else:
            print("Set tally off")
            setTallyState(0,0)
    if oscaddr is "/tally2" and tags is "i":
        if int(args[0]):
            print("Set tally2 on")
            setTallyState(1,1,display=1)
        else:
            print("Set tally2 off")
            setTallyState(0,0,display=1)

scrollDisplayText = ""
scrollDisplayText2 = ""
async def scrollDisplayLoop():
    global scrollDisplayText,scrollDisplayText2

    SCROLL_SPACING = 1 # how much spacing to give between end and beginning of scroll,
    # NB: also check the setScrollDisplay as I add a char in there to indicate EoL
    displayScrollIdx = 0
    displayScrollIdx2 = 0
    while True:
        if len(scrollDisplayText)>8:
            i = displayScrollIdx % (len(scrollDisplayText)+SCROLL_SPACING)
            text = scrollDisplayText[i:i+8] + " "*SCROLL_SPACING + scrollDisplayText
            _setDisplay(text)
            displayScrollIdx += 1
        if len(scrollDisplayText2)>8:
            i = displayScrollIdx2 % (len(scrollDisplayText2)+SCROLL_SPACING)
            text = scrollDisplayText2[i:i+8] + " "*SCROLL_SPACING + scrollDisplayText2
            _setDisplay2(text)
            displayScrollIdx2 += 1
        await uasyncio.sleep(0.15)

async def setScrollDisplay(t):
    global scrollDisplayText
    scrollDisplayText = t + " \x7f"

async def setScrollDisplay2(t):
    global scrollDisplayText2
    scrollDisplayText2 = t + " \x7f"

lastDisplay = ""
async def setDisplay(t, temp=False):
    global lastDisplay
    print("setting display to ",t)
    if len(t)>8:
        await setScrollDisplay(t)
    else:
        await setScrollDisplay("")
        _setDisplay(t)
    if not temp:
        lastDisplay = t


lastDisplay2 = ""
async def setDisplay2(t, temp=False):
    global lastDisplay2
    if len(t)>8:
        await setScrollDisplay2(t)
    else:
        await setScrollDisplay2("")
        _setDisplay2(t)
    if not temp:
        lastDisplay2 = t

async def setTempDisplay(text, seconds):
    def resetDisplay(seconds):
        global lastDisplay
        log.debug("Reset task created")
        await uasyncio.sleep(seconds)
        log.debug("Resetting display to %s",lastDisplay)
        await setDisplay(lastDisplay)
    await setDisplay(text, temp=True)
    log.debug("Creating task to reset display in %f seconds",seconds)
    uasyncio.create_task(resetDisplay(seconds))




buttonFlag = uasyncio.ThreadSafeFlag()
def buttonISR(_):
    buttonFlag.set()

async def buttonLoop():
    lastButtons = 0
    lastButtonPresses = [0,0,0,0]
    while True:
        await buttonFlag.wait() # wait for interrupt pin
        buttons = readButtons()
        changedButtons = lastButtons ^ buttons
        for i in range(4):
            bitFlag = 1 << i
            if changedButtons & bitFlag:
                # print("Button 1 "+("pressed" if (buttons&1) else "released"))
                if (~buttons)&bitFlag:
                    log.info("Button %i released",i+1)
                    if lastButtonPresses[i]+LONG_PRESS<time.ticks_ms():
                        log.info("Button %i long-pressed",i+1)
                        if i==2:
                            machine.reset()
                        if i==3:
                            # button 4
                            # show net info for a bit
                            conf = nl.ifconfig()
                            ip = conf[0]
                            subnet = conf[1]
                            gw = conf[2]
                            dns = conf[3]
                            await setTempDisplay("IP:"+ip+" SUB:"+subnet+" GW:"+gw,12)
                    elif buttonOSC[i][0]:
                        print("OSC will be sent:",buttonOSC[i])
                        osc = OSCClient(buttonOSC[i][0],buttonOSC[i][1])
                        osc.send(buttonOSC[i][2],(buttonOSC[i][3], buttonOSC[i][4]))
                        osc.close()
                elif buttons & bitFlag:
                    log.info("Button %i pressed",i+1)
                    lastButtonPresses[i] = time.ticks_ms()


        lastButtons = buttons

@app.route("/")
async def rootIndex(request):
    return send_file("config.html")

@app.route("/buttons")
async def getButtons(request):
    return buttonOSC

@app.route("/brightness")
async def getBrightness(request):
    global displayBrightness, tallyBrightness
    return [tallyBrightness,displayBrightness]

@app.route("/defaultDisplay")
async def getDefaultDisplay(request):
    global defaultDisplay,defaultDisplay2
    return [defaultDisplay,defaultDisplay2]

@app.post("/setButton")
async def webButtonUpdate(request):
    print("Form:",request.form)
    if request.form is not None and len(request.form)==6:
        data = request.form
        bID = int(data["id"]) - 1
        bIP = data["ip"]
        bPath = data["path"]
        bPort = int(data["port"])
        bType = data["type"]
        bValue = data["value"]
        if bType=="i":
            bValue = int(bValue)
        buttonOSC[bID] = [bIP, bPort, bPath, bType, bValue]
        log.info("Updated button %d: %s",bID+1, str(buttonOSC[bID]))

        await saveButtonConfig(bID)
        return redirect("/")
    else:
        log.warning("Malformed updateButton data")
        return "Malformed data", 400

@app.post("/setBrightness")
async def webBrightnessUpdate(request):
    global displayBrightness, tallyBrightness
    print("Form:",request.form)
    if request.form is not None and len(request.form)==2:
        data = request.form
        tallyBrightness = int(data["tally"])
        displayBrightness = int(data["display"])
        setTallyBrightness(tallyBrightness)
        setDisplayBrightness(displayBrightness)
        await saveBrightnessConfig()
        return redirect("/")
    else:
        log.warning("Malformed brightness data")
        return "Malformed data", 400

@app.route("/identify", methods=["GET", "POST"])
async def identify(request):
    log.info("Blinking Tallys for identify")
    for i in range(8):
        setTallyState(1,0,display=-1)
        await uasyncio.sleep_ms(200)
        setTallyState(0,1,display=-1)
        await uasyncio.sleep_ms(200)
    setTallyState(0,0,reset=True)
    return redirect("/")

@app.post("/setDefaultDisplay")
async def setDefaultDisplay(request):
    global defaultDisplay
    if request.form is not None and len(request.form)==1:
        defaultDisplay = request.form["displayText"].strip()
        _setDisplay(defaultDisplay)
        with open("config/display","w") as f:
            f.write(defaultDisplay)
        log.info("Saved new default text")
        return redirect("/")
    else:
        return "Malformed data", 400

@app.post("/setDefaultDisplay2")
async def setDefaultDisplay2(request):
    global defaultDisplay2
    if request.form is not None and len(request.form)==1:
        defaultDisplay2 = request.form["displayText"].strip()
        _setDisplay2(defaultDisplay2)
        with open("config/display2","w") as f:
            f.write(defaultDisplay2)
        log.info("Saved new default text")
        return redirect("/")
    else:
        return "Malformed data", 400

def loadConfig():
    global displayBrightness, tallyBrightness, defaultDisplay, lastDisplay
    # read and set brightness
    try:
        with open("config/displayBrightness") as f:
                displayBrightness = int(f.read())
    except OSError:
        log.info("No display brightness config file, using defaults")
    setDisplayBrightness(displayBrightness)

    try:        
        with open("config/tallyBrightness") as f:
            tallyBrightness = int(f.read())
    except OSError:
        log.info("No tally brightness config file, using defaults")
    setTallyBrightness(tallyBrightness)

    for i in range(4):
        try:
            with open("config/button"+str(i+1)) as f:
                rawButton = f.read().split(",")
                rawButton[1] = int(rawButton[1])
                if rawButton[3]=="i":
                    rawButton[4] = int(rawButton[4])
                buttonOSC[i] = rawButton[0:5]
        except OSError:
            log.info("No button%i config file",i+1)

    try:
        with open("config/display") as f:
            defaultDisplay = f.read().strip()
            _setDisplay(defaultDisplay)
            lastDisplay = defaultDisplay
    except OSError:
        log.info("No default display text, leaving blank")

    try:
        with open("config/display2") as f:
            defaultDisplay2 = f.read().strip()
            _setDisplay2(defaultDisplay2)
            lastDisplay = defaultDisplay2
    except OSError:
        log.info("No default display2 text, leaving blank")

async def saveButtonConfig(button): # 0-3
    with open("config/button"+str(button+1),"w") as f:
        for i in range(5):
            f.write(str(buttonOSC[button][i])+",")
        log.info("Saved button %d",button+1)

async def saveBrightnessConfig():
    with open("config/tallyBrightness","w") as f:
        f.write(str(tallyBrightness))
        log.info("Saved tally brightness: %d",tallyBrightness)
    with open("config/displayBrightness","w") as f:
        f.write(str(displayBrightness))
        log.info("Saved display brightness: %d",displayBrightness)

async def main():
    # asyncio wants to call the main proc itself first before spawning coroutines
    log.debug("Starting asyncio event loop")
    uasyncio.create_task(run_server("0.0.0.0", 9001, dispatch=oscCallback))
    uasyncio.create_task(buttonLoop())
    uasyncio.create_task(scrollDisplayLoop())

    loop = uasyncio.get_event_loop()
    try:
        app.run(port=80, debug=True)
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG) #  if '-v' in sys.argv[1:] else logging.INFO
    initDisplay()
    readButtons() # clear the interrupt pin if it's set (hopefully buttons aren't being held)
    interrupt.irq(trigger=Pin.IRQ_FALLING, handler=buttonISR)

    _setDisplay("Booting")

    log.info("Obtaining DHCP...")
    try:
        nl.active(1)
    except OSError:
        log.info("Already has network")
    log.info(str(nl.ifconfig()))

    # load config
    loadConfig()

    setTallyState(0,0)
    setTallyState(0,0,display=1)


    uasyncio.run(main())
    