#include <stdio.h>
#include <iostream>
#include <sstream>
#include <fstream>
#include <string.h>
#include <vector>
#include <chrono>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default is USB-type device. Set IS_USB to 0 if using Ethernet-type device.

int IQS_GetIQToTxt()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Pointer to current device memory address.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use dual power from USB data port and independent power port.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle errors accordingly based on return value.

	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, including center frequency, RBW, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ stream info under current configuration, including bandwidth, I/Q sample rate, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize related parameters for IQS mode configuration.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Set center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Set reference level.
	IQS_ProfileIn.DecimateFactor = 2;		 // Set decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Set IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Set trigger mode.
	IQS_ProfileIn.TriggerSource = Bus;       // Set trigger source to internal bus trigger.
	IQS_ProfileIn.TriggerLength = 30000000;     // Set number of samples per trigger. Only effective when TriggerMode is FixedPoints.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Configure IQS mode.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // If Status is not 0, handle errors accordingly based on return value.

	IQStream_TypeDef IQStream;                        // Structure to store IQ packet data, including IQ samples and config info.
	vector<int16_t> I_Data(StreamInfo.StreamSamples); // Create I-channel data array.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); // Create Q-channel data array.

	int num = 0; // Control number of IQ data acquisition loops, currently set to 1.

	// Acquire data and save to IQdata.txt file
	ofstream File("./IQdata.txt", ios::app);

	string buffer;
	buffer.reserve(StreamInfo.StreamSamples * 12);

	while (num<1)
	{
		Status = IQS_BusTriggerStart(&Device); // Trigger the device. If using external trigger, this function is not needed.

		for (int j = 0; j < StreamInfo.PacketCount; j++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ packet, trigger info, max value of I-channel, and index of max value.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				// Note: When using IQ mode, it is recommended to create a dedicated thread for calling IQS_GetIQStream to retrieve data. Do not combine with data processing in the same thread.

				int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;

				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) // The last packet may contain less than a full packet (16242 points); in this case, only loop through remaining points.
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];

					buffer.append(to_string(IQ[i * 2]));
					buffer.push_back('\t');
					buffer.append(to_string(IQ[i * 2 + 1]));
					buffer.push_back('\n');
				}
			}

			else // If Status is not 0, handle errors accordingly based on return value.
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}
		}

		num++;
	}

	File.write(buffer.data(), buffer.size());
	File.close();

	Status = IQS_BusTriggerStop(&Device); // Stop triggering the device. If using external trigger, this function is not needed.

	Device_Close(&Device); // Close the device.	
	
	return 0;

}