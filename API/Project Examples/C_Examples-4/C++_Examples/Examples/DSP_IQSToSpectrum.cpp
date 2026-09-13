#include <stdio.h>
#include <string.h>
#include <iostream>
#include <vector>
#include "htra_api.h" 
#include "example.h"
using namespace std;
#define IS_USB 1 //Defaults to USB device; set IS_USB to 0 for network devices.

int DSP_IQSToSpectrum()
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
	IQS_StreamInfo_TypeDef StreamInfo;  				   //feedback information for the configuration including IQ data points, time domain data etc.
	IQStream_TypeDef IQStream;     						   //Store IQ packets, including: IQ data, configuration information
	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn);   //initialize the IQS_ProfileIn.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       //Center frequency.       
	IQS_ProfileIn.RefLevel_dBm = 0;          //Reference level.
	IQS_ProfileIn.DataFormat = Complex16bit; //Decimate factor.
	IQS_ProfileIn.TriggerMode = FixedPoints; //Specify trigger mode.
	IQS_ProfileIn.TriggerSource = Bus;       //Configure the trigger source as internal bus trigger.
	IQS_ProfileIn.DecimateFactor = 2;        //Decimate factor.
	IQS_ProfileIn.BusTimeout_ms = 5000;      //Set the bus timeout.
	IQS_ProfileIn.TriggerLength = 16242;     //Configure the points collected by a single trigger.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); //Deliver configuration in IQS mode.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); //When Status is not 0, the error is handled according to the return value of Status.

	vector<int16_t> AlternIQStream(StreamInfo.StreamSamples * 2); //Create an array to store IQ data, data storage format for IQIQIQ... .

	void* DSP = NULL;                                                  
	DSP_Open(&DSP); //Turn on the DSP function.

	DSP_FFT_TypeDef IQToSpectrumIn;  //Configure parameters in FFT mode including FFT points, detection method etc.
	DSP_FFT_TypeDef IQToSpectrumOut; //Feedback information in FFT mode including FFT points, detection method etc.
	uint32_t TracePoints = 0;        //Spectrum points after FFT.

	DSP_FFT_DeInit(&IQToSpectrumIn); //Initialize IQToSpectrumIn

	IQToSpectrumIn.Calibration = 0;                      //open calibration, 0 for close and other value for open.
	IQToSpectrumIn.DetectionRatio = 1;                   //Detection ratio.
	IQToSpectrumIn.TraceDetector = TraceDetector_PosPeak;//Detection method.
	IQToSpectrumIn.FFTSize = StreamInfo.StreamSamples;   //FFT points.
	IQToSpectrumIn.Intercept = 1;                        //Interception rate.
	IQToSpectrumIn.SamplePts = StreamInfo.StreamSamples; //Sample points.
	IQToSpectrumIn.WindowType = FlatTop;                 //Window type

	double RBWRatio = 0;                                 //RBW ratio,RBW = RBWRatio * StreamInfo.IQSampleRate.

	DSP_FFT_Configuration(&DSP, &IQToSpectrumIn, &IQToSpectrumOut, &TracePoints, &RBWRatio); //deliver configuration in FFT mode.

	/*Take the IQ data and transfer it to the spectrum*/
	vector<double> Frequency(TracePoints); //Create an array to hold the frequency data
	vector<float> Spectrum(TracePoints);   //Create an array to hold the amplitude data.

	while (1)
	{
		Status = IQS_BusTriggerStart(&Device); //IQS_BusTriggerStart is called to trigger the device. This function need not be called if the trigger source is external.
		if (Status==APIRETVAL_NoError)
		{
			uint32_t IQPoints = 0; //Keep track of the actual IQ points.
			for (int i = 0; i < StreamInfo.PacketCount; i++)
			{
				Status = IQS_GetIQStream_PM1(&Device, &IQStream); //Obtain IQ data.

				if (i != StreamInfo.PacketCount - 1) //Current package is not the last pachage.
				{
					memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * StreamInfo.PacketSamples);
					IQPoints += StreamInfo.PacketSamples * 2;
				}
				else //When the current packet is the last packet.
				{
					if (StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) //last pachage data is less than a whole package.
					{
						memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * (StreamInfo.StreamSamples % StreamInfo.PacketSamples));
					}
					else //last pachage data is a whole package.
					{
						memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * StreamInfo.PacketSamples);
					}
				}
			}
		}
		else //When Status is not 0, the error is handled according to the return value of Status.
		{
			IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
		}
		
		IQStream.AlternIQStream = AlternIQStream.data();                           //AlternIQStream pointer points to the address where the IQ data actually exists.
		DSP_FFT_IQSToSpectrum(&DSP, &IQStream, Frequency.data(), Spectrum.data()); //Execute the IQ transform spectrum function.
	}

	Status = IQS_BusTriggerStop(&Device); //IQS_BusTriggerStop is called to stop the triggering device. This function need not be called if the trigger source is external.

	DSP_Close(&DSP);

	Status = Device_Close(&Device);

	return 0;
}
