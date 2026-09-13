from htra_api import *
from math import *
import numpy as np

###Turn on the device###
Status = 0          #The return value of the function
Device = c_void_p() #The memory address of the current device
DevNum = c_int(0)   #Specifies the device number

BootProfile = BootProfile_TypeDef() #Boot configuration structure, including physical interface, power supply mode, etc.
BootInfo = BootInfo_TypeDef()       #Boot information structure, including device details, USB speed, etc.

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort #Use both USB data port and independent power port for power supply.
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 #Use USB interface for data transmission.

#Configure ETH interface for Ethernet devices
#BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.ETH #Use Ethernet for data transmission.
#BootProfile.ETH_IPVersion = IPVersion_TypeDef.IPv4
#BootProfile.ETH_RemotePort = 5000
#BootProfile.ETH_ReadTimeOut = 10000
#BootProfile.ETH_IPAddress[0] = 192
#BootProfile.ETH_IPAddress[1] = 168
#BootProfile.ETH_IPAddress[2] = 1
#BootProfile.ETH_IPAddress[3] = 100

Status = dll.Device_Open(pointer(Device),DevNum,pointer(BootProfile),pointer(BootInfo)) #Open the device.
if(Status == 0):
    print("Device is opened successfully")
else:
    print("Return other errors Status = {:d}".format(Status))

###Configuration Delivery###
DET_ProfileIn = DET_Profile_TypeDef()  #DET input configuration, including center frequency, decimation factor, reference level, etc.
DET_ProfileOut = DET_Profile_TypeDef() #DET output configuration.
StreamInfo = DET_StreamInfo_TypeDef()  #DET data-related information under the current configuration, including DET data points, bytes, etc.

dll.DET_ProfileDeInit(pointer(Device),pointer(DET_ProfileIn)) #Initialize parameters related to DET mode.

DET_ProfileIn.CenterFreq_Hz = 1e9                           #Set center frequency.
DET_ProfileIn.RefLevel_dBm = 0                              #Set reference level.
DET_ProfileIn.DecimateFactor = 2                            #Set decimation factor.
DET_ProfileIn.TriggerSource = DET_TriggerSource_TypeDef.Bus #Set trigger source to internal bus trigger.

DET_ProfileIn.TriggerMode = TriggerMode_TypeDef.FixedPoints
DET_ProfileIn.TriggerLength = 16240  # Configure the number of points for a single trigger acquisition. Effective only when TriggerMode is set to FixedPoints.

Status = dll.DET_Configuration(pointer(Device), pointer(DET_ProfileIn), pointer(DET_ProfileOut), pointer(StreamInfo))  # Send DET mode related configuration.

if (Status == 0):
    print("configuration delivery succeeded")
else:
    print("DET_Configuration call returned incorrect Status = {:d}".format(Status))

### Acquire data ###
NormalizedPowerPacket = (c_float * StreamInfo.PacketSamples)()  # Create power array (data before unit conversion)
NormalizedPowerStream = (c_float * DET_ProfileOut.TriggerLength)()  # Create power array (data after unit conversion)
ScaleToV = c_float()  # This parameter is the scaling factor for absolute amplitude (in volts)
TriggerInfo = DET_TriggerInfo_TypeDef()  # Structure to store trigger information in DET mode
MeasAuxInfo = MeasAuxInfo_TypeDef()  # Structure to store auxiliary measurement information

# Attempt to import plotting module 'pyplot' to draw DET mode time-power graph
try:
    from plot_module import start_plot
    max = DET_ProfileOut.TriggerLength * 8 * DET_ProfileOut.DecimateFactor
    x_array = np.arange(0, max, 8 * DET_ProfileOut.DecimateFactor)
    update_plot = start_plot(Sup_title="Power Detection",Subplot1_X=x_array,Subplot1_Y=NormalizedPowerStream,xlabel1="time(ns)",ylabel1="PvT(dBm)",title1=None)

except ImportError:
    print("matplotlib.pyplot not available. Plotting disabled.")
    update_plot = None
    start_plot = None


try:
    RawPowerStream = (c_float * DET_ProfileOut.TriggerLength)()
    while True:
        Status = dll.DET_BusTriggerStart(pointer(Device))

        for i in range(0, StreamInfo.PacketCount):
            Status = dll.DET_GetPowerStream(pointer(Device), NormalizedPowerPacket, pointer(ScaleToV),
                                            pointer(TriggerInfo), pointer(MeasAuxInfo))
            
            start_idx = i * StreamInfo.PacketSamples
            if i == StreamInfo.PacketCount - 1 and StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0:
                num_remaining_samples = StreamInfo.StreamSamples % StreamInfo.PacketSamples
                RawPowerStream[start_idx : start_idx + num_remaining_samples] = NormalizedPowerPacket[:num_remaining_samples]
            else:
                RawPowerStream[start_idx : start_idx + StreamInfo.PacketSamples] = NormalizedPowerPacket[:]

        raw_np = np.array(RawPowerStream)
        voltages = raw_np * ScaleToV.value
        dbm_array = 10 * np.log10(20 * (voltages**2) + 1e-18)
        NormalizedPowerStream[:] = dbm_array[:]

        if update_plot and not update_plot():
            break

except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    Status = dll.DET_BusTriggerStop(pointer(Device))  # Call DET_BusTriggerStop to stop triggering the device
    dll.Device_Close(pointer(Device))  # Close the device
    print("Device closed.")
