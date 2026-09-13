#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include <chrono>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default is to use USB device. If using Ethernet, define IS_USB as 0.

int IQS_LevelTrigger_TriggerDelay()
{
	int Status = 0;      // Function return status.
	void* Device = NULL; // Pointer to the current device memory address.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, includes physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, includes device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and separate power port.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open device

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle error based on return value

	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, includes center frequency, RBW, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ data stream info under current config, includes bandwidth, sampling rate, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize parameters for configuring IQS mode.

	IQS_ProfileIn.CenterFreq_Hz = 2.44e9;    // Set center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Set reference level.
	IQS_ProfileIn.DecimateFactor = 2;		 // Set decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Set IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Set trigger mode.
	IQS_ProfileIn.TriggerSource = Level;     // Set trigger source to level trigger
	IQS_ProfileIn.TriggerLevel_dBm = -70;    // Set level trigger threshold. Trigger will occur when input exceeds this threshold.
	IQS_ProfileIn.TriggerDelay = 0.5;          // Set trigger delay time (max delay time is (2^32-1)*8ns)
	IQS_ProfileIn.TriggerLength = 16242;     // Set number of points per trigger acquisition. Only valid when TriggerMode is FixedPoints.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS configuration.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // If Status is not 0, handle error based on return value

	IQStream_TypeDef IQStream;                        // Store IQ data packet, including IQ data, config info, etc.
	vector<int16_t> I_Data(StreamInfo.StreamSamples); // Create array for I-channel data.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); // Create array for Q-channel data.

	// Continuously acquire IQ data
	while (1)
	{
		for (int j = 0; j < StreamInfo.PacketCount; j++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data packet, trigger info, max I value and its index.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				// Note: In actual IQ mode usage, it is recommended to use a dedicated thread to call IQS_GetIQStream to acquire IQ data. Do not place IQ data processing in the same thread.

				/*int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;

				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) // Last packet may not be full (16242 points); so only loop through the remaining points
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
				}*/
			}

			else // If Status is not 0, handle error based on return value
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}
		}
	}

	Device_Close(&Device); // Close device	

	return 0;

}
