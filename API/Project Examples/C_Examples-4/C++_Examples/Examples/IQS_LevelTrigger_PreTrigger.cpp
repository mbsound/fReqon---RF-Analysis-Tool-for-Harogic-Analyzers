#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include <chrono>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default is using USB device. If using Ethernet device, define IS_USB as 0.

int IQS_LevelTrigger_PreTrigger()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use dual power supply from USB data port and independent power port.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the corresponding error according to the Status code

	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ data info under current configuration, including bandwidth, IQ sampling rate, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize parameters related to IQS mode.

	IQS_ProfileIn.CenterFreq_Hz = 2.44e9;    // Configure center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Configure reference level.
	IQS_ProfileIn.DecimateFactor = 2;		 // Configure decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Configure IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Configure trigger mode.
	IQS_ProfileIn.TriggerSource = Level;     // Configure trigger source as level trigger
	IQS_ProfileIn.TriggerLevel_dBm = -70;    // Configure trigger threshold. When input exceeds this level, trigger starts automatically.
	IQS_ProfileIn.PreTriggerTime = 16e-6;    // Configure pre-trigger time (upper limit is 8000*8ns*decimation factor)
	
	IQS_ProfileIn.TriggerLength = 16242;     // Configure number of points per trigger acquisition. Only effective when TriggerMode is set to FixedPoints.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Send IQS mode configuration.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // If Status is not 0, handle the corresponding error according to the Status code

	IQStream_TypeDef IQStream;                        // Store IQ data packet, including IQ data, configuration info, etc.
	vector<int16_t> I_Data(StreamInfo.StreamSamples); // Create I channel data array.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); // Create Q channel data array.

	// Loop to get IQ data
	while (1)
	{
		for (int j = 0; j < StreamInfo.PacketCount; j++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data packet, trigger info, I channel max value and index of max value.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				// Note: When using IQ mode in practice, it is recommended to create a separate thread to call IQS_GetIQStream to acquire IQ data. Do not place data acquisition and processing in the same thread.

				/*int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;

				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) // The last packet may not be a full packet (16242 points); in this case, only loop over the remaining points
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
				}*/
			}

			else // If Status is not 0, handle the corresponding error according to the Status code
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}
		}
	}

	Device_Close(&Device); // Close device	
	
	return 0;

}