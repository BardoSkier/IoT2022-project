from machine import Pin
from machine import ADC
from network import LoRa
import pycom
import socket
import utime
import ubinascii
import ustruct

"""
# this part function is to write data to SD card,
# so that we can collect the current data and 
# try to minimize the measurment error.
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

    # try to get data from socket buffer
    downlink_message = lora_sock.recvfrom(64)

    # the type of "downlink_meaage" is tuple, and 
    # the data we need is the first element of "downlink_meaage".
    if len(downlink_message[0]) == 2:
        data = ustruct.unpack('??',downlink_message[0])
        return data
    else:
        return 0


def send_current(lora_sock, current):
    """
    This function will send the current value by socket,
    but it only send message per 7 senconds subject to 
    the socket's send buffer size. It means there is a 
    time interval at least 7 senconds between two meaasges, 
    the message won't be sent if its time interval with last
    message is less than 7 seconds.

    :param lora_sock: LoRa socket object
    :param current: the current of device
    :returns: empty
    """

    global last_send_time
    send_time = utime.time()

    if 'last_send_time' not in vars():
        last_send_time = 0

    if abs(send_time-last_send_time)<7:
        return
    else:
        # convert current unit to milliamps, because
        # parsing an "int" type data in TTN is more easily.
        current_mA = round(current*1000)

        # encode the message of current and send it to LoRa network
        packet = ustruct.pack('h', current_mA)
        lora_sock.send(packet)

        # update "last_send_time" after send a message to LoRa network
        last_send_time = send_time
        print("FiPy has sent a message: 'current: {}'".format(current))

        return


def collect_data(current):

    global current_actual
    current = str(current)    

    # if you input a actual current, the "current_actual" will be updated.
    current_input = input("Input the actual current (or Enter):")
    if not current_input:
        current_actual = current_input
    
    # write data to CSV file
    data = current_actual + "," + current + "\n"
    with open("/sd/current.csv","a") as datafile:
        datafile.write(data)

    return




# --MAIN FUNCTION--

# connect to LoRa network and generate a LoRa object
lora_sock = join_lora()

# intialize the limit current of the device that we need monitor
current_limit = 2.3                 # unit is "A"

# define some sensor's parameters
sensitivity = 0.23                  # unit is "V/A"
ref_volt = 1.5                      # unit is "V"
offset = 0.08                       # unit is "A"

# turn off the breath light on FiPy, so that we can handle the LED
pycom.heartbeat(False)

# initializa IO port of sensor
adc = ADC()
sensor = adc.channel(pin='P13', attn=ADC.ATTN_11DB)
# initializa IO port of relay
relay = Pin('P8', mode=Pin.OUT)
relay.value(True)
pycom.rgbled(0x007F00)  # green

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

    # if now current is higher than the limit current and the relay is active, 
    # we will trun off the relay and make the LED turn to red.
    if current > current_limit and relay():
        relay.value(False)
        pycom.rgbled(0x7F0000)  # red
        # print("Now relay is inactive.")

    # check if FiPy received any instructions from base station
    data = recv_data(lora_sock)
    if data:
        # instruction type 1: send current to LoRa network
        if data[0]:
            send_current(lora_sock, current)
        # instruction type 2: turn on the relay
        if data[1]:
            relay.value(True)
            pycom.rgbled(0x007F00)  # green

    # send_current(lora_sock, current)

    # collect_data(current)
