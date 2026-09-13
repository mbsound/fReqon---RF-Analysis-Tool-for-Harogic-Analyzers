#include <stdio.h>
#include <string.h>
#include <vector>
#include<chrono>
#include<iostream>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default device is USB type. If using Ethernet device, set IS_USB to 0.

int SWP_Meas_XdBBW()
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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open the device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is not 0, perform corresponding error handling based on the return value of Status.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef ProfileSetOut;  // This structure is used to feedback the automatically recommended configuration.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under the current configuration, including the number of trace points, the number of frequency hops, etc.

	Status = SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize the relevant parameters of the SWP mode.
	SWP_ProfileIn.CenterFreq_Hz = 1e9;                   // Configure center frequency
	SWP_ProfileIn.FreqAssignment = CenterSpan;           // Frequency assignment method
	uint8_t IfDoConfig = 1;                              // When IfDoConfig is 0, SWP_AutoSet needs to be called before SWP_Configuration; when IfDoConfig is 1, the function will call SWP_Configuration internally, no additional call is needed

	SWP_AutoSet(&Device, SWPOBWMeas, &SWP_ProfileIn, &ProfileSetOut, &TraceInfo, IfDoConfig); // This function gives recommended device configuration based on the application target using the spectrum analyzer's sweep mode (SWPMode).

	ProfileSetOut.RBW_Hz = 50e3;                                                      // Modify the recommended RBW value. (Modify the recommended configuration if necessary)
	Status = SWP_Configuration(&Device, &ProfileSetOut, &SWP_ProfileOut, &TraceInfo); // Reset the recommended configuration.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary information for measurement data, including: maximum power index, maximum power, device temperature, latitude, longitude, absolute timestamp, etc.

	Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); // Get the spectrum data.

	float XdB = 3;                             // Bandwidth at XdB down point of signal peak power.
	TraceAnalysisResult_XdB_TypeDef XdBResult; // Occupied bandwidth information under the current configuration.

	DSP_TraceAnalysis_XdBBW(Frequency.data(), PowerSpec_dBm.data(), TraceInfo.FullsweepTracePoints, XdB, &XdBResult);

	Device_Close(&Device);
	return 0;
}
