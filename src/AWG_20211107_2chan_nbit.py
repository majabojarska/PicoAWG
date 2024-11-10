# Arbitrary waveform generator for Rasberry Pi Pico
# Requires 1 or 2 R2R DACs. Works for R=1kOhm
# Achieves up to 125Msps when running 125MHz clock
# Rolf Oldeman, 7/11/2021. CC BY-NC-SA 4.0 licence
# tested with rp2-pico-20210902-v1.17.uf2
from machine import Pin,mem32
from rp2 import PIO, StateMachine, asm_pio
from array import array
from utime import sleep
from math import pi,sin,exp,sqrt,floor
from uctypes import addressof
from random import random

fclock=250000000 #clock frequency to run the pico default 125MHz. Allow 100-250
nbit_ch1=11      #also type sum of nbit_ch1 and nbit_ch1 in 'stream' function !!
nbit_ch2=11     
inv_ch1=False    #set true if MSB comes first
inv_ch2=True
sampword=1       #number of samples per 32-bit word
pinbase=0        #first active pin
maxnword=2048    #maximum number of words per buffer (max 8192 = 128kbyte total)

#set desired clock frequency
if fclock<100e6 or fclock>250e6:
    print("invalid clock speed",fclock)
    exit(1)
PLL_SYS_BASE=0x40028000
PLL_SYS_FBDIV_INT=PLL_SYS_BASE+0x8
PLL_SYS_PRIM     =PLL_SYS_BASE+0xc
if fclock<=130000000:
    FBDIV=int(fclock/1000000)
    POSTDIV1=6  #default 6
    POSTDIV2=2  #default 2
else: 
    FBDIV=int(fclock/2000000)
    POSTDIV1=3  #default 6
    POSTDIV2=2  #default 2
mem32[PLL_SYS_PRIM]=(POSTDIV1<<16)|(POSTDIV2<<12)
mem32[PLL_SYS_FBDIV_INT]=FBDIV
print('clock speed',FBDIV*12/(POSTDIV1*POSTDIV2),'MHz')


DMA_BASE=0x50000000
CH0_READ_ADDR  =DMA_BASE+0x000
CH0_WRITE_ADDR =DMA_BASE+0x004
CH0_TRANS_COUNT=DMA_BASE+0x008
CH0_CTRL_TRIG  =DMA_BASE+0x00c
CH0_AL1_CTRL   =DMA_BASE+0x010
CH1_READ_ADDR  =DMA_BASE+0x040
CH1_WRITE_ADDR =DMA_BASE+0x044
CH1_TRANS_COUNT=DMA_BASE+0x048
CH1_CTRL_TRIG  =DMA_BASE+0x04c
CH1_AL1_CTRL   =DMA_BASE+0x050

PIO0_BASE      =0x50200000
PIO0_TXF0      =PIO0_BASE+0x10
PIO0_SM0_CLKDIV=PIO0_BASE+0xc8

#state machine that just pushes bytes to the pinsß
@asm_pio(out_init=(PIO.OUT_HIGH,)*(nbit_ch1+nbit_ch2),
         out_shiftdir=PIO.SHIFT_RIGHT,
         autopull=True,
         fifo_join=PIO.JOIN_TX,
         pull_thresh=(nbit_ch1+nbit_ch2)*sampword)
def stream():
    out(pins,22)

#initialize PIO - the frequency setting assumes clock speed of 125MHz
sm = StateMachine(0, stream, freq=125000000, out_base=Pin(pinbase))
sm.active(1)

#2-channel chained DMA. channel 0 does the transfer, channel 1 reconfigures
p=array('I',[0]) #global 1-element array
def startDMA(ar,nword):
    #first disable the DMAs to prevent corruption while writing
    mem32[CH0_AL1_CTRL]=0
    mem32[CH1_AL1_CTRL]=0
    #setup first DMA which does the actual transfer
    mem32[CH0_READ_ADDR]=addressof(ar)
    mem32[CH0_WRITE_ADDR]=PIO0_TXF0
    mem32[CH0_TRANS_COUNT]=nword
    IRQ_QUIET=0x1 #do not generate an interrupt
    TREQ_SEL=0x00 #wait for PIO0_TX0
    CHAIN_TO=1    #start channel 1 when done
    RING_SEL=0
    RING_SIZE=0   #no wrapping
    INCR_WRITE=0  #for write to array
    INCR_READ=1   #for read from array
    DATA_SIZE=2   #32-bit word transfer
    HIGH_PRIORITY=1
    EN=1
    CTRL0=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH0_AL1_CTRL]=CTRL0
    #setup second DMA which reconfigures the first channel
    p[0]=addressof(ar)
    mem32[CH1_READ_ADDR]=addressof(p)
    mem32[CH1_WRITE_ADDR]=CH0_READ_ADDR
    mem32[CH1_TRANS_COUNT]=1
    IRQ_QUIET=0x1 #do not generate an interrupt
    TREQ_SEL=0x3f #no pacing
    CHAIN_TO=0    #start channel 0 when done
    RING_SEL=0
    RING_SIZE=0   #no wrapping
    INCR_WRITE=0  #single write
    INCR_READ=0   #single read
    DATA_SIZE=2   #32-bit word transfer
    HIGH_PRIORITY=1
    EN=1
    CTRL1=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH1_CTRL_TRIG]=CTRL1


def invbits(x,n):
    y=0
    for i in range(n):
        if (x&(1<<i))>0 : y+=(1<<(n-1-i))
    return y


def setupwaves(buf,f,w1,w2):
    if sampword==1: mindiv=3
    if sampword==2: mindiv=2
    if sampword==3: mindiv=1
    if sampword==4: mindiv=1
        
    div=fclock/(f*(maxnword*sampword)) # required clock division for maximum buffer size
    if div<mindiv:  #can't speed up clock, duplicate wave instead
        dup=int(mindiv/div)
        nword=int(maxnword*dup*div/mindiv+0.5)
        clkdiv=mindiv
    else:        #stick with integer clock division only
        clkdiv=int(div)+mindiv
        nword=int(maxnword*div/clkdiv+0.5)
        dup=1
    nsamp=nword*sampword    
    print("div",div,"clkdiv",clkdiv,"dup",dup,"nword",nword,"nsamp",nsamp)

    #fill the buffer
    for iword in range(nword):
        word=0
        for i in range(sampword):
            isamp=iword*sampword+i
            val1=max(0,min((1<<nbit_ch1)-1,int((1<<nbit_ch1)*(0.5+0.5*eval(w1,dup*(isamp+0.5)/nsamp)))))
            val2=max(0,min((1<<nbit_ch2)-1,int((1<<nbit_ch2)*(0.5+0.5*eval(w2,dup*(isamp+0.5)/nsamp)))))
            if inv_ch1: val1=invbits(val1,nbit_ch1)
            if inv_ch2: val2=invbits(val2,nbit_ch2)
            word=word+(val1<<(i*(nbit_ch1+nbit_ch2)))
            word=word+(val2<<(i*(nbit_ch1+nbit_ch2)+nbit_ch1))
            #print(iword,i,isamp,val,word)
        buf[iword*4+0]=(word&(255<< 0))>> 0
        buf[iword*4+1]=(word&(255<< 8))>> 8
        buf[iword*4+2]=(word&(255<<16))>>16
        buf[iword*4+3]=(word&(255<<24))>>24
        #print(iword,word)
        
    #set the clock divider
    clkdiv_int=min(clkdiv,65535) 
    clkdiv_frac=0 #fractional clock division results in jitter
    mem32[PIO0_SM0_CLKDIV]=(clkdiv_int<<16)|(clkdiv_frac<<8)

    #start DMA
    startDMA(buf,nword)


#evaluate the content of a wave
def eval(w,x):
    m,s,p=1.0,0.0,0.0
    if 'phasemod' in w.__dict__:
        p=eval(w.phasemod,x)
    if 'mult' in w.__dict__:
        m=eval(w.mult,x)
    if 'sum' in w.__dict__:
        s=eval(w.sum,x)
    x=x*w.replicate-w.phase-p
    x=x-floor(x)  #reduce x to 0.0-1.0 range
    v=w.func(x,w.pars)
    v=v*w.amplitude*m
    v=v+w.offset+s
    return v

#some common waveforms. combine with sum,mult,phasemod
def sine(x,pars):
    return sin(x*2*pi)
def pulse(x,pars): #risetime,uptime,falltime
    if x<pars[0]: return x/pars[0]
    if x<pars[0]+pars[1]: return 1.0
    if x<pars[0]+pars[1]+pars[2]: return 1.0-(x-pars[0]-pars[1])/pars[2]
    return 0.0
def gaussian(x,pars):
    return exp(-((x-0.5)/pars[0])**2)
def sinc(x,pars):
    if x==0.5: return 1.0
    else: return sin((x-0.5)/pars[0])/((x-0.5)/pars[0])
def exponential(x,pars):
    return exp(-x/pars[0])
def noise(x,pars): #p0=quality: 1=uniform >10=gaussian
    return sum([random()-0.5 for _ in range(pars[0])])*sqrt(12/pars[0])
    

#make buffers for the waveform.
#large buffers give better results but are slower to fill
wavbuf={}
wavbuf[0]=bytearray(maxnword*4)
wavbuf[1]=bytearray(maxnword*4)
ibuf=0

#empty class just to attach properties to
class wave:
    pass


wave1=wave()
wave1.amplitude=1.0
wave1.offset=0.0
wave1.phase=0.0
wave1.replicate=1
wave1.func=sine
wave1.pars=[0.0,0.5,0.0]

wave2=wave()
wave2.amplitude=1.0
wave2.offset=0.0
wave2.phase=0.0
wave2.replicate=2
wave2.func=sine
wave2.pars=[0.0,0.5,0.0]



setupwaves(wavbuf[ibuf],1e6,wave1,wave2); ibuf=(ibuf+1)%2
    


