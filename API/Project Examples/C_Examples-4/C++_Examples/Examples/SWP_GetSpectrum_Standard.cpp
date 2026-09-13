#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 //Defaults to USB device; set IS_USB to 0 for network devices.

//This example uses an external reference clock in SWP mode. The configuration method is the same in other modes.

int SWP_GetSpectrum_Standard()
{
	int Status = 0;                  //The fuion return value or error code. Status == 0 indicates no error. For details please check the Appendix 1 in the API Guide document.
	void* Device = NULL;             //Device handle. Use the device handle to specify device for manipulating in the API calls. The device handle must be initialized firstly by function Devcie_Open before it to be used.
	int DevNum = 0;                  //Device Number. For multiple devices, using the device number to decide which device to be opened. The device number accumulate from 0.

	BootProfile_TypeDef BootProfile; //Initialize configuration structure: physical interfaces, power supply.
	BootInfo_TypeDef BootInfo;       //Initialize the information structure, including device information, USB speed, etc.

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

	SWP_Profile_TypeDef SWP_ProfileIn;  //configure parameters for SWP mode including start/stop frequency, RBW, R.L. etc.
	SWP_Profile_TypeDef SWP_ProfileOut; //feedback information including start/stop frequency, RBW, R.L. etc.
	SWP_TraceInfo_TypeDef TraceInfo;    //feedback information for the current trace including trace points etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); //initialize the SWP_ProfileIn.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   //start frequency
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; //stop frequency
	SWP_ProfileIn.RBWMode = RBW_Manual; //Configure RBW update mode to be manual
	SWP_ProfileIn.RBW_Hz = 200e3;       //RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //deliever configuration in SWP mode.
	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //When Status is not 0, the error is handled according to the return value of Status.
	vector<double> Frequency(TraceInfo.FullsweepTracePoints);         //Frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints);      //Power array.
	int HopIndex = 0;                                                 //Hop index.
	int FrameIndex = 0;                                               //Frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                                  //Auxiliary measurement information.
    // Loop to get spectrum data
	while (1)
	{
		for (int i = 0; i < TraceInfo.TotalHops; i++)                //TraceInfo.TotalHops represents the number of frames under the current configuration. Therefore, a complete trace can be obtained by calling SWP_GetPartialSweep through the TraceInfo.TotalHops loop.
		{
			Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); //Obtain spectrum data.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				/*

				For example, display spectrum or do other processing based on the spectrum

				*/
			}

			/*Erroe and warning handling is recommended.*/
			else
			{
				SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
			}
		}
	}

	Device_Close(&Device); //Close the device 
	return 0;
}