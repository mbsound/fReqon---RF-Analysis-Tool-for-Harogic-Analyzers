#include <iostream>
#include <vector>
#include <string>
#include <map>
#include "htra_api.h"
using namespace std;

int Device_GetAndSetIP()
{
	int Status = 0;

	uint8_t DeviceCount;                              // Number of devices.
	NetworkDeviceInfo_TypeDef NetworkDeviceInfo[100]; // Device information, including IP address, subnet mask, UID, etc.

	uint8_t LocalIP[4];
	uint8_t LocalMask[4];
	Status = Device_GetNetworkDeviceList(&DeviceCount, NetworkDeviceInfo, LocalIP, LocalMask); // Get the IP addresses, subnet masks, and other information of all network devices in the network.

	uint8_t IPAddress[4] = { 192,168,3,101 };  // Set the IP to be changed.
	uint8_t SubnetMask[4] = { 255,255,255,0 }; // Set the subnet mask to be changed.

#if 0 // Set the IP address by device UID.
	uint64_t DeviceUID = NetworkDeviceInfo[0].DeviceUID;                  // Be sure to use the correct device number.
	Status = Device_SetNetworkDeviceIP(DeviceUID, IPAddress, SubnetMask); // Set the IP address using the device UID.
#else // Set the IP address by device IP.
	uint8_t DeviceIP[4] = { NetworkDeviceInfo[0].IPAddress[0], NetworkDeviceInfo[0].IPAddress[1],NetworkDeviceInfo[0].IPAddress[2],NetworkDeviceInfo[0].IPAddress[3] }; // Input the current device IP.																													   // Set the subnet mask to be changed.
	Status = Device_SetNetworkDeviceIP_PM1(DeviceIP, IPAddress, SubnetMask); // Set the IP address using the device IP.
#endif

	Status = Device_GetNetworkDeviceList(&DeviceCount, NetworkDeviceInfo, LocalIP, LocalMask); // Get the IP addresses, subnet masks, and other information of all network devices again (in NetworkDeviceInfo).

	cout << "Current DeviceIP:"
		<< static_cast<int>(NetworkDeviceInfo[0].IPAddress[0]) << "."
		<< static_cast<int>(NetworkDeviceInfo[0].IPAddress[1]) << "."
		<< static_cast<int>(NetworkDeviceInfo[0].IPAddress[2]) << "."
		<< static_cast<int>(NetworkDeviceInfo[0].IPAddress[3]) << endl;

	cout << "Current DeviceMask:"
		<< static_cast<int>(NetworkDeviceInfo[0].SubnetMask[0]) << "."
		<< static_cast<int>(NetworkDeviceInfo[0].SubnetMask[1]) << "."
		<< static_cast<int>(NetworkDeviceInfo[0].SubnetMask[2]) << "."
		<< static_cast<int>(NetworkDeviceInfo[0].SubnetMask[3]) << endl;

	// If Device_Open returns a non-zero value, the program ends.
	if (Status) {
		return 0;
	}

	return 0;
}