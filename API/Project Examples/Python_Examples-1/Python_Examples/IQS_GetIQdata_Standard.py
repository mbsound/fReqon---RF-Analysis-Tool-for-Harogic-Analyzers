from htra_api import *

###Open Device###
Status = 0          #Function return value.
Device = c_void_p() #Memory address of the current device.
DevNum = c_int(0)   #Specify device number.

BootProfile = BootProfile_TypeDef() #Boot configuration structure, including physical interface, power supply method, etc.
BootInfo = BootInfo_TypeDef()       #Boot information structure, including device information, USB rate, etc.

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort #Use both USB data port and independent power port for dual power supply.
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 #Use USB interface for data transmission.

#Configure ETH interface for Ethernet device
#BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.ETH #Use Ethernet for data transmission
#BootProfile.ETH_IPVersion = IPVersion_TypeDef.IPv4
#BootProfile.ETH_RemotePort = 5000
#BootProfile.ETH_ReadTimeOut = 10000
#BootProfile.ETH_IPAddress[0] = 192
#BootProfile.ETH_IPAddress[1] = 168
#BootProfile.ETH_IPAddress[2] = 1
#BootProfile.ETH_IPAddress[3] = 100

Status = dll.Device_Open(pointer(Device),DevNum,pointer(BootProfile),pointer(BootInfo)) #Open device.
if(Status == 0):
    print("Device is opened successfully")
else:
    print("Return other errors Status = {:d}".format(Status))

###Configuration Delivery###
IQS_ProfileIn = IQS_Profile_TypeDef()  #IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
IQS_ProfileOut = IQS_Profile_TypeDef() #IQS output configuration.
StreamInfo = IQS_StreamInfo_TypeDef()  #IQ data information under the current configuration, including bandwidth, single-channel IQ sampling rate, etc.

dll.IQS_ProfileDeInit(pointer(Device),pointer(IQS_ProfileIn)) #Initialize configuration parameters for IQS mode.

IQS_ProfileIn.CenterFreq_Hz = 1e9                           #Configure center frequency.
IQS_ProfileIn.RefLevel_dBm = 0                              #Configure reference level.
IQS_ProfileIn.DecimateFactor = 2                            #Configure decimation factor.
IQS_ProfileIn.DataFormat = DataFormat_TypeDef.Complex16bit  #Configure IQ data format.
IQS_ProfileIn.TriggerSource = IQS_TriggerSource_TypeDef.Bus #Configure trigger source as internal bus trigger.

IQS_ProfileIn.TriggerMode = TriggerMode_TypeDef.FixedPoints
IQS_ProfileIn.TriggerLength = 16242                         #Configure the number of points for a single trigger capture, effective only when TriggerMode is set to FixedPoints.

Status = dll.IQS_Configuration(pointer(Device),pointer(IQS_ProfileIn),pointer(IQS_ProfileOut),pointer(StreamInfo))  #Apply IQS mode configuration.

if(Status == 0):
    print("configuration delievery succeeded")
else:
    print("SWP_Configuration call is incorrect Status = {:d}".format(Status))

### Get Data###
IQ_Data = (c_int16 * (StreamInfo.StreamSamples*2))() #Store IQ data.
AlternIQPacket = c_int16_p()                         #Pointer to temporary storage address for IQ data (library function).
ScaleToV = c_float()                                 #Scaling factor to restore amplitude to voltage.
TriggerInfo = TriggerInfo_TypeDef()              #Trace information structure.
MeasAuxInfo = MeasAuxInfo_TypeDef()                  #Measurement auxiliary information structure.

try:
    while(True):
        Status = dll.IQS_BusTriggerStart(pointer(Device)) #Call IQS_BusTriggerStart to trigger the device. If the trigger source is external, this function is not needed.
        for i in range(0,StreamInfo.PacketCount):
            dll.IQS_GetIQStream(pointer(Device),pointer(AlternIQPacket),pointer(ScaleToV),pointer(TriggerInfo),pointer(MeasAuxInfo)) #Get IQ data packet, trigger info, I-channel max value, and max value array index.
            if(i == StreamInfo.PacketCount - 1 and StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0):                        #The last packet may not be full (16242 points); so only the remaining points are needed.
                IQ_Data[(i*StreamInfo.PacketSamples*2):] = AlternIQPacket[0:(2*(StreamInfo.StreamSamples % StreamInfo.PacketSamples))]
                break
            else:
                IQ_Data[(i*StreamInfo.PacketSamples*2):((i+1)*StreamInfo.PacketSamples*2)] = AlternIQPacket[0:(StreamInfo.PacketSamples*2)]
        I_DATA = IQ_Data[0::2] #Separate I data.
        Q_DATA = IQ_Data[1::2] #Separate Q data.
        #To convert data to V units by ScaleToV, separate the data as follows:
        #scale = float(ScaleToV.value)
        #I_DATA = [x * scale for x in IQ_Data[0::2]]
        #Q_DATA = [x * scale for x in IQ_Data[1::2]]


except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    dll.Device_Close(pointer(Device))
    print("Device closed.")

