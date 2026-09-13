from htra_api import *
from ctypes import pointer
import numpy as np
import sys

###Open Device###
Status = 0          #Function return value
Device = c_void_p() #Memory address of the current device
DevNum = c_int(0)   #Specifies device number

BootProfile = BootProfile_TypeDef() #Boot configuration structure, including physical interface, power supply, etc.
BootInfo = BootInfo_TypeDef()       #Boot information structure, including device info, USB speed, etc.

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort #Use both USB data port and independent power port
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 #Use USB interface for data transmission

Status = dll.Device_Open(pointer(Device),DevNum,pointer(BootProfile),pointer(BootInfo)) #Open device
if Status == 0:
    print("Device is opened successfully")
else:
    print("Return other errors Status = {:d}".format(Status))
    sys.exit(-1)

###Configure IQS###
IQS_ProfileIn = IQS_Profile_TypeDef()  #IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
IQS_ProfileOut = IQS_Profile_TypeDef() #IQS output configuration
StreamInfo = IQS_StreamInfo_TypeDef()  #Information on IQ data under current settings, including bandwidth, single-channel sampling rate, etc.
IQStream = IQStream_TypeDef()          #Stores IQ data packets, including IQ data and configuration information

dll.IQS_ProfileDeInit(pointer(Device),pointer(IQS_ProfileIn)) #Initialize parameters for IQS mode

IQS_ProfileIn.CenterFreq_Hz = 1e9                           #Set center frequency
IQS_ProfileIn.RefLevel_dBm = 0                              #Set reference level
IQS_ProfileIn.DecimateFactor = 16                            #Set decimation factor
IQS_ProfileIn.DataFormat = DataFormat_TypeDef.Complex16bit  #Set IQ data format
IQS_ProfileIn.TriggerSource = IQS_TriggerSource_TypeDef.Bus #Set trigger source to internal bus trigger
IQS_ProfileIn.BusTimeout_ms = 5000
IQS_ProfileIn.TriggerMode = TriggerMode_TypeDef.FixedPoints
IQS_ProfileIn.TriggerLength = 16384                         #Set the number of points collected per trigger event

Status = dll.IQS_Configuration(pointer(Device),pointer(IQS_ProfileIn),pointer(IQS_ProfileOut),pointer(StreamInfo)) #Apply IQS mode configuration
if(Status == 0):
    print("configuration delivery succeeded")
else:
    print("IQS_Configuration call returned incorrect Status = {:d}".format(Status))

###Retrieve Data###
AlternIQStream_data = (c_int16 * (StreamInfo.StreamSamples * 2))()  #Create array to store IQ data

#Enable DSP functionality
DSP = c_void_p()
dll.DSP_Open(pointer(DSP)) #Open DSP

#Open DSP
IQToSpectrumIn = DSP_FFT_TypeDef()  #Configure FFT mode parameters
IQToSpectrumOut = DSP_FFT_TypeDef() #Feedback of actual FFT mode parameters applied
TracePoints = c_uint32(0)           #Number of frequency spectrum points after FFT

dll.DSP_FFT_DeInit(pointer(IQToSpectrumIn)) #Initialize FFT mode parameters

IQToSpectrumIn.Calibration = 0                                             #Enable or disable calibration (0 = off, other values = on)
IQToSpectrumIn.DetectionRatio = 1                                          #Set detection ratio
IQToSpectrumIn.TraceDetector = TraceDetector_TypeDef.TraceDetector_PosPeak #Set detection method
IQToSpectrumIn.FFTSize = StreamInfo.StreamSamples                          #Set FFT size
IQToSpectrumIn.Intercept = 1                                               #Set interception ratio
IQToSpectrumIn.SamplePts = StreamInfo.StreamSamples                        #Set number of sampling points
IQToSpectrumIn.WindowType = Window_TypeDef.FlatTop                         #Set window type

RBWRatio = c_double(0) #This parameter returns the RBW ratio,RBW = RBWRatio * StreamInfo.IQSampleRate.
dll.DSP_FFT_Configuration(pointer(DSP),pointer(IQToSpectrumIn),pointer(IQToSpectrumOut),pointer(TracePoints),pointer(RBWRatio))

Frequency_ct = (c_double * TracePoints.value)()    
PowerSpec_dBm_ct = (c_float * TracePoints.value)() 
I_data_ct = (c_float * (StreamInfo.StreamSamples))()    
Q_data_ct = (c_float * (StreamInfo.StreamSamples))()    


Frequency_np = np.ctypeslib.as_array(Frequency_ct)
PowerSpec_np = np.ctypeslib.as_array(PowerSpec_dBm_ct)
I_data_np = np.ctypeslib.as_array(I_data_ct)
Q_data_np = np.ctypeslib.as_array(Q_data_ct)
# Attempt to import the plotting module 'pyplot' to draw IQS mode spectrum and IQ data plots

try:
    from plot_module import start_plot

    center_freq = IQS_ProfileIn.CenterFreq_Hz
    sample_rate = StreamInfo.IQSampleRate
    real_freq_axis = np.linspace(center_freq - sample_rate/2, center_freq + sample_rate/2, TracePoints.value)
    
    x_array = np.arange(StreamInfo.StreamSamples) * (1.0 / StreamInfo.IQSampleRate)
    
    update_plot = start_plot(Sup_title="IQ Streaming", 
                             Subplot1_X=real_freq_axis, 
                             Subplot1_Y=PowerSpec_np, 
                             xlabel1="Frequency(Hz)", ylabel1="Spectrum(dBm)", title1="Spectrum Plot", 
                             Subplot2_X=x_array, I_Data=I_data_np, Q_Data=Q_data_np, 
                             xlabel2="Time(s)", ylabel2="IQvT(V)", title2="IQ Plot")
except ImportError:
    print("matplotlib.pyplot not available. Plotting disabled.")
    update_plot = None

try:
    while(True):

        Status = dll.IQS_BusTriggerStart(pointer(Device)) #Call IQS_BusTriggerStart to trigger the device. If the trigger source is external trigger, this function is not needed.

        for i in range(0,StreamInfo.PacketCount):
            dll.IQS_GetIQStream_PM1(pointer(Device),pointer(IQStream)) #Get IQ data packet, trigger info, I-channel max value, and its array index

            if i != StreamInfo.PacketCount - 1:  #Not the last packet
                samples_to_copy = StreamInfo.PacketSamples * 2
            else: #For the last packet, determine the number of samples to copy
                samples_to_copy = (StreamInfo.StreamSamples % StreamInfo.PacketSamples) * 2 if StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0 else StreamInfo.PacketSamples * 2

            AlternIQStream_type = c_int16 * (samples_to_copy)                             #Define array type to extract data from IQStream.AlternIQStream
            source_data_ptr = cast(IQStream.AlternIQStream, POINTER(AlternIQStream_type)) #Pointer type conversion
            source_data = source_data_ptr.contents                                        #Get data and store in source_data
            for j in range(samples_to_copy):                                              #Loop to concatenate data into AlternIQStream_data 
                AlternIQStream_data[i * (StreamInfo.PacketSamples * 2) + j] = source_data[j]

        # Convert data to proper units using ScaleToV
        for i in range(0, StreamInfo.StreamSamples):
            I_data_ct[i] = AlternIQStream_data[i * 2] * IQStream.IQS_ScaleToV   # Multiply by ScaleToV and store in I_data
            Q_data_ct[i] = AlternIQStream_data[i * 2 + 1] * IQStream.IQS_ScaleToV  # Multiply by ScaleToV and store in Q_data
       
        raw_data_ptr = pointer(AlternIQStream_data)  # Create a pointer to the concatenated data
        IQStream.AlternIQStream = cast(raw_data_ptr, POINTER(c_void_p))  # Cast the original data pointer to a void* type

        dll.DSP_FFT_IQSToSpectrum(pointer(DSP), pointer(IQStream), Frequency_ct, PowerSpec_dBm_ct)  # Perform IQ to spectrum conversion

        if update_plot and not update_plot():
            break

except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    Status = dll.IQS_BusTriggerStop(pointer(Device))  # Call IQS_BusTriggerStop to stop triggering the device
    dll.Device_Close(pointer(Device))  # Close the device
    print("Device closed.")


