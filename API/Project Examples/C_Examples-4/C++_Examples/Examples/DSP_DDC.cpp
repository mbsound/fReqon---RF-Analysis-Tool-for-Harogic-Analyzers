#include <stdio.h>
#include <string.h>
#include <vector>
#include <iostream>
#include "htra_api.h" 
#include "example.h"
using namespace std;

#define IS_USB 1 // Assume USB by default; if using Ethernet interface, add a comment for this line of code.

int DSP_DDC()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specify the device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB speed, etc.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is non-zero, handle errors based on the return value of Status.

	IQS_Profile_TypeDef IQS_ProfileIn;  // Input configuration for IQS mode, including center frequency, decimation factor, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // Output configuration for IQS mode.
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ data stream-related information for the current configuration.
	IQStream_TypeDef IQStream;          // Parameters related to acquiring IQ data in the current configuration, including IQ data, ScaleToV, I_MaxValue, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize IQS mode configuration parameters by calling this function.

	// Set parameter configurations
	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Configure the center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Configure reference level.
	IQS_ProfileIn.DecimateFactor = 1;	     // Configure decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Configure IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Configure trigger mode. FixedPoints mode starts sampling on the rising edge of the trigger signal, and ends sampling after collecting TriggerLength points. Adaptive mode starts sampling on the rising edge and ends sampling on the falling edge.
	IQS_ProfileIn.TriggerSource = Bus;       // Configure trigger source.
	IQS_ProfileIn.BusTimeout_ms = 5000;      // Configure bus timeout.
	IQS_ProfileIn.TriggerLength = 16280;     // Configure the number of sample points. This is effective only when TriggerMode is set to FixedPoints.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS mode configurations by calling this function.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors based on the return value of Status if Status is non-zero.

	vector<int16_t> AlternIQStream(StreamInfo.StreamSamples * 2); // Store IQ data in the format of IQIQIQ...

	/* Start DSP functionality */
	void* DSP = NULL;        // Allocate memory for digital signal processing address
	Status = DSP_Open(&DSP); // Enable signal processing functionality

	/* Configure DDC mode */
	DSP_DDC_TypeDef DDC_ProfileIn;  // Input configuration parameters for DDC mode, including frequency offset, sampling rate, number of samples, etc.
	DSP_DDC_TypeDef DDC_ProfileOut; // Output configuration parameters for DDC mode.
	IQStream_TypeDef IQStreamOut;   // IQ-related data after DDC (configuration, return info, and temporary data).

	Status = DSP_DDC_DeInit(&DDC_ProfileIn); // Initialize DDC mode configuration parameters by calling this function.

	DDC_ProfileIn.DDCOffsetFrequency = 10e6;                               // Configure the frequency offset for DDC.
	DDC_ProfileIn.DecimateFactor = 2;                                      // Configure the decimation factor for DDC.
	DDC_ProfileIn.SamplePoints = StreamInfo.StreamSamples;                 // Configure the number of samples.
	DDC_ProfileIn.SampleRate = StreamInfo.IQSampleRate;                    // Configure the sampling rate.
	Status = DSP_DDC_Configuration(&DSP, &DDC_ProfileIn, &DDC_ProfileOut); // Apply DDC mode configurations by calling this function.

	// FFT mode configuration
	DSP_FFT_TypeDef IQToSpectrumIn;  // FFT mode input parameters, including FFT points, detection method, etc.
	DSP_FFT_TypeDef IQToSpectrumOut; // FFT mode output parameters.
	uint32_t TracePoints = 0;        // Store the number of frequency spectrum points after FFT.

	DSP_FFT_DeInit(&IQToSpectrumIn); // Initialize FFT mode configuration parameters by calling this function.

	IQToSpectrumIn.Calibration = 0;                         // Configure whether calibration is enabled; 0 means no calibration, other values mean calibration is enabled.
	IQToSpectrumIn.DetectionRatio = 1;                      // Configure the detection ratio.
	IQToSpectrumIn.TraceDetector = TraceDetector_PosPeak;   // Configure the detection method.
	IQToSpectrumIn.FFTSize = DDC_ProfileOut.SamplePoints;   // Configure the number of FFT points.
	IQToSpectrumIn.Intercept = 0.8;                           // Configure intercept ratio.
	IQToSpectrumIn.SamplePts = DDC_ProfileOut.SamplePoints; // Configure the number of samples.
	IQToSpectrumIn.WindowType = FlatTop;                    // Configure the window type.

	double RBWRatio = 0; // Return the RBW ratio, RBW = RBWRatio * StreamInfo.IQSampleRate.

	DSP_FFT_Configuration(&DSP, &IQToSpectrumIn, &IQToSpectrumOut, &TracePoints, &RBWRatio); // Apply FFT mode configurations by calling this function.

	vector<double> Frequency(TracePoints); // Store the frequency array.
	vector<float> Spectrum(TracePoints);   // Store the power array.

	// Loop to acquire and process data with FFT.
	while (1)
	{
		Status = IQS_BusTriggerStart(&Device); // Trigger the device using IQS_BusTriggerStart. If the trigger source is external, this function does not need to be called.

		uint32_t IQPoints = 0;
		for (int i = 0; i < StreamInfo.PacketCount; i++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data.

			if (Status == APIRETVAL_NoError)
			{
				if (i != StreamInfo.PacketCount - 1) // If the current packet is not the last one.
				{
					memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * StreamInfo.PacketSamples);
					IQPoints += StreamInfo.PacketSamples * 2;
				}

				else // If the current packet is the last one.
				{
					if (StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) // If the last IQ data packet is not a full packet.
					{
						memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * (StreamInfo.StreamSamples % StreamInfo.PacketSamples));
					}

					else // If the last IQ data packet is a full packet.
					{
						memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * StreamInfo.PacketSamples);
					}
				}

			}
			else // If Status is non-zero, handle errors based on the return value of Status.
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
			}

		}
		IQStream.AlternIQStream = AlternIQStream.data(); // Set the AlternIQStream pointer to the actual IQ data address.
		IQStream.IQS_StreamInfo.PacketSamples = IQStream.IQS_StreamInfo.StreamSamples;

		Status = DSP_DDC_Execute(&DSP, &IQStream, &IQStreamOut);                               // Execute DDC.
		Status = DSP_FFT_IQSToSpectrum(&DSP, &IQStreamOut, Frequency.data(), Spectrum.data()); // Execute IQ to Spectrum conversion.

	}
	Status = IQS_BusTriggerStop(&Device); // Stop the trigger with IQS_BusTriggerStop. If the trigger source is external, this function does not need to be called.

	DSP_Close(&DSP); // Close DSP functionality.
	Status = Device_Close(&Device); // Close the device.
	return 0;
}
