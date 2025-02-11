#-*- coding: utf-8 -*-
# sudo apt-get install -y python3-bitarray
import ctypes
import os
import time
import random
import datetime
#import tty
import sys
#import termios
#orig_settings = termios.tcgetattr(sys.stdin)
#tty.setcbreak(sys.stdin)

from ctypes import *            
from ctypes import create_string_buffer
from ctypes import c_buffer
from ctypes import sizeof
from ctypes import cdll
from datetime import datetime
from datetime import timedelta

#UART奇偶校验位
UART_Parity_No =                     0
UART_Parity_Odd =                    1
UART_Parity_Even =                   2

#UART停止位
UART_StopBits_1 =                    0
UART_StopBits_1_5 =                  1
UART_StopBits_2 =                    2

#SPI速率
SPI_Rate_281K=						0
SPI_Rate_562K=						1
SPI_Rate_1_125M	=					2
SPI_Rate_2_25M=						3
SPI_Rate_4_5M=						4
SPI_Rate_9M	=						5
SPI_Rate_18M=						6
SPI_Rate_36M=						7

#SPI帧格式
SPI_MSB	=							0
SPI_LSB	=							1

#SPI时钟模式
SPI_SubMode_0=						0
SPI_SubMode_1=						1
SPI_SubMode_2=						2
SPI_SubMode_3=						3

#IIC速率
IIC_Rate_1K	=						0
IIC_Rate_5K	=						1
IIC_Rate_10K=						2
IIC_Rate_20K=						3
IIC_Rate_50K=						4
IIC_Rate_80K=						5
IIC_Rate_100K=						6   #130KHz
IIC_Rate_200K=						7   #204KHz
IIC_Rate_400K=						8   #555KHz
IIC_Rate_600K=						9
IIC_Rate_800K=						10
IIC_Rate_1M	=						11

#IIC 寻址模式
IIC_ADDRMOD_7BIT=					0
IIC_ADDRMOD_10BIT=					1

#内建列表功能1
LINE_FUN1_SPI_CS0_0_1=		    	0
LINE_FUN1_SPI_CS0_1_0=		    	1
LINE_FUN1_SPI_CS0_1_1=		    	2
LINE_FUN1_SPI_CS0_0_0=		    	3
LINE_FUN1_SPI_CS1_0_1=		    	4
LINE_FUN1_SPI_CS1_1_0=		    	5
LINE_FUN1_SPI_CS1_1_1=		    	6
LINE_FUN1_SPI_CS1_0_0=		    	7
LINE_FUN1_SPICS_0 =   		    	8
LINE_FUN1_SPICS_1 =   		    	9
LINE_FUN1_IIC_AddStart= 		    	10
LINE_FUN1_IIC_NoStart=		    	11
LINE_FUN1_IICd_send  =		    	12
LINE_FUN1_IICd_read  =		    	13
LINE_FUN1_IICr_send = 		    	14
LINE_FUN1_IICr_read = 		    	15
LINE_FUN1_UART_  =    		    	16
LINE_FUN1_IO_0  =     		    	17
LINE_FUN1_IO_1  =     		    	18
LINE_FUN1_PWM_start = 		    	19
LINE_FUN1_PWM_stop =  		    	20
LINE_FUN1_ADC_0  =     		    	21
LINE_FUN1_ADC_1	=			        22

#内建列表功能2
LINE_FUN2_null	=					0             
LINE_FUN2_SPI_full	=				1
LINE_FUN2_SPI_half	=				2
LINE_FUN2_SPICS_h=					3
LINE_FUN2_SPICS_l=					4
LINE_FUN2_IIC_AddStop=				5
LINE_FUN2_IIC_NoStop=				6
LINE_FUN2_IICd_7bit	=				7
LINE_FUN2_IICd_10bit=				8
LINE_FUN2_IICr_7bit	=				9
LINE_FUN2_IICr_10bit=				10
LINE_FUN2_IO_w	=					11
LINE_FUN2_IO_r=						12


UsbIndex=0
duplex=1
Dir_USB2UARTSPIIICDLL = "D:\\prj_BP1108\\BP1108\\USB2UARTSPIIICDLL.dll"
libtest = ctypes.CDLL(Dir_USB2UARTSPIIICDLL)

startCS=0
endCS=1
clkdiv=0x1
RW_Write=0x80
FIFO= bytes(100)
register_defaults=[]
first=0

def debug(*strings):
    if(0):
        for string in strings:
            print(string,end='')
        print("")
        
def start():
    global first
#    print ("Invoke start",first)
    debug("********** Set Master Configuration 0 Register")
    if (first==0):
        first=1
        return
    MOSI=[RW_Write|0x11,0x1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")


#reset    
def master_reset():
    debug("********** Master Reset L-H")
    IONum=0
    IODir=1
    libtest.IOSetAndRead(IONum,IODir,0,UsbIndex)
    libtest.IOSetAndRead(IONum,IODir,1,UsbIndex)
    Result=libtest.IOSetAndRead(1,IODir,0,UsbIndex)

#Read int_o (master) if available
def ReadInterrupt():
    debug("********** Read int_o")
    IONum=1
    IODir=0
    Result=libtest.IOSetAndRead(IONum,IODir,0,UsbIndex)
    return Result

#LogicAnalyzer_Trigger
def Trigger():
    debug("********** LogicAnalyzer_Trigger")
    IONum=1
    IODir=1
    Result=libtest.IOSetAndRead(IONum,IODir,0,UsbIndex)
    Result=libtest.IOSetAndRead(IONum,IODir,1,UsbIndex)
    Result=libtest.IOSetAndRead(IONum,IODir,0,UsbIndex)

#Directed SETDASA
def SETDASA(static_addr,dynamic_addr):
    debug("********** Directed SETDASA")
    MOSI=[RW_Write|0x30,0x9,0xfc,0x01,0x87,0x7,static_addr<<1,0x01,dynamic_addr<<1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")

#Directed SETAASA
def SETAASA():
    debug("********** Directed SETDASA")
    MOSI=[RW_Write|0x30,0xd,0xfc,0x01,0x29]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")

#RSTDAA
def RSTDAA():
    debug("********** RSTDAA")
    MOSI=[RW_Write|0x30,0x0d,0xfc,0x01,0x06]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")

#Set PID
def set_pid(pid,dynamic_addr):
#    Trigger()
    for i in range(47,-1,-1):
#        Trigger()
        if (pid & (1<<i)):
#            time.sleep(0.1)
            MOSI=[RW_Write|0x30,0x00,dynamic_addr<<1,0x01,0x6]
            SendBuffer=bytes(MOSI)
            Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
            if(ReadInterrupt()!=1):
                print("H ",i)
#                exit(1)
        else:
#            time.sleep(0.1)
            MOSI=[RW_Write|0x30,0x00,dynamic_addr<<1,0x01,0x2]
            SendBuffer=bytes(MOSI)
            Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
            if(ReadInterrupt()!=0):
                print("L ",i)
#                exit(1)
        start()

#Set Master Configuration 0 Register
def setcfg0(mst_cfg0):
    debug("********** Set Master Configuration 0 Register")
    MOSI=[RW_Write|0x02,mst_cfg0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")

#Set Master Configuration 0 Register
def soft_reset():
    debug("********** Set Master Configuration 0 Register")
    MOSI=[RW_Write|0x08,0x2]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")


#ENTDAA
def ENTDAA(dynamic_addr):
    debug("********** ENTDAA")
    parity = 1
    n=dynamic_addr
    while n:
        parity = ~parity
        n = n & (n - 1)
    MOSI=[RW_Write|0x30,0x0d,0xfc,0x02,0x07,(dynamic_addr<<1)|(parity&0x01)]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")

#ENTDAA2
def ENTDAA2(*dynamic_addr):
    debug("********** ENTDAA2")
    MOSI=[RW_Write|0x30,0x0d,0xfc]
    MOSI.append(len(dynamic_addr)+1)
    MOSI.append(0x7)
    for dynaddr in dynamic_addr:
        parity = 1
        n=dynaddr
        while n:
            parity = ~parity
            n = n & (n - 1)
        dynaddr=(dynaddr<<1)|(parity&0x01)
        MOSI.append(dynaddr)

#    MOSI=[RW_Write|0x30,0x0d,0xfc,0x03,0x07,(dynamic_addr<<1)|(parity&0x01),(dynamic_addr2<<1)|(parity2&0x01)]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer),"\r")



#Read FIFO
def ReadFIFO(length):
    debug("********** ReadFIFO(0x40) ",length)
    MOSI=[0x40,0xff]
    SendBuffer=bytes(MOSI)
    FIFO= bytes(2+length)
    Result = libtest.SPISendAndRcvData(0,startCS,endCS,0,duplex,0xff,SendBuffer,FIFO,len(SendBuffer),length,UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))
    debug("MISO ",''.join('{:02x} '.format(a) for a in FIFO),"\r")
    return FIFO

#Low active Test_mode
def Test_mode(data):
    debug("********** Activate Test_Mode",data)
    libtest.SPISetCS1(data,UsbIndex)

#Read Register
def ReadReg(Register):
    debug("********** Read Register: ",Register)
    MOSI=[Register]
    SendBuffer=bytes(MOSI)
    RevBuffer= bytes(len(MOSI)+2)
#    SPISendAndRcvData(unsigned char CSshelect,unsigned char startCS, unsigned char endCS, unsigned int CSdelay, unsigned char duplex,unsigned char dummy,
#														unsigned char *sendBuf,unsigned char *rcvBuf,unsigned int slen,unsigned int rlen,unsigned int UsbIndex);

    Result = libtest.SPISendAndRcvData(0,startCS,endCS,0,duplex,0xff,SendBuffer,RevBuffer,len(SendBuffer),2,UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))
    debug("MISO ",''.join('{:02x} '.format(a) for a in RevBuffer),"\r")
    return RevBuffer[2]

#Write Register
def WriteReg(Register,data):
    debug("********** Read int_status")
    MOSI=[RW_Write|Register]
    MOSI.append(data);
    SendBuffer=bytes(MOSI)
    RevBuffer= bytes(len(MOSI))
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Directed_SETNEWDA
def SETNEWDA(old_addr,new_addr):
    debug("********** SETNEWDA",old_addr,new_addr)
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x88,0x7,old_addr<<1,0x01,new_addr<<1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Private Write FIFO - Start Sampling
def Start_EN(dynamic_addr):
    debug("********** Start_EN")
    MOSI=[RW_Write|0x30,0x00,dynamic_addr<<1,0x02,0x00,0x1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Private Read
def ReadSlaveFIFO(dynamic_addr,length):
    debug("********** Read Slave FIFO (0x30)")
    MOSI=[RW_Write|0x30,0x00,(dynamic_addr<<1) | 0x1,length]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#CheckRegs
def CheckRegs():
    register_addrs = [0x1,0x2,0x3,0x4,0x8,0x11,0x20,0x22]
    for  no, register in enumerate(register_addrs):
        list=[register]
        print("Register :",'0x{:02x} '.format(register),"default:0x{:02x} ".format(register_defaults[no]),"0x{:02x} ".format(ReadReg(register)))
    print("\n")

#GetRegDefaults
def GetRegDefaults():
    register_addrs = [0x1,0x2,0x3,0x4,0x8,0x11,0x20,0x22]
    for  no, register in enumerate(register_addrs):
        register_defaults.append(ReadReg(register))
#
            
#I2C write
def I2C_Write(static_addr,*data):
    debug("********** I2C write")
    MOSI=[RW_Write|0x30,0x14,static_addr<<1]
    MOSI.append(len(data))
    for datum in data:
        MOSI.append(datum)
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#I2C write address
def I2C_WriteAddr(static_addr):
    debug("********** I2C write")
    MOSI=[RW_Write|0x30,0x14,static_addr<<1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
#    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#I2C Read
def I2C_Read(static_addr,length):
    global first
    debug("********** I2C Read")
    MOSI=[RW_Write|0x30,0x14,static_addr<<1|0x1]
    MOSI.append(length)
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#I2C Consecutive Private Write + Private Read
def I2C_Write_Read(static_addr,length,*data):
    debug("********** I2C write + Read")
    MOSI=[RW_Write|0x30,0x10,static_addr<<1]
    MOSI.append(len(data))
    for datum in data:
        MOSI.append(datum)
    MOSI.append(0x16)
    MOSI.append(static_addr<<1|0x1)
    MOSI.append(length)
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#GETMWL
def GETMWL(dynamic_addr):
    debug("********** GETMWL")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x8B,0x7,dynamic_addr<<1|0x1,0x2]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#GETMRL
def GETMRL(dynamic_addr):
    debug("********** GETMRL")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x8C,0x7,dynamic_addr<<1|0x1,0x2]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#GETPID
def GETPID(dynamic_addr):
    debug("********** GETPID")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x8D,0x7,dynamic_addr<<1|0x1,0x6]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#GETBCR
def GETBCR(dynamic_addr):
    debug("********** GETBCR")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x8E,0x7,dynamic_addr<<1|0x1,0x1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#GETDCR
def GETDCR(dynamic_addr):
    debug("********** GETDCR")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x8F,0x7,dynamic_addr<<1|0x1,0x1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))


#GETSTATUS
def GETSTATUS(dynamic_addr):
    debug("********** GETSTATUS")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x90,0x7,dynamic_addr<<1|0x1,0x2]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#SETMWL
def SETMWL(dynamic_addr,MWL_MSB,MWL_LSB):
    debug("********** SETMWL")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x89,0x7,dynamic_addr<<1,0x2,MWL_MSB,MWL_LSB]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#SETMRL
def SETMRL(dynamic_addr,MRL_MSB,MRL_LSB):
    debug("********** SETMWL")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x8A,0x7,dynamic_addr<<1,0x2,MRL_MSB,MRL_LSB]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))
'''
#Broadcast_ENTAS0
def BroadENTAS0(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x02,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Directed_ENTAS0
def DirectENTAS0(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x82,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Broadcast_ENTAS1
def BroadENTAS1(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x03,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Directed_ENTAS1
def DirectENTAS1(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x83,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Broadcast_ENTAS2
def BroadENTAS2(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x04,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Directed_ENTAS2
def DirectENTAS2(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x84,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Broadcast_ENTAS3
def BroadENTAS3(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x01,0xfc,0x01,0x05,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#Directed_ENTAS3
def DirectENTAS3(dynamic_addr):
    debug("********** ENTAS0")
    MOSI=[RW_Write|0x30,0x01,0xfc,0x01,0x85,0x7,dynamic_addr<<1,0x0]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#ENEC
def ENEC(dynamic_addr,data):
    debug("********** ENEC")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x80,0x7,dynamic_addr<<1,0x1,data]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

#DISEC
def DISEC(dynamic_addr,data):
    debug("********** DISEC")
    MOSI=[RW_Write|0x30,0x09,0xfc,0x01,0x81,0x7,dynamic_addr<<1,0x1,data]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))
'''
#Bus Selection
def Bus(bus):
    debug("********** Select Bus",7)
    MOSI=[RW_Write|0x50,bus]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

def ReadIMU(dynamic_addr,reg):
    debug("********** Start_EN")
    MOSI=[RW_Write|0x30,0x00,dynamic_addr<<1,0x01,reg,0x06,dynamic_addr<<1|0x1,0x1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

def ReadASIC(dynamic_addr,reg):
    debug("********** Start_EN")
    MOSI=[RW_Write|0x30,0x00,dynamic_addr<<1,0x01,reg,0x06,dynamic_addr<<1|0x1,0x1]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

def WriteIMU(dynamic_addr,reg,data):
    debug("********** Start_EN")
    MOSI=[RW_Write|0x30,0x04,dynamic_addr<<1,0x02,reg,data]
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

def WriteASIC(dynamic_addr,reg,*data):
    debug("********** Start_EN")
    MOSI=[RW_Write|0x30,0x04,dynamic_addr<<1]
    MOSI.append(len(data)+1)
    MOSI.append(reg)
    for datum in data:
        MOSI.append(datum)
    SendBuffer=bytes(MOSI)
    Result = libtest.SPISendData(startCS,endCS,SendBuffer,len(SendBuffer),UsbIndex)
    start()
    debug("MOSI ",''.join('{:02x} '.format(a) for a in SendBuffer))

def I2C_Write_v2(static_addr,*data):
    debug("********** I2C write")
    temp=[]
    for datum in data:
        temp.append(datum)
    SendBuffer=bytes(temp)
    Result = Is_Send = libtest.IICDirectSend(0,static_addr,SendBuffer,len(SendBuffer),0);
    debug("I2C Write ",''.join('{:02x} '.format(a) for a in SendBuffer))

def I2C_Read_v2 (static_addr,length):
    Buffer=bytes(length)
    Result = libtest.IICDirectRead(0,static_addr,Buffer,length,0);
    debug("I2C Read ",''.join('{:02x} '.format(a) for a in Buffer))
    return Buffer

def ISHFTC(n, d, N):  
    return ((n << d) % (1 << N)) | (n >> (N - d))

Is_Open = libtest.OpenUsb(ctypes.c_uint(0))
if (Is_Open<0):
    print("usb fail")
    libtest.CloseUsb(ctypes.c_uint(0))
    exit(1)
    debug("usb open")
else:
    debug("usb open")
'''
Is_Open = libtest2.OpenUsb(ctypes.c_uint(1))
if (Is_Open<0):
    print("usb fail")
    libtest2.CloseUsb(ctypes.c_uint(1))
    exit(1)
    debug("usb open")
else:
    debug("usb open")
'''
No_complete=0
ERR01=0
ERR03=0
ERR04=0
ERR13=0
ERR15=0
ERR16=0
ERR17=0
ERR18=0
ERR19=0
SPI_Rate_281K = 0
SPI_Rate_562K = 1
SPI_Rate_1_125M = 2
SPI_Rate_2_25M = 3

SPI_Rate_4_5M = 4   #4.5MHz=4.5MPS
SPI_Rate_9M = 5     #9MHz=9MPS

SPI_Rate_18M = 6
#ConfigIICParam(unsigned int rate,unsigned int clkSLevel,unsigned int UsbIndex);
Is_True = libtest.ConfigSPIParam(3,SPI_MSB,SPI_SubMode_3,UsbIndex)
Is_True =libtest.ConfigIICParam(IIC_Rate_400K,10000,0)

libtest.IOSetAndRead(0,1,0,UsbIndex)

I2C_Addr=0x63
#I2C_Addr=0x67
#I2C_Addr=0x6B
#I2C_Addr=0x6F
print("Set Registers")
I2C_Write_v2(I2C_Addr,0x01,0x01)    # Soft RESET
I2C_Write_v2(I2C_Addr,0x20,0x95)    # 7/VREF_EN[7],6-5/ctrl_pga_power[1:0],4-2/ctrl_pga_gain[2:0],1/0,0/ctrl_pga_en
I2C_Write_v2(I2C_Addr,0x23,0x01)    # 7/Vref_ctl,5/ctrl_en_test_iadc,4/ctrl_en_opamp_lp2_iadc,3/ctrl_en_opamp_lp1_iadc,2/ctrl_en_bias_lp_iadc,1/ctrl_en_offset_cal_iadc,0/ctrl_en_chop_sdm
I2C_Write_v2(I2C_Addr,0x2a,0x87)    # 7/DTEST_EN,2/Sel2p5m,1/SCL_PU,0/SDA_PU
I2C_Write_v2(I2C_Addr,0x24,0xff)    # 7-4/SEL2_Y,3-0/SEL1_X
I2C_Write_v2(I2C_Addr,0x25,0x0f)    # 3-0/SEL3_Z
I2C_Write_v2(I2C_Addr,0x26,0x01)    # 3-0/RUN_NUM_CONVERTER[11:8]
I2C_Write_v2(I2C_Addr,0x27,0x00)    # 7-0/RUM_NUM_CONVERTER[7:0], 5-3/ClkDiv[2:0]
I2C_Write_v2(I2C_Addr,0x28,0x28)    # 5-0/REG_NUM_SET[6:0]
I2C_Write_v2(I2C_Addr,0x29,0x20)    # 5-0/REG_NUM_INIT[5:0]
I2C_Write_v2(I2C_Addr,0x1e,0x0)     # DTESTO probe control
#  0x1e     DTESTO
#
#   0x00    LOW
#   0x01    En_Vadc
#   0x02    Clk_2d5_1d25M
#   0x03    Int_250us
#   0x04    complete
#   0x05    int_in_STOP
#   0x06    Clk25M
#   0x07    int_da_matched
#   0x08    pin_SCL
#   0x09    pin_SDA_in
#   0x0A    pin_SDA_out
#   0x0B    pin_SDA_oena
#   0x0C    CS
#   0x0D    PROGEN
#   0x0F    SENSE
#   0x10    adc_ibs
#   0x11    adc_rst
#   0x12    adc_chop

# Dump the register content
for reg in range(0x20,0x31):
    I2C_Write_v2(I2C_Addr,reg)
    print("REG{:x} value 0x{:x}".format(reg,I2C_Read_v2(I2C_Addr,1)[0]))

input ("Hit return to start")

Display_ADC_Data=1

while(1):
#    for commandx in (0b0000_0001,0b0100_0001,0b1000_0001,0b1100_0001,0b0000_0010,0b0100_0010,0b1000_0010,0b1100_0010,0b0000_0011,0b0100_0011,0b1000_0011,0b1100_0011,0b1110_0011,0b0110_0001,0b0110_0010,0b1010_0010,0b1000_0000,0b0110_0000):
#
#  command=0b1100_0011
    command=0b1000_0001  # Read Temp Only
    I2C_Write_v2(I2C_Addr,0x00,command) # Trigger measure

    time.sleep(0.1)
    
# Display the ADC return result, comment it out to disable the extra I2C command for easy probing
    if(Display_ADC_Data):
        Sample_count=[((command &0x1) +((command >>1 ) & 0x1)*3),(((command &0x1) +((command >>1 ) & 0x1)*3)*2)] [(command>>6)==0b11]
        FIFO=I2C_Read_v2(I2C_Addr,Sample_count*3)
        print("I2C Read ",''.join('{:02x} '.format(a) for a in FIFO),end='')
        if (Sample_count==1):
            print("T1:",int.from_bytes(FIFO[0:3],"big",signed="True"))
        elif (Sample_count==2):
            print("T1:",int.from_bytes(FIFO[0:3],"big",signed="True")\
                ,"T2:",int.from_bytes(FIFO[3:6],"big",signed="True"))
        elif (Sample_count==3):
            print("X1:",int.from_bytes(FIFO[0:3],"big",signed="True")\
                ,"Y1:",int.from_bytes(FIFO[3:6],"big",signed="True")\
                ,"Z1:",int.from_bytes(FIFO[6:9],"big",signed="True"))
        elif (Sample_count==4):
            print("X1:",int.from_bytes(FIFO[0:3],"big",signed="True")\
                ,"Y1:",int.from_bytes(FIFO[3:6],"big",signed="True")\
                ,"Z1:",int.from_bytes(FIFO[6:9],"big",signed="True")\
                ,"T1:",int.from_bytes(FIFO[9:12],"big",signed="True"))
        elif (Sample_count==6):
            print("X1:",int.from_bytes(FIFO[0:3],"big",signed="True")\
                ,"Y1:",int.from_bytes(FIFO[3:6],"big",signed="True")\
                ,"Z1:",int.from_bytes(FIFO[6:9],"big",signed="True")\
                ,"X2:",int.from_bytes(FIFO[9:12],"big",signed="True")\
                ,"Y2:",int.from_bytes(FIFO[12:15],"big",signed="True")\
                ,"Z2:",int.from_bytes(FIFO[15:18],"big",signed="True"))    
        elif (Sample_count==8):
            print("X1:",int.from_bytes(FIFO[0:3],"big",signed="True")\
                ,"Y1:",int.from_bytes(FIFO[3:6],"big",signed="True")\
                ,"Z1:",int.from_bytes(FIFO[6:9],"big",signed="True")\
                ,"T1:",int.from_bytes(FIFO[9:12],"big",signed="True")\
                ,"X2:",int.from_bytes(FIFO[12:15],"big",signed="True")\
                ,"Y2:",int.from_bytes(FIFO[15:18],"big",signed="True")\
                ,"Z2:",int.from_bytes(FIFO[18:21],"big",signed="True")\
                ,"T2:",int.from_bytes(FIFO[21:24],"big",signed="True"))    
    else:
            print(".",end='')

libtest.CloseUsb(ctypes.c_uint(0))





























