#include<chrono>
#include <stdio.h>
#include <string.h>
#include <vector>
#include <iostream>
#include <cstdlib>
#include <vector>
#include "example.h"
#include "htra_api.h" 
using namespace std;

#define IS_USB 1 // Default to USB device; define as 0 if using Ethernet device.

int SWP_SetFreqCompensation()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Pointer to the current device.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration struct, includes physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot info struct, includes device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and independent power port for dual power supply.

#if IS_USB==1
	// Configure USB interface.
	BootProfile.PhysicalInterface = USB;
#else 
	// Configure Ethernet interface.
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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Handle errors based on the return value of Status.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input profile, includes start/stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output profile.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace info under current configuration, includes trace point count, hop count, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode parameters.

	SWP_ProfileIn.StartFreq_Hz = 2e8;   // Configure start frequency.
	SWP_ProfileIn.StopFreq_Hz = 3e8;    // Configure stop frequency.
	//SWP_ProfileIn.RBWMode = RBW_Manual; // Set RBW manually.
	//SWP_ProfileIn.RBW_Hz = 30e3;        // Configure RBW.
	//SWP_ProfileIn.TracePoints = 16384;  // Configure trace point count

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP configuration.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors based on Status.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);             // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints);          // Create power array.
	uint8_t compensation_points = 4;                                      // Number of compensation points, must not exceed 256.
	vector<double> Compensate_freq = { 239.999e6,240e6,260e6,260.001e6 }; // Create frequency compensation array.
	vector<float> Compensate_dBm = {0.0f,10.0f,30.0f,0.0f};               // Create power compensation array.

	/* In SWP mode, use frequency compensation mechanism to correct power in specific frequency bands. The compensation rules are as follows:

		1. Interpolation compensation within frequency compensation range:

		Linear interpolation is performed between adjacent points in the Compensate_freq array to ensure a smooth transition of the compensation value within the specified frequency range.

		2. From start frequency (StartFreq_Hz) to start of compensation array (Compensate_freq[0]):

		The compensation value in this range is Compensate_dBm[0], i.e., filled using the start value of the compensation array.

		3. From end of compensation array (Compensate_freq.back()) to stop frequency (StopFreq_Hz):

		The compensation value in this range is Compensate_dBm.back(), i.e., filled using the end value of the compensation array. */

	Status = Devcie_SetFreqResponseCompensation(&Device, 1, Compensate_freq.data(), Compensate_dBm.data(), 4); // Call frequency compensation function

	MeasAuxInfo_TypeDef MeasAuxInfo; // This struct holds auxiliary info of measurement data.

	while (1) 
	{
		Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); // Acquire spectrum data.

		if (Status == APIRETVAL_NoError)
		{
			// UserCode here
			/*

			For example: display the spectrum or do further processing

			*/
		}

		else // Handle errors based on Status, except for open/configuration errors.
		{
			SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
		}

	}

	Device_Close(&Device); // Close device.

	return 0;
}
