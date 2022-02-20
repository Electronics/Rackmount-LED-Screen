from machine import Pin, I2C
import time

i2c = I2C(0, scl=Pin(4), sda=Pin(2), freq=100000)

interrupt = Pin(12, Pin.IN, Pin.PULL_UP)

v14state = 0 # as multiple flags/states in one i2c register - NOT bytes object, int
tallyState = [True,True,True,True]

def setTallyBrightness(brightness): # 4 bits
	global v14state
	v14state = (v14state & 0x0f) | (brightness << 4)
	i2c.writeto(0x23, v14state.to_bytes(1,"big"))

def setTallyState(left, right, display=0, reset=False):
	global tallyState
	if reset:
		# temp change (for identify)
		_setTallyState(tallyState[0],tallyState[1],tallyState[2],tallyState[3])
		return
	if display<0:
		# temp change (for identify)
		_setTallyState(left,right,left,right)
	elif display>0:
		_setTallyState(tallyState[0],tallyState[1],left,right)
		tallyState[2] = left
		tallyState[3] = right
	else:
		_setTallyState(left,right,tallyState[2],tallyState[3])
		tallyState[0] = left
		tallyState[1] = right

def _setTallyState(left, right, disp2Left, disp2Right):
	out = 0
	out |= 2 if left else 0
	out |= 1 if right else 0
	out |= 4 if disp2Right else 0
	out |= 8 if disp2Left else 0
	i2c.writeto(0x24, out.to_bytes(1,"big"))

def setDisplayBrightness(brightness): # 2 bits
	global v14state
	v14state = (v14state & 0xf3) | (brightness << 2)
	i2c.writeto(0x23, v14state.to_bytes(1,"big"))

def initDisplay():
	global v14state
	v14state = 0b00001101 # display ~WR high, display full brightness
	i2c.writeto(0x23, v14state.to_bytes(1,"big")) # turn off lamp test
	i2c.writeto(0x24, b"\x0f") # turn on tally enable

def _setDisplay(text, display=0):
	global v14state
	text = text[0:8]+" "*(8-len(text))
	for i in range(8):
		displayOffset = 8 if display else 0
		i2c.writeto(0x21,(7-i+displayOffset).to_bytes(1,"big")) # address of display (inverted)
		i2c.writeto(0x22,str.encode(text[i])) # data
		v14state &= 0b11111110 # display ~WR low
		i2c.writeto(0x23, v14state.to_bytes(1,"big"))
		v14state |= 0b00000001 # display ~WR high
		i2c.writeto(0x23, v14state.to_bytes(1,"big"))

def _setDisplay2(text):
	_setDisplay(text,display=1)

def readButtons():
	return int.from_bytes(i2c.readfrom(0x20,1),"big") >> 4

lastButtons = 0
def buttonLoop():
	global lastButtons
	if interrupt.value()==0:
		buttons = readButtons()
		changedButtons = lastButtons ^ buttons
		if changedButtons & 1:
			print("Button 1 "+("pressed" if (buttons&1) else "released"))
		elif changedButtons & 2:
			print("Button 2 "+("pressed" if (buttons&2) else "released"))
		elif changedButtons & 4:
			print("Button 3 "+("pressed" if (buttons&4) else "released"))
		elif changedButtons & 8:
			print("Button 4 "+("pressed" if (buttons&8) else "released"))
		lastButtons = buttons


# initDisplay()
# setDisplay("Jamiesux")
# timeout = 0
# while True:
# 	for i in range(1,7):
# 		setTallyBrightness(i)
# 		setDisplayBrightness((i+3)%7+1)
# 		setTallyState(i%2,i%3)
# 		time.sleep(0.2)
# 	timeout += 1
# 	if timeout > 5:
# 		break

