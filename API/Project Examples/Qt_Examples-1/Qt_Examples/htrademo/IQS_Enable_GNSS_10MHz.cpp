#include <stdio.h>
#include <string.h>
#include <vector>
#include "htra_api.h"
#include <chrono>
#include <iostream>
#include <iomanip>
#include<thread>
#include "example.h"
using namespace std;

/* README
For the connection and use of the EIO expansion board, please refer to the relevant chapters on the GNSS module in the "SA NX Series Spectrum Analyzer User Guide."
*/

#define IS_USB 1 // Default assumption is USB. If the interface is ETH, please comment out this line.

int IQS_Enable_GNSS_10MHz()
{
    int Status = 0;      // Return value of the function.
    void* Device = NULL; // Memory address of the current device.
    int DevNum = 0;      // Specifies the device number.

    BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
    BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

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

    Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, handle errors based on the return value of Status.

    /* Set GNSS external antenna */
    GNSSAntennaState_TypeDef GNSSAntennaState; // GNSS antenna information.
    GNSSAntennaState = GNSS_AntennaExternal;   // Configure external antenna.

    // Set GNSS antenna status
    Status = Device_SetGNSSAntennaState(&Device, GNSSAntennaState); // Apply GNSS antenna configuration.

    GNSSInfo_TypeDef GNSSInfo = { 0 }; // GNSS information under the current antenna configuration.

    // Output the current GNSS lock state every second until the device successfully locks the GNSS module.
    while (!GNSSInfo.GNSS_LockState)
    {
        Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo);             // Get real-time GNSS device status.
        cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl; // Output GNSS antenna lock state (GNSS_LockState=1 means locked).
        this_thread::sleep_for(chrono::milliseconds(1000));                      // Delay 1 second.
    }

    DOCXOWorkMode_TypeDef DOCXOWorkMode; // Configure DOCXO antenna status.
    DOCXOWorkMode = DOCXO_LockMode;

    /* Set and get DOCXO status */
    uint16_t HardwareVersion = BootInfo.DeviceInfo.HardwareVersion;
    uint16_t OCXO_Enable = (HardwareVersion >> 10) & 0x3;

    if (OCXO_Enable)
    {
        Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); // Set DOCXO work mode in GNSS.

        auto start_time = std::chrono::high_resolution_clock::now(); // Get current time

        Status = Device_GetGNSSInfo_Realtime(&Device, &GNSSInfo); // Get GNSS device status

        // Check lock state
        if (GNSSInfo.DOCXO_LockState)
        {
            cout << endl;
            // Output current GNSS_LockState status
            cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;
            // Output current DOCXO_LockState status
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
                    // Output current GNSS_LockState status
                    cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;
                    // Output current DOCXO_LockState status
                    cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;
                    break;
                }
                if (GNSSInfo.GNSS_LockState == 0)
                {
                    DOCXOWorkMode = DOCXO_LockMode;
                    Status = Device_SetDOCXOWorkMode(&Device, DOCXOWorkMode); // Set DOCXO work mode in GNSS
                }
                // Output current GNSS_LockState status
                cout << "GNSS_LockState: " << (int16_t)GNSSInfo.GNSS_LockState << endl;

                // Output current DOCXO_LockState status
                cout << "DOCXO_LockState: " << (int16_t)GNSSInfo.DOCXO_LockState << endl;

                // Check for timeout: is it over 180 seconds?
                auto current_time = std::chrono::high_resolution_clock::now();
                auto duration = std::chrono::duration_cast<std::chrono::duration<double, std::ratio<1, 1>>>(current_time - start_time);
                // If it exceeds 600 seconds, exit the loop
                if (duration.count() > 600)
                {
                    cout << "The DOCXO is not locked, please check whether the cable connection is normal." << endl;
                    break;
                    return 0;
                }
                this_thread::sleep_for(chrono::milliseconds(1000)); // Delay 1 second
            }
            cout << "DOCXO is locked!" << endl;
        }
    }

    /* Initialize configuration */
    IQS_Profile_TypeDef IQS_ProfileIn;  // IQS mode input configuration, including center frequency, decimation factor, reference level, etc.
    IQS_Profile_TypeDef IQS_ProfileOut; // IQS mode output configuration.
    IQS_StreamInfo_TypeDef StreamInfo;  // IQ data stream information under current configuration.

    Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize IQS mode configuration.

    /* Apply IQS mode configuration */
    IQS_ProfileIn.CenterFreq_Hz = 1e9;                            // Configure center frequency.
    IQS_ProfileIn.RefLevel_dBm = 0;                                // Configure reference level.
    IQS_ProfileIn.DecimateFactor = 2;                              // Configure decimation factor.
    IQS_ProfileIn.DataFormat = Complex16bit;                       // Configure IQ data format.
    IQS_ProfileIn.TriggerMode = FixedPoints;                       // Configure trigger mode. FixedPoints mode starts sampling at the rising edge of the trigger signal and stops after TriggerLength points.
    IQS_ProfileIn.TriggerSource = Bus;                              // Configure trigger source.
    IQS_ProfileIn.ReferenceClockSource = ReferenceClockSource_Internal_Premium; // Use GNSS module's 10MHz reference clock (only available for high-quality GNSS modules).
    IQS_ProfileIn.ReferenceClockFrequency = 10e6;                  // Set reference clock frequency to 10MHz.
    IQS_ProfileIn.TriggerLength = 16243;                           // Configure the number of points to capture per trigger. This applies only when TriggerMode is FixedPoints.

    Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS mode configuration.

    IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors based on Status if not 0.

    /* Get IQ data */
    IQStream_TypeDef IQStream;                        // Structure for storing IQ data packet and related configuration.
    bool tag = false;                                  // When IQS_ProfileIn.TriggerMode = Adaptive, trigger once before getting data.
    vector<int16_t> I_Data(StreamInfo.StreamSamples);  // Create I-channel data array.
    vector<int16_t> Q_Data(StreamInfo.StreamSamples);  // Create Q-channel data array.

    if (IQS_ProfileIn.TriggerMode == Adaptive)
    {
        I_Data.resize(StreamInfo.PacketSamples); // Resize I_Data to store data in Adaptive mode.
        Q_Data.resize(StreamInfo.PacketSamples); // Resize Q_Data to store data in Adaptive mode.
    }

    while (1)
    {
        if (IQS_ProfileOut.TriggerMode == Adaptive && tag != true) // Trigger once when IQS_ProfileIn.TriggerMode = Adaptive.
        {
            Status = IQS_BusTriggerStart(&Device);             // Call IQS_BusTriggerStart to trigger the device. If the trigger source is external, this function is not required.
            tag = true;
        }
        if (IQS_ProfileOut.TriggerMode == FixedPoints)           // Trigger every loop when TriggerMode = FixedPoints.
        {
            Status = IQS_BusTriggerStart(&Device);               // If the trigger source is external, this function is not required.
        }
        /* Get IQ data */
        for (int j = 0; j < StreamInfo.PacketCount; j++)         // Only effective when TriggerMode is FixedPoints. If TriggerMode is Adaptive, this does not take effect, and StreamInfo.PacketCount is 1.
        {
            Status = IQS_GetIQStream_PM1(&Device, &IQStream);    // Get IQ data packet, trigger info, I-channel max value, and max value array index.

            if (Status == APIRETVAL_NoError)
            {
                // UserCode here
                // Note: When using IQ mode, it's recommended to open a thread to call IQS_GetIQStream for getting IQ data. Do not mix it with IQ data processing in the same thread.

                int16_t* IQ = (int16_t*)IQStream.AlternIQStream;
                uint32_t Points = StreamInfo.PacketSamples;

                // When TriggerMode is FixedPoints, check if the last packet has 16242 points.
                if (j == StreamInfo.PacketCount - 1 && StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0 && IQS_ProfileOut.TriggerMode == FixedPoints) // The last packet may not be a full packet (16242 points), so only loop the remaining points.
                {
                    Points = StreamInfo.StreamSamples % StreamInfo.PacketSamples;
                }
                // Extract I and Q data.
                for (uint32_t i = 0; i < Points; i++)
                {
                    I_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2];
                    Q_Data[i + StreamInfo.PacketSamples * j] = IQ[i * 2 + 1];
                }
            }
            else // Handle errors when Status is not 0.
            {
                IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
            }
        }
    }

    Status = IQS_BusTriggerStop(&Device); // Call IQS_BusTriggerStop to stop triggering the device. If the trigger source is external, this function is not required.

    Device_Close(&Device); // Close the device.

    return 0;
}
