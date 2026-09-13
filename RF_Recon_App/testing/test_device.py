import ctypes
dll = ctypes.CDLL("/opt/htraapi/lib/aarch64/libhtraapi.so")
class BootProfile_TypeDef(ctypes.Structure):
    _fields_ = [("DevicePowerSupply", ctypes.c_int), ("PhysicalInterface", ctypes.c_int), ("ETH_IPVersion", ctypes.c_int), ("ETH_RemotePort", ctypes.c_int), ("ETH_ReadTimeOut", ctypes.c_int), ("ETH_IPAddress", ctypes.c_char * 16)]
class BootInfo_TypeDef(ctypes.Structure):
    _fields_ = [("DeviceInfo", ctypes.c_char * 128), ("BusSpeed", ctypes.c_int), ("BusVersion", ctypes.c_int)]
Device = ctypes.c_void_p()
DevNum = ctypes.c_int(0)
BootProfile = BootProfile_TypeDef()
BootInfo = BootInfo_TypeDef()
BootProfile.DevicePowerSupply = 0
BootProfile.PhysicalInterface = 0
print("Before open")
Status = dll.Device_Open(ctypes.pointer(Device), DevNum, ctypes.pointer(BootProfile), ctypes.pointer(BootInfo))
print("Status:", Status)
