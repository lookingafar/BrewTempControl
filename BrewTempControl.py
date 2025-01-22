import RPi.GPIO as GPIO
import os
import sys 
import time
import datetime
import logging
import spidev as SPI
sys.path.append("..")
import math
import asyncio
import board
import busio
i2c = busio.I2C(board.SCL, board.SDA)
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
#kivy stuff
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.app import async_runTouchApp
from kivy.uix.togglebutton import ToggleButton
#from kivy.uix.behaviors import ToggleButtonBehavior


from PIL import Image,ImageDraw,ImageFont,ImageColor
from w1thermsensor import AsyncW1ThermSensor, Sensor


# water pressure sensor
ads = ADS.ADS1115(i2c)
chan = AnalogIn(ads, ADS.P0)



# Raspberry Pi pin configuration:
SSR = 23
RST = 27
DC = 25
BL = 18
bus = 0 
device = 0 

logging.basicConfig(filename='app_debug.log', level=logging.DEBUG)

class BrewTempControlApp(App):
    def debug_log(self, message):
        logging.debug(message)

    #global pressure variables
    maxPressure = 0.6
    minPressure = 0.5
    ssr_enabled = True  # Flag to control if SSR logic is enabled or disabled

    async def schedule_async_update(self):
        await self.update_sensor_readings()

    def build(self):
        # Initialize Temperature Sensors
        self.sensor1 = AsyncW1ThermSensor(Sensor.DS18B20, "3c0107d67cb6")
        # SSR setup
        self.ssr_setup()
        
        # Create a layout
        layout = GridLayout(cols=2, rows=3)
        # Create labels for temperature and pressure
        self.temperature_label = Label(text='Temperature: --', font_size='30sp')
        self.pressure_label = Label(text='Pressure: --', font_size='30sp')
        self.maxPressure_label = Label(text='Max. Pressure: --', font_size='30sp')
        self.minPressure_label = Label(text='Min. Pressure: --', font_size='30sp')
        layout.add_widget(self.temperature_label)
        layout.add_widget(self.pressure_label)
        layout.add_widget(self.maxPressure_label)
        layout.add_widget(self.minPressure_label)

        # Create the toggle button for SSR control
        self.toggle_button = ToggleButton(text='On', state='down', font_size='30sp')
        self.toggle_button.bind(on_press=self.toggle_ssr)  # Bind the function to the button press
        layout.add_widget(self.toggle_button)
        #layout.add_widget(ToggleButton(text='Off', state='normal', font_size='30sp'))
        #layout.add_widget(Button(text='Timer', font_size='30sp'))
        # Schedule the update_sensor_readings method to be called every second
        Clock.schedule_interval(lambda dt: asyncio.ensure_future(self.schedule_async_update()), 1)
        return layout

    def ssr_setup(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SSR, GPIO.OUT)

    def ssr_on(self):
        GPIO.output(SSR, GPIO.HIGH)

    def ssr_off(self):
        GPIO.output(SSR, GPIO.LOW)

    def toggle_ssr(self, instance):
        """This function will toggle the SSR logic and update the button text."""
        if instance.state == 'down':
            self.ssr_enabled = True  # Enable SSR logic when the button is "On"
            instance.text = 'On'  # Update button text to "On"
        else:
            self.ssr_enabled = False  # Disable SSR logic when the button is "Off"
            self.ssr_off()  # Ensure SSR is off
            instance.text = 'Off'  # Update button text to "Off"
    
    def read_pressure(self):
        pressure=round((chan.value-2572)/2132, 2)
        return pressure


    async def update_sensor_readings(self):
        #self.debug_log('Starting update_sensor_readings')
        # Get the temperature reading
        temperature1 = round(await self.sensor1.get_temperature(), 1)
         # Log temperature
        #self.debug_log(f'Temperature: {temperature1}')
        # Update the temperature label
        self.temperature_label.text = f'Temperature: {temperature1}°C'

        # If SSR logic is disabled, don't run SSR control
        if not self.ssr_enabled:
            return

        # Check the current time to adjust pressure thresholds
        now = datetime.datetime.now()

        # Adjust the pressure thresholds based on the temperature
        if now.hour >= 19 or now.hour < 5:  # Between 6 p.m. and 5 a.m.
            self.minPressure = 0.2
            self.maxPressure = 0.25
        elif temperature1 > 94.5:
            self.minPressure = 0.4
            self.maxPressure = 0.5
        elif ((temperature1 < 94.5) and (temperature1 > 93.3)):
            self.minPressure = 0.45
            self.maxPressure = 0.55
        elif ((temperature1 < 93.3) and (temperature1 > 89)):
            self.maxPressure = 0.75
            self.minPressure = 0.65
        elif ((temperature1 < 89) and (temperature1 > 80)):
            self.maxPressure = 0.9
            self.minPressure = 0.8
        elif temperature1 < 80:
            self.maxPressure = 1.2
            self.minPressure = 1.0

        # Get the pressure reading
        pressure = self.read_pressure()
        # Update the pressure label
        self.pressure_label.text = f'Pressure: {pressure} bar'
        self.maxPressure_label.text = f'Max. Pressure: {self.maxPressure} bar'
        self.minPressure_label.text = f'Min. Pressure: {self.minPressure} bar'

        # Logic to turn the SSR on or off based on the pressure
        if pressure > self.maxPressure:
            self.ssr_off()
        elif pressure < self.minPressure:
            self.ssr_on()

    def on_stop(self):
        # Cleanup GPIO settings here
        self.ssr_off()
        GPIO.cleanup()

# Rest of your code
# ...

if __name__ == '__main__':
    app = BrewTempControlApp()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(app.async_run(async_lib='asyncio'))
    except Exception as e:
        logging.error(f'Error occurred: {e}')
    finally:
        # This will run even if the app crashes or is stopped
        app.ssr_off()  # Ensure SSR is turned off
        GPIO.cleanup()
        logging.info('Application ended and GPIO cleaned up')