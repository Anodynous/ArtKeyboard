"""
pyArtKeyboard
Circuitpython implementation for ArtKeyboard (https://github.com/Roboxtools/ArtKeyboard). Device acts as a BLE HID keyboard to peer devices.
Uses 11 buttons connected to Feather nRF52840. One button is reserved as modifier to activate a secondary layer to enable mapping of up to 20 separate actions per profile.

Pre-mapped profiles:
    Procreate
    Notability
    Infuse (& general media player)
    Comms (Discord/MS Teams/General)

TODO:
    Improvements:
        Look into reducing power consumption, implementing deep sleep mode
        Switch profiles without requiring power cycle
"""

import time
import board
from digitalio import DigitalInOut, Direction, Pull
from random import randrange    # Used for Comms to randomize mouse movement

# BLE libraries
import adafruit_ble
from adafruit_ble.advertising import Advertisement
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.standard.hid import HIDService
from adafruit_ble.services.standard.device_info import DeviceInfoService
# HID libraries
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
# For battery reading
from analogio import AnalogIn
# For neopixel
import neopixel
# For multimedia keyboard controls
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
# For mouse controls
from adafruit_hid.mouse import Mouse


"""
NRF52840 pinout = ['A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'AREF', 'BATTERY', 'BLUE_LED', 'D10', 'D11', 'D12', 'D13', 'D2', 'D3', 'D5', 'D6', 'D9', 'I2C', 'L', 'MISO', 'MOSI', 'NEOPIXEL', 'NFC1', 'NFC2', 'RED_LED', 'RX', 'SCK', 'SCL', 'SDA', 'SPI', 'SWITCH', 'TX', 'UART', 'VOLTAGE_MONITOR']

   Board       Board.pin                     Button Names

   -X-X-       A0 - D12            b_shoulder_left     b_shoulder_right
   |o*0|       A1 - D11            b_small_1           b_large_1
   |o**|       A2 - *              b_small_2               *
   |o*0|       A3 - D10            b_small_3           b_large_2
   |0*o|       A4 - D9             b_large_3           b_small_4
   |**o|       *  - A5                 *               b_small_5
   |o*=|       D5 - On/Off         b_small_6               *
    ---

Universal functions:
b_small_6 = Hold down during boot to get battery voltage reading
"""

# Button setup
b_shoulder_left = DigitalInOut(board.A0)
b_shoulder_right = DigitalInOut(board.D12)
b_small_1 = DigitalInOut(board.A1)
b_small_2 = DigitalInOut(board.A2)
b_small_3 = DigitalInOut(board.A3)
b_small_4 = DigitalInOut(board.D9)
b_small_5 = DigitalInOut(board.A5)
b_small_6 = DigitalInOut(board.D5)
b_large_1 = DigitalInOut(board.D11)
b_large_2 = DigitalInOut(board.D10)
b_large_3 = DigitalInOut(board.A4)

# Other Input/Output assignements
vbat_voltage = AnalogIn(board.VOLTAGE_MONITOR)
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.4, auto_write=False)
red_led = DigitalInOut(board.RED_LED)
blue_led = DigitalInOut(board.BLUE_LED)
red_led.direction = Direction.OUTPUT
blue_led.direction = Direction.OUTPUT



buttons = [b_shoulder_left, b_shoulder_right, b_small_1, b_small_2, b_small_3, b_small_4, b_small_5, b_small_6, b_large_1, b_large_2, b_large_3]
for button in buttons:
    button.direction = Direction.INPUT    # set direction as input, not strictly needed as it is default for DigitalInOut()
    button.pull = Pull.UP    # activate internal pullup, needed as it is not default for DigitalInOut()

# Neopixel colors
DARK = (0, 0, 0)
PURPLE = (180, 0, 255)  # used for Procreate
BLUE = (0, 0, 255)  # used for Notability
ORANGERED = (255, 69, 0)  # used for Infuse
GREEN = (0, 128, 0) # used for Comms
RED = (255, 0, 0) # used for Comms
YELLOW = (255, 255, 0) # used for Comms


hid = HIDService()

# Initiate BLE radio
device_info = DeviceInfoService(software_revision=adafruit_ble.__version__,
                                manufacturer="adafruit")
advertisement = ProvideServicesAdvertisement(hid)
advertisement.appearance = 961
scan_response = Advertisement()
scan_response.complete_name = "ArtKeyboard HID"


ble = adafruit_ble.BLERadio()
ble.name = "ArtKeyboard HID"
if not ble.connected:
    print("advertising")
    ble.start_advertising(advertisement, scan_response)
else:
    print("already connected")
    print(ble.connections)

# Keyboard settings
k = Keyboard(hid.devices)
kl = KeyboardLayoutUS(k)
cc = ConsumerControl(hid.devices)
m = Mouse(hid.devices)

# Set global variables
b_sleep = 0.2
current_tool = ""
modifier_button = False
mic_hot = True
mouse_viggle = False
viggle_timer = 1 # only sets initial countdown timer. Subsequent intervals set randomly
mode = "comms"  # default operating mode
enable_idle_led_time = time.time() # ensures initial value is set to trigger first idle warning when required
idle_alert_on_time = 1 # led on time in seconds for idle alert
idle_alert_off_time = 10 # led off time in seconds for idle alert
disable_idle_led_time = None

def get_voltage():
    """ Returns current battery voltage """
    vbat_voltage_reading = (vbat_voltage.value * 3.3) / 65536 * 2
    return vbat_voltage_reading


def toggle_modifier_button(modifier_button, pixel_color):
    """ Toggles modifier mode on/off """
    if modifier_button:
        pixel.fill(DARK)
        pixel.show()
        modifier_button = False
        print("modifier = false")
    else:
        pixel.fill(pixel_color)
        pixel.show()
        modifier_button = True
        print("modifier = true")
    return modifier_button


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


def rainbow():
    """ Outputs a rainbow effect using the Neopixel """
    for i in range(255):
        color = wheel(i)
        pixel.fill(color)
        pixel.show()
        time.sleep(0.01)


def indicate_mode(pixel_color):
    """ Indicates current mode by flashing Neopixel """
    modifier_button = False
    modifier_button = toggle_modifier_button(modifier_button, pixel_color)
    time.sleep(1.5)
    modifier_button = toggle_modifier_button(modifier_button, pixel_color)


def procreate_mode(modifier_button, current_tool):
    """ Preset for Procreate """
    pixel_color = PURPLE

    # Decrease brush size
    if not b_shoulder_left.value:    # pull up logic means button low when pressed
        if modifier_button:  # Decrease with 1 %
            k.send(Keycode.GUI, Keycode.LEFT_BRACKET)
            time.sleep(b_sleep)
        if not modifier_button:
            k.send(Keycode.LEFT_BRACKET) # Increase with 5 %
            #k.send(Keycode.SHIFT, Keycode.LEFT_BRACKET) # Increase with 10 %
            time.sleep(b_sleep)
        print("Decrease brush size")

    # Increase brush size
    if not b_shoulder_right.value:
        if modifier_button:  # Increase with 1 %
            k.send(Keycode.GUI, Keycode.RIGHT_BRACKET)
            time.sleep(b_sleep)
        if not modifier_button:
            k.send(Keycode.RIGHT_BRACKET) # Increase with 5 %
            #k.send(Keycode.SHIFT, Keycode.RIGHT_BRACKET) # Increase with 10 %
            time.sleep(b_sleep)
        print("Increase brush size")

    # Modifier button toggle
    if not b_small_1.value:
        modifier_button = toggle_modifier_button(modifier_button, pixel_color)
        time.sleep(b_sleep)

    # Undo
    if not b_large_1.value:
        k.send(Keycode.GUI, Keycode.Z)    # add cmd modifier
        time.sleep(b_sleep)
        if not b_large_1.value:  # if button still pressed, keep sending keycode until released for rapid undo/redo
            while not b_large_1.value:
                k.press(Keycode.GUI, Keycode.Z)
            k.release(Keycode.GUI, Keycode.Z)
        print("Undo")

    # Redo
    if not b_large_2.value:
        k.send(Keycode.GUI, Keycode.SHIFT, Keycode.Z)
        time.sleep(b_sleep)
        if not b_large_2.value:  # if button still pressed, keep sending keycode until released for rapid undo/redo
            while not b_large_3.value:
                k.press(Keycode.SHIFT, Keycode.Z)
            k.release(Keycode.SHIFT, Keycode.Z)
        print("Redo")

    # Toggle brush/eraser tool
    if not b_small_2.value:
        if current_tool == 'brush':
            k.send(Keycode.E)
            current_tool = 'eraser'
            time.sleep(b_sleep)
        else:
            k.send(Keycode.B)
            current_tool = 'brush'
            time.sleep(b_sleep)
        print("Toggle brush/eraser")

    # Open color popover
    # Modifier: switch bg/fg colors
    if not b_small_3.value:
        if modifier_button:
            k.send(Keycode.X)
            time.sleep(b_sleep)
            print("Switch bg/fg color")
        if not modifier_button:
            k.send(Keycode.C)
            time.sleep(b_sleep)
            print("Color popover")

    # Transform mode
    # Modifier: Selections mode
    if not b_small_4.value:
        if modifier_button:
            k.send(Keycode.S)
            time.sleep(b_sleep)
            print("Selections mode")
        if not modifier_button:
            k.send(Keycode.V)
            time.sleep(b_sleep)
            print("Transform mode")


    # Open quick menu
    # Modifier: Layers popover
    if not b_small_5.value:

        if modifier_button:
            k.send(Keycode.L)
            time.sleep(b_sleep)
            print("Layers popover")
        if not modifier_button:
            k.send(Keycode.SPACE)
            time.sleep(b_sleep)
            print("Quick menu")

    # Toggle fullscreen / Switch keyboard layout
    if not b_small_6.value:
        if modifier_button:
            k.send(Keycode.GUI, Keycode.SPACE)
            time.sleep(0.5)
            k.send(Keycode.SHIFT, Keycode.LEFT_CONTROL, Keycode.SPACE)
            time.sleep(b_sleep)
            print("Switch keyboard layout")
        if not modifier_button:
            k.send(Keycode.GUI, Keycode.ZERO)
            time.sleep(b_sleep)
            print("Toggle fullscreen")

    # Activate [] while held, for color picker & Smudge with pencil but depends on Procreate settings. Make sure Procreate settings have; []-tap = Eyedropper, []+Apple Pencil = Smudge
    if not b_large_3.value:
        while not b_large_3.value:
            k.press(Keycode.ALT)
        k.release(Keycode.ALT)
        time.sleep(b_sleep)
        print("[] for Color picker/Smudge")

    return(modifier_button, current_tool)


def notability_mode(modifier_button):
    """ Preset for Notability """
    pixel_color = BLUE

    # Undo
    if not b_shoulder_left.value:
        k.send(Keycode.GUI, Keycode.Z)
        time.sleep(b_sleep)
        print("Undo")

    # Redo
    if not b_shoulder_right.value:
        k.send(Keycode.GUI, Keycode.SHIFT, Keycode.Z)
        time.sleep(b_sleep)
        print("Redo")

    # Modifier button toggle
    if not b_small_1.value:
        modifier_button = toggle_modifier_button(modifier_button, pixel_color)
        time.sleep(b_sleep)

    # Pen tool
    if not b_large_1.value:
        k.send(Keycode.GUI, Keycode.TWO)
        time.sleep(b_sleep)
        print("Pen tool")

    # Highlighter tool
    if not b_small_2.value:
        k.send(Keycode.GUI, Keycode.THREE)
        time.sleep(b_sleep)
        print("Highlighter tool")

    # Text tool
    if not b_small_3.value:
        k.send(Keycode.GUI, Keycode.ONE)
        time.sleep(b_sleep)
        print("Text tool")

    # Eraser tool
    if not b_large_2.value:
        k.send(Keycode.GUI, Keycode.FOUR)
        time.sleep(b_sleep)
        print("Eraser tool")

    # Scissors tool
    if not b_large_3.value:
        k.send(Keycode.GUI, Keycode.FIVE)
        time.sleep(b_sleep)
        print("Scissors tool")

    # Scroll up / Previous page
    if not b_small_4.value:
        if modifier_button:  # scroll up
            k.send(Keycode.UP_ARROW)
            time.sleep(b_sleep)
        if not modifier_button:  # previous page
            k.send(Keycode.LEFT_ALT, Keycode.UP_ARROW)
            time.sleep(b_sleep)
        print("Scroll up / previous page")

    # Scroll down / Next page
    if not b_small_5.value:
        if modifier_button:  # scroll down
            k.send(Keycode.DOWN_ARROW)
            time.sleep(b_sleep)
        if not modifier_button:  # next page
            k.send(Keycode.LEFT_ALT, Keycode.DOWN_ARROW)
            time.sleep(b_sleep)
        print("Scroll down / next page")

    # Back to library / Create new note
    if not b_small_6.value:
        if modifier_button:  # create new note
            k.send(Keycode.GUI, Keycode.N)
            time.sleep(b_sleep)
        if not modifier_button:  # back to library
            k.send(Keycode.GUI, Keycode.L)
            time.sleep(b_sleep)
        print("Scroll up / previous page")

    return modifier_button


def comms_mode(modifier_button, mic_hot, mouse_viggle):
    """ Preset for Discord/MS Teams comms and general media/mouse control"""
    pixel_color = YELLOW
    pixel_mic_muted = RED
    pixel_mic_hot = GREEN
    
    # Modifier button toggle
    if not b_small_1.value:
        modifier_button = toggle_modifier_button(modifier_button, pixel_color)
        time.sleep(b_sleep)

    # Mute/Unmute (MS Teams) / Modifier on = scroll-up
    if not b_large_1.value:
        if not modifier_button:
            k.send(Keycode.LEFT_CONTROL, Keycode.SHIFT, Keycode.M)
            # Set mic status indicator light
            if mic_hot:
                mic_hot = False
                pixel.fill(pixel_mic_muted)
            elif not mic_hot:
                mic_hot = True
                pixel.fill(pixel_mic_hot)
            pixel.show()
            time.sleep(b_sleep*2)
            print("mute/unmute")
        if modifier_button: # scroll up
            m.move(wheel=1)
            time.sleep(b_sleep/2)
            print("scroll up")

    # Deafen/Undeafen / Modifier on = scroll-down
    if not b_large_2.value:
        if not modifier_button: 
            k.send(Keycode.LEFT_CONTROL, Keycode.SHIFT, Keycode.L)
            time.sleep(b_sleep*2)
            print("deafen/undeafen")
        if modifier_button: # scroll up
            m.move(wheel=-1)
            time.sleep(b_sleep/2)
            print("scroll up")
    
    # Accept audio Call (MS Teams)
    if not b_small_4.value:
        k.send(Keycode.LEFT_CONTROL, Keycode.SHIFT, Keycode.S)
        time.sleep(b_sleep)
        print("accept audio call")

    # Decline call (MS Teams)
    if not b_small_5.value:
        k.send(Keycode.LEFT_CONTROL, Keycode.SHIFT, Keycode.D)
        time.sleep(b_sleep)
        print("decline call")

    # Volume Up
    if not b_small_2.value:
        cc.send(ConsumerControlCode.VOLUME_INCREMENT)
        time.sleep(b_sleep)
        print("Volume up")

    # Volume Down
    if not b_small_3.value:
        cc.send(ConsumerControlCode.VOLUME_DECREMENT)
        time.sleep(b_sleep)
        print("Volume up")

    # Play/Pause Media
    if not b_large_3.value:
        if not modifier_button: 
            cc.send(ConsumerControlCode.PLAY_PAUSE)
            time.sleep(b_sleep)
            print("play/pause")
        if modifier_button: 
            cc.send(ConsumerControlCode.MUTE)
            time.sleep(b_sleep)
            print("mute/unmute")

    # Next Media Track / Skip forward
    if not b_shoulder_right.value:
        if not modifier_button: 
            cc.send(ConsumerControlCode.SCAN_NEXT_TRACK)
            time.sleep(b_sleep)
            print("next track")
        if modifier_button:
            k.send(Keycode.RIGHT_ARROW)
            time.sleep(b_sleep)
            print("Right arrow")

    # Previous Media Track / Skip back
    if not b_shoulder_left.value:
        if not modifier_button: 
            cc.send(ConsumerControlCode.SCAN_PREVIOUS_TRACK)
            time.sleep(b_sleep)
            print("next track")
        if modifier_button:
            k.send(Keycode.LEFT_ARROW)
            time.sleep(b_sleep)
            print("Left arrow")

    # Mouse click / Toggle Mouse Viggle Mode (Prevent sleep)
    if not b_small_6.value: # Mouse left click
        if not modifier_button:
            m.click(Mouse.LEFT_BUTTON)
            time.sleep(b_sleep) 
        if modifier_button: # Toggle mouse viggle mode
            mouse_viggle = not mouse_viggle

    return modifier_button, mic_hot, mouse_viggle

def infuse_mode(modifier_button):
    """ Preset for Infuse / MediaPlayer """
    pixel_color = ORANGERED

    # Skip back
    if not b_shoulder_left.value:
        if modifier_button:
            k.send(Keycode.GUI, Keycode.LEFT_ARROW)  # skip to previous chapter
            time.sleep(b_sleep)
            print("skip back chapter")
        if not modifier_button:
            k.send(Keycode.LEFT_ARROW) # skip back 10s
            time.sleep(b_sleep)
            print("skip back 10s")

    # Skip forward
    if not b_shoulder_right.value:
        if modifier_button:
            k.send(Keycode.GUI, Keycode.RIGHT_ARROW) # skip to next chapter
            time.sleep(b_sleep)
            print("skip forward chapter")
        if not modifier_button:
            k.send(Keycode.RIGHT_ARROW)  # skip forward 30s
            time.sleep(b_sleep)
            print("skip forward 30s")

    # Modifier button toggle
    if not b_small_1.value:
        modifier_button = toggle_modifier_button(modifier_button, pixel_color)
        time.sleep(b_sleep)

    # Play / Pause
    if not b_large_1.value:
        k.send(Keycode.SPACE)
        time.sleep(b_sleep)
        print("Play / Pause")

    # Volume / Brightness up
    if not b_small_2.value:
        if modifier_button:
            k.send(Keycode.GUI, Keycode.UP_ARROW)  # brightness up
            time.sleep(b_sleep)
            print("Brightness up")
        if not modifier_button:
            k.send(Keycode.UP_ARROW)  # volume up
            time.sleep(b_sleep)
            print("Volume up")

    # Volume / Brightness down
    if not b_small_3.value:
        if modifier_button:
            k.send(Keycode.GUI, Keycode.DOWN_ARROW)  # brightness down
            time.sleep(b_sleep)
            print("Brightness down")
        if not modifier_button:
            k.send(Keycode.DOWN_ARROW)  # volume down
            time.sleep(b_sleep)
            print("Volume down")

    # Stop
    if not b_small_6.value:
        if modifier_button:
            k.send(Keycode.ESCAPE)
            time.sleep(b_sleep)
            print("Stop")

    return modifier_button


# Main loop
while True:
    while not ble.connected:
        pass
    print("Connected...")
    idle_timer = time.time()
    indicate_color = PURPLE

    if not b_small_6.value:
        vbat_voltage_reading = get_voltage()
        time.sleep(3)
        kl.write("Battery charge is " + str(vbat_voltage_reading)) # use keyboard layout for words and sentences
        print("VBat voltage: ", vbat_voltage_reading)

    if not b_large_1.value:
        mode = "notability"
        indicate_color = BLUE
        print("Notability mode set")

    if not b_large_2.value:
        mode = "infuse"
        indicate_color = ORANGERED
        print("Infuse mode set")

    if not b_large_3.value:
        mode = "rainbow"
        print("Rainbow mode")
    
    if not b_small_1.value:
        mode = "comms"
        indicate_color = GREEN
        print("Comms mode")

    indicate_mode(indicate_color)

    if time.time() - idle_timer > 600:  # when device turned on and not connected to BLE and inactive for more than 10 minutes enable indicator leds blinking
        if disable_idle_led_time:
            if time.time() > disable_idle_led_time:
                red_led.value = False
                blue_led.value = False
                enable_idle_led_time = time.time() + idle_alert_off_time
                disable_idle_led_time = None
        else:
            if time.time() > enable_idle_led_time:
                red_led.value = True
                blue_led.value = True
                disable_idle_led_time = time.time() + idle_alert_on_time
                enable_idle_led_time = None

    while ble.connected:
        if mouse_viggle: # viggle mouse at random intervals between 10 and 60s while mouse_viggle mode is enabled
            if time.time() - idle_timer > viggle_timer: 
                    m.move(x=randrange(-3, 3), y=randrange(-3, 3))  # Move mouse randomly by max 3 pixels per direction
                    viggle_timer = randrange(10, 60) # set next interval for triggering mouse viggle to a random value in range
                    idle_timer = time.time()  # zero idle_timer
        
        if time.time() - idle_timer > 1800:  # when device turned on and connected to BLE but inactive for more than 30 minutes enable indicator leds blinking
            if disable_idle_led_time:
                if time.time() > disable_idle_led_time:
                    red_led.value = False
                    blue_led.value = False
                    enable_idle_led_time = time.time() + idle_alert_off_time
                    disable_idle_led_time = None
            else:
                if time.time() > enable_idle_led_time:
                    red_led.value = True
                    blue_led.value = True
                    disable_idle_led_time = time.time() + idle_alert_on_time
                    enable_idle_led_time = None

        for button in buttons:
            if not button.value:
                blue_led.value = False
                red_led.value = False
                idle_timer = time.time()  # zero idle_timer
                if mode == "procreate":
                    modifier_button, current_tool = procreate_mode(modifier_button, current_tool)
                elif mode == "notability":
                    modifier_button = notability_mode(modifier_button)
                elif mode == "infuse":
                    modifier_button = infuse_mode(modifier_button)
                elif mode == "rainbow":
                    while True:
                        rainbow()
                elif mode == "comms":
                    modifier_button, mic_hot, mouse_viggle = comms_mode(modifier_button, mic_hot, mouse_viggle)


    ble.start_advertising(advertisement)