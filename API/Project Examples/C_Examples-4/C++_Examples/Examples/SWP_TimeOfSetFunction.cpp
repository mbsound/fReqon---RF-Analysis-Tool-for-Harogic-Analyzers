#include <stdio.h>
#include <string.h>
#include <chrono>
#include <thread>
#include <iostream>
#include <vector>
#include <sstream>
#include <string>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // By default, a USB device is used. If an Ethernet device is used, set IS_USB to 0.

int SWP_TimeOfSetFunction()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply mode, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and independent power port dual power supply.

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

	std::chrono::duration<double, std::milli> timeofspan; // Time consumed.
	double Speed;									       // Sweep speed.
	double ThroughPut;                                    // Throughput.

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo);              // Open the device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the error based on the return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under current configuration, including number of trace points, hop points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode related parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;                         // Start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.37e9;                       // Stop frequency.
	SWP_ProfileIn.RBWMode = RBW_Manual;                       // Manual RBW.
	SWP_ProfileIn.RBW_Hz = 300e3;                             // Set RBW.
	//SWP_ProfileIn.TraceDetectMode = TraceDetectMode_Manual; // Manual trace detection.
	//SWP_ProfileIn.TraceDetector = TraceDetector_RMS;        // RMS detector.
	//SWP_ProfileIn.SweepTimeMode = SWTMode_minSWT;           // Minimum sweep time scan.

	auto start1 = std::chrono::high_resolution_clock::now();                                                                        // Get current time.
	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);                                               // Call this function to send SWP mode related configuration.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle the error based on the return value.

	auto stop1 = std::chrono::high_resolution_clock::now();
	auto timeout1 = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop1 - start1);
	cout << "SWP_Configuration Completed" << endl;
	cout << "SWP_Configuration Cost:" << timeout1.count() << "ms" << endl;

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement data, including: index of max power, max power value, device temperature, longitude/latitude, absolute timestamp, etc.

	while (1)
	{
		auto start2 = std::chrono::high_resolution_clock::now();
		for (int i = 0; i < TraceInfo.TotalHops; i++)                // TraceInfo.TotalHops represents the number of frames under the current configuration. Loop TraceInfo.TotalHops times calling SWP_GetPartialSweep to get the full trace.
		{
			Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Get spectrum data.
			
			SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle the error based on the return value. 
		}
		auto stop2 = std::chrono::high_resolution_clock::now();                                                    // Get current time.
		auto timeout2 = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop2 - start2); // Calculate time difference.	
		cout << "SWP_GetPartialSweep Completed" << endl;																	
        cout << "SWP_GetPartialSweep Cost:" << timeout2.count() << "ms" << endl;
		timeofspan = timeout2;
		Speed = (SWP_ProfileIn.Span_Hz / timeofspan.count()) * 1e3;                                                // Calculate sweep speed.
		cout << "Current Sweep Time:" << Speed << "Hz/s" << std::endl;
		ThroughPut =(((TraceInfo.FullsweepTracePoints * 12) / timeofspan.count())*1e3) / 1024;                     // Calculate throughput. ((TracePoints * 12) / time) / 1024
		cout << "Current ThroughPut:" << ThroughPut << "KB/s" << std::endl;
	}

	Device_Close(&Device); // Close device.

	return 0;
}
