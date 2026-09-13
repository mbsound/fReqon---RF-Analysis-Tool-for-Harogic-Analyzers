#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <map>
#include "htra_api.h"
#include "example.h"
#include <ctime>
#include <thread>
#include <iomanip> 
#define EXAMPLE_MACRO_NAME
using namespace std;

/*README
For connection and use of the EIO expansion board, please refer to the GNSS module sections in the "SA NX Series Spectrum Analyzer User Guide".
*/

// Convert UTC time to Singapore time
void UtcToSingaporeTime(int16_t& hour_var, int16_t& minute_var, int16_t& second_var,
	int16_t& year_var, int16_t& month_var, int16_t& day_var) {
	// Create tm structure to assist with conversion
	struct tm utc_tm = {};
	// Set values in tm structure, note the year and month range requirements
	utc_tm.tm_year = year_var - 1900;  // tm structure year needs to be offset by 1900
	utc_tm.tm_mon = month_var - 1;      // Months start from 0 in tm structure
	utc_tm.tm_mday = day_var;
	utc_tm.tm_hour = hour_var;
	utc_tm.tm_min = minute_var;
	utc_tm.tm_sec = second_var;
	// Convert tm structure to time_t type
	time_t utc_time = mktime(&utc_tm);
	// Add 8 hours (Singapore is 8 hours ahead of UTC)
	utc_time += 8 * 60 * 60;
	// Use localtime_s instead of localtime
	struct tm Singapore_tm;
	if (localtime_r (&utc_time, &Singapore_tm)!=nullptr) {
		// Update original variables with Singapore time values, handling possible date changes
		hour_var = Singapore_tm.tm_hour;
		minute_var = Singapore_tm.tm_min;
		second_var = Singapore_tm.tm_sec;
		// Update year, month, and day; note that tm structure year needs to be adjusted back by adding 1900, and months need to be converted back from 0-based
		year_var = Singapore_tm.tm_year + 1900;
		month_var = Singapore_tm.tm_mon + 1;
		day_var = Singapore_tm.tm_mday;
	}
	else {
		// Handle error situation
		std::cerr << "Error converting UTC to Singapore Time!" << std::endl;
	}
}

// Convert floating-point longitude or latitude to DMS format string
string ConvertTODMSFormat(float coordinate) {
	int degrees = static_cast<int>(coordinate);
	float minutesFloat = (coordinate - degrees) * 60;
	int minutes = static_cast<int>(minutesFloat);
	float seconds = (minutesFloat - minutes) * 60;

	std::stringstream ss;
	ss << std::abs(degrees) << "°" << minutes << "'" << std::fixed << std::setprecision(2) << seconds << "''";

	return ss.str();
}

#define IS_USB 1 // Default is USB device, change to 0 if using Ethernet device.

// GNSS Reference Clock for SWP
int SWP_GNSSReferenceClock()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specify the device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB speed, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Dual power supply using USB data port and independent power port.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Handle errors if Status is not 0.

	/* Set GNSS external antenna */
	GNSSAntennaState_TypeDef GNSSAntennaState; // Initialize GNSS antenna information
	GNSSAntennaState = GNSS_AntennaExternal;   // Set to external antenna

	// Set GNSS antenna state
	Status = Device_SetGNSSAntennaState(&Device, GNSSAntennaState); // Send GNSS antenna configuration

	GNSSInfo_TypeDef GNSSInfo = { 0 }; // GNSS information for the current antenna configuration

	// Output the current GNSS lock state every second until the device locks onto the GNSS module
	while (!GNSSInfo.GNSS_LockState)
	{
		Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo);				// Get real-time GNSS device status
		cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl; // Output GNSS antenna lock state GNSS_LockState=1 means locked
		this_thread::sleep_for(chrono::milliseconds(1000));					    // Delay for 1 second
	}

	DOCXOWorkMode_TypeDef DOCXOWorkMode; // Configure DOCXO antenna state
	DOCXOWorkMode = DOCXO_LockMode;

	/* Set and get DOCXO status */
	uint16_t HardwareVersion = BootInfo.DeviceInfo.HardwareVersion;
	uint16_t OCXO_Enable = (HardwareVersion >> 10) & 0x3;

	if (OCXO_Enable)
	{
		Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); // Set DOCXO work mode in GNSS

		auto start_time = std::chrono::high_resolution_clock::now(); // Get current time

		Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo); // Get GNSS device status

		// Check lock state
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
				Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo); // Get GNSS device status

				// Check lock state
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
					Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); // Set DOCXO work mode in GNSS
				}
				// Print current GNSS_LockState status
				cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;

				// Print current DOCXO_LockState status
				cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;

				// Check timeout: if more than 180 seconds
				auto current_time = std::chrono::high_resolution_clock::now();
				auto duration = std::chrono::duration_cast<std::chrono::duration<double, std::ratio<1, 1>>>(current_time - start_time);
				// If timeout exceeds 600 seconds, exit loop
				if (duration.count() > 600)
				{
					cout << "The DOCXO is not locked, please check whether the cable connection is normal." << endl;
					break;
					return 0;
				}
				this_thread::sleep_for(chrono::milliseconds(1000)); // Delay for 1 second
			}
			cout << "DOCXO is locked!" << endl;
		}
	}

		
	SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
	SWP_TraceInfo_TypeDef TraceInfo;    // Trace information for the current configuration, including trace points, hop points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP configuration related parameters.

	SWP_ProfileIn.StartFreq_Hz = 9e3;                                           // Set start frequency
	SWP_ProfileIn.StopFreq_Hz = 6.35e9;                                         // Set stop frequency
	SWP_ProfileIn.RBW_Hz = 300e3;                                               // Set RBW
	SWP_ProfileIn.ReferenceClockSource = ReferenceClockSource_Internal_Premium; // Set GNSS 10 MHz reference clock (only for high-quality GNSS module)
	SWP_ProfileIn.ReferenceClockFrequency = 10e6;                               // Set reference clock frequency

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Apply SWP configuration

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors if Status is not 0.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);    // Create frequency array.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints); // Create power array.
	int HopIndex = 0;                                            // Current hop index.
	int FrameIndex = 0;                                          // Current frame index.
	MeasAuxInfo_TypeDef MeasAuxInfo;                             // Auxiliary measurement information, including max power index, max power, device temperature, longitude, latitude, absolute timestamp, etc.

	for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops represents the number of frames for the current configuration, loop through it to get the full trace by calling SWP_GetPartialSweep.
	{
		Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Get spectrum data.

		if (Status == APIRETVAL_NoError)
		{
			// UserCode here
			double time_stamp;
			time_stamp = MeasAuxInfo.AbsoluteTimeStamp;                                                                       // Get current absolute timestamp in seconds
			int16_t hour_var, minute_var, second_var, year_var, month_var, day_var;
			Status = Device_AnysisGNSSTime(time_stamp, &hour_var, &minute_var, &second_var, &year_var, &month_var, &day_var); // Convert to UTC time (parsed as UTC time)
			UtcToSingaporeTime(hour_var, minute_var, second_var, year_var, month_var, day_var);								  // Convert UTC time to Singapore time
		
			cout << year_var << "/" << month_var << "/" << day_var << " " << hour_var << ":" << minute_var << ":" << second_var << endl;
		}

		else
		{
			SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
		}
	}

	Device_Close(&Device);
	return 0;
}
