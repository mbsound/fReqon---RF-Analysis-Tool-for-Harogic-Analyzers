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

#define IS_USB 1 // By default, a USB device is used. Set IS_USB to 0 for an Ethernet device.

int SWP_GetSpectrumAndIQS()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specifies the device number.
	void* I_Data = NULL;
	void* Q_Data = NULL;

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use dual power supply with USB data port and independent power port.

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
	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, perform error handling according to the return value.
	

	SWP_EZProfile_TypeDef SWP_ProfileIn;  // SWP input configuration including start frequency, stop frequency, RBW, reference level, etc.
	SWP_EZProfile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;      // Trace info under current config, including trace points, hop count, etc.

	SWP_EZProfileDeInit(&Device, &SWP_ProfileIn); // Call this function to initialize SWP mode related parameters.

	SWP_ProfileIn.StartFreq_Hz = 1e9;           // Set start frequency.
	SWP_ProfileIn.StopFreq_Hz = 2e9;            // Set stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;               // Set RBW.
	SWP_ProfileIn.TraceType = ClearWriteWithIQ; // Set trace type to acquire both IQ and spectrum data.


	Status = SWP_EZConfiguration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Call this function to apply SWP mode configuration.

	SWPTrace_TypeDef PartialTrace;

	// When the sampling rate is below 31.25M, the data type changes from int16 to int32 to ensure dynamic range.
	if (TraceInfo.DataFormat == Complex16bit)
	{
		PartialTrace.AlternIQStream = (int16_t*)malloc(TraceInfo.SamplePoints * 2 * sizeof(int16_t));
		I_Data = (int16_t*)malloc(TraceInfo.SamplePoints * sizeof(int16_t)); // Allocate memory for I-channel data.
		Q_Data = (int16_t*)malloc(TraceInfo.SamplePoints * sizeof(int16_t)); // Allocate memory for Q-channel data.
	}
	else
	{
		PartialTrace.AlternIQStream = (int32_t*)malloc(TraceInfo.SamplePoints * 2 * sizeof(int32_t));
		I_Data = (int32_t*)malloc(TraceInfo.SamplePoints * sizeof(int32_t)); // Allocate memory for I-channel data.
		Q_Data = (int32_t*)malloc(TraceInfo.SamplePoints * sizeof(int32_t)); // Allocate memory for Q-channel data.
	}

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Dynamically create array to store the full frequency trace.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Dynamically create array to store the full amplitude trace.

	PartialTrace.Freq_Hz = new double[TraceInfo.PartialsweepTracePoints];      // Allocate memory to store frequency data from GetPartial.
	PartialTrace.PowerSpec_dBm = new float[TraceInfo.PartialsweepTracePoints]; // Allocate memory to store power data from GetPartial.

	while (1)
	{
		for (int j = 0; j < TraceInfo.TotalHops; j++) // TraceInfo.TotalHops indicates the number of frames under current config. Call SWP_GetPartialSweep multiple times to get the full trace.
		{
			Status = SWP_GetPartialSweep_PM1(&Device, &PartialTrace);

			
			if (Status == APIRETVAL_NoError)
			{	
				memcpy(Frequency.data() + j * TraceInfo.PartialsweepTracePoints, PartialTrace.Freq_Hz, TraceInfo.PartialsweepTracePoints * sizeof(double));          // Stitch frequency data from GetPartial into a full trace.
				memcpy(PowerSpec_dBm.data() + j * TraceInfo.PartialsweepTracePoints, PartialTrace.PowerSpec_dBm, TraceInfo.PartialsweepTracePoints * sizeof(float)); // Stitch power data from GetPartial into a full trace.

				for (int i = 0; i < TraceInfo.SamplePoints; i++)
				{
					if (TraceInfo.DataFormat == Complex16bit)
					{
						((int16_t*)I_Data)[i] = ((int16_t*)PartialTrace.AlternIQStream)[i * 2];     // Extract I-channel data from interleaved stream.
						((int16_t*)Q_Data)[i] = ((int16_t*)PartialTrace.AlternIQStream)[i * 2 + 1]; // Extract Q-channel data from interleaved stream.
					}
					else
					{
						((int32_t*)I_Data)[i] = ((int32_t*)PartialTrace.AlternIQStream)[i * 2];
						((int32_t*)Q_Data)[i] = ((int32_t*)PartialTrace.AlternIQStream)[i * 2 + 1];
					}
				}
			}
		}
	}

	Device_Close(&Device); // Close the device.

	return 0;
}
