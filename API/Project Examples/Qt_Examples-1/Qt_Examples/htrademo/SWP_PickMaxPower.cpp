#include <stdio.h>
#include <string.h>
#include <vector>
#include <iostream>
#include "htra_api.h"
#include "example.h"
#include <cstdlib>
#include <thread>  
#include <chrono>  
#include <limits>  
using namespace std;

#define IS_USB 1 // By default, use USB device. If using Ethernet device, set IS_USB to 0.

int SWP_PickMaxPower()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply type, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB speed, etc.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo);              // Open the device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the error according to the returned value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information for the current configuration, including trace points, hop points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode-related parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Set start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Set stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;       // Set RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP mode configuration.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle the error according to the returned value.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop point index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement information, including power max index, power max value, device temperature, latitude/longitude, absolute timestamp, etc.

	double StartFreq = SWP_ProfileIn.StartFreq_Hz; // Set initial frequency.
												   
	// Loop to get data.
	while (1)
	{
			for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops represents the number of frames for the current configuration, so loop TraceInfo.TotalHops times to call SWP_GetPartialSweep to get the full trace.
			{
				Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Get spectrum data.

				if (Status == APIRETVAL_NoError)
				{
					// UserCode here
					/*

					For example: display spectrum or perform other processing on the spectrum, etc.

					*/
				}

				else // If Status is not 0, handle the error according to the returned value.
				{
					SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
				}
			}

			// Find the maximum value
			float maxPower = std::numeric_limits<float>::lowest(); 
			double maxFreq = 0.0;                            // Initialize frequency value.
			for (size_t i = 0; i < PowerSpec_dBm.size(); ++i)
			{
				if (Frequency[i] >= StartFreq && PowerSpec_dBm[i] > maxPower)
				{
					maxPower = PowerSpec_dBm[i];
					maxFreq = Frequency[i];
				}
			}
			cout << "Spectrum peak value: " << maxPower << " Frequency: " << maxFreq << endl;
	}

	Device_Close(&Device); // Close the device.

	return 0;
}
