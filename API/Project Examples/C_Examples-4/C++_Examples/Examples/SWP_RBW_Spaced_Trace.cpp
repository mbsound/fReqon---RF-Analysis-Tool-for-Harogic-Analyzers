#include <stdio.h>
#include <string.h>
#include <vector>
#include <cmath>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // By default, a USB device is used. If using a network device, set IS_USB to 0.

int SWP_RBW_Spaced_Trace()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Device memory address.
	int DevNum = 0;      // Device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot info structure, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and external power port.

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
	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the error accordingly.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start/stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace info under current configuration, including number of trace points, hopping points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize parameters related to SWP mode.

	SWP_ProfileIn.RBWMode = RBW_Manual;							 // Set RBW mode to manual.
	SWP_ProfileIn.RBW_Hz = 12.5e3;								 // Manually set desired RBW value.
	SWP_ProfileIn.TraceDetectMode = TraceDetectMode_Manual;		 // Set detector mode to manual.
	SWP_ProfileIn.TraceDetector = TraceDetector_Bypass;			 // Set detector to bypass.
	SWP_ProfileIn.TracePointsStrategy = PointsAccuracyPreferred; // Set trace point mapping strategy to prioritize accuracy.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP configuration.
	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle the error accordingly.

	SWP_ProfileIn.TraceDetectMode = TraceDetectMode_Auto;			                                                    // Set detector mode to automatic.
	SWP_ProfileIn.TracePoints = TraceInfo.FullsweepTracePoints / floor(SWP_ProfileIn.RBW_Hz / TraceInfo.TraceBinBW_Hz); // Calculate actual number of points under desired RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Re-apply configuration based on calculated trace points.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors if Status is not 0.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hopping point index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Measurement auxiliary info, including max power index, max power, device temperature, GPS info, absolute timestamp, etc.

	// Continuously acquire spectrum data
	while (1)
	{
		Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); // Get spectrum data.

		if (Status == APIRETVAL_NoError)
		{
			// UserCode here
			/*

			For example: display the spectrum or perform other processing.

			*/
		}

		else // If Status is not 0, handle the error accordingly.
		{
			SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
		}
	}

	Device_Close(&Device); // Close the device.

	return 0;
}
