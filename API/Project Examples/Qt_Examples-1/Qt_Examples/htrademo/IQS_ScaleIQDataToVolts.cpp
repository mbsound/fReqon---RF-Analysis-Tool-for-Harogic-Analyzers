#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default is USB device, change IS_USB to 0 for Ethernet device.

/* Example of converting IQ data obtained in FixedPoints mode to voltage units in professional configuration. */
int IQS_ScaleIQDataToVolts()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Current device memory address.
	int DevNum = 0;      // Specify device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and separate power port for dual power supply.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Error handling if Status is not 0.

	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ data information for current configuration, including bandwidth, single channel sample rate, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize configuration parameters for IQS mode.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Set center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Set reference level.
	IQS_ProfileIn.DecimateFactor = 2;	     // Set decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Set IQ data format.
	IQS_ProfileIn.TriggerSource = Bus;       // Set trigger source to internal bus trigger.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Set trigger mode to FixedPoints.
	IQS_ProfileIn.TriggerLength = 16384;     // Set number of points to collect for each trigger.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Configure IQS mode with relevant settings.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Error handling if Status is not 0.

	IQStream_TypeDef IQStream;                      // Structure to hold IQ data packet, including IQ data, configuration info, etc.
	vector<float> I_Data(StreamInfo.StreamSamples); // Create array for I-channel data.
	vector<float> Q_Data(StreamInfo.StreamSamples); // Create array for Q-channel data.

	while (1)
	{
		Status = IQS_BusTriggerStart(&Device); // Trigger device using IQS_BusTriggerStart.

		for (int j = 0; j < StreamInfo.PacketCount; j++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data packet, trigger info, I-channel data max value, and max value index.

			if (Status == APIRETVAL_NoError)
			{
				int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;

				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) // The last packet may not be full (16242 points); only loop for the number of incomplete points.
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2] * IQStream.IQS_ScaleToV;
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1] * IQStream.IQS_ScaleToV;
				}
			}

			else // Error handling if Status is not 0.
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}
		}
	}

	Status = IQS_BusTriggerStop(&Device); // Stop device trigger using IQS_BusTriggerStop.

	Device_Close(&Device); // Close the device.
	
	return 0;
}