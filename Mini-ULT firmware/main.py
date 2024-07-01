import machine, onewire, ds18x20, time
import usys as sys
import neopixel

from urandom import getrandbits, seed
from utime import ticks_us
from uasyncio import sleep, sleep_ms, create_task, Loop, CancelledError, get_event_loop

uart0 = machine.UART(0, baudrate=38400, tx=machine.Pin(0), rx=machine.Pin(1))

serial_no = '0000'

print(f'mini-ULT {serial_no} Starting')
import lvgl as lv

uart0.write(f'"sn": "{serial_no}", "event": "boot", "value": "started"\r\n')

seed(ticks_us())
lv.init()

import ili9xxx
import xpt2046

# NeoPixels
num_pixels = 10
np = neopixel.NeoPixel(machine.Pin(19), num_pixels)

# Reed Switch
reed = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
reed_state = reed.value()

spi=machine.SPI(
    1,
    baudrate=24_000_000,
    polarity=0,
    phase=0,
    sck=machine.Pin(10,machine.Pin.OUT),
    mosi=machine.Pin(11,machine.Pin.OUT),
    miso=machine.Pin(12,machine.Pin.IN)
)


ds_pin = machine.Pin(18)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = ds_sensor.scan()
if len(roms) > 0:
    print('Found DS devices: ', roms)


disp=ili9xxx.Ili9341(rot=ili9xxx.ILI9XXX_PORTRAIT,spi=spi,cs=6,dc=8,bl=9,rst=7,rp2_dma=None,factor=8,asynchronous=True)
disp.set_backlight(100)
touch=xpt2046.Xpt2046(spi=spi,cs=13,rot=xpt2046.XPT2046_INV_PORTRAIT)

arc = lv.arc(lv.scr_act())
arc.set_size(150, 150)
arc.set_rotation(135)
arc.set_bg_angles(0, 270)
arc.remove_style(None, lv.PART.KNOB) 
arc.clear_flag(lv.obj.FLAG.CLICKABLE)
arc.set_value(0)
arc.center()

label = lv.label(lv.scr_act())
label.set_style_text_font(lv.font_montserrat_32, 0)
label.center()
label.set_text(' - ')

door_state = lv.label(lv.scr_act())
door_state.set_align(lv.ALIGN.BOTTOM_RIGHT)

value = 0

display_F = False

def door_status(state):
    door_state.set_text(f'Door: {state}')
    uart0.write(f'"sn": "{serial_no}", "event": "door", "value": "{state}"\r\n')

async def log_temp():
    while True:
        if value > 0:
            uart0.write(f'"sn": "{serial_no}", "event": "temp", "value": "{value}"\r\n')
        await sleep(10)

async def display_temp():
    while True:
        global value
        ds_sensor.convert_temp()
        await sleep_ms(750)
        value = ds_sensor.read_temp(roms[0])
        if display_F:
            temp = (1.8 * value) + 32
            suffix = "°F"
        else:
            temp = value
            suffix = "°C"
    
        label.set_text(f"{temp:.1f}{suffix}")
        arc.set_value(int(temp))

def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        return (0, 0, 0)
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)

async def rainbow_cycle():
    while True:
        for j in range(255):
            for i in range(num_pixels):
                rc_index = (i * 256 // num_pixels) + j
                np[i] = wheel(rc_index & 255)
            np.write()
            await sleep_ms(0)

async def check_door():
    while True:
        global reed_state
        state = reed.value()
        if state != reed_state:
            reed_state = state
            if state == 0:
                door_status("Closed")
            elif state == 1:
                door_status("Opened")
        await sleep_ms(50)

if len(roms) > 0:
    create_task(display_temp())

create_task(rainbow_cycle())
create_task(check_door())
create_task(log_temp())

async def cb_event_handler(event):
    await sleep(0)
    global display_F
    if cb.get_state() & lv.STATE.CHECKED:
        display_F = True
    else:
        display_F = False


loop = get_event_loop()
cb = lv.checkbox(lv.scr_act())
cb.set_align(lv.ALIGN.BOTTOM_LEFT)
cb.set_text("°F")
cb.add_event(lambda e: loop.create_task(cb_event_handler(e)), lv.EVENT.VALUE_CHANGED, None)

if reed_state:
    door_status("Opened")
else:
    door_status("Closed")


loop.run_forever()