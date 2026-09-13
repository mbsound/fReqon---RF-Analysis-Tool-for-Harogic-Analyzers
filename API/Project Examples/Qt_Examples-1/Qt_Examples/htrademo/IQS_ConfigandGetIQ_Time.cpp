#include <stdio.h>
#include <iostream>
#include <string.h>
#include <vector>
#include <chrono>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default is USB device, if using Ethernet device set IS_USB to 0.

int IQS_ConfigandGetIQ_Time()
{
    int Status = 0;      // Function return value.
    void* Device = NULL; // Memory address of the current device.
    int DevNum = 0;      // Specify the device number.

    BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply type, etc.
    BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB speed, etc.

    BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use USB data port and separate power port for dual power supply.

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

    Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is not 0, handle errors based on the Status return value.

    IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
    IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
    IQS_StreamInfo_TypeDef StreamInfo;  // IQ data information under the current configuration, including bandwidth, IQ single-channel sample rate, etc.

    Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn);  // Initialize the IQS mode configuration parameters.

    IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Configure center frequency.
    IQS_ProfileIn.RefLevel_dBm = 0;          // Configure reference level.
    IQS_ProfileIn.DecimateFactor = 2;		 // Configure decimation factor.
    IQS_ProfileIn.DataFormat = Complex16bit; // Configure IQ data format.
    IQS_ProfileIn.TriggerMode = Adaptive; // Configure trigger mode.
    IQS_ProfileIn.TriggerSource = Bus;       // Set trigger source to internal bus.
    IQS_ProfileIn.TriggerLength = 16242;     // Configure the number of points to trigger and acquire. Only effective when TriggerMode is set to FixedPoints.

    auto start1 = std::chrono::high_resolution_clock::now(); // Measure time for the first Config.
    
    Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS mode configuration.

    IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // When Status is not 0, handle errors based on the Status return value.

    auto stop1 = std::chrono::high_resolution_clock::now();
    auto timeout1 = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop1 - start1);
    cout << "First Config Time: " << timeout1.count() << " ms" << endl;

    auto start2 = std::chrono::high_resolution_clock::now(); // Measure average time for Config after the first attempt.
        
    for (int i = 0; i < 10; i++) 
    {
        Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS mode configuration.

        IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors when Status is not 0.
    }
    
    auto stop2 = std::chrono::high_resolution_clock::now();
    auto timeout2 = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop2 - start2);
    cout << "Configuration time after the first attempt: " << timeout2.count() / 10 << " ms" << endl;

    IQStream_TypeDef IQStream; // Stores IQ data packet, including IQ data, configuration information, etc.
    
    Status = IQS_BusTriggerStart(&Device);

    auto start3 = std::chrono::high_resolution_clock::now(); // Measure the start time for data acquisition.
    int count = 10;                                           // Count the number of data acquisition loops.


    for (int n = 0; n < count; n++)
    {
        Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data packets, trigger info, I channel data max values, and max value array index.
        if (Status == APIRETVAL_NoError)
        {

        }

        else // Handle errors when Status is not 0.
        {
            IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
        }
    }
        

    auto stop3 = std::chrono::high_resolution_clock::now(); // Measure the end time for data acquisition.
    auto timeout3 = std::chrono::duration_cast<std::chrono::duration<double, ratio<1, 1000>>>(stop3 - start3);
    cout << "IQS_Get data acquisition time: " << timeout3.count() / count << " ms" << endl;

    Status = IQS_BusTriggerStop(&Device); // Stop triggering the device. If the trigger source is external, this function is not needed.

    Device_Close(&Device); // Close the device.

    return 0;
}
