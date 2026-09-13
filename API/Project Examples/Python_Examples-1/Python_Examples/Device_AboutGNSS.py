from htra_api import *
import time
from ctypes import byref
from datetime import datetime, timedelta

### Open device ###
Status = 0          # Return value of the function
Device = c_void_p() # Memory address of the current device
DevNum = c_int(0)   # Specified device number

BootProfile = BootProfile_TypeDef() # Boot configuration structure, includes physical interface, power supply, etc.
BootInfo = BootInfo_TypeDef()       # Boot information structure, includes device info, USB speed, etc.

BootProfile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort # Use USB data port and separate power port for dual supply
BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.USB                 # Use USB interface for data transmission

# Configure ETH interface for network device
#BootProfile.PhysicalInterface = PhysicalInterface_TypeDef.ETH # Use Ethernet for data transmission
#BootProfile.ETH_IPVersion = IPVersion_TypeDef.IPv4
#BootProfile.ETH_RemotePort = 5000
#BootProfile.ETH_ReadTimeOut = 10000
#BootProfile.ETH_IPAddress[0] = 192
#BootProfile.ETH_IPAddress[1] = 168
#BootProfile.ETH_IPAddress[2] = 1
#BootProfile.ETH_IPAddress[3] = 100

Status = dll.Device_Open(pointer(Device),DevNum,pointer(BootProfile),pointer(BootInfo)) # Open device
if(Status == 0):
    print("Device is opened successfully")
else:
    print("Return other errors Status = {:d}".format(Status))

# Set GNSS external antenna
GNSSAntennaState = GNSSAntennaState_TypeDef() # Initialize GNSS antenna info
GNSSAntennaState = GNSSAntennaState_TypeDef.GNSS_AntennaExternal

# Set GNSS antenna state
Status = dll.Device_SetGNSSAntennaState(pointer(Device), GNSSAntennaState) # Send GNSS antenna configuration

# Wait for GNSS lock (print every 1s)
GNSSInfo = GNSSInfo_TypeDef()  # GNSS information under current antenna configuration
while True:
    Status = dll.Device_GetGNSSInfo_Realtime(pointer(Device), byref(GNSSInfo))
    # 0: Not locked; 1: Locked
    print(f"GNSS_LockState: {int(GNSSInfo.GNSS_LockState)}")
    if GNSSInfo.GNSS_LockState == 1:
        break
    time.sleep(1)

# Configure and wait for DOCXO lock (if hardware supported)
HardwareVersion = BootInfo.DeviceInfo.HardwareVersion
OCXO_Enable = (HardwareVersion >> 10) & 0x3
if OCXO_Enable:
    DOCXOWorkMode = DOCXOWorkMode_TypeDef.DOCXO_LockMode
    Status = dll.Device_SetDOCXOWorkMode(pointer(Device), DOCXOWorkMode)

    start_time = time.time()

    # Get status once initially
    Status = dll.Device_GetGNSSInfo_Realtime(pointer(Device), byref(GNSSInfo))

    if GNSSInfo.DOCXO_LockState:
        print()
        print(f"GNSS_LockState: {int(GNSSInfo.GNSS_LockState)}")
        print(f"DOCXO_LockState: {int(GNSSInfo.DOCXO_LockState)}")
    else:
        while True:
            Status = dll.Device_GetGNSSInfo_Realtime(pointer(Device), byref(GNSSInfo))

            # Exit if both are locked
            if GNSSInfo.DOCXO_LockState == 1 and GNSSInfo.GNSS_LockState == 1:
                print()
                print(f"GNSS_LockState: {int(GNSSInfo.GNSS_LockState)}")
                print(f"DOCXO_LockState: {int(GNSSInfo.DOCXO_LockState)}")
                print("DOCXO is locked!")
                break

            # If GNSS is not locked, force DOCXO back to Lock mode
            if GNSSInfo.GNSS_LockState == 0:
                DOCXOWorkMode = DOCXOWorkMode_TypeDef.DOCXO_LockMode
                Status = dll.Device_SetDOCXOWorkMode(pointer(Device), DOCXOWorkMode)

            print(f"GNSS_LockState: {int(GNSSInfo.GNSS_LockState)}")
            print(f"DOCXO_LockState: {int(GNSSInfo.DOCXO_LockState)}")

            # Timeout check: 600 s
            if time.time() - start_time > 600:
                print("The DOCXO is not locked, please check whether the cable connection is normal.")
                break

            time.sleep(1)


# Print Singapore Time (GNSS provides UTC, here +8 hours)
print("Singapore Time:")
try:
    utc_dt = datetime(
        int(GNSSInfo.Year), int(GNSSInfo.month), int(GNSSInfo.day),
        int(GNSSInfo.hour), int(GNSSInfo.minute), int(GNSSInfo.second)
    )
    bj_dt = utc_dt + timedelta(hours=8)
    print(bj_dt.strftime("%Y/%m/%d %H:%M:%S"))
except Exception:
    # If struct time fields unavailable, fallback to direct +8 display (may overflow to next day)
    print(f"{GNSSInfo.Year}/{GNSSInfo.month}/{GNSSInfo.day} "
          f"{int(GNSSInfo.hour) + 8}:{GNSSInfo.minute}:{GNSSInfo.second}")

def deg_to_dms(deg: float) -> str:
    sign = "-" if deg < 0 else ""
    a = abs(float(deg))
    d = int(a)
    m_float = (a - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    return f"{sign}{d}°{m}'{s:.2f}"

# Print latitude, longitude, altitude
latitudeDMS_GN = deg_to_dms(GNSSInfo.latitude)
longitudeDMS_GN  = deg_to_dms(GNSSInfo.longitude)

print(f"Current Latitude : {latitudeDMS_GN}")
print(f"Current Longitude :{longitudeDMS_GN}")
print(f"Current altitude : {int(GNSSInfo.altitude)}")

# Get GNSS_SatData (satellite SNR, etc.)
GNSS_SatDate = GNSS_SatDate_TypeDef()
Status = dll.Device_GetGNSS_SatDate_Realtime(pointer(Device), byref(GNSS_SatDate))

print(f"Max C/N0 (used for position): {int(GNSS_SatDate.GNSS_SNR_UsePos.Max_SatxC_No)}")
print(f"Min C/N0 (used for position): {int(GNSS_SatDate.GNSS_SNR_UsePos.Min_SatxC_No)}")
print(f"Avg C/N0 (used for position): {int(GNSS_SatDate.GNSS_SNR_UsePos.Avg_SatxC_No)}")


### Configuration delivery ###
IQS_ProfileIn = IQS_Profile_TypeDef()  # IQS input configuration, includes start/stop frequency, RBW, reference level, etc.
IQS_ProfileOut = IQS_Profile_TypeDef() # IQS output configuration
StreamInfo = IQS_StreamInfo_TypeDef()  # IQ data info under current configuration, includes bandwidth, single-channel sampling rate, etc.

dll.IQS_ProfileDeInit(pointer(Device),pointer(IQS_ProfileIn)) # Initialize IQS mode parameters

IQS_ProfileIn.CenterFreq_Hz = 1e9                           # Set center frequency
IQS_ProfileIn.RefLevel_dBm = 0                              # Set reference level
IQS_ProfileIn.DecimateFactor = 2                            # Set decimation factor
IQS_ProfileIn.DataFormat = DataFormat_TypeDef.Complex16bit  # Set IQ data format
IQS_ProfileIn.TriggerSource = IQS_TriggerSource_TypeDef.Bus # Set trigger source to internal bus
IQS_ProfileIn.TriggerMode = TriggerMode_TypeDef.FixedPoints
IQS_ProfileIn.TriggerLength = 16242                         # Set number of points per trigger (only effective when TriggerMode = FixedPoints)
IQS_ProfileIn.NativeIQSampleRate_SPS=128e6

Status = dll.IQS_Configuration(pointer(Device),pointer(IQS_ProfileIn),pointer(IQS_ProfileOut),pointer(StreamInfo))  # Deliver IQS configuration

if(Status == 0):
    print("IQS configuration delivery succeeded")
else:
    print("SWP_Configuration call is incorrect Status = {:d}".format(Status))

### Acquire data ###
IQ_Data = (c_int16 * (StreamInfo.StreamSamples*2))() # Store IQ data
AlternIQPacket = c_int16_p()                         # Temporary pointer for IQ data from library function
ScaleToV = c_float()                                 # Scaling factor to restore amplitude to voltage
TriggerInfo = IQS_TriggerInfo_TypeDef()              # Trigger info structure
MeasAuxInfo = MeasAuxInfo_TypeDef()                  # Measurement auxiliary info structure

try:
    while(True):
        Status = dll.IQS_BusTriggerStart(pointer(Device))  # Call IQS_BusTriggerStart to trigger the device. Not required if the trigger source is external.
        for i in range(0, StreamInfo.PacketCount):
            dll.IQS_GetIQStream(pointer(Device), pointer(AlternIQPacket), pointer(ScaleToV),pointer(TriggerInfo), pointer(MeasAuxInfo))  # Retrieve IQ data packets, trigger info, I-channel max value and its index array

            if(i == StreamInfo.PacketCount - 1 and StreamInfo.StreamSamples % StreamInfo.PacketSamples != 0):
                # The last packet may not be a full packet (16242 points), so only copy the remaining points
                IQ_Data[(i * StreamInfo.PacketSamples * 2):] = AlternIQPacket[0:(2 * (StreamInfo.StreamSamples % StreamInfo.PacketSamples))]
                break
            else:
                IQ_Data[(i * StreamInfo.PacketSamples * 2):((i + 1) * StreamInfo.PacketSamples * 2)] = AlternIQPacket[0:(StreamInfo.PacketSamples * 2)]

        time_stamp = float(MeasAuxInfo.AbsoluteTimeStamp)
        hour_var   = c_int16()
        minute_var = c_int16()
        second_var = c_int16()
        year_var   = c_int16()
        month_var  = c_int16()
        day_var    = c_int16()

        Status = dll.Device_AnysisGNSSTime(
            c_double(time_stamp),
            byref(hour_var), byref(minute_var), byref(second_var),
            byref(year_var), byref(month_var), byref(day_var)
        )

        try:
            utc_dt = datetime(int(year_var.value), int(month_var.value), int(day_var.value),
                            int(hour_var.value), int(minute_var.value), int(second_var.value))
            bj_dt = utc_dt + timedelta(hours=8)
            print(bj_dt.strftime("%Y/%m/%d %H:%M:%S"))
        except Exception:
            print(f"{year_var.value}/{month_var.value}/{day_var.value} "
                f"{hour_var.value + 8}:{minute_var.value}:{second_var.value}")

        def deg_to_dms(deg: float) -> str:
            sign = "-" if deg < 0 else ""
            a = abs(float(deg))
            d = int(a)
            m_float = (a - d) * 60.0
            m = int(m_float)
            s = (m_float - m) * 60.0
            return f"{sign}{d}°{m}'{s:.2f}"

        lon = float(MeasAuxInfo.Longitude)
        lat = float(MeasAuxInfo.Latitude)

        longitudeDMS = deg_to_dms(lon)
        latitudeDMS = deg_to_dms(lat)

        print("Current Longitude:", longitudeDMS)
        print("Current Latitude:", latitudeDMS)

except KeyboardInterrupt:
    print("Stopped by user with Ctrl+C")
finally:
    dll.Device_Close(pointer(Device))
    print("Device closed.")