#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include <chrono>
#include<thread>
#include "htra_api.h"
#include "example.h"
using namespace std;

/*README
For details on the connection and usage of the EIO extension board, please refer to the GNSS module usage chapter in the "SA NX Series Spectrum Analyzer User Manual"
*/

#define IS_USB 1 //The default is USB device. If using an Ethernet device, define IS_USB as 0.

int IQS_GNSS_1PPS()
{
	int Status = 0;      //Function return value.
	void* Device = NULL; //Memory address of the current device.
	int DevNum = 0;      //Specifies the device number.

	BootProfile_TypeDef BootProfile; //Startup configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       //Startup info structure, including device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; //Use both USB data port and independent power port for power supply.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); //When Status is not 0, handle the error based on its return value.

	/*Set GNSS external antenna*/
	GNSSAntennaState_TypeDef GNSSAntennaState; //Start GNSS antenna info
	GNSSAntennaState = GNSS_AntennaExternal;   //Configure external antenna

	//Set GNSS antenna status
	Status = Device_SetGNSSAntennaState(&Device, GNSSAntennaState); //Send GNSS antenna configuration

	GNSSInfo_TypeDef GNSSInfo = { 0 }; //GNSS info under the current antenna configuration

	//Output the current GNSS lock status every 1s until GNSS module is successfully locked
	while (!GNSSInfo.GNSS_LockState)
	{
		Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo);				//Get real-time GNSS device status
		cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl; //Output GNSS antenna lock status. GNSS_LockState=1 means locked
		this_thread::sleep_for(chrono::milliseconds(1000));					    //Delay 1s
	}

	DOCXOWorkMode_TypeDef DOCXOWorkMode;					  //Configure DOCXO antenna status
	DOCXOWorkMode = DOCXO_LockMode;

	/*Set and get DOCXO status*/
	uint16_t HardwareVersion = BootInfo.DeviceInfo.HardwareVersion;
	uint16_t OCXO_Enable = (HardwareVersion >> 10) & 0x3;

	if (OCXO_Enable)
	{
		Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); //Set DOCXO work status in GNSS

		auto start_time = std::chrono::high_resolution_clock::now(); // Get current time

		Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo); //Get GNSS device status

		// Check lock status
		if (GNSSInfo.DOCXO_LockState)
		{
			cout << endl;
			// Print current GNSS_LockState status
			cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;
			// Print current DOCXO_LockState status
			cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;
		}
		else
		{
			while (1)
			{
				Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo); //Get GNSS device status

				// Check lock status
				if (GNSSInfo.DOCXO_LockState == 1 && GNSSInfo.GNSS_LockState == 1)
				{
					cout << endl;
					// Print current GNSS_LockState status
					cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;
					// Print current DOCXO_LockState status
					cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;
					break;
				}
				if (GNSSInfo.GNSS_LockState == 0)
				{
					DOCXOWorkMode = DOCXO_LockMode;
					Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); //Set DOCXO work status in GNSS
				}
				// Print current GNSS_LockState status
				cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;

				// Print current DOCXO_LockState status
				cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;

				// Check timeout: whether over 180 seconds
				auto current_time = std::chrono::high_resolution_clock::now();
				auto duration = std::chrono::duration_cast<std::chrono::duration<double, std::ratio<1, 1>>>(current_time - start_time);
				// If timeout over 600s, exit loop
				if (duration.count() > 600)
				{
					cout << "The DOCXO is not locked, please check whether the cable connection is normal." << endl;
					break;
					return 0;
				}
				this_thread::sleep_for(chrono::milliseconds(1000)); //Delay 1s
			}
			cout << "DOCXO is locked!" << endl;
		}
	}

	IQS_Profile_TypeDef IQS_ProfileIn;  //IQS mode input configuration, including center frequency, decimation factor, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; //IQS mode output configuration
	IQS_StreamInfo_TypeDef StreamInfo;  //IQ data stream info under current configuration

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); //Call this function to initialize parameters related to IQS mode configuration.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       //Set center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          //Set reference level.
	IQS_ProfileIn.DecimateFactor = 2;		 //Set decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; //Set IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; //Set trigger mode. FixedPoints means sampling starts at rising edge, ends after collecting TriggerLength samples. Adaptive means starts at rising edge, ends at falling edge.
	IQS_ProfileIn.TriggerSource = GNSS1PPS;  //Set trigger source to internal 1PPS signal from GNSS
	IQS_ProfileIn.TriggerLength = 16384;     //Set number of samples per trigger. Only valid for FixedPoints mode.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); //Send IQS mode configurations.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); //When Status is not 0, handle the error accordingly.

	IQStream_TypeDef IQStream;                        //Store IQ data packet (IQ data and related config info)
	vector<int16_t> I_Data(StreamInfo.StreamSamples); //Create I channel data array.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); //Create Q channel data array.

	if (IQS_ProfileIn.TriggerMode == Adaptive)
	{
		I_Data.resize(StreamInfo.PacketSamples); //Resize I_Data to store data in Adaptive mode.
		Q_Data.resize(StreamInfo.PacketSamples); //Resize Q_Data to store data in Adaptive mode.
	}

	while (1)
	{
		for (int j = 0; j < StreamInfo.PacketCount; j++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); //Get IQ data packet, trigger info, max I data value and index.

			if (Status == APIRETVAL_NoError)
			{
				// UserCode here
				//Note: In actual use of IQ mode, it is recommended to call IQS_GetIQStream in a dedicated thread. Do not place IQ data processing in the same thread.

				int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
				uint32_t Points = StreamInfo.PacketSamples;
				//When TriggerMode is FixedPoints, check if the last packet contains 16242 samples.
				if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0 && IQS_ProfileOut.TriggerMode == FixedPoints) //The last packet may be incomplete (less than 16242 samples); only loop through remaining samples.
				{
					Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
				}
				//Separate IQ channel data
				for (uint32_t i = 0; i < Points; i++)
				{
					I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
					Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
				}
			}

			else //When Status is not 0, handle the error accordingly.
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}	
		}
	}

	Device_Close(&Device); //Close the device	

	return 0;
}
