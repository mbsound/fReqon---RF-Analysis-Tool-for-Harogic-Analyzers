#include <stdio.h>
#include <vector>
#include "htra_api.h"
#include "example.h"
#include <string>
#include<iostream>

using namespace std;
//When using this example, make sure the device minor version matches the API minor version.
//For example, if the MCU version of the device is 0.55.41, the API version should also be 0.55.xx.

#define IS_USB 1 //Default is USB type device; define IS_USB as 0 if using an Ethernet type device.

int SWP_CalibrateRefClock()
{
	int Status = 0;      //Function return value.
	void* Device = NULL; //Memory address of the current device.
	int DevNum = 0;      //Specify device number.

	BootProfile_TypeDef BootProfile; //Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       //Boot info structure, including device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; //Use USB data port and independent power port for dual power supply.

#if IS_USB==1
	//Configure USB interface.
	BootProfile.PhysicalInterface = USB;
#else 
	//Configure ETH interface.
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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); //If Status is not 0, perform corresponding error handling based on the return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  //SWP input configuration, including start freq, stop freq, RBW, ref level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; //SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    //Trace info under current configuration, including number of trace points, hops, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); //Call this function to initialize SWP mode parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;    //Configure start frequency.
	SWP_ProfileIn.StopFreq_Hz = 2e9;    //Configure stop frequency.
	SWP_ProfileIn.RBWMode = RBW_Manual; //Set RBW mode.
	SWP_ProfileIn.RBW_Hz = 10e3;        //Configure RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //Send SWP mode configurations.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //If Status is not 0, perform corresponding error handling based on the return value.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    //Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); //Create power array.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             //Measurement auxiliary info, including max power index, max power, temperature, location, timestamp, etc.
	double Freq_Max = 0;                                         //Store the frequency of peak value.
	float Power_Max = 0;                                         //Store the power of peak value.

	Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); //Get full sweep spectrum data.

	SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //If Status is not 0, perform corresponding error handling based on the return value.

	Freq_Max = Frequency[MeasAuxInfo.MaxIndex]; //Find the peak frequency before calibration.
	Power_Max = MeasAuxInfo.MaxPower_dBm;	    //Find the peak power before calibration.

	cout << "Frequency corresponding to the peak: " << Freq_Max << endl; //Output peak frequency before calibration.
	cout << "Peak power : " << Power_Max << endl;    //Output peak power before calibration.

	ClkCalibrationSource_TypeDef ClkCalibrationSource = CalibrateByExternal; //Calibrate clock via external trigger. For GNSS1PPS, contact support.
	double TriggerPeriod_s = 1;												 //Set the precise signal period of the calibration source.
	uint64_t TriggerCount = 2;												 //Set the number of calibration triggers.
	bool RewriteRFCal = false;												 //Set to false: calibration result not written to file (lost after power off); true: write to file (persistent).
	double RefCLKFreq_Hz = 0;												 //Store the calibrated reference clock frequency.

	Status = Device_CalibrateRefClock(&Device, ClkCalibrationSource, TriggerPeriod_s, TriggerCount, RewriteRFCal, &RefCLKFreq_Hz); //Start calibration.

	SWP_ProfileIn.ReferenceClockFrequency = RefCLKFreq_Hz; //Send the new reference clock frequency obtained from calibration.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //Send updated SWP configuration.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //If Status is not 0, perform corresponding error handling based on the return value.

	vector<double> Frequency_a(TraceInfo.FullsweepTracePoints);    //Create frequency array.
	vector<float> PowerSpec_dBm_a(TraceInfo.FullsweepTracePoints); //Create power array.
	double Freq_Max_a = 0;                                         //Store peak frequency after calibration.
	float Power_Max_a = 0;                                         //Store peak power after calibration.
	MeasAuxInfo_TypeDef MeasAuxInfo_a;                             //Used to store auxiliary measurement info.

	Status = SWP_GetFullSweep(&Device, Frequency_a.data(), PowerSpec_dBm_a.data(), &MeasAuxInfo_a); //Get full sweep spectrum data.

	if (Status == APIRETVAL_NoError)
	{
		// UserCode here
		/*

		For example: display spectrum or perform other operations.

		*/
	}

	else //If Status is not 0, perform corresponding error handling based on the return value.
	{
		SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
	}

	Freq_Max_a = Frequency_a[MeasAuxInfo_a.MaxIndex]; //Find peak frequency after calibration.
	Power_Max_a = MeasAuxInfo_a.MaxPower_dBm;		  //Find peak power after calibration.

	std::cout << "Frequency corresponding to the peak: " << Freq_Max_a << std::endl; //Output calibrated peak frequency.
	std::cout << "Peak power: " << Power_Max_a << std::endl; //Output calibrated peak power.

	Device_Close(&Device); //Close device.

	return 0;
}
