from machine import Pin
from machine import ADC
from network import LoRa
import pycom
import socket
import utime
import ubinascii
import ustruct

"""
from machine import SD
import os
sd = SD()
os.mount(sd, '/sd')
os.listdir('/sd')
"""

def join_lora():

    # Initialize LoRa in LORAWAN mode
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)

    # create OTAA authentication parameters
    app_eui = ubinascii.unhexlify('0000000000000000')
    app_key = ubinascii.unhexlify('9123A357C99A6E2304C5289F694FD6BD')
    #dev_eui = ubinascii.unhexlify('70B3D54990DC335F')

    # join a network using OTAA (Over the Air Activation)
    lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0)
    #lora.join(activation=LoRa.OTAA, auth=(dev_eui, app_eui, app_key), timeout=0)

    # wait for connection
    while not lora.has_joined():
        utime.sleep(2)
        print('Waiting for LoRaWAN network connection...')

    print('Network joined!')

    # create a LoRa socket
    lora_sock = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    # set the LoRaWAN data rate
    lora_sock.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
    # make the socket non-blocking
    lora_sock.setblocking(False)

    return lora_sock


def get_current(adc_channel, sensitivity, ref_volt, offset):

    # get analog voltage from sensor pin
    analog_volt = adc_channel.voltage()/1000            # unit is "V"    
    current = (analog_volt - ref_volt)/sensitivity + offset   # unit is "A"
        
    return current


def recv_data(lora_sock):
    
    data = lora_sock.recvfrom(16)

    if len(data)>=1:
        downlink_message = ustruct.unpack('?',data[0])

    if downlink_message[0]:   
        return 1
    else:
        return 0


def send_current(lora_sock, current):

    current_mA = round(current*1000)
    # encode the message of current and send it to TTN
    packet = ustruct.pack('h', current_mA)
    lora_sock.send(packet)

    return


def collect_data(current):

    global current_actual

    current = str(current)
    current_input = input("Input the actual current (or Enter):")
    if not current_input:
        current_actual = current_input
    data = current_actual + "," + current + "\n"

    with open("/sd/current.csv","a") as datafile:
        datafile.write(data)

    return



    
# --MAIN FUNCTION--

lora_sock = join_lora()

current_limit = 2.3                 # unit is "A"
sensitivity = 0.23                  # unit is "V/A"
ref_volt = 1.5                      # unit is "V"
offset = 0.08

adc = ADC()
sensor = adc.channel(pin='P16', attn=ADC.ATTN_11DB)
relay = Pin('P8', mode=Pin.OUT)     # initialize relay's port
relay.value(False)

pycom.heartbeat(False)

while(True):
    
    # get current value from sensor
    current_sample = []
    for i in range(10):
        c = get_current(sensor, sensitivity, ref_volt, offset)
        current_sample.append(c)
        utime.sleep(0.1)
    current = sum(current_sample)/len(current_sample)
    current = round(current*1000)/1000
    print("The current is {} A.".format(current))  

    if current < current_limit:
        relay.value(True)
        pycom.rgbled(0x007F00)  # green
        # print("Relay active.")        
    else:
        relay.value(False)
        pycom.rgbled(0x007F00)  # green
        # print("Relay inactive.")

    if recv_data(lora_sock):
        send_current(lora_sock, current)

    # collect_data(current)

