#include <stdio.h>
#include <string.h>
#include <vector>
#include<chrono>
#include<iostream>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default device is USB type. If using Ethernet device, set IS_USB to 0.

// Example for testing IP3/IM3 at 1 GHz frequency point. By using two signal generators and a combiner, merge signals with center frequencies of 999 MHz (amplitude -2 dBm) and 1.001 GHz (amplitude -2 dBm) into one signal, then input it into the spectrum analyzer.

int SWP_Meas_IM3()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and independent power port for dual power supply.

#if IS_USB==1
	// Configure USB interface.
	BootProfile.PhysicalInterface = USB;
#else 
	// Configure ETH interface.
	BootProfile.PhysicalInterface = ETH;
	BootProfile.ETH_IPVersion = IPv4;
	BootProfile.ETH_RemotePort = 5000;
	BootProfile.ETH_ReadTimeOut = 5000;
	BootProfile.ETH_IPAddress[0] = 192;
	BootProfile.ETH_IPAddress[1] = 168;
	BootProfile.ETH_IPAddress[2] = 1;
	BootProfile.ETH_IPAddress[3] = 100;
#endif

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is non-zero, handle the error based on the Status return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef ProfileSetOut;  // This structure is used to feedback the automatically recommended configuration.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under the current configuration, including trace points, hop points, etc.

	Status = SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode-related parameters.
	SWP_ProfileIn.CenterFreq_Hz = 1e9;                   // Configure center frequency.
	SWP_ProfileIn.FreqAssignment = CenterSpan;           // Frequency assignment method.
	uint8_t IfDoConfig = 1;                              // When IfDoConfig is 0, SWP_AutoSet needs to be called before SWP_Configuration; When IfDoConfig is 1, the function will automatically call SWP_Configuration, no need to call it separately.
	
	SWP_AutoSet(&Device, SWPIM3Meas, &SWP_ProfileIn, &ProfileSetOut, &TraceInfo, IfDoConfig); // This function gives the recommended device configuration based on the application target for the spectrum analyzer's sweep mode (SWPMode).

	ProfileSetOut.Span_Hz = 10e6;                                                     // Modify the recommended Span value. (If needed, modify the recommended configuration)
	Status = SWP_Configuration(&Device, &ProfileSetOut, &SWP_ProfileOut, &TraceInfo); // Reset recommended configuration.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement data, including: max power index, max power, device temperature, longitude, latitude, timestamp, etc.

	Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); // Get spectrum data.

	TraceAnalysisResult_IP3_TypeDef  IM3Result; // IM3 structure under the current configuration.

	DSP_TraceAnalysis_IM3(Frequency.data(), PowerSpec_dBm.data(), TraceInfo.FullsweepTracePoints, &IM3Result);

	Device_Close(&Device); // Close the device.
	return 0;
}
