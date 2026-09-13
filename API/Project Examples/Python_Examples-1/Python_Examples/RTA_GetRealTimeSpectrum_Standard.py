from htra_api import *
import numpy as np
### Open Device###
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
RTA_ProfileIn = RTA_Profile_TypeDef()  #RTA input configuration, including center frequency, decimation factor, reference level, etc.
RTA_ProfileOut = RTA_Profile_TypeDef() #RTA output configuration.
FrameInfo = RTA_FrameInfo_TypeDef()    #RTA data-related information under the current configuration, including start frequency, stop frequency, data points, etc.

dll.RTA_ProfileDeInit(pointer(Device),pointer(RTA_ProfileIn)) #Initialize configuration parameters for RTA mode.

RTA_ProfileIn.CenterFreq_Hz = 1e9                           #Configure center frequency.
RTA_ProfileIn.RefLevel_dBm = 0                              #Configure reference level.
RTA_ProfileIn.DecimateFactor = 1                            #Configure decimation factor.
RTA_ProfileIn.TriggerSource = RTA_TriggerSource_TypeDef.Bus #Configure trigger source as internal bus trigger.
RTA_ProfileIn.TriggerMode = TriggerMode_TypeDef.FixedPoints
RTA_ProfileIn.TriggerAcqTime = 0.1 						#Configure sampling time after trigger as 0.1s, effective only in FixedPoints mode.

Status = dll.RTA_Configuration(pointer(Device),pointer(RTA_ProfileIn),pointer(RTA_ProfileOut),pointer(FrameInfo)) #Apply RTA mode configuration.

if(Status == 0):
    print("configuration delievery succeeded")
else:
    print("SWP_Configuration call is incorrect Status = {:d}".format(Status))

###Get Data###
SpectrumTrace = (c_uint8 *FrameInfo.PacketValidPoints)()                      #Spectrum array.
SpectrumBitmap = (c_uint16 *(FrameInfo.FrameHeight * FrameInfo.FrameWidth))() #Spectrum bitmap array.
Spectrum = (c_float *FrameInfo.FrameWidth)()                                  #Power array.
RTA_PlotInfo = RTA_PlotInfo_TypeDef()                                         #Plot information.
TriggerInfo = RTA_TriggerInfo_TypeDef()                                       #Trigger information.
MeasAuxInfo = MeasAuxInfo_TypeDef()                                           #Auxiliary measurement information.

# Try to import the plotting module pyplot and plot the RTA mode spectrum graph
try:
    from plot_module import start_plot
    max = FrameInfo.StopFrequency_Hz
    x_array = np.arange(FrameInfo.StartFrequency_Hz, max, ((FrameInfo.StopFrequency_Hz-FrameInfo.StartFrequency_Hz)/FrameInfo.FrameWidth))
    update_plot = start_plot(Sup_title="Real-time Spectrum", Subplot1_X=x_array, Subplot1_Y=Spectrum, xlabel1="Frequency(Hz)", ylabel1="Spectrum(dBm)",title1=None)

except ImportError:
    print("matplotlib.pyplot not available. Plotting disabled.")
    update_plot = None
    start_plot = None

try:
    while True:
        Status = dll.RTA_BusTriggerStart(pointer(Device))
        for i in range(0,FrameInfo.PacketCount):
            Status = dll.RTA_GetRealTimeSpectrum(Device,SpectrumTrace,SpectrumBitmap,pointer(RTA_PlotInfo),pointer(TriggerInfo),pointer(MeasAuxInfo)) #Get RTA data and trigger information.
            for j in range(0,FrameInfo.FrameWidth):#Conversion.
                Spectrum[j] = SpectrumTrace[j] * RTA_PlotInfo.ScaleTodBm + RTA_PlotInfo.OffsetTodBm

        if update_plot and not update_plot(): 
            break

except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    dll.Device_Close(pointer(Device))
    print("Device closed.")