#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include <chrono>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default is using a USB device. If using a network device, set IS_USB to 0.

int IQS_TimerTrigger()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specify device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Dual power supply using USB data port and separate power port.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open the device

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Handle errors based on the returned Status when it's not 0

	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ data information under the current configuration, including bandwidth, IQ single-channel sample rate, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize IQS mode configuration parameters.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Set the center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Set the reference level.
	IQS_ProfileIn.DecimateFactor = 2;		 // Set the decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Set IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Set trigger mode.
	IQS_ProfileIn.TriggerSource = Timer;     // Set trigger source to timer-triggered.
	IQS_ProfileIn.TriggerTimer_Period = 1;   // Set the trigger period for timer trigger, in seconds.
	IQS_ProfileIn.TriggerLength = 16384;     // Set the number of points for a single trigger collection. This is effective only when TriggerMode is set to FixedPoints.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Issue the IQS mode configuration.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors based on the returned Status when it's not 0.

	IQStream_TypeDef IQStream;                        // Container for IQ data packet, including IQ data, configuration information, etc.
	vector<int16_t> I_Data(StreamInfo.StreamSamples); // Create an array for I-channel data.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); // Create an array for Q-channel data.

	if (IQS_ProfileIn.TriggerMode == Adaptive)
	{
		I_Data.resize(StreamInfo.PacketSamples); // Resize I_Data for Adaptive mode to store I-channel data.
		Q_Data.resize(StreamInfo.PacketSamples); // Resize Q_Data for Adaptive mode to store Q-channel data.
	}

	// Loop to get IQ data
	while (1)
	{
		for (int j = 0; j < StreamInfo.PacketCount; j++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data packet, trigger information, I-channel data max value, and its index.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				// Note: In actual use of IQ mode, it is recommended to open a separate thread to call IQS_GetIQStream to get IQ data, and not handle IQ data processing in the same thread.

				/*int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;

				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0 && IQS_ProfileOut.TriggerMode == FixedPoints) // The last packet might not be a full packet (16242 points); so we only need to loop through the remaining points.
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}

				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
				}*/
			}

			else // Handle errors based on the returned Status when it's not 0
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}
		}
	}

	Device_Close(&Device); // Close the device	
	
	return 0;

}