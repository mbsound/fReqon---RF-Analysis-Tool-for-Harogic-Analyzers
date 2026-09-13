#include <iostream>
#include <vector>
#include <string>
#include <map>
#include "htra_api.h"
#include "example.h"
using namespace std;

#define IS_USB 1 // The default device type is USB. If using an Ethernet device, set IS_USB to 0.

int Device_SysPowerState()
{
	map<uint16_t, string> SysPowerStateToState; // Mapping system power state to state descriptions.
	SysPowerStateToState[0x00] = "PowerON";      // All work areas of the system are powered on.
	SysPowerStateToState[0x01] = "RFPowerOFF";   // RF power off state, cannot quickly wake up.
	SysPowerStateToState[0x02] = "RFStandby";    // Standby state, can quickly wake up.

	int Status = 0;      // Function return status.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specifies the device number.

	BootProfile_TypeDef BootProfile; // Boot configuration.
	BootInfo_TypeDef BootInfo;       // Boot information.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Dual power supply via USB data port and independent power port.

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

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // Handle errors based on the Status return value when Status is not 0.

	SysPowerState_TypeDef SysPowerState;

	SysPowerState = PowerON; 
	Status = Device_SetSysPowerState(&Device, SysPowerState); // Set the device state.
	cout << "SysPowerState: " << SysPowerStateToState[SysPowerState] << endl;

	/*
	Insert customer code here (initialization, configuration, etc.)
	For example: get trace, display spectrum, etc.

	After executing the program, if you want to put the device into low power state, you can set the RF to power off state. (The specific code is as follows)
	*/

	SysPowerState = RFPowerOFF;                               // RF is in the power-off state, cannot quickly wake up.
	Status = Device_SetSysPowerState(&Device, SysPowerState); // Set the device state.
	cout << "SysPowerState: " << SysPowerStateToState[SysPowerState] << endl;

	Device_Close(&Device); // Close the device.
	return 0;
}