#include <stdio.h>
#include <string.h>
#include <vector>
#include <chrono>
#include <vector>
#include <iostream>
#include <cmath>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define PERCENTAGE(x, percent) ((x) * (percent) / 100)
#define IS_USB 1 // Default device is USB type. If using Ethernet device, set IS_USB to 0.

size_t findMaxPowerIndex(float* powerSpec, size_t size);                              // Function to find the index of the maximum power.
void copyArrayF(double* source, double* destination, size_t startIndex, size_t size); // Function to reset the power array.
void copyArrayP(float* source, float* destination, size_t startIndex, size_t size);   // Function to reset the frequency array.

int SWP_Meas_PhaseNoise()
{
	int Status = 0;      // Function return value.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specified device number.

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
	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is non-zero, handle the error based on the Status return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_Profile_TypeDef ProfileSetOut;  // This structure is used to feedback the automatically recommended configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under the current configuration, including trace points, hop points, etc.

	Status = SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode-related parameters.
	SWP_ProfileIn.CenterFreq_Hz = 1e9;                   // Configure center frequency.
	SWP_ProfileIn.FreqAssignment = CenterSpan;           // Frequency assignment method.
	uint8_t IfDoConfig = 1;                              // When IfDoConfig is 0, SWP_AutoSet needs to be called before SWP_Configuration; When IfDoConfig is 1, the function will automatically call SWP_Configuration, no need to call it separately.
	SWP_AutoSet(&Device, SWPPhaseNoiseMeas, &SWP_ProfileIn, &ProfileSetOut, &TraceInfo, IfDoConfig); // This function gives the recommended device configuration based on the application target for the spectrum analyzer's sweep mode (SWPMode)
	
	ProfileSetOut.RBW_Hz = 200;                                                       // Modify the recommended RBW value.
	Status = SWP_Configuration(&Device, &ProfileSetOut, &SWP_ProfileOut, &TraceInfo); // Reset recommended configuration.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement data, including: max power index, max power, device temperature, longitude, latitude, timestamp, etc.

	Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); // Get spectrum data.

	size_t maxPowerIndex = findMaxPowerIndex(PowerSpec_dBm.data(), TraceInfo.FullsweepTracePoints); // Find the peak index in the power array.
	size_t newSize = TraceInfo.FullsweepTracePoints - maxPowerIndex;                                // Determine the new array size from the peak to the end.
	vector<double> NewFrequencyArray(newSize);                                                      // Create a new frequency array for phase noise measurement.
	vector<float> NewPowerSpec_dBm(newSize);                                                        // Create a new power array for phase noise measurement.
	copyArrayF(Frequency.data(), NewFrequencyArray.data(), maxPowerIndex, newSize);                 // Copy the peak and its subsequent points from the frequency array to the new array.
	copyArrayP(PowerSpec_dBm.data(), NewPowerSpec_dBm.data(), maxPowerIndex, newSize);              // Copy the peak and subsequent points from the power array to the new array.

	SmoothMethod_TypeDef SmoothMethod;
	SmoothMethod = MovingAvrage;            // Choose smoothing and denoising technique.
	float smoothing_start_frequency = 10e3; // Set the start smoothing frequency.
	unsigned int IndexOffset = 0;           // Initialize the number of offset carrier points.
	double difference = 0;

// Traverse the frequency array to find the closest target difference.
	for (unsigned int m = 1; m < newSize; m++) 
	{
		difference = NewFrequencyArray[m] - NewFrequencyArray[0];

		// Check if the difference is less than or equal to smoothing_start_frequency and closest to the target.
		if (difference <= smoothing_start_frequency) 
		{
			IndexOffset = m; // Update the number of offset carrier points.
		} 
		else 
		{
			break;
		}
	}

	unsigned int WindowLength = PERCENTAGE(newSize, 1); // Select 1% of the points for the window length.
	unsigned int PolynomialOrder = 0;                   // Polynomial order.

	DSP_TraceSmooth(NewPowerSpec_dBm.data(), newSize, SmoothMethod, IndexOffset, WindowLength, PolynomialOrder); // Trace smoothing.

	const double OffsetFreqs[] = { 100,1000,10000,100000,1000000,10000000 }; // Frequency offset array (in Hz).
	const uint32_t OffsetFreqsToAnalysis = 6;                                // Number of offset frequency points to analyze.
	double CarrierFreqOut[OffsetFreqsToAnalysis] = { 0 };                    // Actual carrier frequencies.
	float PhaseNoiseOut_dBc[OffsetFreqsToAnalysis] = { 0 };                  // Phase noise corresponding to the frequency offsets.

	Status = DSP_TraceAnalysis_PhaseNoise(NewFrequencyArray.data(), NewPowerSpec_dBm.data(), OffsetFreqs, newSize, OffsetFreqsToAnalysis, CarrierFreqOut, PhaseNoiseOut_dBc); // Analyze the phase noise of the trace.

	// Normalize the results, normalize to per Hz
	for (int i = 0; i < 6; i++)
	{
		PhaseNoiseOut_dBc[i] -= 10 * log10(SWP_ProfileOut.RBW_Hz);
	}
	Device_Close(&Device); // Close the device.
	return 0;
}

// Function to find the index of the maximum power.
size_t findMaxPowerIndex(float* powerSpec, size_t size) {
	size_t maxIndex = 0;
	float maxValue = powerSpec[0];

	for (size_t i = 1; i < size; ++i) {
		if (powerSpec[i] > maxValue) {
			maxValue = powerSpec[i];
			maxIndex = i;
		}
	}

	return maxIndex;
}

// Implementation of function to copy the frequency array (double type).
void copyArrayF(double* source, double* destination, size_t startIndex, size_t size) {
	for (size_t i = 0; i < size; ++i) {
		destination[i] = source[startIndex + i];
	}
}

// Implementation of function to copy the power array (float type).
void copyArrayP(float* source, float* destination, size_t startIndex, size_t size) {
	for (size_t i = 0; i < size; ++i) {
		destination[i] = source[startIndex + i];
	}
}
