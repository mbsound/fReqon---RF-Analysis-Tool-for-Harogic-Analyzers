#include <stdio.h>
#include <string.h>
#include <vector>
#include "example.h"
#include "htra_api.h"
using namespace std;

#define IS_USB 1 // Default uses USB-type device. If using Ethernet-type device, set IS_USB to 0.

int SWP_GetSpectrum_TraceAlign()
{
    int Status = 0;      // Function return value.
    void* Device = NULL; // Memory address of the current device.
    int DevNum = 0;      // Specified device number.

    BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
    BootInfo_TypeDef BootInfo;       // Boot information structure, including device information, USB speed, etc.

    BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Dual power supply using USB data port and separate power port.

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

    Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo);              // Open the device.

    Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Error handling based on the Status return value when Status is non-zero.

    SWP_Profile_TypeDef SWP_ProfileIn;  // SWP input configuration, including start frequency, stop frequency, RBW, reference level, etc.
    SWP_Profile_TypeDef SWP_ProfileOut; // SWP output configuration.
    SWP_TraceInfo_TypeDef TraceInfo;    // Trace information for the current configuration, including trace points, hop points, etc.

    SWP_ProfileDeInit(&Device, &SWP_ProfileIn); // Initialize SWP mode parameters.

    SWP_ProfileIn.StartFreq_Hz = 9e3;        // Configure start frequency.
    SWP_ProfileIn.StopFreq_Hz = 6.35e9;      // Configure stop frequency.
    SWP_ProfileIn.RBW_Hz = 300e3;            // Configure RBW.
    SWP_ProfileIn.TraceAlign = AlignToStart; // Trace alignment mode is set to align to start frequency, if alignment to center frequency is needed, set this parameter to AlignToCenter.

    Status = SWP_Configuration(&Device, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);                                               // Issue SWP mode configuration by calling this function.

    SWP_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo); // Error handling based on the Status return value when Status is non-zero.

    // When calling SWP_GetPartialSweep() to get spectrum data frame by frame, aligning to the start frequency/center frequency might lead to zero padding. It is not recommended to directly use TraceInfo.FullsweepTracePoints for array size allocation.
    // When calling SWP_GetFullSweep() to get data, you can directly use TraceInfo.FullsweepTracePoints for array size allocation.
    vector<double> Frequency(TraceInfo.PartialsweepTracePoints * TraceInfo.TotalHops);    // Create frequency array.
    vector<float> PowerSpec_dBm(TraceInfo.PartialsweepTracePoints * TraceInfo.TotalHops); // Create power array.

    // Store the spectrum and amplitude data after removing zero padding.
    vector<double> Frequency_c(TraceInfo.FullsweepTracePoints);    // Create frequency array.
    vector<float> PowerSpec_dBm_c(TraceInfo.FullsweepTracePoints); // Create power array.
    int HopIndex = 0;                                              // Current hop point index.
    int FrameIndex = 0;                                            // Current frame index.
    MeasAuxInfo_TypeDef MeasAuxInfo;                               // Auxiliary measurement information, including power maximum index, power maximum value, device temperature, latitude, longitude, and absolute timestamp.

    // Loop to acquire data.
    while (1)
    {
        for (int i = 0; i < TraceInfo.TotalHops; i++) // TraceInfo.TotalHops represents the number of frames under the current configuration, so loop TraceInfo.TotalHops times to call SWP_GetPartialSweep to get the full trace.
        {
            Status = SWP_GetPartialSweep(&Device, Frequency.data() + i * TraceInfo.PartialsweepTracePoints, PowerSpec_dBm.data() + i * TraceInfo.PartialsweepTracePoints, &HopIndex, &FrameIndex, &MeasAuxInfo); // Acquire spectrum data.

            if (Status == APIRETVAL_NoError)
            {
                // User code here
                /*

                For example: display spectrum or process spectrum data.

                */
            }

            else // Error handling based on the Status return value when Status is non-zero.
            {
                SWP_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &SWP_ProfileIn, &SWP_ProfileOut, &TraceInfo);
            }

        }

        memcpy(Frequency_c.data(), Frequency.data(), sizeof(double)* TraceInfo.FullsweepTracePoints);         // Store the frequency data after removing zero padding.
        memcpy(PowerSpec_dBm_c.data(), PowerSpec_dBm.data(), sizeof(float) * TraceInfo.FullsweepTracePoints); // Store the power data after removing zero padding.
    }

    Device_Close(&Device); // Close the device.

    return 0;
}
