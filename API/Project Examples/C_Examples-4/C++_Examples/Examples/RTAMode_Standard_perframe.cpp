#include <stdio.h>
#include <string.h>
#include <vector>
#include <chrono>
#include "example.h"
#include "htra_api.h"

using namespace std;

#define IS_USB 1 // Default is USB device; if using Ethernet device, set IS_USB to 0.

int RTAMode_Standard_perframe()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Pointer to the current device.
	int DevNum = 0;      // Specified device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and independent power port.

#if IS_USB==1
	// Configure USB interface.
	BootProfile.PhysicalInterface = USB;
#else 
	// Configure Ethernet interface.
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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is not 0, handle error based on Status value.

	RTA_Profile_TypeDef RTA_ProfileIn;  // RTA input configuration including center frequency, decimation factor, reference level, etc.
	RTA_Profile_TypeDef RTA_ProfileOut; // RTA output configuration.
	RTA_FrameInfo_TypeDef FrameInfo;    // Frame-related info under current RTA config, including start/stop freq, number of data points, etc.

	RTA_ProfileDeInit(&Device, &RTA_ProfileIn); // Initialize RTA profile parameters.

	RTA_ProfileIn.CenterFreq_Hz = 1e9;    // Set center frequency.
	RTA_ProfileIn.RefLevel_dBm = 0;       // Set reference level.
	RTA_ProfileIn.DecimateFactor = 1;	  // Set decimation factor.
	RTA_ProfileIn.TriggerMode = Adaptive; // Set trigger mode.
	RTA_ProfileIn.TriggerSource = Bus;    // Set trigger source to internal bus.
	RTA_ProfileIn.TriggerAcqTime = 0.1;   // Set acquisition time after trigger to 0.1s. Only effective in FixedPoints mode.

	Status = RTA_Configuration(&Device, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo); // Apply RTA configuration.

	RTA_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo); // When Status is not 0, handle error accordingly.

	vector<uint8_t> SpectrumTrace(FrameInfo.PacketValidPoints);                    // Create spectrum data array.
	vector<uint16_t> SpectrumBitmap(FrameInfo.FrameHeight * FrameInfo.FrameWidth); // Create spectrum bitmap array.
	vector<float> Spectrum(FrameInfo.FrameWidth);                                  // Create spectrum array in dBm.
	RTA_PlotInfo_TypeDef RTA_PlotInfo;                                             // Plot information.
	RTA_TriggerInfo_TypeDef TriggerInfo;                                           // Trigger information.
	MeasAuxInfo_TypeDef MeasAuxInfo;                                               // Auxiliary measurement data including: max power index, max power, device temperature, GPS info, absolute timestamp, etc.

	bool tag = false;		 // When RTA_ProfileOut.TriggerMode = Adaptive, trigger once before data acquisition.
	float time_multiple = 0; // Total time for multiple data acquisitions.
	float time_avg = 0;		 // Average time for each frame acquisition.
	int t = 0;				 // Controls the while loop iteration count.

	while (t<1000)
	{
		if (RTA_ProfileOut.TriggerMode == Adaptive && tag != true)
		{
			Status = RTA_BusTriggerStart(&Device); // Trigger the device. If the trigger source is external, this function is not needed.
			tag = true;
		}
		if (RTA_ProfileOut.TriggerMode == FixedPoints)
		{
			Status = RTA_BusTriggerStart(&Device); // Trigger the device. If the trigger source is external, this function is not needed.
		}
		for (uint32_t i = 0; i < FrameInfo.PacketCount; i++)
		{
			auto start = std::chrono::high_resolution_clock::now();

			Status = RTA_GetRealTimeSpectrum(&Device, SpectrumTrace.data(), SpectrumBitmap.data(), &RTA_PlotInfo, &TriggerInfo, &MeasAuxInfo); // Get RTA data and trigger info.
			if (Status == 0)
			{
				auto stop = std::chrono::high_resolution_clock::now();
				auto timeout = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop - start);
				time_multiple += timeout.count();
		
				// UserCode here
				

				// Convert RTA spectrum data to dBm
				/*for (int i = 0; i < FrameInfo.FrameWidth; i++)
				{
					Spectrum[i] = (float)SpectrumTrace[i] * RTA_PlotInfo.ScaleTodBm + RTA_PlotInfo.OffsetTodBm;
					Frequency[i] = FrameInfo.StartFrequency_Hz + i * step;
				}*/

				
			}

			else // When Status is not 0, handle the error based on Status value.
			{

				RTA_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &RTA_ProfileIn, &RTA_ProfileOut, &FrameInfo);

			}
		}
		t++;	
	}

	time_avg = time_multiple / (FrameInfo.PacketCount * 1000); // Calculate the average time per frame.
	printf("The time taken to obtain a frame of data is as follows: %lf ms", time_avg);

	Status = RTA_BusTriggerStop(&Device); // Stop device triggering. If using external trigger, this function is not needed.

	Device_Close(&Device); // Close the device.

	return 0;
}
