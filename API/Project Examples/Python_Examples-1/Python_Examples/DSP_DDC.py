from htra_api import *
import matplotlib.pyplot as plt

###Open Device###
Status = 0          #Function return value
Device = c_void_p() #Memory address of the current device
DevNum = c_int(0)   #Specified device number

BootProfile = BootProfile_TypeDef() #Boot configuration struct, includes physical interface, power supply method, etc.
BootInfo = BootInfo_TypeDef()       #Boot info struct, includes device info, USB speed, etc.

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort #Use dual power supply: USB data port + independent power port
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 #Use USB interface for data transmission

#Use an Ethernet device to set up the ETH interface
#BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.ETH #Use Ethernet for data transmission
#BootProfile.ETH_IPVersion = IPVersion_TypeDef.IPv4
#BootProfile.ETH_RemotePort = 5000
#BootProfile.ETH_ReadTimeOut = 10000
#BootProfile.ETH_IPAddress[0] = 192
#BootProfile.ETH_IPAddress[1] = 168
#BootProfile.ETH_IPAddress[2] = 1
#BootProfile.ETH_IPAddress[3] = 100

Status = dll.Device_Open(pointer(Device),DevNum,pointer(BootProfile),pointer(BootInfo)) #Open the device
if(Status == 0):
    print("Device is opened successfully")
else:
    print("Return other errors Status = {:d}".format(Status))

###Configuration Delivery###
IQS_ProfileIn = IQS_Profile_TypeDef()  #IQS input config, including start freq, stop freq, RBW, reference level, etc.
IQS_ProfileOut = IQS_Profile_TypeDef() #IQS output config
StreamInfo = IQS_StreamInfo_TypeDef()  #IQ data stream info including bandwidth, sample rate, etc.
IQStream = IQStream_TypeDef()          #IQ data packets, includes IQ data and config info

dll.IQS_ProfileDeInit(pointer(Device),pointer(IQS_ProfileIn)) #Initialize parameters related to IQS mode

IQS_ProfileIn.CenterFreq_Hz = 400e6                           #Set center frequency
IQS_ProfileIn.RefLevel_dBm = 0                              #Set reference level
IQS_ProfileIn.DecimateFactor = 4                            #Set decimation factor
IQS_ProfileIn.DataFormat = DataFormat_TypeDef.Complex16bit  #Set IQ data format
IQS_ProfileIn.TriggerSource = IQS_TriggerSource_TypeDef.Bus #Set trigger source to internal bus
IQS_ProfileIn.BusTimeout_ms = 5000
IQS_ProfileIn.TriggerMode = TriggerMode_TypeDef.FixedPoints
IQS_ProfileIn.TriggerLength = 600000                         #Set number of points per trigger; only valid when TriggerMode is FixedPoints

Status = dll.IQS_Configuration(pointer(Device),pointer(IQS_ProfileIn),pointer(IQS_ProfileOut),pointer(StreamInfo)) #Deliver IQS mode config
if(Status == 0):
    print("configuration delievery succeeded")
else:
    print("IQS_Configuration call is incorrect Status = {:d}".format(Status))

###Data Acquisition###
AlternIQStream_data = (c_int16 * (StreamInfo.StreamSamples * 2))()  #Create array to store IQ data

#Open DSP function
DSP = c_void_p()
dll.DSP_Open(pointer(DSP)) #Open DSP function

#Configure DDC
DDC_ProfileIn = DSP_DDC_TypeDef()
DDC_ProfileOut = DSP_DDC_TypeDef()
IQStreamOut = IQStream_TypeDef()

dll.DSP_DDC_DeInit(pointer(DDC_ProfileIn)) 

DDC_ProfileIn.DDCOffsetFrequency = 0                    #Set DDC frequency offset
DDC_ProfileIn.DecimateFactor = 2000                     #Set DDC decimation factor
DDC_ProfileIn.SamplePoints = StreamInfo.StreamSamples   #Set number of sample points
DDC_ProfileIn.SampleRate = StreamInfo.IQSampleRate      #Set sampling rate
dll.DSP_DDC_Configuration(pointer(DSP), pointer(DDC_ProfileIn),pointer(DDC_ProfileOut))#Deliver DDC config

IQToSpectrumIn = DSP_FFT_TypeDef()  #FFT mode input config
IQToSpectrumOut = DSP_FFT_TypeDef() #FFT mode output feedback
TracePoints = c_uint32(0)           #Number of spectrum points after FFT

dll.DSP_FFT_DeInit(pointer(IQToSpectrumIn)) #Initialize FFT mode parameters

IQToSpectrumIn.Calibration = 0                                             #Whether to enable calibration; 0 means no calibration
IQToSpectrumIn.DetectionRatio = 2                                          #Set detection ratio
IQToSpectrumIn.TraceDetector = TraceDetector_TypeDef.TraceDetector_PosPeak #Set detector mode
IQToSpectrumIn.FFTSize = DDC_ProfileOut.SamplePoints                       #Set FFT size
IQToSpectrumIn.Intercept = 1                                               #Set FFT size
IQToSpectrumIn.SamplePts = DDC_ProfileOut.SamplePoints                     #Set number of sampling points
IQToSpectrumIn.WindowType = Window_TypeDef.FlatTop                         #Set window type

RBWRatio = c_double(0) #RBW ratio,RBW = RBWRatio * StreamInfo.IQSampleRate
dll.DSP_FFT_Configuration(pointer(DSP),pointer(IQToSpectrumIn),pointer(IQToSpectrumOut),pointer(TracePoints),pointer(RBWRatio))
Frequency = (c_double * TracePoints.value)()    #Create array to store frequency data
PowerSpec_dBm = (c_float * TracePoints.value)() #Create array to store amplitude data

#Use matplotlib for plotting
fig, ax = plt.subplots()
line, = ax.plot([], [], label='Spectrum') #Initialize an empty line
ax.set_title('IQSToSpectrum')
ax.set_xlabel('Frequency')
ax.set_ylabel('PowerSpec_dBm')

ax.set_xlim(IQS_ProfileIn.CenterFreq_Hz-StreamInfo.IQSampleRate/DDC_ProfileIn.DecimateFactor/2, IQS_ProfileIn.CenterFreq_Hz+StreamInfo.IQSampleRate/DDC_ProfileIn.DecimateFactor/2)
ax.set_ylim(-160, 25)
ax.legend()
# Display the plot without closing it after the loop ends (interactive mode)
plt.ion()
plt.show()

try:
    while(True):

        Status = dll.IQS_BusTriggerStart(pointer(Device)) #Start device trigger. If external trigger is used, this call is not needed

        for i in range(0,StreamInfo.PacketCount):
            dll.IQS_GetIQStream_PM1(pointer(Device),pointer(IQStream)) #Get IQ packets, trigger information, I-channel data maxima and maxima array subscripts

            if i != StreamInfo.PacketCount - 1:  # Not the spliced points at the last packet
                samples_to_copy = StreamInfo.PacketSamples * 2
            else: #Confirmation of splice points when it is the last packet
                samples_to_copy = (StreamInfo.StreamSamples % StreamInfo.PacketSamples) * 2 if StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0 else StreamInfo.PacketSamples * 2

            AlternIQStream_type = c_int16 * (samples_to_copy)                             #Define array type to extract data from IQStream
            source_data_ptr = cast(IQStream.AlternIQStream, POINTER(AlternIQStream_type)) #Pointer type conversion
            source_data = source_data_ptr.contents                                        #Get data into source_data
            for j in range(samples_to_copy):                                              #Loop to splice data into AlternIQStream_data
                AlternIQStream_data[i * (StreamInfo.PacketSamples * 2) + j] = source_data[j]

        raw_data_ptr = pointer(AlternIQStream_data)                     #Create pointer to the combined data
        IQStream.AlternIQStream = cast(raw_data_ptr, POINTER(c_void_p)) #Cast raw data pointer to void* type
        IQStream.IQS_StreamInfo.PacketSamples = IQS_ProfileIn.TriggerLength

        dll.DSP_DDC_Execute(pointer(DSP), pointer(IQStream), pointer(IQStreamOut))
        dll.DSP_FFT_IQSToSpectrum(pointer(DSP), pointer(IQStreamOut), Frequency, PowerSpec_dBm) #Execute IQ to Spectrum FFT
        dll.DSP_DDC_Reset(pointer(DSP))                                                            #Reset DDC cache to avoid jitter

        line.set_xdata(Frequency)                                                            #Plot spectrum
        line.set_ydata(PowerSpec_dBm)

        ax.relim()
        ax.autoscale_view()
        plt.draw()
        plt.pause(0.01)

except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    dll.Device_Close(pointer(Device))
    print("Device closed.")