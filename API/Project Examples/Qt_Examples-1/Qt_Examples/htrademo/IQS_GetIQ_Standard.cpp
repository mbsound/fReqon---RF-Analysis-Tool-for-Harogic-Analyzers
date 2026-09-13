#include <iostream>
#include <vector>
#include <string>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 //Defaults to USB device; set IS_USB to 0 for network devices.

int IQS_GetIQ_Standard()
{
	int Status = 0;                  //The function return value or error code. Status == 0 indicates no error. For details please check the Appendix 1 in the API Guide document.
	void* Device = NULL;             //Return the memory address of the currently opened device. Subsequent calls to other apis must use this address parameter to index the opened device.
	int DevNum = 0;                  //Device Number. For multiple devices, using the device number to decide which device to be opened. The device number accumulate from 0.

	BootProfile_TypeDef BootProfile; //Initialize configuration structure: physical interfaces, power supply.
	BootInfo_TypeDef BootInfo;       //Feedback information of the devic boot. Hardware version, firmware version etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; //Both the USB data port and independent power port are used for power supply.

#if IS_USB==1
	//set USB interface
	BootProfile.PhysicalInterface = USB;
#else 
	//Set ETH interface
	BootProfile.PhysicalInterface = ETH;
	BootProfile.ETH_IPVersion = IPv4;
	BootProfile.ETH_RemotePort = 5000;
	BootProfile.ETH_ReadTimeOut = 5000;
	BootProfile.ETH_IPAddress[0] = 192;
	BootProfile.ETH_IPAddress[1] = 168;
	BootProfile.ETH_IPAddress[2] = 1;
	BootProfile.ETH_IPAddress[3] = 100;
#endif

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); //Open the device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); //When Status is not 0, the error is handled according to the return value of Status.

	IQS_Profile_TypeDef IQS_ProfileIn;                     //Configure parameters for IQS mode including start/stop frequency, decimate factor, R.L. etc.
	IQS_Profile_TypeDef IQS_ProfileOut;                    //Feedback information for IQS mode including start/stop frequency, decimate factor, R.L. etc.
	IQS_StreamInfo_TypeDef StreamInfo;                     //feedback information for the configuration including IQ data points, time domain data etc.
	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn);            //initialize the IQS_ProfileIn.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       //Center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          //Reference level.
	IQS_ProfileIn.DecimateFactor = 2;	     //Decimate factor.
	IQS_ProfileIn.DataFormat = Complex16bit; //IQ data format.
	IQS_ProfileIn.TriggerSource = Bus;       //Configure the trigger source as internal bus trigger.
	IQS_ProfileIn.TriggerMode = FixedPoints; //Specify trigger mode.
	IQS_ProfileIn.TriggerLength = 16384;     //Configure the points collected by a single trigger.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); //Deliver configuration in IQS mode.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); //When Status is not 0, the error is handled according to the return value of Status.

	IQStream_TypeDef IQStream; //Structure for IQ data package including IQ data and related configuration information.
	bool tag = false;		   //When IQS_ProfileIn.TriggerMode = Adaptive, the control triggers once before fetching data.

	vector<int16_t> I_Data(StreamInfo.StreamSamples); //I-channel array.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); //Q-channel array.

	if (IQS_ProfileIn.TriggerMode == Adaptive)
	{
		I_Data.resize(StreamInfo.PacketSamples); //Re-adjust the size of I_Data to store I channel data in Adaptive mode.
		Q_Data.resize(StreamInfo.PacketSamples); //Re-adjust the size of Q_Data to store Q channel data in Adaptive mode.
	}

	while (1)
	{
		if (IQS_ProfileOut.TriggerMode == Adaptive && tag != true) //Triggers only once when IQS_ProfileIn.TriggerMode = Adaptive.
		{
			Status = IQS_BusTriggerStart(&Device);                 //Call IQS_BusTriggerStart to trigger the device. If the trigger source is an external trigger, then this function does not need to be called.
			tag = true;
		}
		if (IQS_ProfileOut.TriggerMode == FixedPoints)             //When IQS_ProfileIn.TriggerMode = FixedPoints, a trigger occurs in every loop.
		{
			Status = IQS_BusTriggerStart(&Device);                 //If the trigger source is an external trigger, then this function does not need to be called.
		}

		for (int j = 0; j < StreamInfo.PacketCount; j++)		   //This only takes effect when TriggerMode is FixedPoints. It does not take effect when TriggerMode is Adaptive. StreamInfo.PacketCount is 1.
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream);      //Acquire IQ data packets, trigger information, the maximum value of the I-channel data, and the array index of the maximum value.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				//Note: When using IQ mode in actual applications, it is recommended to open a separate thread to specifically call IQS_GetIQStream to obtain IQ data. Do not place this operation in the same thread as the IQ data processing.

				int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;

				//When TriggerMode is set to FixedPoints, determine if the last packet is 16242 points.
				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0 && IQS_ProfileOut.TriggerMode == FixedPoints) //Maybe the last packet is less than a whole packet (16,242 points). So you only need to loop over less than a packet of points
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}

				//Take out the two IQ data respectively
				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
				}
			}

			else //When Status is not 0, the error is handled according to the return value of Status.
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}
		}
	}

	Status = IQS_BusTriggerStop(&Device); //IQS_BusTriggerStop is called to stop the triggering device.

	Device_Close(&Device); //Close the device.

	return 0;

}
