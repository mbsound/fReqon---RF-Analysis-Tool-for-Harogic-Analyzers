#include <stdio.h>
#include <string.h>
#include <vector>
#include <fstream>
#include<chrono>
#include<vector>
#include<iostream>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // Default is USB device. If using Ethernet device, set IS_USB to 0.

typedef struct
{
	uint32_t TraceCount;
	uint32_t TracePoints;
	uint32_t CurrentTraceCount;
	vector<float> PowerSpec_dBmAve;

}Trace_Profile_TypeDef;

// Function declarations
int TraceAvg_Open(void** Trace, uint32_t TraceCount, uint32_t TracePoints);					// Configure trace average parameters, including number of averages and trace points.
void TraceAvg_Execute(void** Trace, const float PowerSpec_dBm[], float PowerSpecAve_dBm[]); // Perform trace averaging.
void TraceAvg_Reset(void** Trace);                                                          // Reset trace average.
void TraceAvg_Close(void** Trace);															// Close trace average.

int SWP_TraceAverage()
{
	int Status = 0;       // Return value of the function.
	void* Device = NULL;  // Memory address of the current device.
	void* Trace = NULL;   // Memory address of the current trace.
	int DevNum = 0;       // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and independent power port for dual power supply.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the corresponding error based on the return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under current configuration, including number of trace points, hop points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize parameters related to SWP mode.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Set start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Set stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;       // Set RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Send SWP configuration.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // If Status is not 0, handle the corresponding error based on the return value.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement data, including max power index, max power value, device temperature, GPS location, absolute timestamp, etc.
	
	uint32_t TraceCount = 100;                             // Set number of trace averages.
	uint32_t TracePoints = TraceInfo.FullsweepTracePoints; // Set number of trace points.

	TraceAvg_Open(&Trace, TraceCount, TracePoints);                 // Open trace average.
	vector<float> PowerSpecAve_dBm(TraceInfo.FullsweepTracePoints); // Create power average array.

	// Loop to get data.
	while (1)
	{
		Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo);                                                   // Get trace data.

		if (Status == APIRETVAL_NoError)
		{
			// UserCode here
			/*

			For example: display spectrum or perform other processing.

			*/
		}

		else // If Status is not 0, handle the corresponding error based on the return value.
		{
			SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
		}

		TraceAvg_Execute(&Trace, PowerSpec_dBm.data(), PowerSpecAve_dBm.data());                                                                    // Perform trace average.
	}

	Device_Close(&Device); // Close device.

	return 0;
}

int  TraceAvg_Open(void** Trace, uint32_t TraceCount, uint32_t TracePoints)
{
	*Trace = new Trace_Profile_TypeDef;
	Trace_Profile_TypeDef* pTrace = (Trace_Profile_TypeDef*)(*Trace);
	pTrace->TraceCount = TraceCount;
	pTrace->TracePoints = TracePoints;
	pTrace->PowerSpec_dBmAve.resize(pTrace->TracePoints);
	pTrace->CurrentTraceCount = 0;
	return 0;
}

void TraceAvg_Execute(void** Trace, const float PowerSpec_dBm[], float PowerSpecAve_dBm[])
{
	Trace_Profile_TypeDef* pTrace = (Trace_Profile_TypeDef*)(*Trace);

	if (pTrace->CurrentTraceCount < pTrace->TraceCount) {
		pTrace->CurrentTraceCount++;
	}

	if (pTrace->CurrentTraceCount > 1) {
		for (uint32_t i = 0; i < pTrace->TracePoints; i++)
		{
			PowerSpecAve_dBm[i] = ((pTrace->CurrentTraceCount - 1.0) / pTrace->CurrentTraceCount) * pTrace->PowerSpec_dBmAve[i] + (1.0 / pTrace->CurrentTraceCount) * PowerSpec_dBm[i];
			pTrace->PowerSpec_dBmAve[i] = PowerSpecAve_dBm[i];
		}
	}
	else {
		memcpy(PowerSpecAve_dBm, PowerSpec_dBm, sizeof(float) * pTrace->TracePoints);
		memcpy(pTrace->PowerSpec_dBmAve.data(), PowerSpec_dBm, sizeof(float) * pTrace->TracePoints);
	}
}

void TraceAvg_Reset(void** Trace)
{
	Trace_Profile_TypeDef* pTrace = (Trace_Profile_TypeDef*)(*Trace);
	pTrace->CurrentTraceCount = 0; // Reset current trace count.
}

void TraceAvg_Close(void** Trace)
{
	delete (Trace_Profile_TypeDef*)(*Trace);
}
