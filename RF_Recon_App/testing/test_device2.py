import ctypes
from htra_api_wrapper import *
Device = ctypes.c_void_p()
DevNum = ctypes.c_int(0)
BootProfile = BootProfile_TypeDef()
BootInfo = BootInfo_TypeDef()
BootProfile.DevicePowerSupply = 0
BootProfile.PhysicalInterface = 0
Status = dll.Device_Open(ctypes.pointer(Device), DevNum, ctypes.pointer(BootProfile), ctypes.pointer(BootInfo))
print("Status:", Status)
SWP_ProfileIn = SWP_Profile_TypeDef()
SWP_ProfileOut = SWP_Profile_TypeDef()
TraceInfo = SWP_TraceInfo_TypeDef()
dll.SWP_ProfileDeInit(ctypes.pointer(Device), ctypes.pointer(SWP_ProfileIn))
SWP_ProfileIn.StartFreq_Hz = int(1e9)
SWP_ProfileIn.StopFreq_Hz = int(2e9)
SWP_ProfileIn.RBW_Hz = int(50e3)
SWP_ProfileIn.RBWMode = RBWMode_TypeDef.RBW_Manual
SWP_ProfileIn.VBWMode = VBWMode_TypeDef.VBW_TenTimesRBW
SWP_ProfileIn.FreqAssignment = SWP_FreqAssignment_TypeDef.StartStop
Status_SWP = dll.SWP_Configuration(ctypes.pointer(Device), ctypes.pointer(SWP_ProfileIn), ctypes.pointer(SWP_ProfileOut), ctypes.pointer(TraceInfo))
print("SWP Config Status:", Status_SWP)
