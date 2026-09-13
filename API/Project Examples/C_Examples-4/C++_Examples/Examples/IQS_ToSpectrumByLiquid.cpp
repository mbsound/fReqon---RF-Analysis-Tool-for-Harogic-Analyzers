#include <stdio.h>
#include <string.h>
#include <vector>
#include <complex>
#ifdef _WIN32
#define _LIBCPP_COMPLEX
#endif // DEBUG
#include "liquid.h"
#include "htra_api.h" 
#include "example.h"
using namespace std;

#define PI acos(-1)
#define IS_USB 1 // Default is USB device. If using Ethernet device, set IS_USB to 0.

void DSP_GetWindow(Window_TypeDef Window, int n, double Window_Coefficient[])
{
	if (n >= 0)
	{
		switch (Window)
		{
		case 0:/*flat top window*/
		{
			const double a0 = 0.21557895;
			const double a1 = 0.41663158;
			const double a2 = 0.277263158;
			const double a3 = 0.083578947;
			const double a4 = 0.006947368;
			for (int i = 0; i < n; i++)
			{
				double b1 = cos(1 * (2 * PI * i / n));
				double b2 = cos(2 * (2 * PI * i / n));
				double b3 = cos(3 * (2 * PI * i / n));
				double b4 = cos(4 * (2 * PI * i / n));
				Window_Coefficient[i] = (a0 - a1 * b1 + a2 * b2 - a3 * b3 + a4 * b4);//Normalized
			}
			break;
		}
		default:
			for (int i = 0; i < n; i++)
			{
				Window_Coefficient[i] = 1;
			}
			break;
		}
	}
}

int FFT_IQSToSpectrum(const IQStream_TypeDef* IQStream, double Freq_Hz[], float PowerSpec_dBm[])
{
	int Status = 0;

	DataFormat_TypeDef DataFormat;
	DataFormat = Complex16bit;

	Window_TypeDef Window;
	Window = FlatTop;
	vector<double> Window_Coefficient(IQStream->IQS_StreamInfo.StreamSamples);

	DSP_GetWindow(Window, IQStream->IQS_StreamInfo.StreamSamples, Window_Coefficient.data());

	int16_t* IQ = (int16_t*)IQStream->AlternIQStream;
	vector<double> IQ_Windowing(IQStream->IQS_StreamInfo.StreamSamples * 2);
	vector<double> I_Windowed(IQStream->IQS_StreamInfo.StreamSamples);
	vector<double> Q_Windowed(IQStream->IQS_StreamInfo.StreamSamples);

	for (uint32_t i = 0; i < IQStream->IQS_StreamInfo.StreamSamples; i++)
	{
		I_Windowed[i] = IQ[i * 2] * Window_Coefficient[i];
		Q_Windowed[i] = IQ[i * 2 + 1] * Window_Coefficient[i];
	}

	//FFT
	vector<std::complex<float>> x(IQStream->IQS_StreamInfo.StreamSamples);
	vector<std::complex<float>> y(IQStream->IQS_StreamInfo.StreamSamples);

	for (uint32_t i = 0; i < IQStream->IQS_StreamInfo.StreamSamples; i++)
	{
		x[i].real(I_Windowed[i]);
		x[i].imag(Q_Windowed[i]);
	}

	fftplan plan = fft_create_plan(IQStream->IQS_StreamInfo.StreamSamples, x.data(), y.data(), LIQUID_FFT_FORWARD, 0); // Issue configuration
	fft_execute(plan);                                                                                                 // Execute FFT

	for (uint32_t i = 0; i < IQStream->IQS_StreamInfo.StreamSamples; i++)
	{
		PowerSpec_dBm[i] = 10 * log10(pow(y[i].real(), 2) + pow(y[i].imag(), 2)) + 10 * log10(20) - 20 * log10(IQStream->IQS_StreamInfo.StreamSamples) + 13.3279 + 20 * log10(IQStream->IQS_ScaleToV);
		double step = IQStream->IQS_StreamInfo.IQSampleRate / (IQStream->IQS_StreamInfo.StreamSamples - 1);
		Freq_Hz[i] = IQStream->IQS_Profile.CenterFreq_Hz - (IQStream->IQS_StreamInfo.IQSampleRate / 2) + i * step;
	}

	double temp = 0;
	for (int i = 0; i < IQStream->IQS_StreamInfo.StreamSamples / 2; i++)
	{
		temp = PowerSpec_dBm[i];
		PowerSpec_dBm[i] = PowerSpec_dBm[IQStream->IQS_StreamInfo.StreamSamples / 2 + i];
		PowerSpec_dBm[IQStream->IQS_StreamInfo.StreamSamples / 2 + i] = temp;
	}

	fft_destroy_plan(plan);
	return Status;
}


int IQS_ToSpectrumByLiquid()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specify the device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
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

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle the error based on Status

	IQStream_TypeDef IQStream;         // Store IQ data related parameters, including IQ data, ScaleToV, I_MaxValue, etc.
	IQS_Profile_TypeDef IQSIn;         // IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	IQS_Profile_TypeDef IQSOut;        // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo; // Current IQ stream information, including bandwidth, IQ single-rate sampling, etc.

	Status = IQS_ProfileDeInit(&Device, &IQSIn); // Initialize IQS mode related parameters.

	IQSIn.CenterFreq_Hz = 1e9;					// Set center frequency.        
	IQSIn.RefLevel_dBm = 0;						// Set reference level.
	IQSIn.DataFormat = Complex16bit;			// Set IQ data format.
	IQSIn.TriggerMode = FixedPoints;			// Set trigger mode.
	IQSIn.TriggerSource = Bus;					// Set trigger source as internal bus trigger.
	IQSIn.DecimateFactor = 2;					// Set decimation factor.
	IQSIn.BusTimeout_ms = 5000;					// Set bus timeout.
	IQSIn.TriggerLength = 16242;				// Set sample points.
	//IQSIn.DCCancelerMode = DCCAutoOffsetMode;	// For decimation mode, enable high-pass filter and automatic offset to avoid DC drift.

	Status = IQS_Configuration(&Device, &IQSIn, &IQSOut, &StreamInfo); // Issue IQS mode configuration.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQSIn, &IQSOut, &StreamInfo); // Handle errors based on Status if not 0

	vector<int16_t> AlternIQStream(StreamInfo.StreamSamples * 2); // Create an array to store IQ data, format as IQIQIQ...
	vector<double> Frequency(StreamInfo.StreamSamples);           // Create an I data array.
	vector<float> Spectrum(StreamInfo.StreamSamples);             // Create a Q data array.

	// Loop to fetch and perform FFT
	while (1)
	{
		Status = IQS_BusTriggerStart(&Device); // Trigger the device using IQS_BusTriggerStart.

		uint32_t IQPoints = 0;
		for (int i = 0; i < StreamInfo.PacketCount; i++)
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data.
			if (Status == APIRETVAL_NoError)
			{
				if (i != StreamInfo.PacketCount - 1) // When the current packet is not the last packet.
				{
					memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * StreamInfo.PacketSamples);
					IQPoints += StreamInfo.PacketSamples * 2;
				}
				else // When the current packet is the last packet.
				{
					if (StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0) // If the last IQ data packet is not full.
					{
						memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * (StreamInfo.StreamSamples % StreamInfo.PacketSamples));
					}
					else // If the last IQ data packet is full.
					{
						memcpy(AlternIQStream.data() + IQPoints, IQStream.AlternIQStream, sizeof(int16_t) * 2 * StreamInfo.PacketSamples);
					}
				}
			}

			else // Handle errors based on Status if not 0.
			{
				IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQSIn, &IQSOut, &StreamInfo);
			}
		}
		float ScaleToV = IQStream.IQS_ScaleToV;
		IQStream.AlternIQStream = AlternIQStream.data();                 // Point AlternIQStream to the actual IQ data address.
		FFT_IQSToSpectrum(&IQStream, Frequency.data(), Spectrum.data()); // Perform IQ to spectrum conversion.
	}

	Status = IQS_BusTriggerStop(&Device); // Stop triggering the device using IQS_BusTriggerStop.

	Status = Device_Close(&Device); // Close the device.

	return 0;
} 
