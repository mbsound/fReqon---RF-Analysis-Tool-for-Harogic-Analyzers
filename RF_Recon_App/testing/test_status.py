import sys, ctypes
from htra_api_wrapper import *
import numpy as np

device = ctypes.c_void_p()
dev_num = ctypes.c_int(0)
boot_profile = BootProfile_TypeDef()
boot_profile.DevicePowerSupply = 0
boot_profile.PhysicalInterface = 0
boot_info = BootInfo_TypeDef()

Status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
print("Open:", Status)

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
print("Config:", Status)

partial_freq_ctypes = (ctypes.c_double * trace_info.PartialsweepTracePoints)()
partial_spec_ctypes = (ctypes.c_float * trace_info.PartialsweepTracePoints)()
hop_index = ctypes.c_int(0)
frame_index = ctypes.c_int(0)
meas_aux = MeasAuxInfo_TypeDef()

for sweep in range(3):
    print("Sweep", sweep)
    for i in range(trace_info.TotalHops):
        Status = dll.SWP_GetPartialSweep(ctypes.pointer(device), partial_freq_ctypes, partial_spec_ctypes, ctypes.pointer(hop_index), ctypes.pointer(frame_index), ctypes.pointer(meas_aux))
        if Status != 0:
            print("Hop", i, "Error Status:", Status)

dll.Device_Close(ctypes.pointer(device))
print("Done")
