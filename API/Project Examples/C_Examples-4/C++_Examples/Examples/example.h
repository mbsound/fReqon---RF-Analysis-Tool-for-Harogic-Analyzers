#define EXAMPLE_MACRO_NAME
#include "htra_api.h"


int Device_GetDeviceInfo(); // Get device information, including: API version, USB version, device model, device UID, MCU version, FPGA version, and device temperature.
int Device_SysPowerState(); // Example of setting the device standby state, which can be set to normal operation or RF powered off (low power).
int Device_AboutGNSS();     // Get GNSS module information, including latitude, longitude, altitude, and time, and GNSS-related information in MeasAuxInfo under SWP mode and in IQStream.DeviceState under IQS mode.
int Device_GetAndSetIP();   // Get the device IP address, and modify the IP address through the device UID or the current device IP.
int Device_MeasureModeSwitchTime(); // Get the time required for switching different modes by the host PC.


int SWP_GetSpectrum_Standard();	  // Get spectrum data by calling the function interface.
int SWP_MaxHold_MinHold();        // Set the trace mode to MaxHold or MinHold and reset hold using SWP_ResetTraceHold.
int SWP_TraceAverage();           // Perform averaging on the acquired trace.
int SWP_AutoSetMeasure();	      // Automatically configure related parameters based on specific SWP applications and complete measurement by issuing automatic configuration parameters.
int SWP_SetFreqCompensation();    // Apply frequency compensation for power correction over a specific frequency band or the entire band in SWP mode.
int SWP_TimeOfSetFunction();
int SWP_PickMaxPower();           // Get the maximum power point and its corresponding frequency point in the current spectrum.
int SWP_GetSpectrum_SigAndSpur(); // Distinguish signal and spurs after getting the spectrum data.
int SWP_GetSpectrumAndIQS();      // Simultaneously acquire spectrum data and IQ data.
int SWP_GNSSReferenceClock();     // Use the high-quality GNSS module's 10MHz reference clock in SWP mode.
int SWP_GetSpectrum_Trigger();    // Get spectrum data when the trigger source is set to external trigger.
int SWP_GetSpectrum_TraceAlign(); // Get spectrum data when the trace alignment mode is set to align to the start frequency or the center frequency.
int SWP_Fixedtime_GetFrames();    // Loop 50 times to get 10s spectrum data and calculate the average spectrum frame count within 10s.
int SWP_CalibrateRefClock();      // Device clock calibration through GNSS-1PPS or Ext trigger.
int SWP_Meas_PhaseNoise();        // Phase noise measurement.
int SWP_Meas_ChannelPower();      // Channel power measurement.
int SWP_Meas_ACPR();              // Adjacent Channel Power Ratio measurement.
int SWP_Meas_OBW();               // Measure occupied bandwidth in percentage.
int SWP_Meas_XdBBW();             // Measure occupied bandwidth in XdB.
int SWP_Meas_IM3();               // IM3 measurement.
int SWP_RBW_Spaced_Trace();       // Set the frequency spacing between two trace points to be close to RBW.
int SWP_RefCLKSource_External();  // Use external 10MHz reference clock. (The method for using an external 10MHz reference clock in SWP mode is given as an example, and the same applies to other modes.)


int IQS_GetIQ_Standard();              // Acquire fixed-point or continuous stream IQ data under professional configuration.
int IQS_ScaleIQDataToVolts();          // Convert acquired IQ data to data in volts.
int IQS_ConfigandGetIQ_Time();         // Get the time consumed by IQS_Configuration and IQS_GetIQStream_PM1 function calls.
int IQS_ToSpectrumByLiquid();          // Convert the acquired time-domain IQ data to spectrum data using the liquid library's spectrum analysis method.
int IQS_AudioAnalysis();               // Perform audio analysis on demodulated IQ data to obtain audio voltage, audio frequency, SNR, and total harmonic distortion.
int IQS_GetIQToTxt();                  // Write the acquired IQ data to a .txt file.
int IQS_Multithread_GetIQ_FFT_Write(); // Multi-threaded acquisition of IQ data, performing FFT on IQ data, and writing the IQ data to a txt file.
int IQS_GNSS_1PPS();                   // Use GNSS module's 1PPS trigger in IQS mode.
int IQS_MultiDevSync_fixed();          // Synchronize multiple devices to simultaneously collect the same signal at the same time.
int IQS_ExternalTrigger();             // Configure the trigger source as external trigger.
int IQS_TimerTrigger();                // Configure the trigger source as timer trigger.
int IQS_LevelTrigger_PreTrigger();     // Configure the trigger source as level trigger and set the pre-trigger time.
int IQS_LevelTrigger_TriggerDelay();   // Configure the trigger source as level trigger and set the trigger delay time.
int IQS_Enable_GNSS_10MHz();           // Use high-quality GNSS module's 10MHz reference clock in IQS mode.
int IQS_FMDataAnalysis();			   // FM data analysis
int IQS_AMDataAnalysis();			   // AM data analysis

int DSP_IQSToSpectrum(); // Convert the acquired time-domain IQ data to spectrum data using spectrum analysis.
int DSP_DDC();           // Perform decimation on the acquired IQ data.
int DSP_LPF();           // Perform low-pass filtering on the acquired IQ data.


int DETMode_Standard();   // Acquire fixed-point or continuous stream detection data.


int RTAMode_Standard();          // Acquire fixed-point (duration) or continuous stream real-time spectrum data.
int RTAMode_Standard_perframe(); // Get 100 frames of data and calculate the average processing time for each frame.


int ASG_SignalOutput(); // Output single-tone/sweep/power-scan signals on demand.


void Device_Open_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo); // Error handling during device opening
void SWP_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, SWP_Profile_TypeDef* SWP_ProfileIn, SWP_Profile_TypeDef* SWP_ProfileOut, SWP_TraceInfo_TypeDef* TraceInfo); // Error handling during SWP mode configuration
void IQS_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, IQS_Profile_TypeDef* IQS_ProfileIn, IQS_Profile_TypeDef* IQS_ProfileOut, IQS_StreamInfo_TypeDef* StreamInfo); // Error handling during IQS mode configuration
void DET_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, DET_Profile_TypeDef* DET_ProfileIn, DET_Profile_TypeDef* DET_ProfileOut, DET_StreamInfo_TypeDef* StreamInfo); // Error handling during DET mode configuration
void RTA_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, RTA_Profile_TypeDef* RTA_ProfileIn, RTA_Profile_TypeDef* RTA_ProfileOut, RTA_FrameInfo_TypeDef* FrameInfo); // Error handling during RTA mode configuration
void SWP_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, SWP_Profile_TypeDef* SWP_ProfileIn, SWP_Profile_TypeDef* SWP_ProfileOut, SWP_TraceInfo_TypeDef* TraceInfo); // Error handling during SWP mode function calls except for device opening and configuration
void IQS_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, IQS_Profile_TypeDef* IQS_ProfileIn, IQS_Profile_TypeDef* IQS_ProfileOut, IQS_StreamInfo_TypeDef* StreamInfo); // Error handling during IQS mode function calls except for device opening and configuration
void DET_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, DET_Profile_TypeDef* DET_ProfileIn, DET_Profile_TypeDef* DET_ProfileOut, DET_StreamInfo_TypeDef* StreamInfo); // Error handling during DET mode function calls except for device opening and configuration
void RTA_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, RTA_Profile_TypeDef* RTA_ProfileIn, RTA_Profile_TypeDef* RTA_ProfileOut, RTA_FrameInfo_TypeDef* FrameInfo); // Error handling during RTA mode function calls except for device opening and configuration
