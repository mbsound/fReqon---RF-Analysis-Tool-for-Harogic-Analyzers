#include <iostream>
#include <vector>
#include <string>
#include <map>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // Default device is USB; if using an Ethernet device, set IS_USB to 0.

int Device_GetDeviceInfo()
{
	map<uint16_t, string> ModelToDevName; // Map model to device name.
	ModelToDevName[12] = "E90 R2";
	ModelToDevName[13] = "E90 R3";
	ModelToDevName[22] = "E200 R2";
	ModelToDevName[23] = "E200 R3";
	ModelToDevName[53] = "N60 R4";
	ModelToDevName[54] = "M60 R4";
	ModelToDevName[55] = "N45 R4";
	ModelToDevName[56] = "M80 R5";
	ModelToDevName[57] = "M60 R5";
	ModelToDevName[58] = "N60 R5";
	ModelToDevName[59] = "N45 R5";
	ModelToDevName[94] = "N400 R2V2";

	int apiVersion = Get_APIVersion();
	int major = 0, minor = 0, rev = 0;
	major = (apiVersion >> 16) & 0xffff;
	minor = (apiVersion >> 8) & 0xff;
	rev = apiVersion & 0xff;
	cout << "htra_api version: " << major << "." << minor << "." << rev << endl; // Print the htra_api version.

	int Status = 0;
	void* Device = NULL;
	int DevNum = 0;

	BootProfile_TypeDef BootProfile; // Boot configuration.
	BootInfo_TypeDef BootInfo;       // Boot information.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort;

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // When Status is not 0, handle errors according to the return value of Status.

	// Print device information
	cout << "BusSpeed: " << BootInfo.BusSpeed << endl; // BootInfo.BusSpeed: 3 for USB3.0, 2 for USB2.0.
	cout << "Model: " << BootInfo.DeviceInfo.Model << ", " << ModelToDevName[BootInfo.DeviceInfo.Model] << endl;
	cout << std::hex << "DeviceInfo.DeviceUID: " << BootInfo.DeviceInfo.DeviceUID << std::dec << endl; // Print device UID in hexadecimal.

	// Print MCU firmware version
	major = (BootInfo.DeviceInfo.MFWVersion >> 16) & 0xffff;
	minor = (BootInfo.DeviceInfo.MFWVersion >> 8) & 0xff;
	rev = BootInfo.DeviceInfo.MFWVersion & 0xff;
	cout << "MCU Firmware: " << major << "." << minor << "." << rev << endl;

	// Print FPGA firmware version
	major = (BootInfo.DeviceInfo.FFWVersion >> 16) & 0xffff;
	minor = (BootInfo.DeviceInfo.FFWVersion >> 8) & 0xff;
	rev = BootInfo.DeviceInfo.FFWVersion & 0xff;
	cout << "FPGA Firmware: " << major << "." << minor << "." << rev << endl;

	// Print Bus firmware version
	major = (BootInfo.BusVersion >> 16) & 0xffff;
	minor = (BootInfo.BusVersion >> 8) & 0xff;
	rev = BootInfo.BusVersion & 0xff;
	cout << "Bus Firmware: " << major << "." << minor << "." << rev << endl;

	// If Device_Open returns a non-zero value, exit the program.
	if (Status) {
		return 0;
	}

	DeviceInfo_TypeDef DeviceInfo;
	Status = Device_QueryDeviceInfo_Realtime(&Device, &DeviceInfo); // Query device information.

	DeviceState_TypeDef DeviceState;
	Status = Device_QueryDeviceState_Realtime(&Device, &DeviceState); // Query device state.
	cout << "Device Temperature: " << DeviceState.Temperature * 0.01 << "℃" << endl;

	Device_Close(&Device); // Close the device.
	return 0;
}
