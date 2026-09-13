import ctypes
from htra_api_wrapper import *
device = ctypes.c_void_p()
dev_num = ctypes.c_int(0)
boot_profile = BootProfile_TypeDef()
boot_info = BootInfo_TypeDef()
boot_profile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort
boot_profile.PhysicalInterface = PhysicalInterface_TypeDef.USB
status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
print("Open Status:", status)

swp_profile_in = SWP_Profile_TypeDef()
swp_profile_out = SWP_Profile_TypeDef()
trace_info = SWP_TraceInfo_TypeDef()

swp_profile_in.StartFreq_Hz = int(1e9)
swp_profile_in.StopFreq_Hz = int(2e9)
swp_profile_in.RBW_Hz = 50e3
swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_Manual
swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_TenTimesRBW
swp_profile_in.FreqAssignment = SWP_FreqAssignment_TypeDef.StartStop

status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
print("Config Status:", status)

dll.Device_Close(ctypes.pointer(device))
