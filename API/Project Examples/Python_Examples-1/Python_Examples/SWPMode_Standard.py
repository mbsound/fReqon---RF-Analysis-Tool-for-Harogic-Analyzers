from htra_api import *
import numpy as np
from ctypes import pointer
###Open Device###
Status = 0          #Function return value.
Device = c_void_p() #Memory address of the current device.
DevNum = c_int(0)   #Specify device number.

BootProfile = BootProfile_TypeDef() #Boot configuration structure, including physical interface, power supply mode, etc.
BootInfo = BootInfo_TypeDef()       #Boot information structure, including device information, USB rate, etc.

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort #Use both USB data port and independent power port for power supply.
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 #Use USB interface for data transmission.

#Configure ETH interface for network port devices
#BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.ETH #Use network port for data transmission
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
SWP_ProfileIn = SWP_Profile_TypeDef()  #SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
SWP_ProfileOut = SWP_Profile_TypeDef() #SWP output configuration.
TraceInfo = SWP_TraceInfo_TypeDef()    #Trace information under the current configuration, including trace points, frequency hopping points, etc.

dll.SWP_ProfileDeInit(pointer(Device),pointer(SWP_ProfileIn)) #Initialize relevant parameters in SWP mode.

SWP_ProfileIn.StartFreq_Hz = 1e9                        #Configure start frequency.
SWP_ProfileIn.StopFreq_Hz = 2e9                         #Configure stop frequency.
SWP_ProfileIn.RBW_Hz=50e3                               #Configure RBW.
SWP_ProfileIn.RBWMode = RBWMode_TypeDef.RBW_Manual      #Configure RBW mode.
SWP_ProfileIn.VBWMode = VBWMode_TypeDef.VBW_TenTimesRBW #Configure VBW.
SWP_ProfileIn.FreqAssignment = SWP_FreqAssignment_TypeDef.StartStop

Status = dll.SWP_Configuration(pointer(Device),pointer(SWP_ProfileIn),pointer(SWP_ProfileOut),pointer(TraceInfo))   #Deliver SWP mode configuration.

if(Status == 0):
    print("configuration delievery succeeded")
else:
    print("SWP_Configuration call is incorrect Status = {:d}".format(Status))

### Data Acquisition###

FullsweepPoints = TraceInfo.FullsweepTracePoints
PartialsweepPoints = TraceInfo.PartialsweepTracePoints

PartialFreq_ctypes = (c_double * PartialsweepPoints)()
PartialSpec_ctypes = (c_float * PartialsweepPoints)()

Frequency_np = np.zeros(FullsweepPoints)
PowerSpec_np = np.zeros(FullsweepPoints)

HopIndex = c_int(0)                                            #Current frequency hopping point index.
FrameIndex = c_int(0)                                          #Current frame index.
MeasAuxInfo = MeasAuxInfo_TypeDef()                            #This structure stores auxiliary information of measurement data.

# Try to import the plotting module pyplot to plot the SWP mode spectrum
try:
    from plot_module import start_plot
    update_plot = start_plot(Sup_title="Standard Spectrum", 
                             Subplot1_X=np.linspace(SWP_ProfileIn.StartFreq_Hz, SWP_ProfileIn.StopFreq_Hz, FullsweepPoints), # 频率通常是线性的，可以直接生成，无需每次从设备读
                             Subplot1_Y=PowerSpec_np, 
                             xlabel1="Frequency(Hz)", 
                             ylabel1="Spectrum(dBm)", 
                             title1=None)
except ImportError:
    print("matplotlib.pyplot not available. Plotting disabled.")
    update_plot = None


try:
    while(True):
        for i in range(0,TraceInfo.TotalHops):
            Status = dll.SWP_GetPartialSweep(pointer(Device), PartialFreq_ctypes, PartialSpec_ctypes, pointer(HopIndex), pointer(FrameIndex), pointer(MeasAuxInfo))
            start_idx = i * PartialsweepPoints
            end_idx = (i + 1) * PartialsweepPoints

            temp_spec = np.frombuffer(PartialSpec_ctypes, dtype=np.float32)
            PowerSpec_np[start_idx:end_idx] = temp_spec

        if update_plot and not update_plot():  # Plot the spectrum
            break

except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    dll.Device_Close(pointer(Device))
    print("Device closed.")


