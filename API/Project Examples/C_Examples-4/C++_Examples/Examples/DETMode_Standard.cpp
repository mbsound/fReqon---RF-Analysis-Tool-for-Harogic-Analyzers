#include <stdio.h>
#include <string.h>
#include <vector>
#include <iostream>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 //Defaults to USB device; set IS_USB to 0 for network devices.

int DETMode_Standard()
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

	DET_Profile_TypeDef DET_ProfileIn;                     //Configure parameters for DET mode including start/stop frequency, decimate factor, R.L. etc.
	DET_Profile_TypeDef DET_ProfileOut;                    //Feedback information for DET mode including start/stop frequency, decimate factor, R.L. etc.
	DET_StreamInfo_TypeDef StreamInfo;                     //feedback information for DET mode under current configuration including data points and detection method etc.

	DET_ProfileDeInit(&Device, &DET_ProfileIn);            //initialize the DET_ProfileIn.

	DET_ProfileIn.CenterFreq_Hz = 1e9;                     //Center frequency.
	DET_ProfileIn.RefLevel_dBm = 0;                        //Reference level.
	DET_ProfileIn.DecimateFactor = 2;			           //Decimate factor.
	DET_ProfileIn.TriggerMode = Adaptive;                  //Specify trigger mode.
	DET_ProfileIn.TriggerSource = Bus;                     //Bus trigger, External for external triiger.

	Status = DET_Configuration(&Device, &DET_ProfileIn, &DET_ProfileOut, &StreamInfo); //Deliver configuration in IQS mode.

	DET_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &DET_ProfileIn, &DET_ProfileOut, &StreamInfo); //When Status is not 0, the error is handled according to the return value of Status.

	vector<float> NormalizedPowerStream(StreamInfo.PacketSamples); //Create the power array.
	float ScaleToV = 0;                                            //ratio factor for absolute amplititude(V).
	DET_TriggerInfo_TypeDef TriggerInfo;                           //Trigger information in DET mode.
	MeasAuxInfo_TypeDef MeasAuxInfo;                               //Auxiliary information for measurement data.

	bool tag = false; 											   //When RTA_ProfileOut.TriggerMode = Adaptive, the control triggers once before fetching the data.

	while (1)
	{
		if (DET_ProfileOut.TriggerMode == Adaptive && tag != true)	   //Trigger only once when DET_ProfileOut.TriggerMode == Adaptive.
		{
			Status = DET_BusTriggerStart(&Device);                     //DET_BusTriggerStart is invoked to trigger the device. This function need not be called if the trigger source is external.
			tag = true;
		}
		if (DET_ProfileOut.TriggerMode == FixedPoints)                 //This is triggered each time through the loop when DET_ProfileOut.TriggerMode == FixedPoints.
		{
			Status = DET_BusTriggerStart(&Device);                     //The device is triggered by calling DET_BusTriggerStart. This function need not be called if the trigger source is external.
		}
		for (uint32_t i = 0; i < StreamInfo.PacketCount; i++)		   //StreamInfo.PacketCount is 1 when TriggerMode is FixedPoints.
		{
			Status = DET_GetPowerStream(&Device, NormalizedPowerStream.data(), &ScaleToV, &TriggerInfo, &MeasAuxInfo); //Get DET data and trigger information.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				

				//Converter DET data unit into dBm.
				/*for (int i = 0; i < StreamInfo.PacketSamples; i++)
				{
					NormalizedPowerStream[i] = 10 * log10(20 * pow(NormalizedPowerStream[i] * ScaleToV, 2));
				}*/

				
			}

			else //When Status is not 0, the error is handled according to the return value of Status.
			{
				DET_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &DET_ProfileIn, &DET_ProfileOut, &StreamInfo);
			}
		}
	}

	Status = DET_BusTriggerStop(&Device); //Stop triggering the device. This function need not be called if the trigger source is external.

	Device_Close(&Device); //Close the device.

	return 0;
}