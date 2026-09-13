from htra_api import *
import matplotlib.pyplot as plt

###Turn on the device###
Status = 0          #The return value of the function
Device = c_void_p() #The memory address of the current device
DevNum = c_int(0)   #Specifies the device number

BootProfile = BootProfile_TypeDef() #Boot configuration structure,including physical interface,power supply method,etc.
BootInfo = BootInfo_TypeDef()       #Boot information structure,including device info,USB speed,etc

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort #Dual power supply using USB data port and independent power port.
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 #Data transfer using the USB interface.

#Use Ethernet interface(ETH) configuration for network device
#BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.ETH # Use Ethernet interface for data transmission.
#BootProfile.ETH_IPVersion = IPVersion_TypeDef.IPv4
#BootProfile.ETH_RemotePort = 5000
#BootProfile.ETH_ReadTimeOut = 10000
#BootProfile.ETH_IPAddress[0] = 192
#BootProfile.ETH_IPAddress[1] = 168
#BootProfile.ETH_IPAddress[2] = 1
#BootProfile.ETH_IPAddress[3] = 100

Status = dll.Device_Open(pointer(Device),DevNum,pointer(BootProfile),pointer(BootInfo)) #open device

if(Status == 0):
    print("Device is opened successfully")
else:
    print("Return other errors Status = {:d}".format(Status))

### Configuration setup ###
SWP_ProfileIn = SWP_Profile_TypeDef()  # SWP input configuration,including start frequency,stop frequency,RBW,reference level,etc.
SWP_ProfileOut = SWP_Profile_TypeDef() # SWP output configuration.
TraceInfo = SWP_TraceInfo_TypeDef()    # Trace information under current configuration,including number of trace points, number of hopping points, etc.

dll.SWP_ProfileDeInit(pointer(Device),pointer(SWP_ProfileIn))   # Initialize SWP mode related configuration.

SWP_ProfileIn.StartFreq_Hz = 1e9 # Set start frequency.
SWP_ProfileIn.StopFreq_Hz = 2e9  # Set stop frequency.

Status = dll.SWP_Configuration(pointer(Device),pointer(SWP_ProfileIn),pointer(SWP_ProfileOut),pointer(TraceInfo)) # Apply SWP mode related configuration.

if(Status == 0):
    print("configuration delievery succeeded")
else:
    print("SWP_Configuration call is incorrect Status = {:d}".format(Status))

ASG_ProfileIn = ASG_Profile_TypeDef()  #ASG input configuration,including signal source output mode,frequency,power,and other parameter settings for each mode.
ASG_ProfileOut = ASG_Profile_TypeDef() #ASG output configuration.
ASG_Info = ASG_Info_TypeDef()          #Information on the number of scan points under the current configuration.

dll.ASG_ProfileDeInit(pointer(Device),pointer(ASG_ProfileIn)) #Initialize ASG mode related parameters.

#Single-tone signal
ASG_ProfileIn.CenterFreq_Hz = 1.51e9
ASG_ProfileIn.Level_dBm = -20
ASG_ProfileIn.Mode = ASG_Mode_TypeDef.ASG_FixedPoint
ASG_ProfileIn.Port = ASG_Port_TypeDef.ASG_Port_Internal

#Frequency sweep signal
#ASG_ProfileIn.StartFreq_Hz = 1.2e9
#ASG_ProfileIn.StopFreq_Hz = 1.4e9
#ASG_ProfileIn.StepFreq_Hz = 1e6
#ASG_ProfileIn.Level_dBm = -20
#ASG_ProfileIn.Mode = ASG_Mode_TypeDef.ASG_FrequencySweep

#Power sweep signal
#ASG_ProfileIn.CenterFreq_Hz = 1.6e9
#ASG_ProfileIn.StartLevel_dBm = -30
#ASG_ProfileIn.StopLevel_dBm = -20
#ASG_ProfileIn.Mode = ASG_Mode_TypeDef.ASG_PowerSweep

dll.ASG_Configuration(pointer(Device),pointer(ASG_ProfileIn), pointer(ASG_ProfileOut), pointer(ASG_Info))

###Siganl output###
Frequency = (c_double * TraceInfo.FullsweepTracePoints)()    #Create frequency array.
PowerSpec_dBm = (c_float * TraceInfo.FullsweepTracePoints)() #Create power array.
MeasAuxInfo = MeasAuxInfo_TypeDef()                          #Auxiliary information for measument data,including:power maximum value index,power maximum value,device temperature,Latitude and longitude,absolute timestamp,etc.

try:
    while True:
        Status = dll.SWP_GetFullSweep(pointer(Device),Frequency,PowerSpec_dBm,pointer(MeasAuxInfo)) #Get the trace data.
        plt.plot(Frequency, PowerSpec_dBm)                                                    #Plot the data.
        plt.xlabel('Frequency')
        plt.ylabel('PowerSpec_dBm')

        #Display the plot
        plt.show()
except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    dll.Device_Close(pointer(Device))
    print("Device closed.")