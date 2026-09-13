from htra_api import *

ModelToDevName = {
    12: "E90 R2",
    13: "E90 R3",
    22: "E200 R2",
    23: "E200 R3",
    53: "N60 R4",
    54: "M60 R4",
    55: "N45 R4",
    56: "M80 R5",
    57: "M60 R5",
    58: "N60 R5",
    59: "N45 R5",
    94: "N400 R2V2"
}

apiVersion = dll.Get_APIVersion()
major = (apiVersion >> 16) & 0xffff
minor = (apiVersion >> 8) & 0xff
rev = apiVersion & 0xff
print("htra_api version: {}.{}.{}".format(major, minor, rev))

###Open Device###
Status = 0          #Function return value
Device = c_void_p() #Memory address of the current device
DevNum = c_int(0)   #Specifies device number

BootProfile = BootProfile_TypeDef() #Boot configuration structure, including physical interface, power supply, etc.
BootInfo = BootInfo_TypeDef()       #Boot information structure, including device info, USB speed, etc.

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort #Use both USB data port and independent power port
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 #Use USB interface for data transmission

#Configure ETH interface for Ethernet devices
#BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.ETH #Use Ethernet for data transmission
#BootProfile.ETH_IPVersion = IPVersion_TypeDef.IPv4
#BootProfile.ETH_RemotePort = 5000
#BootProfile.ETH_ReadTimeOut = 10000
#BootProfile.ETH_IPAddress[0] = 192
#BootProfile.ETH_IPAddress[1] = 168
#BootProfile.ETH_IPAddress[2] = 1
#BootProfile.ETH_IPAddress[3] = 100

Status = dll.Device_Open(pointer(Device),DevNum,pointer(BootProfile),pointer(BootInfo)) #Open device
print("Device_Open:{}".format(Status))

###Get Device Info###
DeviceInfo = DeviceInfo_TypeDef()                                        #Structure to store device information, including UID, model, firmware version, etc.
Status = dll.Device_QueryDeviceInfo(pointer(Device),pointer(DeviceInfo)) #Retrieve device information

print("BusSpeed:{:d}".format(BootInfo.BusSpeed))
print("Model:{:d} {}".format(DeviceInfo.Model,ModelToDevName.get(DeviceInfo.Model, "Unknown Device")))
print("DeviceInfo.DeviceUID:{:x}".format(DeviceInfo.DeviceUID))

print("MCU Firmware:{:d}.{:d}.{:d}".format((DeviceInfo.MFWVersion>>16)&0XFFFF,(DeviceInfo.MFWVersion>>8)&0XFF,DeviceInfo.MFWVersion&0XFF))
print("FPGA Firmware:{:d}.{:d}.{:d}".format((DeviceInfo.FFWVersion>>16)&0XFFFF,(DeviceInfo.FFWVersion>>8)&0XFF,DeviceInfo.FFWVersion&0XFF))

###Get Device Status###
DeviceState = DeviceState_TypeDef()                                                 #Structure to store device status, including temperature, RF state, etc.
Status = dll.Device_QueryDeviceState_Realtime(pointer(Device),pointer(DeviceState)) #Retrieve device status
print("Device Temperature:{}deg C".format(DeviceState.Temperature/100))

###Close Device###
Status = dll.Device_Close(pointer(Device))




