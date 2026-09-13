#include <stdio.h>
#include <stdlib.h>
#include <cstdio>
#include <string>
#include <sstream>
#include <vector>
#include "htra_api.h"
#include "math.h"
#include <ctime>
#include <iomanip> 
#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <map>
#include "example.h"
#define EXAMPLE_MACRO_NAME

using namespace std;

int IQS_MultiDevSync_fixed()
{
	int Status0 = 0; // Return value of functions for Device 0
	int Status1 = 0; // Return value of functions for Device 1

	int DevNum0 = 0; // Specify Device 0
	int DevNum1 = 1; // Specify Device 1

	void* Device0 = NULL; // Memory address of Device 0
	void* Device1 = NULL; // Memory address of Device 1

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply mode, etc.

	BootInfo_TypeDef BootInfo0; // Boot information structure for Device 0, including device info, USB speed, etc.
	BootInfo_TypeDef BootInfo1; // Boot information structure for Device 1, including device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and independent power port for power supply
	BootProfile.PhysicalInterface = USB;				 // Use USB interface for data transmission

	Status0 = Device_Open(&Device0, DevNum0, &BootProfile, &BootInfo0); // Open Device 0
	Status1 = Device_Open(&Device1, DevNum1, &BootProfile, &BootInfo1); // Open Device 1

	IQS_Profile_TypeDef IQS_ProfileIn; // IQS input configuration, including start freq, stop freq, RBW, reference level, etc.

	IQS_Profile_TypeDef IQS_ProfileOut0; // IQS output configuration for Device 0
	IQS_Profile_TypeDef IQS_ProfileOut1; // IQS output configuration for Device 1

	IQS_StreamInfo_TypeDef StreamInfo0;	// IQ stream information of Device 0, including bandwidth, IQ sampling rate, etc.
	IQS_StreamInfo_TypeDef StreamInfo1;	// IQ stream information of Device 1, including bandwidth, IQ sampling rate, etc.						

	IQS_ProfileDeInit(&Device0, &IQS_ProfileIn); // Initialize parameters related to IQS mode configuration for Device 0
	IQS_ProfileDeInit(&Device1, &IQS_ProfileIn); // Initialize parameters related to IQS mode configuration for Device 1

	IQS_ProfileIn.CenterFreq_Hz = 1e9;               // Set center frequency
	IQS_ProfileIn.RefLevel_dBm = 0;                  // Set reference level
	IQS_ProfileIn.DecimateFactor = 2;		         // Set decimation factor
	IQS_ProfileIn.DataFormat = Complex16bit;         // Set IQ data format
	IQS_ProfileIn.TriggerMode = FixedPoints;         // Set trigger mode
	IQS_ProfileIn.TriggerSource = MultiDevSyncByExt; // Set trigger source to external, devices will trigger synchronously upon external signal
	IQS_ProfileIn.TriggerLength = 16242;			 // Set number of points collected per trigger; only effective when TriggerMode is FixedPoints

	// Use same configuration across devices (can also be different, but TriggerSource must be MultiDevSync)
	Status0 = IQS_Configuration(&Device0, &IQS_ProfileIn, &IQS_ProfileOut0, &StreamInfo0);
	Status1 = IQS_Configuration(&Device1, &IQS_ProfileIn, &IQS_ProfileOut1, &StreamInfo1);

	/* Query device status in the system */
	DeviceState_TypeDef DeviceState0;
	DeviceState_TypeDef DeviceState1;

	IQStream_TypeDef IQStream0;                              // Device 0: Holds IQ data packet, configuration, etc.
	double* I_Data0 = new double[StreamInfo0.StreamSamples]; // Device 0: Create I channel data array
	double* Q_Data0 = new double[StreamInfo0.StreamSamples]; // Device 0: Create Q channel data array
	double* Power_Data0 = new double[StreamInfo0.StreamSamples];
	vector<double> Power_Data0_dBm(StreamInfo0.StreamSamples);

	IQStream_TypeDef IQStream1;                              // Device 1: Holds IQ data packet, configuration, etc.
	double* I_Data1 = new double[StreamInfo1.StreamSamples]; // Device 1: Create I channel data array
	double* Q_Data1 = new double[StreamInfo1.StreamSamples]; // Device 1: Create Q channel data array
	double* Power_Data1 = new double[StreamInfo1.StreamSamples];
	vector<double> Power_Data1_dBm(StreamInfo1.StreamSamples);

	Status0 = IQS_MultiDevice_WaitExternalSync(&Device0, &IQS_ProfileOut0); // Use one of the devices to wait for the external trigger; this function completes when the trigger is captured

	// After system captures trigger signal, enable synchronized operation across devices
	Status0 = IQS_MultiDevice_Run(&Device0);
	Status1 = IQS_MultiDevice_Run(&Device1);

	void* AlternIQStream0 = nullptr;       // Stores IQ data acquired from Device 0
	IQS_TriggerInfo_TypeDef  TriggerInfo0; // Trigger information of Device 0
	MeasAuxInfo_TypeDef MeasAuxInfo0;      // Auxiliary measurement info of Device 0, includes max power index, max power, temperature, GPS, timestamp, etc.

	void* AlternIQStream1 = nullptr;       // Stores IQ data acquired from Device 1
	IQS_TriggerInfo_TypeDef  TriggerInfo1; // Trigger information of Device 1
	MeasAuxInfo_TypeDef MeasAuxInfo1;      // Auxiliary measurement info of Device 1, includes max power index, max power, temperature, GPS, timestamp, etc.

	while (1)
	{

		for (int j = 0; j < StreamInfo0.PacketCount; j++)
		{
			/* Get data from Dev0 */
			Status0 = IQS_GetIQStream_PM1(&Device0, &IQStream0); // Get IQ packet, trigger info, max I channel value and index from Device 0

			if (Status0 == 0)
			{
				/* Note: When using IQ mode, it is recommended to call IQS_GetIQStream in a dedicated thread instead of mixing with processing logic. */
				int16_t* IQ = (int16_t*)IQStream0.AlternIQStream; // Extract IQ data

				uint32_t Points = StreamInfo0.PacketSamples;

				if (j == StreamInfo0.PacketCount - 1 && StreamInfo0.StreamSamples % StreamInfo0.PacketSamples != 0) // Last packet may be incomplete (16242 points), so loop only through actual number of points
				{
					Points = StreamInfo0.StreamSamples % StreamInfo0.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data0[i + StreamInfo0.PacketSamples * j] = IQ[i * 2] * IQStream0.IQS_ScaleToV;     // Convert Q channel to real voltage
					Q_Data0[i + StreamInfo0.PacketSamples * j] = IQ[i * 2 + 1] * IQStream0.IQS_ScaleToV; // Convert I channel to real voltage
					Power_Data0[i + StreamInfo0.PacketSamples * j] = sqrt(pow(I_Data0[i + StreamInfo0.PacketSamples * j], 2) + pow(Q_Data0[i + StreamInfo0.PacketSamples * j], 2)); // Calculate amplitude
					Power_Data0_dBm[i + StreamInfo0.PacketSamples * j] = 10 * log10(20 * (Power_Data0[i + StreamInfo0.PacketSamples * j] * Power_Data0[i + StreamInfo0.PacketSamples * j])); // Convert to dBm
				}
			}
		}

		for (int j = 0; j < StreamInfo0.PacketCount; j++)
		{

			/* Get data from Dev1 */
			Status1 = IQS_GetIQStream_PM1(&Device1, &IQStream1); // Get IQ packet, trigger info, max I channel value and index from Device 1

			if (Status1 == 0)
			{
				/* Note: When using IQ mode, it is recommended to call IQS_GetIQStream in a dedicated thread instead of mixing with processing logic. */
				int16_t* IQ = (int16_t*)IQStream1.AlternIQStream; // Extract IQ data

				uint32_t Points = StreamInfo1.PacketSamples;

				if (j == StreamInfo1.PacketCount - 1 && StreamInfo1.StreamSamples % StreamInfo1.PacketSamples != 0) // Last packet may be incomplete (16242 points), so loop only through actual number of points
				{
					Points = StreamInfo1.StreamSamples % StreamInfo1.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data1[i + StreamInfo1.PacketSamples * j] = IQ[i * 2] * IQStream1.IQS_ScaleToV;
					Q_Data1[i + StreamInfo1.PacketSamples * j] = IQ[i * 2 + 1] * IQStream1.IQS_ScaleToV;
					Power_Data1[i + StreamInfo1.PacketSamples * j] = sqrt(pow(I_Data1[i + StreamInfo1.PacketSamples * j], 2) + pow(Q_Data1[i + StreamInfo1.PacketSamples * j], 2));
					Power_Data1_dBm[i + StreamInfo1.PacketSamples * j] = 10 * log10(20 * (Power_Data1[i + StreamInfo1.PacketSamples * j] * Power_Data1[i + StreamInfo1.PacketSamples * j]));
				}
			}
		}

		vector<double> PacketSamplesDouble(StreamInfo0.PacketSamples);
		for (int i = 0; i < StreamInfo0.PacketSamples; i++)
		{
			PacketSamplesDouble[i] = i;
		}
	}

	// Release dynamic arrays
	delete[] I_Data0;
	delete[] Q_Data0;
	delete[] I_Data1;
	delete[] Q_Data1;
	delete[] Power_Data0;
	delete[] Power_Data1;
	Device_Close(&Device0); // Close Device 0
	Device_Close(&Device1); // Close Device 1

	return 0;
}