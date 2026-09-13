#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include <chrono>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default to using USB device. Set IS_USB to 0 if using Ethernet device.

int IQS_ExternalTrigger()
{
	int Status = 0;      // Function return status
	void* Device = NULL; // Device memory address
	int DevNum = 0;      // Device number

	BootProfile_TypeDef BootProfile; // Boot configuration struct, includes physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot info struct, includes device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and separate power port.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open device

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Handle error if Status is not 0

	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration: center freq, RBW, ref level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ data stream info: bandwidth, sample rate, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize IQS mode parameters

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Set center frequency
	IQS_ProfileIn.RefLevel_dBm = 0;          // Set reference level
	IQS_ProfileIn.DecimateFactor = 2;		 // Set decimation factor
	IQS_ProfileIn.DataFormat = Complex16bit; // Set IQ data format
	IQS_ProfileIn.TriggerMode = FixedPoints; // Set trigger mode
	IQS_ProfileIn.TriggerSource = External;  // Set trigger source to external
	IQS_ProfileIn.TriggerLength = 16384;     // Set number of points per trigger (only valid for FixedPoints mode)

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS configuration

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle configuration errors if Status != 0

	IQStream_TypeDef IQStream;                        // Stores IQ packet data, including IQ samples and config
	vector<int16_t> I_Data(StreamInfo.StreamSamples); // Allocate I channel buffer
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); // Allocate Q channel buffer

	if (IQS_ProfileIn.TriggerMode == Adaptive)
	{
		I_Data.resize(StreamInfo.PacketSamples); // Resize I_Data for Adaptive mode
		Q_Data.resize(StreamInfo.PacketSamples); // Resize Q_Data for Adaptive mode
	}

	// Continuously retrieve IQ data
	while (1)
	{
		for (int j = 0; j < StreamInfo.PacketCount; j++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ packet, trigger info, I max value and its index

			if (Status == APIRETVAL_NoError)
			{
				// User code here
				// Note: It is recommended to run IQS_GetIQStream in a dedicated thread,and NOT in the same thread as the data processing.

				int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;

				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0 && IQS_ProfileOut.TriggerMode == FixedPoints) // The last packet may be incomplete (e.g., not a full 16242 samples),so only loop through the remaining samples
				{	
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
				}
			}

			else // If Status != 0, handle IQ stream errors
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}
		}
	}

	Device_Close(&Device); // Close device

	return 0;

}
