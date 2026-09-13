#include "htra_api.h"
#include "example.h"
#include <iostream>
#include <vector>
#include <algorithm>
#include <iomanip>
using namespace std;

#define IS_USB 1 // The default is to use a USB device. Set IS_USB to 0 if using an Ethernet device.

// By checking whether values in the data_arr array exceed the noise threshold noiseThreshold, this function searches for and records the indexes of peaks into peak_index.
void peak_seek(const vector<float>& data_arr, const float noiseThreshold, vector<int>& peak_index)
{
	bool flag = false; // Used to mark whether currently inside a peak region.
	int indexOfMax;    // Used to store the index of the current peak.

	// Traverse the data array.
	for (int i = 0; i < data_arr.size(); i++)
	{
		// If the current value is greater than the noise threshold, it might be part of a peak.
		if (data_arr[i] > noiseThreshold)
		{
			// If flag is false, it means we weren't in a peak region before, and now we are entering one.
			if (flag == false)
			{
				flag = true;    // Set flag to true, indicating we're now in a peak region.
				indexOfMax = i; // Record the index of the current peak.
			}
			else
			{
				// If already in a peak region and current value is greater than the previous max, update the index.
				if (data_arr[i] > data_arr[indexOfMax])
				{
					indexOfMax = i; // Update the current peak index.
				}
			}
		}
		else
		{
			// If current value is less than the threshold and we were in a peak region before, save the found peak index.
			if (flag == true)
			{
				flag = false;                     // Exit peak region, set flag to false.
				peak_index.push_back(indexOfMax); // Add the found peak index to the result list.
			}
		}
	}
}

// Find signals and spurs, and add corresponding frequency, power, and limit-exceeding power to ssfreq, ssSpec, and ssDelt.
void SigAndSpur(const vector<double>& Freq_Hz, const vector<float>& PowerSpec_dBm, const float limit, vector<double>& ssfreq, vector<float>& ssSpec, vector<float>& ssDelt)
{
	// Define a list to store peak indexes.
	vector<int> peak_index_list(0);

	// Call peak_seek to find peaks in the spectrum greater than the threshold limit, and return a list of their indexes.
	peak_seek(PowerSpec_dBm, limit, peak_index_list);

	// Iterate over each peak index.
	for (int i = 0; i < peak_index_list.size(); i++)
	{
		// Add the frequency corresponding to the peak to ssfreq.
		ssfreq.push_back(Freq_Hz[peak_index_list[i]]);

		// Add the power value corresponding to the peak to ssSpec.
		ssSpec.push_back(PowerSpec_dBm[peak_index_list[i]]);

		// Calculate the difference between current peak power and the threshold limit, and add the result to ssDelt.
		ssDelt.push_back(PowerSpec_dBm[peak_index_list[i]] - limit);
	}
}


int SWP_GetSpectrum_SigAndSpur(void)
{
	int Status = 0;      // Function return status.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Device index number.

	BootProfile_TypeDef BootProfile; // Boot profile including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot information including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and separate power supply.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is not 0, handle error based on return value.

	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration including start/stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information under current configuration, including trace points, hop points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP-related parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Configure start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Configure stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;       // Configure RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Send SWP configuration to device.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle configuration errors if Status is not 0.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power spectrum array.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement info, including: max power index, value, temperature, GPS, timestamp, etc.

	SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); // Acquire spectrum data.

	SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors except for open/config.

	vector<double> ssfreq(0); // Store frequencies of peaks (unit: Hz).
	vector<float> ssSpec(0);  // Store power values of peaks (unit: dBm).
	vector<float> ssDelt(0);  // Store differences between peak power and threshold (unit: dB).

	SigAndSpur(Frequency, PowerSpec_dBm, -76.0f, ssfreq, ssSpec, ssDelt); // Get peaks with power greater than -76.0 dBm.

	int sigIndex = distance(ssDelt.begin(), max_element(ssDelt.begin(), ssDelt.end())); // Get index of the peak with the maximum delta.

	cout << "index\t" << "frequency\t" << "power\t\t" << "Δlimit" << endl; // Print table header: index, frequency, power, delta.

	for (int i = 0; i < ssDelt.size(); i++) // Loop through all peak deltas and print peak info.
	{
		if (i == sigIndex) // If current peak has the maximum delta, highlight it in yellow.
		{
			cout << "\033[1;33m"; // Set text color to yellow.
			cout << i << "\t";    // Print peak index.

			cout.setf(ios::fixed);                                         // Set fixed-point format.
			cout << fixed << setprecision(9) << ssfreq[i] / 1e9 << "GHz\t";
			cout.unsetf(ios::fixed);                                       // Unset fixed-point format.

			cout << fixed << setprecision(2) << ssSpec[i] << "dBm\t";      // Print peak power in dBm with 2 decimal places.

			cout << fixed << setprecision(2) << ssDelt[i] << "dB" << endl; // Print delta between peak and threshold with 2 decimal places.
			cout << "\033[m";  // Reset text color.
		}
		else
		{
			cout << i << "\t"; // For non-maximum peak, print in normal format.

			cout.setf(ios::fixed);                                          // Print peak frequency in GHz with 9 decimal places.
			cout << fixed << setprecision(9) << ssfreq[i] / 1e9 << "GHz\t";
			cout.unsetf(ios::fixed);                                        // Unset fixed-point format.

			cout << fixed << setprecision(2) << ssSpec[i] << "dBm\t";       // Print peak power in dBm with 2 decimal places.

			cout << fixed << setprecision(2) << ssDelt[i] << "dB" << endl;  // Print delta between peak and threshold with 2 decimal places.
		}
	}

	Device_Close(&Device); // Close the device.

	return 0;
}
