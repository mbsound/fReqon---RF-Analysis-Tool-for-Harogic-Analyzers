#include <stdio.h>
#include <string.h>
#include <vector>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 //Defaults to USB device; set IS_USB to 0 for network devices.

int ASG_SignalOutput()
{
	int Status = 0;                  //The function return value or error code. Status == 0 indicates no error. For details please check the Appendix 1 in the API Guide document.
	void* Device = NULL;             //Device handle. Use the device handle to specify device for manipulating in the API calls. The device handle must be initialized firstly by function Devcie_Open before it to be used.
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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); //Open the device.

	Device_Open_ErrorHandling(Status,&Device, DevNum, &BootProfile, &BootInfo); //When Status is not 0, the error is handled according to the return value of Status.

	SWP_Profile_TypeDef SWP_ProfileIn;          //configure parameters for SWP mode including start/stop frequency, RBW, R.L. etc.
	SWP_Profile_TypeDef SWP_ProfileOut;         //feedback information including start/stop frequency, RBW, R.L. etc.
	SWP_TraceInfo_TypeDef TraceInfo;            //feedback information for the current trace including trace points etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); //initialize the SWP_ProfileIn.

	SWP_ProfileIn.StartFreq_Hz = 1e9; //start frequency
	SWP_ProfileIn.StopFreq_Hz = 2e9;  //stop frequency

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //deliever configuration in SWP mode.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //When Status is not 0, the error is handled according to the return value of Status.
	ASG_Profile_TypeDef ASG_ProfileIn;  //ASG input configuration, including signal source output mode, frequency in each mode, power and other parameter Settings.
	ASG_Profile_TypeDef ASG_ProfileOut; //The ASG output configuration.
	ASG_Info_TypeDef ASG_Info;         //Information about the number of scan points in the current configuration.

	ASG_ProfileDeInit(&Device, &ASG_ProfileIn); //Initialize the relevant parameters of the configuration ASG mode.

#define SIGNAL_CW 1              //The desired signal is a single tone signal, set this value to 1.
#define SIGNAL_Frequency_sweep 0 //The desired signal is the frequency scan signal, set this value to 1.
#define SIGNAL_Power_sweep 0     //The desired signal is the power scan signal, set this value to 1.

#if SIGNAL_CW == 1
	/*tone signal*/
	ASG_ProfileIn.CenterFreq_Hz = 1.51e9;
	ASG_ProfileIn.Level_dBm = 0;
	ASG_ProfileIn.Mode = ASG_FixedPoint;
	ASG_ProfileIn.Port = ASG_Port_External;

#elif SIGNAL_Frequency_sweep == 1
	/*frequency sweep*/
	ASG_ProfileIn.StartFreq_Hz = 1.2e9;
	ASG_ProfileIn.StopFreq_Hz = 1.4e9;
	ASG_ProfileIn.StepFreq_Hz = 1e6;
	ASG_ProfileIn.Level_dBm = -20;
	ASG_ProfileIn.Mode = ASG_FrequencySweep;

#elif SIGNAL_Power_sweep == 1
	/*power sweep*/
	ASG_ProfileIn.CenterFreq_Hz = 1.6e9;
	ASG_ProfileIn.StartLevel_dBm = -30;
	ASG_ProfileIn.StopLevel_dBm = -20;
	ASG_ProfileIn.Mode = ASG_PowerSweep;

#endif

	ASG_Configuration(&Device, &ASG_ProfileIn, &ASG_ProfileOut, &ASG_Info); //deliver ASG related configuration.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    //Frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); //Amplititude array.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             //Auxiliary information of measurement data, including: power maximum value index, power maximum value, device temperature, latitude and longitude, absolute timestamp, etc.

	//The spectrum data is acquired cyclically.
	while (1)
	{
		Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); //Obtain trace.
		SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); //When Status is not 0, the error is handled according to the return value of Status.
	}

	Device_Close(&Device); //Close the device.

	return 0;
}