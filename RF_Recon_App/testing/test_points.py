import sys, ctypes
from htra_api_wrapper import *

device = ctypes.c_void_p()
dev_num = ctypes.c_int(0)
boot_profile = BootProfile_TypeDef()
boot_profile.DevicePowerSupply = 0
boot_profile.PhysicalInterface = 0
boot_info = BootInfo_TypeDef()

Status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))

swp_profile_in = SWP_Profile_TypeDef()
swp_profile_out = SWP_Profile_TypeDef()
trace_info = SWP_TraceInfo_TypeDef()

dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
swp_profile_in.StartFreq_Hz = int(1e9)
swp_profile_in.StopFreq_Hz = int(2e9)
swp_profile_in.RBW_Hz = int(50e3)
swp_profile_in.RBWMode = 0
swp_profile_in.VBWMode = 0
swp_profile_in.FreqAssignment = 0

Status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))

print("TotalHops:", trace_info.TotalHops)
print("FullsweepTracePoints:", trace_info.FullsweepTracePoints)
print("PartialsweepTracePoints:", trace_info.PartialsweepTracePoints)

dll.Device_Close(ctypes.pointer(device))
