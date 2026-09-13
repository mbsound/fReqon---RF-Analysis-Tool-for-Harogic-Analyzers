#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // Default to USB device; set IS_USB to 0 if using Ethernet device.

// This example uses an external reference clock in SWP mode; the configuration method is consistent across other modes.

int SWP_RefCLKSource_External()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Pointer to the current device.
	int DevNum = 0;      // Specified device index.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and independent power port for power supply.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open the device.
	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the error according to its return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start/stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under the current configuration, including trace points, hop count, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize parameters related to SWP mode.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Set start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Set stop frequency.
	SWP_ProfileIn.RBWMode = RBW_Manual; // Set RBW update mode to manual.
	SWP_ProfileIn.RBW_Hz = 200e3;       // Set RBW.
	SWP_ProfileIn.ReferenceClockSource = ReferenceClockSource_External; // Set reference clock source to external.
	SWP_ProfileIn.ReferenceClockFrequency = 10e6;                       // Set reference clock frequency.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP mode configuration.
	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle the error accordingly.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement data including: peak power index, peak power value, device temperature, GPS coordinates, absolute timestamp, etc.

	// Loop to acquire spectrum data
	while (1)
	{
		for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops represents the number of frames under the current configuration, so calling SWP_GetPartialSweep this many times yields a full trace.
		{
			Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Acquire spectrum data.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				/*

				Example: display spectrum or perform other operations.

				*/
			}

			else // If Status is not 0, handle the error based on its return value.
			{
				SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
			}
		}
	}

	Device_Close(&Device); // Close the device.

	return 0;
}
