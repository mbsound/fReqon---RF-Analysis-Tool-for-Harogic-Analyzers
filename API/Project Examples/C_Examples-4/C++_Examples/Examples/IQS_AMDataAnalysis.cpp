#include <stdio.h>
#include <string.h>
#include <vector>
#include <iostream>
#include "htra_api.h" 
#include "example.h"
using namespace std;
#define IS_USB 1 // By default, a USB-type device is used. If using an Ethernet-type device, define IS_USB as 0.

int IQS_AMDataAnalysis()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specifies the device number.

	BootProfile_TypeDef BootProfile; // Boot profile structure, includes physical interface, power supply type, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, includes device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and external power port for power supply.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo);              // Open the device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, perform corresponding error handling based on the return value.

	IQStream_TypeDef IQStream;							   // This structure is used to store parameters related to IQ data, including IQ data, ScaleToV, I_MaxValue, and others.
	IQS_Profile_TypeDef IQS_ProfileIn;                     //Configure parameters for IQS mode including start/stop frequency, decimate factor, R.L. etc.
	IQS_Profile_TypeDef IQS_ProfileOut;                    //Feedback information for IQS mode including start/stop frequency, decimate factor, R.L. etc.
	IQS_StreamInfo_TypeDef StreamInfo;                     //feedback information for the configuration including IQ data points, time domain data etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize related parameters for IQS mode configuration.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;				 // Set the center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;					 // Set the reference level.
	IQS_ProfileIn.DataFormat = Complex16bit;		 // Set the IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints;		 // Set the trigger mode. 
	IQS_ProfileIn.TriggerSource = Bus;				 // Set the trigger source as internal bus trigger. 
	IQS_ProfileIn.DecimateFactor = 256;				 // Set the decimation factor.
	IQS_ProfileIn.BusTimeout_ms = 5000;				 // Set the bus timeout
	IQS_ProfileIn.TriggerLength = 16242 * 1;

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Configure IQS mode settings by calling this function.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Perform corresponding error handling based on the Status return value when it is not 0.

	//Demod
	AMDemodParam_TypeDef AMDemodParam;
	void* ADM = nullptr;
	ADM_Open(&ADM);

	vector<int16_t> IQ(StreamInfo.StreamSamples * 2);
	vector<float> DemodWaveform(IQS_ProfileIn.TriggerLength);


	// Continuously acquire and play FM broadcast
	while (1)
	{
		uint32_t Points = StreamInfo.PacketSamples;
		Status = IQS_BusTriggerStart(&Device);

		// Concatenate multiple IQ data packets
		for (uint32_t i = 0; i < StreamInfo.PacketCount; i++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream);
			if (Status) {
				std::cout << "IQS_GetIQStream_PM1: " << Status << std::endl;
			}
			else {
				if (i == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0)
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}
				memcpy(IQ.data() + i * StreamInfo.PacketSamples * 2, IQStream.AlternIQStream, Points * 2 * sizeof(IQ[0]));
			}
		}
		IQStream.AlternIQStream = IQ.data();
		ADM_AMDemod_PM1(&ADM, IQStream.AlternIQStream, IQStream.IQS_Profile.DataFormat, IQStream.IQS_Profile.TriggerLength, IQStream.IQS_StreamInfo.IQSampleRate, IQStream.IQS_ScaleToV, &AMDemodParam);

	}
	ADM_Close(&ADM);          // Release all resources allocated for analog demodulation.
	Status = Device_Close(&Device); // Release all resources allocated by htra_api.

	return 0;

}
