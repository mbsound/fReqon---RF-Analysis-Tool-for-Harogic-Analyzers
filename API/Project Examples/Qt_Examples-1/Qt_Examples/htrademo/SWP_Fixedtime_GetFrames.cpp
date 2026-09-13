#include <stdio.h>
#include <string.h>
#include <vector>
#include <chrono>
#include<iostream>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // Default uses USB device. Set IS_USB to 0 if using Ethernet device.

int SWP_Fixedtime_GetFrames()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration struct, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot info struct, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and independent power port.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo);              // Open device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle error according to the return value.


	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input config, including start/stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output config.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace info of current config, including number of points, hops, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Configure start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Configure stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;       // Configure RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP config.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle error accordingly.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Measurement auxiliary info: max power index, max power, device temperature, GPS, timestamp, etc.

	int t = 0;              // Loop counter.
	int frame = 0;          // Frame count per loop.
	int frame_mul = 0;      // Total frame count.
	double frame_avg = 0.0; // Average frame count.
	double time = 10.0;     // Time limit per loop (seconds).

	// Initialize device and variables etc.
	// Device Device.
	// Other variable and function initializations.

	auto start = std::chrono::high_resolution_clock::now();  // Start time of outer loop.
	
	 // Loop 5 times.
	while (t < 5) { 
	
		frame = 0; // Reset frame count.

		// Continuously call SWP_GetPartialSweep before reaching time limit.
		auto loop_start = std::chrono::high_resolution_clock::now(); // Start time of inner loop.
		auto stop = loop_start;
		auto timeout = std::chrono::duration_cast<std::chrono::duration<double, std::ratio<1, 1>>>(stop - start);

		while (timeout.count() < time) 
		{
			Status = SWP_GetPartialSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &HopIndex, &FrameIndex, &MeasAuxInfo); // Get spectrum data.

			SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle error accordingly.
			
			stop = std::chrono::high_resolution_clock::now();
			timeout = std::chrono::duration_cast<std::chrono::duration<double, std::ratio<1, 1>>>(stop - loop_start);

			frame++; // Accumulate spectrum frames.

		}

		// Output results of current loop.
		cout << "In the " << t + 1 << "th loop, the number of spectrum frames that can be obtained within " << timeout.count() << " seconds is: " << frame << endl;
		frame_mul += frame;  // Accumulate total spectrum frames.
		t++;  // Increment loop count.

		// Restart timer.
		start = std::chrono::high_resolution_clock::now();
	}

	// Calculate and output average frame count.
	frame_avg = static_cast<double>(frame_mul) / t;
	cout << "The average number of spectrum frames that can be obtained within 10 seconds (5 times): " << frame_avg << endl;
	Device_Close(&Device); // Close device.

	return 0;
}
