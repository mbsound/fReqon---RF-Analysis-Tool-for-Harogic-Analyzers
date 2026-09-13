#include <stdio.h>
#include <string.h>
#include <vector>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 //Defaults to USB device; set IS_USB to 0 for network devices.

int RTAMode_Standard()
{
	int Status = 0;                  //The function return value or error code. Status == 0 indicates no error. For details please check the Appendix 1 in the API Guide document.
	void* Device = NULL;             //Return the memory address of the currently opened device. Subsequent calls to other apis must use this address parameter to index the opened device.
	int DevNum = 0;                  //Device Number. For multiple devices, using the device number to decide which device to be opened. The device number accumulate from 0.

	BootProfile_TypeDef BootProfile; //Initialize configuration structure: physical interfaces, power supply.
	BootInfo_TypeDef BootInfo;       //Feedback information of the devic boot. Hardware version, firmware version and other information.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); //open device 

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); //When Status is not 0, the error is handled according to the return value of Status.

	RTA_Profile_TypeDef RTA_ProfileIn;  //Configure parameters for RTA mode including start/stop frequency, decimate factor, R.L. etc.
	RTA_Profile_TypeDef RTA_ProfileOut; //Feedback information for RTA mode including start/stop frequency, decimate factor, R.L. etc.
	RTA_FrameInfo_TypeDef FrameInfo;    //RTA data related information under the current configuration, including start frequency, end frequency, data points, etc.

	RTA_ProfileDeInit(&Device, &RTA_ProfileIn); //Initialize the relevant parameters of the configured RTA mode.

	RTA_ProfileIn.CenterFreq_Hz = 1e9;    //Center frequency.
	RTA_ProfileIn.RefLevel_dBm = 0;       //Reference level.
	RTA_ProfileIn.DecimateFactor = 1;	  //Decimate factor.
	RTA_ProfileIn.TriggerMode = Adaptive; //Specify trigger mode.
	RTA_ProfileIn.TriggerSource = Bus;    //Bus trigger
	RTA_ProfileIn.TriggerAcqTime = 0.1;   //The sampling time after the configuration is triggered is 0.1s, which is only effective in FixedPoints mode./

	Status = RTA_Configuration(&Device, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo); //Deliver configuration in RTA mode.

	RTA_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo); //When Status is not 0, the error is handled according to the return value of Status.
	double step = (FrameInfo.StopFrequency_Hz - FrameInfo.StartFrequency_Hz) / FrameInfo.FrameWidth; //Calculate frequency step

	vector<double> Frequency(FrameInfo.FrameWidth);  // Create the frequency array.
	vector<uint8_t> SpectrumTrace(FrameInfo.PacketValidPoints);                    //Spectrum array.
	vector<uint16_t> SpectrumBitmap(FrameInfo.FrameHeight * FrameInfo.FrameWidth); //SpectrumBitmap array.
	vector<float> Spectrum(FrameInfo.FrameWidth);                                  //Spectrum array in dBm.
	RTA_PlotInfo_TypeDef RTA_PlotInfo;                                             //Plot information.
	RTA_TriggerInfo_TypeDef TriggerInfo;                                           //Trigger information.
	MeasAuxInfo_TypeDef MeasAuxInfo;                                               //Auxiliary information for measurement data, including: power maximum value index, power maximum value, device temperature, latitude and longitude, absolute timestamp, etc.

	bool tag = false; //When RTA_ProfileOut.TriggerMode = Adaptive, control the trigger once before acquiring data.

	while (1)
	{
		if (RTA_ProfileOut.TriggerMode == Adaptive && tag != true) //When RTA_ProfileOut.TriggerMode = Adaptive, it triggers only once.
		{
			Status = RTA_BusTriggerStart(&Device);                 //RTA_BusTriggerStart is invoked to trigger the device. This function need not be called if the trigger source is external.
			tag = true;
		}
		if (RTA_ProfileOut.TriggerMode == FixedPoints)             //Triggered each time through the loop when RTA_ProfileOut.TriggerMode = FixedPoints.
		{
			Status = RTA_BusTriggerStart(&Device);                 //RTA_BusTriggerStart is invoked to trigger the device. This function need not be called if the trigger source is external.
		}
		for (uint32_t i = 0; i < FrameInfo.PacketCount; i++)	   //StreamInfo.PacketCount is 1 when TriggerMode is FixedPoints.
		{
			Status = RTA_GetRealTimeSpectrum(&Device, SpectrumTrace.data(), SpectrumBitmap.data(), &RTA_PlotInfo, &TriggerInfo, &MeasAuxInfo); //Get RTA data and trigger information.
			if (Status == 0)
			{
				// UserCode here
				

				//The units of the RTA spectrum data are converted into dBm
				for (int i = 0; i < FrameInfo.FrameWidth; i++)
				{
					Spectrum[i] = (float)SpectrumTrace[i] * RTA_PlotInfo.ScaleTodBm + RTA_PlotInfo.OffsetTodBm;
					Frequency[i] = FrameInfo.StartFrequency_Hz + i * step;

				}

				
			}
			else //When Status is not 0, the error is handled according to the return value of Status.
			{
				RTA_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo);

			}
		}
	}

	Status = RTA_BusTriggerStop(&Device); //Stop triggering the device. This function need not be called if the trigger source is external.

	Device_Close(&Device); //Close the device.

	return 0;
}
