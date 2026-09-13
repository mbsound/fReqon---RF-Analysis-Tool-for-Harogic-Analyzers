#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // By default, USB devices are used. If an Ethernet device is used, set IS_USB to 0.

int DSP_LPF()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specify the device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and independent power port for dual power supply.

#if IS_USB==1
	// Configure USB interface
	BootProfile.PhysicalInterface = USB;
#else 
	// Configure ETH interface
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

	IQS_Profile_TypeDef IQS_ProfileIn;  // IQS mode input configuration, including center frequency, decimation factor, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut; // IQS mode output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;  // IQ data stream-related information for the current configuration.
	IQStream_TypeDef IQStream;          // Parameters related to acquiring IQ data in the current configuration, including IQ data, ScaleToV, I_MaxValue, etc.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Call this function to initialize the configuration parameters for IQS mode.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Configure the center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Configure the reference level.
	IQS_ProfileIn.DecimateFactor = 1;		 // Configure the decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Configure IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Configure trigger mode. FixedPoints mode starts sampling on the rising edge of the trigger signal. Sampling ends after collecting TriggerLength points. Adaptive mode starts sampling on the rising edge and ends on the falling edge.
	IQS_ProfileIn.TriggerSource = Bus;       // Configure trigger source.
	IQS_ProfileIn.BusTimeout_ms = 5000;      // Configure bus timeout.
	IQS_ProfileIn.TriggerLength = 16242;     // Configure the number of sample points. This is effective only when TriggerMode is set to FixedPoints.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS mode configuration by calling this function.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors based on the return value of Status if Status is non-zero.

	vector<int16_t> AlternIQStream(StreamInfo.StreamSamples * 2); // Store IQ data, formatted as IQIQIQ...

	/* Start DSP functionality */
	void* DSP = NULL;        // Allocate memory for DSP address.
	Status = DSP_Open(&DSP); // Enable signal processing functionality.

	/* Configure low-pass filter */
	Filter_TypeDef LPF_ProfileIn;  // Parameters required for generating filter coefficients, including filter taps, cutoff frequency, stopband attenuation, etc.
	Filter_TypeDef LPF_ProfileOut; // Output filter coefficients.
	IQStream_TypeDef IQStreamOut;  // IQ data after low-pass filtering.

	DSP_LPF_DeInit(&LPF_ProfileIn); // Initialize low-pass filter configuration parameters.

	LPF_ProfileIn.As = 90;                            // Configure the stopband attenuation.
	LPF_ProfileIn.fc = 0.25;                          // Configure the cutoff frequency.
	LPF_ProfileIn.mu = 0;                             // Configure fractional sample offset.
	LPF_ProfileIn.n = 90;                             // Configure filter order.
	LPF_ProfileIn.Samples = StreamInfo.StreamSamples; // Configure number of samples.

	DSP_LPF_Configuration(&DSP, &LPF_ProfileIn, &LPF_ProfileOut); // Apply low-pass filter configuration parameters.

	/* Configure FFT parameters */
	DSP_FFT_TypeDef IQToSpectrumIn;  // Parameters required for configuring FFT mode, including FFT points, detection method, etc.
	DSP_FFT_TypeDef IQToSpectrumOut; // Feedback actual FFT parameters.
	uint32_t TracePoints = 0;        // This parameter stores the number of spectrum points after FFT.

	DSP_FFT_DeInit(&IQToSpectrumIn); // Initialize FFT configuration parameters.

	IQToSpectrumIn.Calibration = 0;                       // Configure whether to enable calibration; 0 means no calibration, other values enable calibration.
	IQToSpectrumIn.DetectionRatio = 1;                    // Configure detection ratio.
	IQToSpectrumIn.TraceDetector = TraceDetector_PosPeak; // Configure detection method.
	IQToSpectrumIn.FFTSize = StreamInfo.StreamSamples;    // Configure FFT points.
	IQToSpectrumIn.Intercept = 1;                         // Configure intercept ratio.
	IQToSpectrumIn.SamplePts = StreamInfo.StreamSamples;  // Configure number of samples.
	IQToSpectrumIn.WindowType = FlatTop;                  // Configure window type.

	double RBWRatio = 0; // This parameter returns the RBW ratio, RBW = RBWRatio * StreamInfo.IQSampleRate.

	DSP_FFT_Configuration(&DSP, &IQToSpectrumIn, &IQToSpectrumOut, &TracePoints, &RBWRatio); // Apply FFT configuration by calling this function.

	vector<double> Frequency(TracePoints); // Create an array to store frequency data.
	vector<float> Spectrum(TracePoints);   // Create an array to store amplitude data.

	// Loop to acquire and apply FFT
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

		IQStream.AlternIQStream = AlternIQStream.data();                              // Set the AlternIQStream pointer to the actual IQ data address.
		DSP_LPF_Execute_Complex(&DSP, &IQStream, &IQStreamOut);                       // Execute low-pass filtering.
		DSP_FFT_IQSToSpectrum(&DSP, &IQStreamOut, Frequency.data(), Spectrum.data()); // Execute IQ to spectrum conversion.

	}

	Status = IQS_BusTriggerStop(&Device); // Stop triggering the device with IQS_BusTriggerStop. If the trigger source is external, this function does not need to be called.

	DSP_Close(&DSP); // Close DSP functionality.
	
	Status = Device_Close(&Device); // Close the device.

	return 0;
}
