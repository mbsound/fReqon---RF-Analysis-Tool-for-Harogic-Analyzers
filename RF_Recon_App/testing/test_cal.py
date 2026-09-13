import os, sys, shutil, ctypes
from htra_api_wrapper import *

temp_dir = "/tmp/harogic_cal_test"
os.makedirs(temp_dir, exist_ok=True)
for f in os.listdir("CalFile"):
    shutil.copy(os.path.join("CalFile", f), temp_dir)

os.chdir(temp_dir)

device = ctypes.c_void_p()
dev_num = ctypes.c_int(0)
boot_profile = BootProfile_TypeDef()
boot_profile.DevicePowerSupply = 0
boot_profile.PhysicalInterface = 0
boot_info = BootInfo_TypeDef()

Status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
print("Open Status:", Status)

dll.Device_Close(ctypes.pointer(device))
