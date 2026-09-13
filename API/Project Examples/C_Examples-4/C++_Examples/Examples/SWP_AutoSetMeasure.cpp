#include <iostream>
#include <vector>
#include <string>
#include <map>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // By default, the USB type device is used. If using an Ethernet type device, define IS_USB as 0.

int SWP_AutoSetMeasure()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot profile structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the error accordingly based on the return value.

	SWPApplication_TypeDef Application; // Select measurement function.
	SWP_Profile_TypeDef ProfileIn;      // SWP input configuration, including start/stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef ProfileOut;		// SWP output configuration.
	SWP_Profile_TypeDef AutoProfileOut; // Output configuration from automatic parameter setting.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under current configuration, including trace points, hop points, etc.

	uint8_t ifDoConfig = 0;   // Return value indicating whether the configuration was successfully sent: 0 = no error; non-zero = error.
	Application = SWPOBWMeas; // Occupied bandwidth measurement. Refer to SWPApplication_TypeDef for other measurements.

	ProfileIn.StartFreq_Hz = 9e3;
    ProfileIn.StopFreq_Hz = 6.35e9;
	ProfileIn.RBW_Hz = 300e3;       // Set RBW.

    Status = SWP_ProfileDeInit(&Device, &ProfileIn);

	// Use SWP_AutoSet to obtain AutoProfileOut, which will then be used as the configuration for SWP_Configuration to achieve automatic configuration.
	Status = SWP_AutoSet(&Device, Application, &ProfileIn, &AutoProfileOut, &TraceInfo, ifDoConfig); 
	Status = SWP_Configuration(&Device, &AutoProfileOut, &ProfileOut, &TraceInfo); // Send SWP configuration by calling this function.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &ProfileIn, &ProfileOut, &TraceInfo); // If Status is not 0, handle the error accordingly based on the return value.
	
	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement info, including: max power index, max power, device temperature, GPS, absolute timestamp, etc.

	// Continuously acquire spectrum data
	while (1)
	{
		for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops represents the number of frames under the current configuration, so calling SWP_GetPartialSweep TraceInfo.TotalHops times will result in a full trace.
		{
			Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Get spectrum data.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				/*

				For example: display spectrum or perform other processing on the spectrum.

				*/
			}

			else // If Status is not 0, handle the error accordingly based on the return value.
			{
				SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &ProfileIn, &ProfileOut, &TraceInfo);
			}
		}
	}

	Device_Close(&Device); // Close the device.

	return 0;

}
