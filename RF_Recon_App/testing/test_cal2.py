import os, sys, shutil, ctypes
from htra_api_wrapper import *

device = ctypes.c_void_p()
dev_num = ctypes.c_int(0)
boot_profile = BootProfile_TypeDef()
boot_profile.DevicePowerSupply = 0
boot_profile.PhysicalInterface = 0
boot_info = BootInfo_TypeDef()

Status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
print("Open Status:", Status)

if Status == 0:
    dll.Device_Close(ctypes.pointer(device))
