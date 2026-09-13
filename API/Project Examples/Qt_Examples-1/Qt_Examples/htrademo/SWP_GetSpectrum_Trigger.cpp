#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // By default, a USB device is used. If an Ethernet device is used, set IS_USB to 0.

int SWP_GetSpectrum_Trigger()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specify device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both the USB data port and an independent power port.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, perform corresponding error handling based on the return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under current configuration, including trace points, hops, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Set start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Set stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;       // Set RBW.

#define TRIGGER 2 // Change TRIGGER value to 0, 1, or 2 to configure trigger source as needed.

#if TRIGGER == 0
	/* Internal trigger, free run (bus trigger) */
	SWP_ProfileIn.TriggerSource = InternalFreeRun;

#elif TRIGGER == 1
	/* External trigger, each trigger hops one frequency point */
	SWP_ProfileIn.TriggerSource = ExternalPerHop;

#elif TRIGGER==2
	/* External trigger, each trigger refreshes one full trace */
	SWP_ProfileIn.TriggerSource = ExternalPerSweep;
#else
	/* External trigger, each trigger applies a new configuration */
	SWP_ProfileIn.TriggerSource = ExternalPerProfile;
#endif

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP mode configuration through this function.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, perform corresponding error handling based on the return value.

	// Acquire partial sweep spectrum data under SWP mode
	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement information, including max power index, max power, device temperature, GPS, absolute timestamp, etc.

	// Loop to get data.
	while (1)
	{
		for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops indicates number of frames under current configuration. Loop TraceInfo.TotalHops times to call SWP_GetPartialSweep to get full trace.
		{
			Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Acquire spectrum data.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				/*

				For example: display spectrum or perform other operations

				*/
			}

			else // If Status is not 0, perform corresponding error handling based on the return value.
			{
				SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
			}
		}
	}

	Device_Close(&Device); // Close device.

	return 0;
}
