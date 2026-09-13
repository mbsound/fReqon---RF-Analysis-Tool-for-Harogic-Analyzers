#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <map>
#include "htra_api.h"
#include "example.h"
#include <ctime>
#include<thread>
#include <iomanip> 
#define EXAMPLE_MACRO_NAME
using namespace std;

/*README
For the connection and usage of the EIO expansion board, please refer to the relevant chapters on the GNSS module in the "SA NX Series Spectrum Analyzer User Guide."
*/

#define IS_USB 1 // The default device is USB. If the Ethernet device is used, set IS_USB to 0.

// Convert UTC time to Singapore Time.
void utcToSingaporeTime(int16_t& hour_var, int16_t& minute_var, int16_t& second_var,
    int16_t& year_var, int16_t& month_var, int16_t& day_var) {
    // Create a tm structure to assist with the conversion.
    struct tm utc_tm = {};
    // Set the fields of the tm structure, noting the required ranges for year and month.
    utc_tm.tm_year = year_var - 1900; // Year in tm structure needs to be subtracted by 1900.
    utc_tm.tm_mon = month_var - 1;    // Month is counted from 0 in tm structure.
    utc_tm.tm_mday = day_var;
    utc_tm.tm_hour = hour_var;
    utc_tm.tm_min = minute_var;
    utc_tm.tm_sec = second_var;
    // Convert tm structure to time_t type.
    time_t utc_time = mktime(&utc_tm);
    // Add 8 hours (Singapore Time is UTC + 8 hours).
    utc_time += 8 * 60 * 60;
    // Use localtime_s instead of localtime.
    struct tm Singapore_tm;
    if (localtime_r(&utc_time,&Singapore_tm)!=nullptr) {
        // Update original variables with Singapore Time values, and handle possible date changes.
        hour_var = Singapore_tm.tm_hour;
        minute_var = Singapore_tm.tm_min;
        second_var = Singapore_tm.tm_sec;
        // Update year, month, and day. Note that year needs to add 1900, and month needs to be converted back to normal counting.
        year_var = Singapore_tm.tm_year + 1900;
        month_var = Singapore_tm.tm_mon + 1;
        day_var = Singapore_tm.tm_mday;
    }
    else {
        // Handle error case.
        std::cerr << "Error converting UTC to Singapore Time!" << std::endl;
    }
}

// Convert floating-point longitude or latitude to DMS format string.
string ConvertToDMSFormat(float coordinate) {
    int degrees = static_cast<int>(coordinate);
    float minutesFloat = (coordinate - degrees) * 60;
    int minutes = static_cast<int>(minutesFloat);
    float seconds = (minutesFloat - minutes) * 60;

    std::stringstream ss;
    ss << std::abs(degrees) << "°" << minutes << "'" << std::fixed << std::setprecision(2) << seconds << "''";

    return ss.str();
}

int Device_AboutGNSS()
{
    int Status = 0;      // Function return status.
    void* Device = NULL; // Current device memory address.
    int DevNum = 0;      // Specify device number.

    BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply mode, etc.
    BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

    BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and separate power port for dual power supply.

#if IS_USB == 1
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

    Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Handle errors based on the Status return value.

    /* Set GNSS external antenna */
    GNSSAntennaState_TypeDef GNSSAntennaState; // GNSS antenna state for startup.
    GNSSAntennaState = GNSS_AntennaExternal;   // Configure external antenna.

    // Set GNSS antenna state
    Status = Device_SetGNSSAntennaState(&Device, GNSSAntennaState); // Send GNSS antenna configuration.

    GNSSInfo_TypeDef GNSSInfo = {0}; // GNSS information under the current antenna configuration.

    // Output GNSS lock state every 1 second until the device successfully locks the GNSS module.
    while (!GNSSInfo.GNSS_LockState)
    {
        Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo);  // Get GNSS device status in real-time.
        cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl; // Output GNSS antenna lock state: GNSS_LockState=1 means locked.
        this_thread::sleep_for(chrono::milliseconds(1000));          // Delay for 1 second.
    }

    DOCXOWorkMode_TypeDef DOCXOWorkMode; // DOCXO antenna work mode configuration.
    DOCXOWorkMode = DOCXO_LockMode;

    /* Set and get DOCXO state */
    uint16_t HardwareVersion = BootInfo.DeviceInfo.HardwareVersion;
    uint16_t OCXO_Enable = (HardwareVersion >> 10) & 0x3;    // Check if OCXO is enabled based on hardware version.
    
    if (OCXO_Enable)
    {
        Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); // Set DOCXO work mode for GNSS.

        auto start_time = std::chrono::high_resolution_clock::now(); // Record the current time.

        Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo); // Get GNSS device status.

        // Check lock state
        if (GNSSInfo.DOCXO_LockState)
        {
            cout << endl;
            // Print current GNSS_LockState.
            cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;
            // Print current DOCXO_LockState.
            cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;
        }
        else
        {
            while (1)
            {
                Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo); // Get GNSS device status.

                // Check lock state
                if (GNSSInfo.DOCXO_LockState == 1 && GNSSInfo.GNSS_LockState == 1)
                {
                    cout << endl;
                    // Print current GNSS_LockState.
                    cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;
                    // Print current DOCXO_LockState.
                    cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;
                    break;
                }
                if (GNSSInfo.GNSS_LockState == 0)
                {
                    DOCXOWorkMode = DOCXO_LockMode;
                    Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); // Set DOCXO work mode for GNSS.
                }
                // Print current GNSS_LockState.
                cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;

                // Print current DOCXO_LockState.
                cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;

                // Check timeout: Has it exceeded 180 seconds?
                auto current_time = std::chrono::high_resolution_clock::now();
                auto duration = std::chrono::duration_cast<std::chrono::duration<double, std::ratio<1, 1>>>(current_time - start_time);
                // If timeout exceeds 600 seconds, break the loop.
                if (duration.count() > 600)
                {
                    cout << "DOCXO is not locked, please check the cable connection." << endl;
                    break;
                    return 0;
                }
                this_thread::sleep_for(chrono::milliseconds(1000)); // Delay for 1 second.
            }
            cout << "DOCXO is locked!" << endl;
        }
    }

    // Get GNSS time information.
    cout << "Singapore Time:" << endl;
    cout << GNSSInfo.Year << "/" << GNSSInfo.month << "/" << GNSSInfo.day << " " << GNSSInfo.hour + 8 << ":" << GNSSInfo.minute << ":" << GNSSInfo.second << endl;
    
    // Convert longitude and latitude to DMS format strings.
    string longitudeDMS_GN = ConvertToDMSFormat(GNSSInfo.latitude);   
    string latitudeDMS_GN = ConvertToDMSFormat(GNSSInfo.longitude);

    // Get GNSS latitude and longitude.
    cout << "Current Longitude :" << longitudeDMS_GN << endl;
    cout << "Current Latitude : " << latitudeDMS_GN << endl;

    // Get GNSS altitude information.
    cout << "Current altitude : " << GNSSInfo.altitude << endl;

    // Get GNSS satellite signal-to-noise ratio information.
    GNSS_SatDate_TypeDef GNSS_SatDate;

    Status = Device_GetGNSS_SatDate_Realtime(&Device, &GNSS_SatDate);
    cout << "Average signal-to-noise ratio: " << (int)GNSS_SatDate.GNSS_SNR_UsePos.Max_SatxC_No << endl; // Get the maximum signal-to-noise ratio of the positioning satellite.
    cout << "Average signal-to-noise ratio: " << (int)GNSS_SatDate.GNSS_SNR_UsePos.Min_SatxC_No << endl; // Get the minimum signal-to-noise ratio of the positioning satellite.
    cout << "Average signal-to-noise ratio: " << (int)GNSS_SatDate.GNSS_SNR_UsePos.Avg_SatxC_No << endl; // Get the average signal-to-noise ratio of the positioning satellite.

#define IS_SWP 1  // Default assumption: Get the absolute timestamp for SWP mode. If the absolute timestamp for IQS mode is needed, set IS_SWP to 0.

#if IS_SWP==1
	/*--------------------------------------------------Parse the Absolute TimeStamp in the MeasAuxInfo structure obtained from SWP_GetFullSweep---------------------------------------------------*/

	SWP_Profile_TypeDef SWP_ProfileIn;  // Configure SWP mode parameters, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_Profile_TypeDef SWP_ProfileOut; // Feedback the actual configured SWP mode parameters, including start frequency, stop frequency, RBW, reference level, etc.
	SWP_TraceInfo_TypeDef TraceInfo;    // Feedback trace information under the current configuration, including trace points, frequency modulation points, etc.

	SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize the SWP mode parameters by calling this function.

	SWP_ProfileIn.StartFreq_Hz = 9e3;   // Set the start frequency.
	SWP_ProfileIn.StopFreq_Hz = 6.35e9; // Set the stop frequency.
	SWP_ProfileIn.RBW_Hz = 300e3;       // Set the RBW.

	Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Configure SWP mode by calling this function.

	SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors if Status is not 0.

	vector<double> Frequency(TraceInfo.FullsweepTracePoints);         // Dynamically allocate array to store the full frequency data.
	vector<float> PowerSpec_dBm(TraceInfo.FullsweepTracePoints);      // Dynamically allocate array to store the full amplitude data.
	MeasAuxInfo_TypeDef MeasAuxInfo;                                  // Structure to store auxiliary measurement data.

	Status = SWP_GetFullSweep(&Device, Frequency.data(), PowerSpec_dBm.data(), &MeasAuxInfo); // Get the spectrum data.

	SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Handle errors if Status is not 0.

	double time_stamp; 
	time_stamp = MeasAuxInfo.AbsoluteTimeStamp;                                                                       // Get the current absolute timestamp in seconds.
	int16_t hour_var, minute_var, second_var, year_var, month_var, day_var;
	Status = Device_AnysisGNSSTime(time_stamp, &hour_var, &minute_var, &second_var, &year_var, &month_var, &day_var); // Convert to UTC time (parse as UTC time).
	utcToSingaporeTime(hour_var, minute_var, second_var, year_var, month_var, day_var);								  // Convert UTC to Singapore Time.

	cout << year_var << "/" << month_var << "/" << day_var << " " << hour_var << ":" << minute_var << ":" << second_var << endl; // Output Singapore Time.

#else

	/*--------------------------------------------------Parse the Absolute TimeStamp in DeviceState obtained from IQS_GetIQStream_PM1---------------------------------------------------*/
	/*Initialize configuration*/
	IQS_Profile_TypeDef IQS_ProfileIn;                     // Configure IQS mode parameters.
	IQS_Profile_TypeDef IQS_ProfileOut;                    // Feedback the actual configured IQS mode parameters.
	IQS_StreamInfo_TypeDef StreamInfo;                     // Feedback IQ stream related information under the current configuration.

	Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn);   // Initialize IQS mode parameters by calling this function.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Set the center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Set the reference level.
	IQS_ProfileIn.DecimateFactor = 2;		 // Set the decimation factor.
	IQS_ProfileIn.DataFormat = Complex16bit; // Set IQ data format.
	IQS_ProfileIn.TriggerMode = FixedPoints; // Set the trigger mode. FixedPoints mode starts sampling on the rising edge of the trigger signal, ending after TriggerLength points. Adaptive mode starts on the rising edge and ends on the falling edge.
	IQS_ProfileIn.TriggerSource = Bus;       // Set the trigger source as the 1PPS signal provided by the GNSS system.
	IQS_ProfileIn.TriggerLength = 16384;     // Set the number of points to capture in one trigger. This is only effective when TriggerMode is set to FixedPoints.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Configure IQS mode by calling this function.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors if Status is not 0.

	/*Get IQ data*/
	IQStream_TypeDef IQStream; // Store IQ data packet (IQ data and related configuration information).
	bool tag = false;		   // When IQS_ProfileIn.TriggerMode = Adaptive, control the trigger once before getting data.

	vector<int16_t> I_Data(StreamInfo.StreamSamples); // Allocate memory to store I-channel data in FixedPoints mode.
	vector<int16_t> Q_Data(StreamInfo.StreamSamples); // Allocate memory to store Q-channel data in FixedPoints mode.

	if (IQS_ProfileIn.TriggerMode == Adaptive)
	{
		I_Data.resize(StreamInfo.PacketSamples);  // Resize I_Data to store I-channel data in Adaptive mode.
		Q_Data.resize(StreamInfo.PacketSamples);  // Resize Q_Data to store Q-channel data in Adaptive mode.
	}


	if (IQS_ProfileOut.TriggerMode == Adaptive && tag != true) // Trigger only once when IQS_ProfileIn.TriggerMode = Adaptive.
	{
		Status = IQS_BusTriggerStart(&Device);                 // Trigger the device with IQS_BusTriggerStart. If the trigger source is external, this function is not needed.
		tag = true;
	}
	if (IQS_ProfileOut.TriggerMode == FixedPoints)             // Trigger on every iteration when IQS_ProfileIn.TriggerMode = FixedPoints.
	{
		Status = IQS_BusTriggerStart(&Device);                 // Trigger the device if the trigger source is external.
	}
	/*Get IQ data*/
	for (int j = 0; j < StreamInfo.PacketCount; j++)		   // This only works when TriggerMode is FixedPoints. It doesn't work with Adaptive mode. StreamInfo.PacketCount equals 1 in that case.
	{
		Status = IQS_GetIQStream_PM1(&Device, &IQStream);      // Get IQ data packet, trigger info, and I-channel data maximum value and its index.

		IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors if Status is not 0.
	}

	/*Extract timestamp and geolocation from the IQS_GetIQStream_PM1 data*/
	double time_stamp;
	time_stamp = IQStream.DeviceState.AbsoluteTimeStamp; // Get the absolute timestamp.
	int16_t hour_var, minute_var, second_var, year_var, month_var, day_var;
	Status = Device_AnysisGNSSTime(time_stamp, &hour_var, &minute_var, &second_var, &year_var, &month_var, &day_var);            // Get the current absolute timestamp.
	utcToSingaporeTime(hour_var, minute_var, second_var, year_var, month_var, day_var);								             // Convert UTC to Singapore Time.
	cout << year_var << "/" << month_var << "/" << day_var << " " << hour_var << ":" << minute_var << ":" << second_var << endl; // Output Singapore Time.

	string longitudeDMS = ConvertToDMSFormat(IQStream.DeviceState.Longitude); // Convert longitude and latitude from float to DMS string format.
	string latitudeDMS = ConvertToDMSFormat(IQStream.DeviceState.Latitude);
	cout << "Current Longitude :" << longitudeDMS << endl;					  // Output longitude information.
	cout << "Current Latitude : " << latitudeDMS << endl;				      // Output latitude information.

	Status = IQS_BusTriggerStop(&Device); // Stop triggering the device by calling IQS_BusTriggerStop. If the trigger source is external, this function is not needed.
#endif
	Device_Close(&Device); // Close the device.
	return 0;
}
