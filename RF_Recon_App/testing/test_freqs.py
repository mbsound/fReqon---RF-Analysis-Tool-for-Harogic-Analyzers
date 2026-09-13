import ctypes
import numpy as np
from htra_api_wrapper import *
device = ctypes.c_void_p()
dev_num = ctypes.c_int(0)
boot_profile = BootProfile_TypeDef()
boot_info = BootInfo_TypeDef()
boot_profile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort
boot_profile.PhysicalInterface = PhysicalInterface_TypeDef.USB
status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
if status < 0 and status != -33 and status != -34 and status != -43:
    print("Open failed")
else:
    swp_in = SWP_Profile_TypeDef()
    swp_out = SWP_Profile_TypeDef()
    trace_info = SWP_TraceInfo_TypeDef()
    swp_in.StartFreq_Hz = int(1e9)
    swp_in.StopFreq_Hz = int(2e9)
    swp_in.RBW_Hz = 50000
    dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_in), ctypes.pointer(swp_out), ctypes.pointer(trace_info))
    print("In:", swp_in.StartFreq_Hz, swp_in.StopFreq_Hz)
    print("Out:", swp_out.StartFreq_Hz, swp_out.StopFreq_Hz)
    print("Trace:", trace_info.FullsweepTracePoints)
    dll.Device_Close(ctypes.pointer(device))
