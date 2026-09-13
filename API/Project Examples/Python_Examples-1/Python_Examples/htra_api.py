#Call the necessary Python libraries
import ctypes
from ctypes import *
import os
import sys


dll = ctypes.CDLL("./htraapi/libhtraapi.so")


#Type declaration
c_int16_p = POINTER(c_int16)

#Physical bus type BootProfile.PhysicalInterface
class PhysicalInterface_TypeDef(c_int):
    USB = 0x00                      #Using USB as a physical interface is suitable for USB interface products such as SAE, SAM, SAN, etc
    QSFP = 0x02                     #Using 40Gbps QSFP+ as a physical interface
    ETH = 0x03                      #Using 100M/1000M Ethernet as a physical interface is suitable for Ethernet interface products such as NXE, NXM, NXN, etc
    HLVDS = 0x04                    #Debugging only, do not use
    VIRTUAL = 0x07                  #Using a virtual bus, that is, no physical bus, for simulation and debugging

#Device power supply method BootProfile.DevicePowerSupply
class DevicePowerSupply_TypeDef(c_int):
    USBPortAndPowerPort = 0x00      #Powered by USB data and power ports
    USBPortOnly = 0x01              #Powered solely by the USB data port
    Others = 0x02                   #Other methods, use this option when using the ETH bus

#IP address version BootProfile.IPVersion
class IPVersion_TypeDef(c_int):
    IPv4 = 0x00                     #Using IPv4 address
    IPv6 = 0x01                     #Using IPv6 address

#Frequency allocation method(SWP)
class SWP_FreqAssignment_TypeDef(c_int):
    StartStop = 0x00                #Set the frequency range with the starting frequency and the ending frequency
    CenterSpan = 0x01               #Set the frequency range with the center frequency and the frequency sweep width

#Window type(SWP\RTA\DSP)
class Window_TypeDef(c_int):
    FlatTop = 0x00                  #Flat-top window
    Blackman_Nuttall = 0x01         #Nuttall window
    Blackman = 0x02                 #Blackman window
    Hamming = 0x03                  #Hamming window
    Hanning = 0x04                  #Hanning window

#RBW Update method(SWP)
class RBWMode_TypeDef(c_int):
    RBW_Manual = 0x00               #Manual entry RBW
    RBW_Auto = 0x01                 #Automatic update with SPAN RBW,RBW = SPAN / 2000
    RBW_OneThousandthSpan = 0x02    #Force RBW = 0.001 * SPAN
    RBW_OnePercentSpan = 0x03       #Force RBW = 0.01 * SPAN

#VBW Update method(SWP)
class VBWMode_TypeDef(c_int):
    VBW_Manual = 0x00               #Manual input VBW
    VBW_EqualToRBW = 0x01           #Force VBW = RBW
    VBW_TenPercentRBW = 0x02        #Force VBW = 0.1 * RBW
    VBW_OnePercentRBW = 0x03        #Force VBW = 0.01 * RBW
    VBW_TenTimesRBW = 0x04          #Force VBW = 10 * RBW,Bypass VBW filter completely

#Scan time configuration mode(SWP)
class SweepTimeMode_TypeDef(c_int):
    SWTMode_minSWT = 0x00           #Scan with the shortest possible scan time
    SWTMode_minSWTx2 = 0x01         #Scan with a time approximately twice the shortest possible scan time
    SWTMode_minSWTx4 = 0x02         #Scan with a time approximately four times the shortest possible scan time
    SWTMode_minSWTx10 = 0x03        #Scan with a time approximately ten times the shortest possible scan time
    SWTMode_minSWTx20 = 0x04        #Scan with a time approximately twenty times the shortest possible scan time
    SWTMode_minSWTx50 = 0x05        #Scan with a time approximately fifty times the shortest possible scan time
    SWTMode_minSWTxN = 0x06         #Scan with a time approximately N times the shortest possible scan time, where N equals SweepTimeMultiple
    SWTMode_Manual = 0x07           #Scan with a time approximately specified, with the scan time equal to SweepTime
    SWTMode_minSMPxN = 0x08         #Sample individual frequency points approximately N times the shortest sampling time, where N equals SampleTimeMultiple

#Multiple frame detection method within a frequency point(SWP\RTA)
class Detector_TypeDef(c_int):
    Detector_Sample  = 0x00         #No frame detection between power spectra of each frequency point
    Detector_PosPeak = 0x01         #Frame detection is performed between the power spectra of each frequency point, with the final output being a single frame; frames are held with a maximum hold (MaxHold)
    Detector_Average = 0x02         #Frame detection is performed between the power spectra of each frequency point, with the final output being a single frame; frames are averaged
    Detector_NegPeak = 0x03         #Frame detection is performed between the power spectra of each frequency point, with the final output being a single frame; frames are held with a minimum hold (MinHold)
    Detector_MaxPower = 0x04        #Before the FFT, each frequency point undergoes long-duration sampling, and the frame with the highest power is selected for FFT to capture transient signals such as pulses (only available in SWP mode)
    Detector_RawFrames = 0x05       #Each frequency point is sampled multiple times, with multiple FFT analyses performed, and the power spectrum is output frame by frame (only available in SWP mode)
    Detector_RMS = 0x06             #Frame detection is performed between the power spectra of each frequency point, with the final output being a single frame; frames are combined using Root Mean Square (RMS)
    Detector_AutoPeak = 0x07        #Frame detection is performed between the power spectra of each frequency point, with the final output being a single frame; frames are combined using the AutoPeak method

#Frequency detection method(DSP)
class TraceFormat_TypeDef(c_int):
    TraceFormat_Standard = 0x00     #Equal frequency spacing
    TraceFormat_PrecisFrq = 0x01    #Frequency accuracy

#Trace detection method(SWP\RTA\DSP)
class TraceDetectMode_TypeDef(c_int):   
    TraceDetectMode_Auto = 0x00     #Automatically select the trace detection mode
    TraceDetectMode_Manual = 0x01   #Specify the trace detection mode

#Trace detection method(SWP\RTA\DSP)
class TraceDetector_TypeDef(c_int):
    TraceDetector_AutoSample = 0x00 #Automatic sampling detection
    TraceDetector_Sample = 0x01     #Stochastic detection
    TraceDetector_PosPeak = 0x02    #Positive peak detection
    TraceDetector_NegPeak = 0x03    #Negative peak detection
    TraceDetector_RMS = 0x04        #Root Mean Square (RMS) detection
    TraceDetector_Bypass = 0x05     #No detection performed
    TraceDetector_AutoPeak = 0x06   #Automatic peak detection

#Trace point approximation method(SWP)
class TracePointsStrategy_TypeDef(c_int):
    SweepSpeedPreferred = 0x00      #Prioritize ensuring the fastest scan speed, and then try to get as close as possible to the set target number of trace points
    PointsAccuracyPreferred = 0x01  #Prioritize ensuring that the actual number of trace points is close to the set target number of trace points
    BinSizeAssined = 0x02           #Prioritize generating traces according to the set frequency intervals

#Trace alignment method(SWP)
class TraceAlign_TypeDef(c_int):
    NativeAlign = 0x00              #Natural alignment
    AlignToStart = 0x01             #Aligned to the starting frequency
    AlignToCenter = 0x02            #Aligned to the center frequency

#FFT Platform (SWP)
class FFTExecutionStrategy_TypeDef(c_int):
    Auto = 0x00                     #Automatically select the use of CPU or FPGA for FFT calculation based on settings
    Auto_CPUPreferred = 0x01        #Automatically select the use of CPU or FPGA for FFT calculation based on settings, with CPU priority
    Auto_FPGAPreferred = 0x02       #Automatically select the use of CPU or FPGA for FFT calculation based on settings, with FPGA priority
    CPUOnly_LowResOcc = 0x03        #Force the use of CPU for computation, with low resource consumption and a maximum FFT point count of 256K
    CPUOnly_MediumResOcc = 0x04     #Force the use of CPU for computation, with moderate resource consumption and a maximum FFT point count of 1M
    CPUOnly_HighResOcc = 0x05       #Forced use of CPU computing, high resource usage, maximum FFT points 4M
    FPGAOnly = 0x06                 #Force the use of FPGA calculations                

#Transmit and receive mode port status: the former is transmit, the latter is receive (only applicable to TRx series)(VNA)
class RxPort_TypeDef(c_int):
    ExternalPort = 0x00             #External port
    InternalPort = 0x01             #Internal port
    ANT_Port = 0x02                 #only for TRx series
    TR_Port = 0x03                  #only for TRx series
    SWR_Port = 0x04                 #only for TRx series
    INT_Port = 0x05                 #only for TRx series

#Spurious suppression type(SWP)
class SpurRejection_TypeDef(c_int):
    Bypass = 0x00                   #No spurious suppression
    Standard = 0x01                 #Intermediate spurious inhibition
    Enhanced = 0x02                 #Advanced spurious suppression.


#System reference clock(all)
class ReferenceClockSource_TypeDef(c_int):
    ReferenceClockSource_Internal  = 0x00           #Internal clock source (default: 10MHz)
    ReferenceClockSource_External = 0x01            #External clock source (Default: 10MHz). When the system detects that the external clock source cannot be locked, the system automatically switches to the internal reference
    ReferenceClockSource_Internal_Premium = 0x02    #Internal clock Source - High quality, choose DOCXO or OCXO
    ReferenceClockSource_External_Forced = 0x03     #External clock source, and ignore the lock condition, even if the lock is lost will not switch to the internal reference

#System clock(all)
class SystemClockSource_TypeDef(c_int):
    SystemClockSource_Internal = 0x00   #Internal system clock source
    SystemClockSource_External = 0x01   #External system clock source

#Scan mode Trigger source and trigger mode(SWP)
class SWP_TriggerSource_TypeDef(c_int):
    InternalFreeRun = 0x00              #Internal trigger free running
    ExternalPerHop = 0x01               #External trigger, each trigger jumps a frequency point
    ExternalPerSweep = 0x02             #External trigger, refresh a trace with each trigger
    ExternalPerProfile = 0x03           #External triggers, with each trigger applying a new configuration

#Trigger input edge(all)
class TriggerEdge_TypeDef(c_int):
    RisingEdge = 0x00                   #Rising edge trigger
    FallingEdge = 0x01                  #Falling edge trigger
    DoubleEdge = 0x02                   #Double edge trigger

#Trigger output type(all)
class TriggerOutMode_TypeDef(c_int):
    NNone = 0x00                    #No-trigger output
    PerHop = 0x01                   #Output with each completion of frequency hopping
    PerSweep = 0x02                 #Output at the completion of each scan
    PerProfile = 0x03               #Switch output with each configuration

#Trigger output signal polarity(all)
class TriggerOutPulsePolarity_TypeDef(c_int):
    Positive = 0x00                 #Positive type pulse
    Negative = 0x01                 #Negative type pulse

#Gain mode(all)
class GainStrategy_TypeDef(c_int):
    LowNoisePreferred = 0x00        #Focus on low noise
    HighLinearityPreferred = 0x01   #Focus on high linearity

#Preselected amplifier(all)
class PreamplifierState_TypeDef(c_int):
    AutoOn = 0x00                   #The preamplifier is automatically enabled
    ForcedOff = 0x01                #Force to keep the preamplifier off

#Trace update mode(SWP)
class SWP_TraceType_TypeDef(c_int):
    ClearWrite = 0x00               #Output normal trace
    MaxHold = 0x01                  #Output the trace maintained by the maximum value
    MinHold = 0x02                  #Output the trace maintained by the minimum value
    ClearWriteWithIQ = 0x03         #At the same time, the time domain and frequency domain data of the current frequency point are output

#Local oscillator optimization(all)
class LOOptimization_TypeDef(c_int):
    LOOpt_Auto = 0x00               #Local oscillator optimization, automatic
    LOOpt_Speed = 0x01              #Local vibration optimization, high sweep speed
    LOOpt_Spur = 0x02               #Local oscillator optimization, low spurious
    LOOpt_PhaseNoise = 0x03         #Local vibration optimization, low phase noise

#Stream mode Data Format Type (IQS/DSP)
class DataFormat_TypeDef(c_int):
    Complex16bit = 0x00             #IQ,Single data 16 bits
    Complex32bit = 0x01             #IQ, single channel data 32 bits.
    Complex8bit = 0x02              #IQ, single channel data 8 bits.
    Complexfloat = 0x06             #IQ, single channel data 32-bit float format tpye (IQS mode is not available, only by DDC function output data to write back the enumeration variable).

#DSP calculating platform(SWP)
class DSPPlatform_Typedef(c_int):
    CPU_DSP  = 0x00                 #CPU
    FPGA_DSP = 0x01                 #FPGA

#Fixed frequency point mode (IQS\RTA\DET) trigger source
class IQS_TriggerSource_TypeDef(c_int):
    FreeRun = 0x00                  #Free running
    External = 0x01                 #External trigger. Triggered by a physical signal connected to a trigger input port outside the device.
    Bus = 0x02                      #The bus is triggered. Triggered by a function (instruction).
    Level = 0x03                    #Level trigger. The device detects the input signal according to the set level threshold, and triggers automatically when the input exceeds the threshold.
    Timer = 0x04                    #The timer is triggered. Use the device internal timer to automatically trigger the set time period.
    TxSweep = 0x05                  #Output trigger of signal generator scan; When this trigger source is selected, the acquisition process will be triggered by the output trigger signal scanned by the signal source.
    MultiDevSyncByExt = 0x06        #When the external trigger signal arrives, multiple machines perform synchronous trigger behavior.
    MultiDevSyncByGNSS1PPS = 0x07   #When GNSS-1PPS arrives, multiple machines trigger synchronously.
    SpectrumMask = 0x08             #Spectrum template trigger, available only in RTA mode. Not available in this stage.
    GNSS1PPS = 0x09                 #Use 1PPS provided by GNSS in the system to trigger.

#Trigger mode(IQS\RTA\DET)
class TriggerMode_TypeDef(c_int):
    FixedPoints = 0x00              #Get the fixed point length data.
    Adaptive = 0x01                 #Data is continuously obtained after triggering

#The timer trigger is synchronized with the outer trigger edge
class TriggerTimerSync_TypeDef(c_int):
    NoneSync = 0x00                         #Timer trigger is not synchronized with the external trigger.
    SyncToExt_RisingEdge = 0x01             #Timer trigger is synchronized with the external trigger rising edge. 
    SyncToExt_FallingEdge = 0x02            #Timer trigger is synchronized with the external trigger falling edge.
    SyncToExt_SingleRisingEdge = 0x03       #Timer trigger and external trigger rise edge single synchronization (need to call instruction function, single synchronization).
    SyncToExt_SingleFallingEdge = 0x04      #Timer trigger and external trigger fall edge single synchronization (need to call instruction function, single synchronization).
    SyncToGNSS1PPS_RisingEdge = 0x05        #Timer trigger synchronizes with the rising edge of GNSS-1PPS. 
    SyncToGNSS1PPS_FallingEdge = 0x06       #Timer trigger synchronizes with the falling edge of GNSS-1PPS.
    SyncToGNSS1PPS_SingleRisingEdge	= 0x07  #Timer triggers single synchronization with GNSS-1PPS rising edge (need to call instruction function, perform single synchronization).
    SyncToGNSS1PPS_SingleFallingEdge = 0x08 #Timer triggers single synchronization with GNSS-1PPS falling edge (need to call instruction function, perform single synchronization).

#DC suppression(IQS\DET\RTA)
class DCCancelerMode_TypeDef(c_int):
    DCCOff = 0x00                           #Disable the DC suppression function.
    DCCHighPassFilterMode = 0x01            #Open, high-pass filter mode. This mode has a good DC suppression effect, but will damage the signal component from DC to low frequency (about 100kHz).
    DCCManualOffsetMode = 0x02              #Open, manual bias mode. In this mode, the bias value needs to be specified manually, and the suppression effect is weaker than that of the high-pass filter mode, but the signal component on the DC will not be damaged.
    DCCAutoOffsetMode = 0x03                #Open, automatic bias mode.

#Quadrature demodulation correction(IQS\DET\RTA)
class QDCMode_TypeDef(c_int):
    QDCOff = 0x00                           #Close the QDC.
    QDCManualMode = 0x01                    #Manually perform QDC based on the given parameters.
    QDCAutoMode = 0x02                      #Automatic QDC: The system automatically performs the calibration and uses the parameters obtained during each IQS_Configuration call.

class ASG_Port_TypeDef(c_int):
    ASG_Port_External = 0x00                #External port
    ASG_Port_Internal = 0x01                #Internal port
    ASG_Port_ANT = 0x02                     #ANT port (only applicable to TRx series)
    ASG_Port_TR = 0x03                      #TR port (only applicable to TRx series)
    ASG_Port_SWR = 0x04                     #SWR port (only applicable to TRx series)
    ASG_Port_INT = 0x05                     #INT port (only applicable to TRx series)

class ASG_Mode_TypeDef(c_int):
    ASG_Mute = 0x00                         #Mute
    ASG_FixedPoint = 0x01                   #Fixed frequency and power
    ASG_FrequencySweep = 0x02               #Frequency sweep
    ASG_PowerSweep = 0x03                   #Power sweep

class ASG_TriggerSource_TypeDef(c_int):
    ASG_TriggerIn_FreeRun = 0x00            #Free run
    ASG_TriggerIn_External = 0x01           #External trigger
    ASG_TriggerIn_Bus = 0x02                #Timer trigger

class ASG_TriggerInMode_TypeDef(c_int):
    ASG_TriggerInMode_Null = 0x00           #Free run
    ASG_TriggerInMode_SinglePoint = 0x01    #Single-point trigger (triggers once for a single frequency or power setting)
    ASG_TriggerInMode_SingleSweep = 0x02    #Single-sweep trigger (triggers once for a full sweep cycle)
    ASG_TriggerInMode_Continous = 0x03      #Continuous sweep trigger (triggers once to start continuous operation)


class ASG_TriggerOutMode_TypeDef(c_int):
    ASG_TriggerOutMode_Null = 0x00          #Free run
    ASG_TriggerOutMode_SinglePoint = 0x01   #Single-point trigger (outputs one pulse per frequency hop))
    ASG_TriggerOutMode_SingleSweep = 0x02   #Single-sweep trigger (outputs one pulse per sweep)

# GNSS antenna status
class GNSSAntennaState_TypeDef(c_int):
    GNSS_AntennaExternal = 0x00   # External antenna
    GNSS_AntennaInternal = 0x01   # Internal antenna

# DOCXO status
class DOCXOWorkMode_TypeDef(c_int):
    DOCXO_LockMode = 0x00         # Lock mode
    DOCXO_HoldMode = 0x01         # Tracking mode


RTA_TriggerSource_TypeDef = IQS_TriggerSource_TypeDef
DET_TriggerSource_TypeDef = IQS_TriggerSource_TypeDef

#Boot configuration (Configuration)
class BootProfile_TypeDef(Structure):
    _fields_ = [("PhysicalInterface",PhysicalInterface_TypeDef),    #Physical interface selection
                ("DevicePowerSupply", DevicePowerSupply_TypeDef),   #Power supply mode selection
                ("ETH_IPVersion", IPVersion_TypeDef),               #ETH Internet Protocol version
                ("ETH_IPAddress", c_uint8 * 16),                    #IP address of the ETH interface
                ("ETH_RemotePort", c_uint16),                       #Listening port of an ETH interface
                ("ETH_ErrorCode", c_int32),                         #Return code of the ETH interface
                ("ETH_ReadTimeOut", c_int32)]                       #Read timeout of the ETH interface (ms)

#Device information (Return)
class DeviceInfo_TypeDef(Structure):
    _fields_ = [("DeviceUID",c_uint64),         #Equipment serial number
                ("Model",c_uint16),             #Device type
                ("HardwareVersion",c_uint16),   #Hardware version
                ("MFWVersion",c_uint32),        #MCU Firmware version
                ("FFWVersion",c_uint32),]       #FPGA Firmware version

#Startup information (Return)
class BootInfo_TypeDef(Structure):
    _fields_ = [("DeviceInfo",DeviceInfo_TypeDef),  #Device information
                ("BusSpeed",c_uint32),              #Bus speed information.
                ("BusVersion",c_uint32),            #Bus firmware version.
                ("APIVersion",c_uint32),            #API version
                ("ErrorCodes",c_int * 7),           #List of error codes during startup.
                ("Errors",c_int),                   #Total number of errors during startup.
                ("WarningCodes",c_int * 7),         #List of warning codes during startup.
                ("Warnings",c_int)]                 #Total number of warnings during startup.

#Device status (advanced variable, not recommended)(Return)
class DeviceState_TypeDef(Structure):
    _fields_ = [("Temperature",c_int16),            #Equipment Temperature, Celsius = 0.01 * Temperature.
                ("RFState",c_uint16),               #Radio status.
                ("BBState",c_uint16),               #Baseband status.
                ("AbsoluteTimeStamp",c_double),     #The absolute timestamp of the current packet.
                ("Latitude",c_float),               #Latitude coordinates corresponding to the current packet. North latitude is positive and south latitude is negative, so as to distinguish north and south latitudes.
                ("Longitude",c_float),              #The longitude coordinate corresponding to the current packet is positive in east longitude and negative in west longitude, so as to distinguish east longitude from west longitude.
                ("GainPattern",c_uint16),           #Gain control word used by the frequency point of the current packet.
                ("RFCFreq",c_int64),                #RF center frequency used by the frequency point of the current packet.
                ("ConvertPattern",c_uint32),        #Frequency conversion mode used by the frequency point of the current packet.
                ("NCOFTW",c_uint32),                #NCO frequency word used by the current packet frequency point.
                ("SampleRate",c_uint32),            #Equivalent sampling rate used by the current packet frequency point, equivalent sampling rate = ADC sampling rate/extraction multiple.
                ("CPU_BCFlag",c_uint16),            #CPU-FFT Specifies the BC flag bit required for the frame.
                ("IFOverflow",c_uint16),            #If the equipment is overloaded, consider and BBState or RFState.
                ("DecimateFactor",c_uint16),        #The extraction multiple used by the current packet frequency point.
                ("OptionState",c_uint16),           #Optional status.
                ("LicenseCode",c_int16)]            #License code

#SWP configuration structure (basic configuration)
class SWP_Profile_TypeDef(Structure):
    _fields_ = [("StartFreq_Hz",c_double),                                  #start frequency
                ("StopFreq_Hz",c_double),                                   #Stop frequency
                ("CenterFreq_Hz",c_double),                                 #center frequency
                ("Span_Hz",c_double),                                       #span
                ("RefLevel_dBm",c_double),                                  #R.L.
                ("RBW_Hz",c_double),                                        #RBW
                ("VBW_Hz",c_double),                                        #VBW
                ("SweepTime",c_double),                                     #When the sweep time mode is Manual, the parameter is absolute time. When specified as *N, this parameter is the scan time multiplier
                ("TraceBinSize_Hz",c_double),                               #The frequency interval between adjacent frequency points of the trace
                ("FreqAssignment",SWP_FreqAssignment_TypeDef),              #Select StartStop or CenterSpan to set the frequency
                ("Window",Window_TypeDef),                                  #Window type used for FFT analysis
                ("RBWMode",RBWMode_TypeDef),                                #RBW update mode. Manual input, automatically set according to Span
                ("VBWMode",VBWMode_TypeDef),                                #VBW update mode. Manual input, VBW = RBW, VBW = 0.1*RBW,  VBW = 0.01*RBW
                ("SweepTimeMode",SweepTimeMode_TypeDef),                    #Scan time mode
                ("Detector",Detector_TypeDef),                              #detector
                ("TraceFormat",TraceFormat_TypeDef),                        #Trace format
                ("TraceDetectMode",TraceDetectMode_TypeDef),                #Trace detection mode
                ("TraceDetector",TraceDetector_TypeDef),                    #Trace detector
                ("TracePoints",c_uint32),                                   #Trace count
                ("TracePointsStrategy",TracePointsStrategy_TypeDef),        #Trace point mapping strategy
                ("TraceAlign",TraceAlign_TypeDef),                          #Trace alignment is specified
                ("FFTExecutionStrategy",FFTExecutionStrategy_TypeDef),      #FFT implements the policy
                ("RxPort",RxPort_TypeDef),                                  #Rf input port
                ("SpurRejection",SpurRejection_TypeDef),                    #Spurious Rejection
                ("ReferenceClockSource",ReferenceClockSource_TypeDef),      #Reference clock source.
                ("ReferenceClockFrequency",c_double),                       #Reference clock frequency, Hz.
                ("EnableReferenceClockOut",c_uint8),                        #enable reference clock output.
                ("SystemClockSource",SystemClockSource_TypeDef),            #The default system clock source is the internal system clock.Use it under the guidance of the vendor.
                ("ExternalSystemClockFrequency",c_double),                  #External system clock frequency (Hz).
                ("TriggerSource",SWP_TriggerSource_TypeDef),                # Input trigger source.
                ("TriggerEdge",TriggerEdge_TypeDef),                        #Input trigger edge.
                ("TriggerOutMode",TriggerOutMode_TypeDef),                  #Trigger output mode.
                ("TriggerOutPulsePolarity",TriggerOutPulsePolarity_TypeDef),#Trigger output pulse polarity.
                ("PowerBalance",c_uint32),                                  #Balance between power consumption and scanning speed.
                ("GainStrategy",GainStrategy_TypeDef),                      #Gain strategy.
                ("Preamplifier",PreamplifierState_TypeDef),                 #Preamplifier action set.
                ("AnalogIFBWGrade",c_uint8),                                #Intermediate frequency bandwidth range
                ("IFGainGrade",c_uint8),                                    #Intermediate frequency gain gear
                ("EnableDebugMode",c_uint8),                                #Debug mode. Advanced applications are not recommended. The default value is 0.
                ("CalibrationSettings",c_uint8),                            #Calibration selection. Advanced applications are not recommended. The default value is 0.
                ("Atten",c_int8),                                           #Calibration selection. Advanced applications are not recommended. The default value is 0.
                ("TraceType",SWP_TraceType_TypeDef),                        # Output trace type.
                ("LOOptimization",LOOptimization_TypeDef)]                  #LO optimization
    
#Trace information structure of SWP mode (return)
class SWP_TraceInfo_TypeDef(Structure):
    _fields_ = [("FullsweepTracePoints",c_int),         #The points of the complete trace.
                ("PartialsweepTracePoints",c_int),      #Trace points of each frequency point, that is, the points of GetPart each time.
                ("TotalHops",c_int),                    #The number of frequency points of complete traces, that is, the number of times a complete trace needs GetPart
                ("UserStartIndex",c_uint32),            #Array index corresponding to the user-specified StartFreq_Hz in the trace array, that is, when HopIndex = 0, Freq[UserStartIndex] is the closest frequency point to SWPProfile.StartFreq_Hz.
                ("UserStopIndex",c_uint32),             #Array index corresponding to the user-specified StopFreq_Hz in the trace array, that is, when HopIndex = TotalHops-1, Freq[UserStopIndex] is the frequency point closest to SWPProfile.StopFreq_Hz.
                ("TraceBinBW_Hz",c_double),             #The frequency interval between two points of the trace.
                ("StartFreq_Hz",c_double),              #The frequency of the first frequency point of the trace.
                ("AnalysisBW_Hz",c_double),             #Analysis bandwidth corresponding to each frequency point.
                ("TraceDetectRatio",c_int),             #Detection ratio of video detection.
                ("DecimateFactor",c_int),               #Multiple of time domain data extraction.
                ("FrameTimeMultiple",c_float),          #Frame analysis time multiple: The analysis time of the device at a single frequency = default analysis time (set by the system) * frame time multiple. Increasing the frame time multiple will increase the device's minimum scan time, but is not strictly linear.
                ("FrameTime",c_double),                 #Frame sweep time: duration (in seconds) of the signal used for single frame FFT analysis.
                ("EstimateMinSweepTime",c_double),      #The minimum scanning time that can be set under the current configuration (unit: second, the result is mainly affected by Span, RBW, VBW, frame scanning time and other factors). 
                ("DataFormat",DataFormat_TypeDef),      #Time domain data format.
                ("SamplePoints",c_uint64),              #Time domain data sampling length.
                ("GainParameter",c_uint32),             #Gain related parameters, including Space(31 to 24Bit), PreAmplifierState(23 to 16Bit), StartRFBand(15 to 8Bit), StopRFBand(7 to 0Bit).
                ("DSPPlatform",DSPPlatform_Typedef)]    #DSP calculating platform under current configuration

#Auxiliary information for measurement data (Return)
class MeasAuxInfo_TypeDef(Structure):
    _fields_ = [("MaxIndex",c_uint32),                  #Index of the maximum power value in the current packet
                ("MaxPower_dBm",c_float),               #The maximum power in the current packet
                ("Temperature",c_int16),                #Device Temperature, Celsius = 0.01 x temperature
                ("RFState",c_uint16),                   #Rf state
                ("BBState",c_uint16),                   #Baseband state
                ("GainPattern",c_uint16),               #The gain control word used by the frequency of the current packet
                ("ConvertPattern",c_uint32),            #Frequency conversion mode used by the current packet frequency point
                ("SysTimeStamp",c_double),              #System time stamp of the current packet, in seconds
                ("AbsoluteTimeStamp",c_double),         #Absolute timestamp of the current packet
                ("Latitude",c_float),                   #The latitude coordinates corresponding to the current packet are positive in north latitude and negative in south latitude to distinguish between north and south latitude
                ("Longitude",c_float)]                  #The longitude coordinates corresponding to the current data packet are positive in east longitude and negative in west longitude to distinguish between east and west longitude

#Configuration structure of IQS (Configuration)
class IQS_Profile_TypeDef(Structure):
    _fields_ = [("CenterFreq_Hz",c_double),                                 #Center frequency.
                ("RefLevel_dBm",c_double),                                  #Reference level.
                ("DecimateFactor",c_uint32),                                #Decimate Factor of time domain.
                ("RxPort",RxPort_TypeDef),                                  #RF input port.
                ("BusTimeout_ms",c_uint32),                                 #Transmission timeout
                ("TriggerSource",IQS_TriggerSource_TypeDef),                #Input trigger source.
                ("TriggerEdge",TriggerEdge_TypeDef),                        #Input trigger edge.
                ("TriggerMode",TriggerMode_TypeDef),                        #Input trigger mode.	
                ("TriggerLength",c_uint64),                                 #Enter the number of sampling points after triggering. This takes effect only in FixedPoints mode.
                ("TriggerOutMode",TriggerOutMode_TypeDef),                  #Trigger output mode.
                ("TriggerOutPulsePolarity",TriggerOutPulsePolarity_TypeDef),#Trigger output pulse polarity.
                ("TriggerLevel_dBm",c_double),                              #Level trigger threshold.
                ("TriggerLevel_SafeTime",c_double),                         #Level trigger anti-shaking safety time, in seconds.
                ("TriggerDelay",c_double),                                  #Trigger delay,in seconds
                ("PreTriggerTime",c_double),                                #Pre-trigger time,in seconds.
                ("TriggerTimerSync",TriggerTimerSync_TypeDef),              #Synchronization options for timed and out-triggered edges. The trigger mode is effective when the trigger is timed.
                ("TriggerTimer_Period",c_double),                           #The trigger period of the timed trigger, in s. The trigger mode is effective when the trigger is timed.		
                ("EnableReTrigger",c_uint8),                                #Enable the device to respond multiple times after capturing a trigger. This function is available only in FixedPoint mode.
                ("ReTrigger_Period",c_double),                              #Time interval for multiple responses of a trigger device. It is also used as the trigger period in the Timer trigger mode (unit: s).
                ("ReTrigger_Count",c_uint16),                               #After a trigger, several responses are required in addition to the triggered response.
                ("DataFormat",DataFormat_TypeDef),                          #Data format.
                ("GainStrategy",GainStrategy_TypeDef),                      #Gain strategy.
                ("Preamplifier",PreamplifierState_TypeDef),                 #Preamplifier action.
                ("AnalogIFBWGrade",c_uint8),                                #Intermediate frequency bandwidth grade.
                ("IFGainGrade",c_uint8),                                    #intermediate frequency gain grade.
                ("EnableDebugMode",c_uint8),                                #Debug mode. Advanced applications are not recommended. The default value is 0.
                ("ReferenceClockSource",ReferenceClockSource_TypeDef),      #Reference clock source.
                ("ReferenceClockFrequency",c_double),                       #Reference clock frequency.
                ("EnableReferenceClockOut",c_uint8),                        #enable reference clock output.
                ("SystemClockSource",SystemClockSource_TypeDef),            #System clock source.
                ("ExternalSystemClockFrequency",c_double),                  #External system clock frequency (Hz).
                ("NativeIQSampleRate_SPS",c_double),                        #Suitable for specific equipment. Native IQ sampling rate. For devices with variable sampling rate, the sampling rate can be adjusted by adjusting this parameter; Nonvariable sampling rate device configurations are always configured to the system default fixed value.
                ("EnableIFAGC",c_uint8),                                    #Suitable for specific equipment. Medium frequency AGC control, 0: AGC off, using MGC mode; 1: The AGC is enabled.
                ("Atten",c_int8),                                           #attenuation.
                ("DCCancelerMode",DCCancelerMode_TypeDef),                  #Suitable for specific equipment. Dc suppression. 0: disables the DCC. 1: Open, high-pass filter mode (better suppression effect, but will damage the signal in the range of DC to 100 KHZ); 2: Open, manual bias mode (need manual calibration, but not low frequency damage signal).
                ("QDCMode",QDCMode_TypeDef),                                #Suitable for specific equipment. IQ amplitude and phase corrector. QDCOff: disables the QDC function. QDCManualMode: Enable and use manual mode; QDCAutoMode: Enables and uses the automatic QDC mode.
                ("QDCIGain",c_float),                                       #Suitable for specific equipment. Normalized linear gain I, 1.0 indicates no gain, set range 0.8 to 1.2.
                ("QDCQGain",c_float),                                       #Suitable for specific equipment. Normalized linear gain Q, 1.0 indicates no gain, set range 0.8~1.2.
                ("QDCPhaseComp",c_float),                                   #Suitable for specific equipment. Normalized phase compensation coefficient, set range -0.2~+0.2.
                ("DCCIOffset",c_int8),                                      #Suitable for specific equipment. I channel DC offset, LSB.
                ("DCCQOffset",c_int8),                                      #Suitable for specific equipment. Q channel DC offset, LSB.
                ("LOOptimization",LOOptimization_TypeDef)]                  #LO optimization

#Flow information structure returned after IQS configuration (returned)
class IQS_StreamInfo_TypeDef(Structure):
    _fields_ = [("Bandwidth",c_double),         #The current configuration corresponds to the receiver's physical channel or digital signal processing bandwidth.
                ("IQSampleRate",c_double),      #Single-channel sampling rate of IQ corresponding to the current configuration (unit: Sample/second).
                ("PacketCount",c_uint64),       #The total number of data packets corresponding to the current configuration takes effect only in FixedPoints mode.
                ("StreamSamples",c_uint64),     #In Fixedpoints mode, it represents the total number of sampling points corresponding to the current configuration. In Adaptive mode, the value has no physical significance and is 0.
                ("StreamDataSize",c_uint64),    #In Fixedpoints mode, it indicates the total number of bytes of samples corresponding to the current configuration. In Adaptive mode, the value has no physical significance and is 0.
                ("PacketSamples",c_uint32),     #Sampling points in packets obtained by each IQS_GetIQStream invocation Sample points contained in each packet.
                ("PacketDataSize",c_uint32),    #The number of valid data bytes to be obtained per call to IQS_GetIQStream.
                ("GainParameter",c_uint32)]     #Gain dependent parameters, including Space(31~24Bit),PreAmplifierState(23~16Bit),StartRFBand(15~8Bit)??StopRFBand(7~0Bit).

#Trigger information structure contained in IQS packet, trigger information return structure of DET and RTA is the same (return)
class TriggerInfo_TypeDef(Structure):
    _fields_ = [("SysTimerCountOfFirstDataPoint",c_uint64),     #The system timestamp corresponding to the first data point of the current packet.
                ("InPacketTriggeredDataSize",c_uint16),         #The number of bytes of valid trigger data in the current packet.
                ("InPacketTriggerEdges",c_uint16),              #The number of trigger edges contained in the current package.
                ("StartDataIndexOfTriggerEdges",c_uint32 * 25), #The data location in the current package corresponding to the trigger edge.
                ("SysTimerCountOfEdges",c_uint64 * 25),         #The system timestamp of the trigger edge in the current package.
                ("EdgeType",c_int8 * 25)]                       #The polarity of each trigger edge in the current packet.

class IQStream_TypeDef(Structure):
    _fields_ = [("AlternIQStream",POINTER(c_void_p)),     #Interleaved IQ time-domain data; a single channel may be in i8, i16, or i32 format
                ("IQS_ScaleToV",c_float),         #Coefficient to convert int type to absolute voltage (V)
                ("MaxPower_dBm",c_float),              #Maximum power value (in dBm) in the current data packet
                ("MaxIndex",c_uint32), #Index of the maximum power value in the current data packet
                ("IQS_Profile",IQS_Profile_TypeDef),         #IQ stream profile info, typically updated via the IQS_Configuration function (IQS_ProfileOut)
                ("IQS_StreamInfo", IQS_StreamInfo_TypeDef), # IQ stream format info, typically updated via the IQS_Configuration function
                ("IQS_TriggerInfo", TriggerInfo_TypeDef),  # Trigger information associated with the IQ stream, usually updated via IQS_GetIQStream
                ("DeviceInfo", DeviceInfo_TypeDef),  # Device information related to the IQ stream, usually updated via IQS_GetIQStream
                ("DeviceState", DeviceState_TypeDef)]  # Device status related to the IQ stream, usually updated via IQS_GetIQStream


#Detector mode structure (Detector)
class DET_Profile_TypeDef(Structure):
    _fields_ = [("CenterFreq_Hz",c_double),                                 #Center frequency.
                ("RefLevel_dBm",c_double),                                  #R.L.
                ("DecimateFactor",c_uint32),                                #Decimate factor of time domain data.
                ("RxPort",RxPort_TypeDef),                                  #RF input port.
                ("BusTimeout_ms",c_uint32),                                 #Transmission timeout.
                ("TriggerSource",DET_TriggerSource_TypeDef),                #Input trigger source.
                ("TriggerEdge",TriggerEdge_TypeDef),                        #Input trigger edge.
                ("TriggerMode",TriggerMode_TypeDef),                        #Input trigger mode.	
                ("TriggerLength",c_uint64),                                 #number of sampling points after the input trigger, only available in FixedPoints mode.
                ("TriggerOutMode",TriggerOutMode_TypeDef),                  #Trigger output mode        
                ("TriggerOutPulsePolarity",TriggerOutPulsePolarity_TypeDef),#Trigger the output pulse polarity.
                ("TriggerLevel_dBm",c_double),                              #Level trigger threshold.
                ("TriggerLevel_SafeTime",c_double),                         #Safety time of level trigger anti-shaking, unit: s.
                ("TriggerDelay",c_double),                                  #Trigger delay, unit: s.
                ("PreTriggerTime",c_double),                                #Pre-trigger time, unit: s.
                ("TriggerTimerSync",TriggerTimerSync_TypeDef),              #Synchronization options of timer trigger and outer trigger edge.
                ("TriggerTimer_Period",c_double),                           #Period of timed trigger	
                ("EnableReTrigger",c_uint8),                                #Enable the device to respond multiple times after capturing a trigger. This function is available only in FixedPoint mode.
                ("ReTrigger_Period",c_double),                              #The interval between multiple responses of the device is also used as the trigger period in the Timer trigger mode (unit: s).
                ("ReTrigger_Count",c_uint16),                               #After a trigger, you need to make several responses in addition to the response brought by the trigger.
                ("Detector",Detector_TypeDef),                              #Detection.
                ("DetectRatio",c_uint16),                                   #Detection ratio, the detector detects the power trace, and each original data point is detected as 1 output trace point
                ("GainStrategy",GainStrategy_TypeDef),                      #Gain strategy.
                ("Preamplifier",PreamplifierState_TypeDef),                 #Preamplifier action.
                ("AnalogIFBWGrade",c_uint8),                                #Intermediate frequency bandwidth grade.
                ("IFGainGrade",c_uint8),                                    #Intermediate frequency gain grade.
                ("EnableDebugMode",c_uint8),                                #Debug mode. Advanced applications are not recommended. The default value is 0.
                ("ReferenceClockSource",ReferenceClockSource_TypeDef),      #Reference clock source.     
                ("ReferenceClockFrequency",c_double),                       #Reference clock frequency.
                ("EnableReferenceClockOut",c_uint8),                        #Enable reference clock output.
                ("SystemClockSource",SystemClockSource_TypeDef),            #System clock source.
                ("ExternalSystemClockFrequency",c_double),                  #External system clock frequency: Hz.
                ("Atten",c_int8),                                           #attenuation.
                ("DCCancelerMode",DCCancelerMode_TypeDef),                  #Suitable for specific equipment. Dc suppression. 0: disables the DCC. 1: Open, high-pass filter mode (better suppression effect, but will damage the signal in the range of DC to 100 KHZ); 2: Open, manual bias mode (need manual calibration, but not low frequency damage signal).
                ("QDCMode",QDCMode_TypeDef),                                #Suitable for specific equipment. IQ amplitude and phase corrector. QDCOff: disables the QDC function. QDCManualMode: Enable and use manual mode; QDCAutoMode: Enables and uses the automatic QDC mode.
                ("QDCIGain",c_float),                                       #Suitable for specific equipment. Normalized linear gain I, 1.0 indicates no gain, set range 0.8 to 1.2.
                ("QDCQGain",c_float),                                       #Suitable for specific equipment. Normalized linear gain Q, 1.0 indicates no gain, set range 0.8~1.2.
                ("QDCPhaseComp",c_float),                                   #Suitable for specific equipment. Normalized phase compensation coefficient, set range -0.2~+0.2.
                ("DCCIOffset",c_int8),                                      #Suitable for specific equipment. I channel DC offset, LSB.
                ("DCCQOffset",c_int8),                                      #Suitable for specific equipment. Q channel DC offset, LSB.
                ("LOOptimization",LOOptimization_TypeDef)]                  #LO optimization

#The stream information structure returned after the DET configuration (returned)
class DET_StreamInfo_TypeDef(Structure):
    _fields_ = [("PacketCount",c_uint64),       #The total number of data packets corresponding to the current configuration takes effect only in FixedPoints mode.
                ("StreamSamples",c_uint64),     #In Fixedpoints mode, it represents the total number of sampling points corresponding to the current configuration. In Adaptive mode, the value has no physical significance and is 0.
                ("StreamDataSize",c_uint64),    #In Fixedpoints mode, it indicates the total number of bytes of samples corresponding to the current configuration. In Adaptive mode, the value has no physical significance and is 0.
                ("PacketSamples",c_uint32),     #Sampling points in packets obtained by each call to DET_GetTrace Indicates the sample points contained in each packet.
                ("PacketDataSize",c_uint32),    #The number of bytes of valid data obtained from each call to DET_GetTrace.
                ("TimeResolution",c_double),    #Time-domain point resolution
                ("GainParameter",c_uint32)]     #Gain related parameters, including Space(31 to 24Bit), PreAmplifierState(23 to 16Bit), StartRFBand(15 to 8Bit), StopRFBand(7 to 0Bit).

#RTA configuration structure (configuration)
class RTA_Profile_TypeDef(Structure):
    _fields_ = [("CenterFreq_Hz",c_double),                                 #Center frequency.
                ("RefLevel_dBm",c_double),                                  #Reference level.
                ("RBW_Hz",c_double),                                        #RBW
                ("VBW_Hz",c_double),                                        #VBW
                ("RBWMode",RBWMode_TypeDef),                                #RBW update mode, mannually, according to the span.
                ("VBWMode",VBWMode_TypeDef),                                #VBW updated mode,mannually,VBW = RBW,VBW = 0.1*RBW, VBW = 0.01*RBW
                ("DecimateFactor",c_uint32),                                #Decimate factor of time domain data.
                ("Window",Window_TypeDef),                                  #Window type.
                ("SweepTimeMode",SweepTimeMode_TypeDef),                    #Sweep time mode.
                ("SweepTime",c_double),                                     #When the sweep time mode is Manual, the parameter is absolute time. When specified as *N, this parameter is the scan time multiplier
                ("Detector",Detector_TypeDef),                              #Detector
                ("TraceDetectMode",TraceDetectMode_TypeDef),                #Trace detection mode.
                ("TraceDetectRatio",c_uint32),                              #Trace detection ratio
                ("TraceDetector",TraceDetector_TypeDef),                    #Trace detector detector
                ("RxPort",RxPort_TypeDef),                                  #Receiving port setting.
                ("BusTimeout_ms",c_uint32),                                 #Transmission timeout.
                ("TriggerSource",RTA_TriggerSource_TypeDef),                #Input trigger source.
                ("TriggerEdge",TriggerEdge_TypeDef),                        #Input trigger edge.
                ("TriggerMode",TriggerMode_TypeDef),                        #Input trigger mode.
                ("TriggerAcqTime",c_double),                                #This parameter is valid only in FixedPoints mode (unit: s)
                ("TriggerOutMode",TriggerOutMode_TypeDef),                  #Trigger output mode
                ("TriggerOutPulsePolarity",TriggerOutPulsePolarity_TypeDef),#Trigger output pulse polarity
                ("TriggerLevel_dBm",c_double),                              #Level trigger threshold.
                ("TriggerLevel_SafeTime",c_double),                         #Level trigger: anti-shake safety time, unit is s
                ("TriggerDelay",c_double),                                  #Level trigger: Trigger delay, in s
                ("PreTriggerTime",c_double),                                #Level trigger: pre-trigger time, expressed in s
                ("TriggerTimerSync",TriggerTimerSync_TypeDef),              #Timed trigger: Sync option with external trigger edge
                ("TriggerTimer_Period",c_double),                           #Timing trigger period.	
                ("EnableReTrigger",c_uint8),                                #Enable the device to respond multiple times after capturing a trigger. This function is available only in FixedPoint mode.
                ("ReTrigger_Period",c_double),                              #The interval between multiple responses of the device is also used as the trigger period in the Timer trigger mode (unit: s).
                ("ReTrigger_Count",c_uint16),                               #After a trigger, you need to make several responses in addition to the response brought by the trigger.
                ("GainStrategy",GainStrategy_TypeDef),                      #Gain strategy.
                ("Preamplifier",PreamplifierState_TypeDef),                 #Preamplifier action.
                ("AnalogIFBWGrade",c_uint8),                                #Intermediate frequency bandwidth grade.
                ("IFGainGrade",c_uint8),                                    #Intermediate frequency gain grade.
                ("EnableDebugMode",c_uint8),                                #Debug mode. Advanced applications are not recommended. The default value is 0.
                ("ReferenceClockSource",ReferenceClockSource_TypeDef),      #Reference clock source.
                ("ReferenceClockFrequency",c_double),                       #Reference clock frequency.
                ("EnableReferenceClockOut",c_uint8),                        #Enable reference clock output.
                ("SystemClockSource",SystemClockSource_TypeDef),            #System clock source.
                ("ExternalSystemClockFrequency",c_double),                  #External system clock frequency: Hz.
                ("Atten",c_int8),                                           #attenuation
                ("DCCancelerMode",DCCancelerMode_TypeDef),                  #Suitable for specific equipment. Dc suppression. 0: disables the DCC. 1: Open, high-pass filter mode (better suppression effect, but will damage the signal in the range of DC to 100 KHZ); 2: Open, manual bias mode (need manual calibration, but not low frequency damage signal).
                ("QDCMode",QDCMode_TypeDef),                                #Suitable for specific equipment. IQ amplitude and phase corrector. QDCOff: disables the QDC function. QDCManualMode: Enable and use manual mode; QDCAutoMode: Enables and uses the automatic QDC mode.
                ("QDCIGain",c_float),                                       #Suitable for specific equipment. Normalized linear gain I, 1.0 indicates no gain, set range 0.8 to 1.2.
                ("QDCQGain",c_float),                                       #Suitable for specific equipment. Normalized linear gain Q, 1.0 indicates no gain, set range 0.8~1.2.
                ("QDCPhaseComp",c_float),                                   #Suitable for specific equipment. Normalized phase compensation coefficient, set range -0.2~+0.2.
                ("DCCIOffset",c_int8),                                      #Suitable for specific equipment. I channel DC offset, LSB.
                ("DCCQOffset",c_int8),                                      #Suitable for specific equipment. Q channel DC offset, LSB.
                ("LOOptimization",LOOptimization_TypeDef)]                  #LO optimization.

# Package information structure returned after RTA configuration (Returned)
class RTA_FrameInfo_TypeDef(Structure):
    _fields_ = [("StartFrequency_Hz",c_double),     #The start frequency of the spectrum.
                ("StopFrequency_Hz",c_double),      #The stop frequency of the spectrum.
                ("POI",c_double),                   #The shortest duration of the signal with 100% probability of interception, unit: s.
                ("TraceTimestampStep",c_double),    #Timestamp step of each Trace in each packet of data. (package overall timestamp in TriggerInfo SysTimerCountOfFirstDataPoint).
                ("TimeResolution",c_double),        #The sampling time of each time domain data which is also the resolution of the timestamp.
                ("PacketAcqTime",c_double),         #Data collection time of each packet.
                ("PacketCount",c_uint32),           #The total number of data packets corresponding to the current configuration takes effect only in FixedPoints mode.
                ("PacketFrame",c_uint32),           #The number of valid frames per packet.
                ("FFTSize",c_uint32),               #The number of FFTS per frame.
                ("FrameWidth",c_uint32),            #The number of points after FFT frame interception is also the number of points of each Trace in the packet, which can be used as the number of points on the X-axis of the probability density graph (width).
                ("FrameHeight",c_uint32),           #The spectrum amplitude range corresponding to the FFT frame can be used as the number of Y-axis points (height) of the probability density map.
                ("PacketSamplePoints",c_uint32),    #Number of collection points corresponding to each packet of data.
                ("PacketValidPoints",c_uint32),     #The number of valid data points in the frequency domain contained in each packet.
                ("MaxDensityValue",c_uint32),       #Upper limit of individual site element value of probability density bitmap.
                ("GainParameter",c_uint32)]         #Include Space(31~24Bit),PreAmplifierState(23~16Bit),StartRFBand(15~8Bit),StopRFBand(7~0Bit)

#The drawing information structure returned by RTA after obtaining it
class RTA_PlotInfo_TypeDef(Structure):
    _fields_ = [("ScaleTodBm",c_float),             #Compression from linear power to logarithmic power. The absolute power of Trace is equal to Trace[] * ScaleTodBm + OffsetTodBm(the absolute power axis of Bitmap is the same below).
                ("OffsetTodBm",c_float),            #The shift of relative power into absolute power. The absolute power axis range of bitmap (Y-axis) is equal to FrameHeigh * ScaleTodBm + OffsetTodBm(Trace physical power ditto above).
                ("SpectrumBitmapIndex",c_uint64)]   #The number of times a probability density map is obtained, which can be used as an index when plotting.
   
#Auxiliary information for measurement data (Return)
class MeasAuxInfo_TypeDef(Structure):
    _fields_ = [("MaxIndex",c_uint32),              #Index of the maximum power value in the current packet
                ("MaxPower_dBm",c_float),           #The maximum power in the current packet
                ("Temperature",c_int16),            #Device Temperature, Celsius = 0.01 x temperature
                ("RFState",c_uint16),               #Rf state
                ("BBState",c_uint16),               #Baseband state
                ("GainPattern",c_uint16),           #The gain control word used by the frequency of the current packet
                ("ConvertPattern",c_uint32),        #Frequency conversion mode used by the current packet frequency point
                ("SysTimeStamp",c_double),          #System time stamp of the current packet, in seconds
                ("AbsoluteTimeStamp",c_double),     #Absolute timestamp of the current packet
                ("Latitude",c_float),               #The latitude coordinates corresponding to the current packet are positive in north latitude and negative in south latitude to distinguish between north and south latitude
                ("Longitude",c_float)]              #The longitude coordinates corresponding to the current data packet are positive in east longitude and negative in west longitude to distinguish between east and west longitude
    
DET_TriggerInfo_TypeDef = TriggerInfo_TypeDef
RTA_TriggerInfo_TypeDef = TriggerInfo_TypeDef

class DSP_FFT_TypeDef(Structure):
    _fields_ = [("FFTSize",c_uint32),              #Number of FFT analysis points
                ("SamplePts",c_uint32),           #Number of valid sampling points
                ("WindowType",Window_TypeDef),            #Window type
                ("TraceDetector",TraceDetector_TypeDef),               #Trace detection method
                ("DetectionRatio",c_uint32),               #Trace detection ratio
                ("Intercept",c_float),           #Spectrum output ratio (e.g., Intercept = 0.8 means output 80% of spectrum result)
                ("Calibration",c_bool)]        #Whether calibration is performed

class DSP_DDC_TypeDef(Structure):
    _fields_ = [("DDCOffsetFrequency",c_double), #Frequency offset for complex mixing
                ("SampleRate",c_double),         #Sampling rate for complex mixing
                ("DecimateFactor",c_float),      #Resampling decimation factor, range: 1 ~ 2^16
                ("SamplePoints",c_uint64),       #Number of sampling points     
                ]

class ASG_Profile_TypeDef(Structure):
    _fields_ = [("CenterFreq_Hz",c_double),         #Current center frequency in Hz, valid in SIG_Fixed mode; Range: 1M-1GHz; Step: 1Hz
                ("Level_dBm",c_double),             #Current power in dBm, valid in SIG_Fixed mode; Range: -127 to -5 dBm; Step: 0.25 dB
                ("StartFreq_Hz",c_double),          #Start frequency for sweep mode in Hz, valid in SIG_FreqSweep_* mode; Range: 1M-1GHz; Step: 1Hz
                ("StopFreq_Hz", c_double),          #Stop frequency for sweep mode in Hz, valid in SIG_FreqSweep_* mode; Range: 1M-1GHz; Step: 1Hz
                ("StepFreq_Hz", c_double),          #Step frequency in sweep mode in Hz; Range: 1M-1GHz; Step: 1Hz
                ("StartLevel_dBm", c_double),       #Start power in sweep mode, in dBm
                ("StopLevel_dBm", c_double),        #Stop power in sweep mode, in dBm
                ("StepLevel_dBm", c_double),        #Step power in sweep mode, in dBm
                ("DwellTime_s", c_double),          #Dwell time in sweep mode (frequency or power), in seconds. Valid when trigger mode is BUS; Range: 0-1,000,000; Step: 1
                ("ReferenceClockFrequency", c_double),      #Reference clock frequency (applies to both internal and external clock)

                ("ReferenceClockSource",ReferenceClockSource_TypeDef),              #Reference clock input source: internal or external
                ("Port",ASG_Port_TypeDef),                                          #Signal generator output port
                ("Mode",ASG_Mode_TypeDef),                                          #Off, fixed frequency, frequency sweep (external trigger, sync with receiver), power sweep (external trigger, sync with receiver)
                ("TriggerSource",ASG_TriggerSource_TypeDef),                        #Trigger input source
                ("TriggerInMode",ASG_TriggerInMode_TypeDef),                        #Trigger input mode
                ("TriggerOutMode",ASG_TriggerOutMode_TypeDef)]                      #Trigger output mode

class GNSSInfo_TypeDef(Structure):
    _fields_ = [
        ("latitude", c_float),                   # Latitude
        ("longitude", c_float),                  # Longitude
        ("altitude", c_int16),                   # Altitude
        ("SatsNum", c_uint8),                    # Number of satellites currently in use
        ("GNSS_LockState", c_uint8),             # GNSS lock status
        ("DOCXO_LockState", c_uint8),            # DOCXO lock status
        ("DOCXO_WorkMode", DOCXOWorkMode_TypeDef),  # DOCXO operating mode
        ("GNSSAntennaState", GNSSAntennaState_TypeDef), # Antenna status
        ("hour", c_int16),
        ("minute", c_int16),
        ("second", c_int16),
        ("Year", c_int16),
        ("month", c_int16),
        ("day", c_int16),]
class GNSS_SNR_TypeDef(Structure):
    _fields_ = [
        ("Max_SatxC_No", c_uint8),  # Maximum SNR
        ("Min_SatxC_No", c_uint8),  # Minimum SNR
        ("Avg_SatxC_No", c_uint8),  # Average SNR
    ]

class GNSS_SatDate_TypeDef(Structure):
    _fields_ = [
        ("SatsNum_All", c_uint8),           # Total visible satellites in range
        ("SatsNum_Use", c_uint8),           # Number of satellites used for positioning
        ("GNSS_SNR_UsePos", GNSS_SNR_TypeDef),     # SNR of satellites used for positioning
        ("GNSS_SNR_NotUsePos", GNSS_SNR_TypeDef),]

class ASG_Info_TypeDef(Structure):
    _fields_ = [("SweepPoints",c_uint32)]         #Current center frequency in Hz, effective when the signal generator is operating in SIG_Fixed mode; input range 1MHz to 1GHz; step size 1Hz

dll.Get_APIVersion.argtypes = []
dll.Get_APIVersion.restype = c_int

#Device interface - this function must be called before any device operation to acquire the device resource.
dll.Device_Open.argtypes = [POINTER(c_void_p),c_int,POINTER(BootProfile_TypeDef),POINTER(BootInfo_TypeDef)]
dll.Device_Open.restype = c_int

#The dev interface to shut down the device. This function must be called to release device resources after the operation on the device is complete
dll.Device_Close.argtypes = [POINTER(c_void_p)]
dll.Device_Close.restype = c_int

#The dev interface to obtain device information, including device serial number, software and hardware version and other related information, non-real-time mode, without interrupting data acquisition, but information is only updated after obtaining data packets
dll.Device_QueryDeviceInfo.argtypes = [POINTER(c_void_p),POINTER(DeviceInfo_TypeDef)]
dll.Device_QueryDeviceInfo.restype = c_int

#The dev interface to obtain device status, including device temperature, hardware working status, geo-time information (optional support is required), etc., non-real-time mode, without interrupting data acquisition, but information is only updated after obtaining data packets
dll.Device_QueryDeviceState.argtypes = [POINTER(c_void_p),POINTER(DeviceState_TypeDef)]
dll.Device_QueryDeviceState.restype = c_int

# dev interface: Set GNSS antenna state (requires optional support)
dll.Device_SetGNSSAntennaState.argtypes = [POINTER(c_void_p), GNSSAntennaState_TypeDef]
dll.Device_SetGNSSAntennaState.restype = c_int

# dev interface: Get GNSS antenna state (requires optional support), non-real-time
dll.Device_GetGNSSAntennaState.argtypes = [POINTER(c_void_p), POINTER(GNSSAntennaState_TypeDef)]
dll.Device_GetGNSSAntennaState.restype = c_int

# dev interface: Get GNSS antenna state (requires optional support), real-time
dll.Device_GetGNSSAntennaState_Realtime.argtypes = [POINTER(c_void_p), POINTER(GNSSAntennaState_TypeDef)]
dll.Device_GetGNSSAntennaState_Realtime.restype = c_int

# dev interface: Parse GNSS time and date information (requires optional support)
dll.Device_AnysisGNSSTime.argtypes = [c_double, POINTER(c_int16), POINTER(c_int16), POINTER(c_int16),POINTER(c_int16), POINTER(c_int16), POINTER(c_int16)]
dll.Device_AnysisGNSSTime.restype = c_int

# dev interface: Get GNSS altitude (requires optional support), non-real-time
dll.Device_GetGNSSAltitude.argtypes = [POINTER(c_void_p), POINTER(c_int16)]
dll.Device_GetGNSSAltitude.restype = c_int

# dev interface: Get GNSS altitude (requires optional support), real-time
dll.Device_GetGNSSAltitude_Realtime.argtypes = [POINTER(c_void_p), POINTER(c_int16)]
dll.Device_GetGNSSAltitude_Realtime.restype = c_int

# dev interface: Set DOCXO working mode in GNSS (requires optional support)
dll.Device_SetDOCXOWorkMode.argtypes = [POINTER(c_void_p), DOCXOWorkMode_TypeDef]
dll.Device_SetDOCXOWorkMode.restype = c_int

# dev interface: Get DOCXO working mode in GNSS (requires optional support), real-time
dll.Device_GetDOCXOWorkMode_Realtime.argtypes = [POINTER(c_void_p), POINTER(DOCXOWorkMode_TypeDef)]
dll.Device_GetDOCXOWorkMode_Realtime.restype = c_int

# dev interface: Get DOCXO working mode in GNSS (requires optional support), non-real-time
dll.Device_GetDOCXOWorkMode.argtypes = [POINTER(c_void_p), POINTER(DOCXOWorkMode_TypeDef)]
dll.Device_GetDOCXOWorkMode.restype = c_int

# dev interface: Get GNSS device status (requires optional support), non-real-time
dll.Device_GetGNSSInfo.argtypes = [POINTER(c_void_p), POINTER(GNSSInfo_TypeDef)]
dll.Device_GetGNSSInfo.restype = c_int

# dev interface: Get GNSS device status (requires optional support), real-time
dll.Device_GetGNSSInfo_Realtime.argtypes = [POINTER(c_void_p), POINTER(GNSSInfo_TypeDef)]
dll.Device_GetGNSSInfo_Realtime.restype = c_int

# dev interface: Get GNSS SNR (requires optional support), non-real-time, does not interrupt data acquisition, info updates after each data packet
dll.Device_GetGNSS_SatDate.argtypes = [POINTER(c_void_p), POINTER(GNSS_SatDate_TypeDef)]
dll.Device_GetGNSS_SatDate.restype  = c_int

# dev interface: Get GNSS SNR (requires optional support), real-time, temporarily occupies data channel
dll.Device_GetGNSS_SatDate_Realtime.argtypes = [POINTER(c_void_p), POINTER(GNSS_SatDate_TypeDef)]
dll.Device_GetGNSS_SatDate_Realtime.restype  = c_int

#SWP mode, configure SWP_Profile to the default value
dll.SWP_ProfileDeInit.argtypes = [POINTER(c_void_p),POINTER(SWP_Profile_TypeDef)]
dll.SWP_ProfileDeInit.restype = c_int

# SWP mode, set SWP mode parameters
dll.SWP_Configuration.argtypes = [POINTER(c_void_p),POINTER(SWP_Profile_TypeDef),POINTER(SWP_Profile_TypeDef),POINTER(SWP_TraceInfo_TypeDef)]
dll.SWP_Configuration.restype = c_int

#SWP mode, obtain partial scanning spectrum data in SWP mode
dll.SWP_GetPartialSweep.argtypes = [POINTER(c_void_p),POINTER(c_double),POINTER(c_float),POINTER(c_int),POINTER(c_int),POINTER(MeasAuxInfo_TypeDef)]
dll.SWP_GetPartialSweep.restype = c_int

# SWP mode, obtain the completely refreshed spectrum data in SWP mode
dll.SWP_GetFullSweep.argtypes = [POINTER(c_void_p),POINTER(c_double),POINTER(c_float),POINTER(MeasAuxInfo_TypeDef)]
dll.SWP_GetFullSweep.restype = c_int

#IQS mode, set IQS_Profile to the default value
dll.IQS_ProfileDeInit.argtypes = [POINTER(c_void_p),POINTER(IQS_Profile_TypeDef)]
dll.IQS_ProfileDeInit.restype = c_int

#IQS mode, set IQS mode parameters
dll.IQS_Configuration.argtypes = [POINTER(c_void_p),POINTER(IQS_Profile_TypeDef),POINTER(IQS_Profile_TypeDef),POINTER(IQS_StreamInfo_TypeDef)]
dll.IQS_Configuration.restype = c_int

#IQS mode, initiating the bus trigger
dll.IQS_BusTriggerStart.argtypes = [POINTER(c_void_p)]
dll.IQS_BusTriggerStart.restype = c_int

#IQS mode, terminating the bus trigger
dll.IQS_BusTriggerStop.argtypes = [POINTER(c_void_p)]
dll.IQS_BusTriggerStop.restype =c_int

#IQS mode, the interwoven IQ data stream under IQS mode is obtained, and the scale factor from integer to absolute amplitude (V units) and the related information of trigger are obtained
dll.IQS_GetIQStream.argtypes = [POINTER(c_void_p),POINTER(c_int16_p),POINTER(c_float),POINTER(TriggerInfo_TypeDef),POINTER(MeasAuxInfo_TypeDef)]
dll.IQS_GetIQStream.restype = c_int
dll.IQS_GetIQStream_PM1.argtypes = [POINTER(c_void_p),POINTER(IQStream_TypeDef)]
dll.IQS_GetIQStream_PM1.restype = c_int

#DET mode, set DET_Profile to the default value
dll.DET_ProfileDeInit.argtypes = [POINTER(c_void_p),POINTER(DET_Profile_TypeDef)]
dll.DET_ProfileDeInit.restype = c_int

#DET mode, set parameters related to the DET mode
dll.DET_Configuration.argtypes = [POINTER(c_void_p),POINTER(DET_Profile_TypeDef),POINTER(DET_Profile_TypeDef),POINTER(DET_StreamInfo_TypeDef)]
dll.DET_Configuration.restype = c_int

#DET mode, initiating the bus trigger
dll.DET_BusTriggerStart.argtypes = [POINTER(c_void_p)]
dll.DET_BusTriggerStart.restype = c_int

#DET mode, terminating the bus trigger
dll.DET_BusTriggerStop.argtypes = [POINTER(c_void_p)]
dll.DET_BusTriggerStop.restype = c_int

#DET mode, obtain the detection data in DET mode, and obtain the scale factor from integer to absolute amplitude (V units) and trigger related information. NormalizedPowerStream is the square root of I square +Q square
dll.DET_GetPowerStream.argtypes = [POINTER(c_void_p),POINTER(c_float),POINTER(c_float),POINTER(DET_TriggerInfo_TypeDef),POINTER(MeasAuxInfo_TypeDef)]
dll.DET_GetPowerStream.restype = c_int

# RTA mode, set RTA_Profile to the default value
dll.RTA_ProfileDeInit.argtypes = [POINTER(c_void_p),POINTER(RTA_Profile_TypeDef)]
dll.RTA_ProfileDeInit.restype = c_int

#RTA mode, set parameters related to the RTA mode
dll.RTA_Configuration.argtypes = [POINTER(c_void_p),POINTER(RTA_Profile_TypeDef),POINTER(RTA_Profile_TypeDef),POINTER(RTA_FrameInfo_TypeDef)]
dll.RTA_Configuration.restype = c_int

#RTA mode, initiating the bus trigger
dll.RTA_BusTriggerStart.argtypes = [POINTER(c_void_p)]
dll.RTA_BusTriggerStart.restype = c_int

#RTA mode, terminating the bus trigger
dll.RTA_BusTriggerStop.argtypes = [POINTER(c_void_p)]
dll.RTA_BusTriggerStop.restype = c_int

#RTA mode, real-time spectrum data and trigger related information are obtained in RTA mode
dll.RTA_GetRealTimeSpectrum.argtypes = [POINTER(c_void_p),POINTER(c_uint8),POINTER(c_uint16),POINTER(RTA_PlotInfo_TypeDef),POINTER(RTA_TriggerInfo_TypeDef),POINTER(MeasAuxInfo_TypeDef)]
dll.RTA_GetRealTimeSpectrum.restype = c_int

#DSP auxiliary functions
#DSP auxiliary function to start DSP functionality
dll.DSP_Open.argtypes = [POINTER(c_void_p)]
dll.DSP_Open.restype = c_int

# DSP helper function: initialize FFT configuration parametersdll.DSP_FFT_DeInit.argtypes = [POINTER(DSP_FFT_TypeDef)]
dll.DSP_FFT_DeInit.argtypes = [POINTER(DSP_FFT_TypeDef)]
dll.DSP_FFT_DeInit.restype = c_int

#DSP helper function: initialize DDC configuration parameters
dll.DSP_DDC_DeInit.argtypes = [POINTER(DSP_DDC_TypeDef)]
dll.DSP_DDC_DeInit.restype = c_int

#DSP helper function: configure DDC
dll.DSP_DDC_Configuration.argtypes = [POINTER(c_void_p),POINTER(DSP_DDC_TypeDef),POINTER(DSP_DDC_TypeDef)]
dll.DSP_DDC_Configuration.restype = c_int

#DSP helper function: execute DDC
dll.DSP_DDC_Execute.argtypes = [POINTER(c_void_p),POINTER(IQStream_TypeDef),POINTER(IQStream_TypeDef)]
dll.DSP_DDC_Execute.restype = c_int

dll.DSP_DDC_Reset.argtypes = [POINTER(c_void_p)]
dll.DSP_DDC_Reset.restype = c_int

#DSP helper function: configure FFT parameters
dll.DSP_FFT_Configuration.argtypes = [POINTER(c_void_p),POINTER(DSP_FFT_TypeDef),POINTER(DSP_FFT_TypeDef),POINTER(c_uint32), POINTER(c_double)]
dll.DSP_FFT_Configuration.restype = c_int

# DSP helper function: convert IQ data into spectrum datadll.DSP_FFT_IQSToSpectrum.argtypes = [POINTER(c_void_p),POINTER(IQStream_TypeDef),POINTER(c_double),POINTER(c_float)]
dll.DSP_FFT_IQSToSpectrum.argtypes = [POINTER(c_void_p),POINTER(IQStream_TypeDef),POINTER(c_double),POINTER(c_float)]
dll.DSP_FFT_IQSToSpectrum.restype = c_int

# Analog Signal Generator (ASG): set Profile to default valuesdll.ASG_ProfileDeInit.argtypes = [POINTER(c_void_p),POINTER(ASG_Profile_TypeDef)]
dll.ASG_ProfileDeInit.argtypes = [POINTER(c_void_p),POINTER(ASG_Profile_TypeDef)]
dll.ASG_ProfileDeInit.restype = c_int

# Analog Signal Generator: configure working statusdll.ASG_Configuration.argtypes = [POINTER(c_void_p),POINTER(ASG_Profile_TypeDef),POINTER(ASG_Profile_TypeDef),POINTER(ASG_Info_TypeDef)]
dll.ASG_Configuration.argtypes = [POINTER(c_void_p),POINTER(ASG_Profile_TypeDef),POINTER(ASG_Profile_TypeDef),POINTER(ASG_Info_TypeDef)]
dll.ASG_Configuration.restype = c_int