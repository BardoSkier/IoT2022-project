from machine import Pin
from machine import ADC
from network import LoRa
import pycom
import socket
import utime
import ubinascii
import ustruct


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



def get_current():

    current = 0             # unit is "A"
    analog_volt = 0         # unit is "V"
    sensitivity = 0.23      # unit is "V/A"
    ref_volt = 1.5          # unit is "V"

    adc = ADC()

    # update calibrated voltage before measuremant
    adc.vref(1100)

    # We choose 11dB attenuation, so that 1V will be registered as 0.3V.
    adc_channel = adc.channel(pin='P16', attn=ADC.ATTN_11DB)

    # get analog voltage from sensor pin
    analog_volt = adc_channel.voltage()/1000
    print("The analog voltage is {} V.".format(analog_volt))
    
    current = (analog_volt-ref_volt)/sensitivity
    print("The current is {} A.".format(current))  
    
    return current


def check_downlink_message():

    global relay_active
    
    downlink_message, port = lora_sock.recvfrom(64)

    if not downlink_message:
        return 0
    
    if downlink_message[0]:
        relay_active = True
    else:
        relay_active = False

    # if downlink_message[1]:

    return 1



# --MAIN FUNCTION--

current_limit = 2.3                 # unit is "A"
relay = Pin('P8', mode=Pin.OUT)     # initialize relay's port
relay.value(False)
pycom.heartbeat(False)

while(True):
    
    # get current value from sensor
    current = get_current()

    # encode the message of current and send it to TTN
    packet = ustruct.pack('f', current)
    lora_sock.send(packet)

    # get downlink message from TTN to make the relay active/inactive
    for i in range(10):
        # Code at the indent happens every 0.1 seconds
        check_flag = check_downlink_message()
        if check_flag == 1:
            break

        utime.sleep(0.1)

    # if we can't get message from TTN in 1 second, 
    # the controller will handle the relay by itself.
    if check_flag == 0:
        if current <= current_limit:
            relay_active = True
        else:
            relay_active = False

    # make the relay active/inactive
    relay.value(relay_active)
    if relay_active:
        print("Relay active.")
        pycom.rgbled(0x007F00)  # green
    else:
        print("Relay inactive.")
        pycom.rgbled(0x7F0000)  # red

