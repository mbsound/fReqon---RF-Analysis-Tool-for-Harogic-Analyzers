#include <stdio.h>
#include <string.h>
#include <chrono>
#include <thread>
#include <chrono>
#include <iostream>
#include <vector>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // The default device type is USB. If using an Ethernet device, set IS_USB to 0.

int Status = 0;      // Function return status.
void* Device = NULL; // Memory address of the current device.
int DevNum = 0;      // Specifies the device number.

void SwpMode(BootProfile_TypeDef* BootProfile, BootInfo_TypeDef *BootInfo) // SWP mode configuration.
{
	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under the current configuration, including number of trace points, number of hops, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Call this function to initialize the configuration for SWP mode parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.37e9; // Stop frequency.
	SWP_ProfileIn.RBWMode = RBW_Manual; // Manual RBW.
	SWP_ProfileIn.RBW_Hz = 15e3;        // Set RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Issue the SWP mode configuration.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, BootProfile, BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors based on the Status return value when Status is not 0.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create an array for frequency.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create an array for power.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary information for measurement data, including power max index, power max value, device temperature, latitude/longitude, absolute timestamp, etc.

	for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops represents the number of frames under the current configuration, so loop TraceInfo.TotalHops times to call SWP_GetPartialSweep to get the full trace.
	{
		Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Get spectrum data.

		SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, BootProfile, BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors based on the Status return value when Status is not 0.
	}
	cout << "SWP Data Acquisition Completed" << endl;
}

void RtaMode(BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo) // RTA mode configuration.
{
	RTA_Profile_TypeDef RTA_ProfileIn;  // RTA input configuration, including center frequency, decimation factor, reference level, etc.
	RTA_Profile_TypeDef RTA_ProfileOut; // RTA output configuration.
	RTA_FrameInfo_TypeDef FrameInfo;    // Trace information under the current configuration, including start frequency, stop frequency, POI, etc.

	RTA_ProfileDeInit(&Device, &RTA_ProfileIn); // Call this function to initialize the configuration for RTA mode parameters.

	RTA_ProfileIn.CenterFreq_Hz = 1.86e9; // Configure center frequency.
	RTA_ProfileIn.RefLevel_dBm = 0;       // Configure reference level.
	RTA_ProfileIn.DecimateFactor = 1;     // Configure decimation factor.
	RTA_ProfileIn.TriggerMode = Adaptive; // Configure trigger mode.
	RTA_ProfileIn.TriggerSource = Bus;    // Configure trigger source.

	Status = RTA_Configuration(&Device, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo); // Issue the RTA mode configuration.

	RTA_Configuration_ErrorHandling(Status, &Device, DevNum, BootProfile, BootInfo, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo); // Handle errors based on the Status return value when Status is not 0.

	vector<uint8_t> SpectrumTrace(FrameInfo.PacketValidPoints);                    // Spectrum array.
	vector<uint16_t> SpectrumBitmap(FrameInfo.FrameHeight * FrameInfo.FrameWidth); // Spectrum bitmap array.
	vector<float> Spectrum(FrameInfo.FrameWidth);                                  // Spectrum array in dBm.
	RTA_PlotInfo_TypeDef RTA_PlotInfo;                                             // Plot information.
	RTA_TriggerInfo_TypeDef TriggerInfo;                                           // Trigger information.
	MeasAuxInfo_TypeDef MeasAuxInfo;                                               // Auxiliary information for measurement data.

	Status = RTA_BusTriggerStart(&Device); // Trigger the device using RTA_BusTriggerStart.

	for (uint32_t i = 0; i < FrameInfo.PacketCount; i++)
	{
		Status = RTA_GetRealTimeSpectrum(&Device, SpectrumTrace.data(), SpectrumBitmap.data(), &RTA_PlotInfo, &TriggerInfo, &MeasAuxInfo); // Get RTA data and trigger information.

		RTA_ErrorHandlingExceptOpenAndConfiguration(Status, &Device,DevNum, BootProfile, BootInfo, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo); // Handle errors based on the Status return value when Status is not 0.
	}

	Status = RTA_BusTriggerStop(&Device); // Stop triggering the device using RTA_BusTriggerStop.
	cout << "RTA Data Acquisition Completed" << endl;
}

void IQSMode(BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo) 
{
	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, including center frequency, decimation factor, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;  // Trace information under the current configuration, including IQ data points, time domain sample data type, etc.

	IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Call this function to initialize the configuration for IQS mode parameters.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Configure center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Configure reference level.
	IQS_ProfileIn.DecimateFactor = 2;	     // Configure decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Configure IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Configure trigger mode.
	IQS_ProfileIn.TriggerSource = Bus;       // Configure trigger source as internal bus trigger.
	IQS_ProfileIn.TriggerLength = 16384;     // Configure the number of points collected per trigger.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Issue the IQS mode configuration.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, BootProfile, BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors based on the Status return value when Status is not 0.

	IQStream_TypeDef IQStream;                         // Structure to store IQ packet data, including IQ data and related configuration information.
	vector<int16_t> I_Data(StreamInfo.StreamSamples);  // Allocate memory to store I data.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples);  // Allocate memory to store Q data.

	Status = IQS_BusTriggerStart(&Device); // Trigger the device using IQS_BusTriggerStart. If the trigger source is external, this function does not need to be called.

	for (int j = 0; j < StreamInfo.PacketCount; j++)
	{
		Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data.

		if (Status == APIRETVAL_NoError)
		{
			// User code here
			// Note: It is recommended to run IQS_GetIQStream in a separate thread when using IQ mode, not in the same thread as the IQ data processing.

			/*int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
			 uint32_t Points = StreamInfo.PacketSamples;

			 if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) // The last packet may not be a full packet (16242 points); only need to loop through the points that do not fill a full packet.
			 {
				Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
			 }

			 for (uint32_t i = 0; i < Points; i++)
			 {
			   I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
			   Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
			  }*/

		}
		else // When Status is not 0, handle errors based on the Status return value.
		{
			IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, BootProfile, BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); 
		}
	}

	Status = IQS_BusTriggerStop(&Device); // Stop the trigger after the acquisition is complete.
	cout << "IQS Data Acquisition Completed" << endl;
}

int Device_MeasureModeSwitchTime()
{
	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply mode, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and independent power port for dual power supply.

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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open the device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is not 0, handle errors according to the return value of Status.

	// SWP mode to RTA mode.
	SwpMode(&BootProfile, &BootInfo);						 // Run SWP mode.
	auto start1 = std::chrono::high_resolution_clock::now(); // Get the current time.
	RtaMode(&BootProfile, &BootInfo);						 // Run RTA mode.
	auto stop1 = std::chrono::high_resolution_clock::now();  // Get the current time.

	auto timeout1 = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop1 - start1); // Calculate the elapsed time.
	cout << "SWP To RTA Cost:" << timeout1.count() << "ms" << endl;
	
	// IQS mode to SWP mode.
	IQSMode(&BootProfile, &BootInfo);						 // Run IQS mode.
	auto start2 = std::chrono::high_resolution_clock::now(); // Get the current time.
	SwpMode(&BootProfile, &BootInfo);						 // Run SWP mode.
	auto stop2 = std::chrono::high_resolution_clock::now();  // Get the current time.

	auto timeout2 = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop2 - start2); // Calculate the elapsed time.
	cout << "IQS To SWP Cost:" << timeout2.count() << "ms" << endl;

	Device_Close(&Device); // Close the device.

	return 0;
}

