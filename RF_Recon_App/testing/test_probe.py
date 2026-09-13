import ctypes
from htra_api_wrapper import *
device = ctypes.c_void_p()
dev_num = ctypes.c_int(0)
boot_profile = BootProfile_TypeDef()
boot_info = BootInfo_TypeDef()
boot_profile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort
boot_profile.PhysicalInterface = PhysicalInterface_TypeDef.USB
status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
print("Status:", status)
print("Model:", boot_info.DeviceInfo.Model)
print("UID:", f"{boot_info.DeviceInfo.DeviceUID:016x}")
dll.Device_Close(ctypes.pointer(device))
