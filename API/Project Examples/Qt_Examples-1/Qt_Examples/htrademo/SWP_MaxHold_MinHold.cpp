#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // Default device is USB type. If using Ethernet device, set IS_USB to 0.

int SWP_MaxHold_MinHold()
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
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under the current configuration, including trace points, hop points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode-related parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Configure start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Configure stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;       // Configure RBW.
	SWP_ProfileIn.TraceType = MaxHold;  // Configure trace type as MaxHold.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP mode configuration.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // When Status is non-zero, handle the error based on the Status return value.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement data, including max power index, max power, device temperature, longitude, latitude, timestamp, etc.

    // Loop to acquire spectrum data
	while (1)
	{
		for (int j = 0; j < 10; j++) // Set the loop to run 10 times before resetting the hold.
		{
			for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops represents the number of frames under the current configuration, thus calling SWP_GetPartialSweep TotalHops times to obtain the full trace.
			{
			  Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Get spectrum data.
			  
			  if (Status == APIRETVAL_NoError)
			  {
				  // UserCode here
				  /*

				  For example: Display the spectrum or perform other processing on the spectrum.

				  */
			  }

			  else // When Status is non-zero, handle the error based on the Status return value.
			  {
				  SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
			  }
			}
		}

		SWP_ResetTraceHold(&Device); // Reset the held trace data when TraceType is MaxHold or MinHold.
	}

	Device_Close(&Device); // Close the device.

	return 0;
}
