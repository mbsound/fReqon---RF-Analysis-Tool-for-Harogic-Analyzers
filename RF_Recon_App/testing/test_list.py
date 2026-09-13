import ctypes
from htra_api_wrapper import *
DeviceCount = ctypes.c_uint8(0)
DevNum = (ctypes.c_uint8 * 16)()
DeviceInfo_O = (DeviceInfo_TypeDef * 16)()
BootProfile = BootProfile_TypeDef()
BootProfile.DevicePowerSupply = 0
BootProfile.PhysicalInterface = 0
Status = dll.Device_List(ctypes.pointer(BootProfile), ctypes.pointer(DeviceCount), DevNum, DeviceInfo_O)
print("Status:", Status, "DeviceCount:", DeviceCount.value)
