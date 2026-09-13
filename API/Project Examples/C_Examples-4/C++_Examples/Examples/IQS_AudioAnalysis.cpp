#include <stdio.h>
#include <string.h>
#include <vector>
#include <iostream>
#include "htra_api.h" 
#include "example.h"
using namespace std;

#define IS_USB 1 // Default is to use USB devices. If using Ethernet devices, define IS_USB as 0.

// Example of demodulating a 1 GHz, -20 dBm, modulation rate 3 kHz, and frequency offset 75 kHz FM signal, and analyzing its demodulation sensitivity.

int IQS_AudioAnalysis()
{
    int Status = 0;      // Return value of the function.
    void* Device = NULL; // Memory address of the current device.
    int DevNum = 0;      // Specified device number.

    BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply, etc.
    BootInfo_TypeDef BootInfo;       // Boot information structure, including device info, USB speed, etc.

    BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and independent power supply port for dual power.

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

    Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Handle errors based on the return value of Status if it is not 0.

    IQStream_TypeDef IQStream;          // Stores IQ data packet data, including IQ data, configuration information, etc.
    IQS_Profile_TypeDef IQS_ProfileIn;  // IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
    IQS_Profile_TypeDef IQS_ProfileOut; // IQS output configuration.
    IQS_StreamInfo_TypeDef StreamInfo;  // Information on IQ data under the current configuration, including bandwidth, IQ single-channel sample rate, etc.

    Status = IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize IQS mode related parameters.

    IQS_ProfileIn.CenterFreq_Hz = 1e9;    // Set the center frequency.
    IQS_ProfileIn.RefLevel_dBm = 0;        // Set the reference level.
    IQS_ProfileIn.DataFormat = Complex16bit; // Set the IQ data format.
    IQS_ProfileIn.TriggerMode = Adaptive;    // Set the trigger mode.
    IQS_ProfileIn.TriggerSource = Bus;       // Set the trigger source to internal bus trigger.
    IQS_ProfileIn.DecimateFactor = 64;      // Set the decimation factor.
    IQS_ProfileIn.BusTimeout_ms = 5000;      // Set the bus timeout.

    Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS mode configuration.
    
    IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Handle errors based on the return value of Status if it is not 0.

    // Demod
    void* AnalogMod = NULL; // Memory address for modulation and demodulation related information.
    ADM_Open(&AnalogMod);   // Enable modulation and demodulation functions.
    double carrierOffsetHz = 0;

    vector<float> audio(StreamInfo.PacketSamples);     // Create an array to store demodulated audio data.


    // DSP (Digital Signal Processing)
    void* DSP = NULL; // Memory address for digital signal processing related information.
    DSP_Open(&DSP);   // Enable digital signal processing.

    Status = IQS_BusTriggerStart(&Device); // Trigger the device. If the trigger source is external, this function does not need to be called.

    // Audio analysis
    DSP_AudioAnalysis_TypeDef  AudioAnalysis; // Structure to start audio analysis.
    int num = 0;
    
    while (num < 500)
    {
        Status = IQS_GetIQStream_PM1(&Device, &IQStream); // Get IQ data.
        if (Status == APIRETVAL_NoError)
        {
            Status = ADM_FMDemod(&AnalogMod, IQStream.AlternIQStream, IQS_ProfileOut.DataFormat, StreamInfo.PacketSamples, StreamInfo.IQSampleRate, 0, audio.data());

            vector<double> Audio(audio.begin(), audio.end()); // Convert audio data to a different data type.

            DSP_AudioAnalysis(Audio.data(), StreamInfo.PacketSamples,  StreamInfo.IQSampleRate, &AudioAnalysis);

            num++;
        }

        else // Handle errors based on the return value of Status if it is not 0.
        {
            IQS_ErrorHandlingExceptOpenAndConfiguration(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo);
        }
    }

    Status = IQS_BusTriggerStop(&Device); // Stop triggering the device. If the trigger source is external, this function does not need to be called.

    DSP_Close(&DSP);       // Close digital signal processing.
    ADM_Close(&AnalogMod); // Close modulation and demodulation.

    Status = Device_Close(&Device); // Close the device.

    return 0;
}
