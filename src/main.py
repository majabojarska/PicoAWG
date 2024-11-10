from machine import Pin
from rp2 import PIO, StateMachine, asm_pio
from utime import sleep_us

@asm_pio(out_init=(PIO.OUT_HIGH,)*8, out_shiftdir=PIO.SHIFT_RIGHT, autopull=True, pull_thresh=16)
def parallel_prog():
    pull()
    out(pins, 8)

parallel_state_machine = StateMachine(0, parallel_prog, out_base=Pin(8))
parallel_state_machine.active()

while True:
    for i in range(254):
        parallel_state_machine.put(i)
        print(i)
        sleep_us(1000)