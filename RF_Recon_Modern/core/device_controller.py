import ctypes
import numpy as np
import multiprocessing
import os
import platform
import threading
from pathlib import Path
import ipaddress
import queue
import time
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QSettings
try:
    from .htra_api_wrapper import *
    from . import htra_api_wrapper as _api
    from .tinysa_device import find_tinysa, tinysa_process, TinySAError
except ImportError:
    from htra_api_wrapper import *
    import htra_api_wrapper as _api
    from tinysa_device import find_tinysa, tinysa_process, TinySAError

# Acquisition statuses whose data is valid: success, or the IF-overload warning.
ACQ_OK = (0, -12)  # APIRETVAL_NoError, APIRETVAL_WARNING_IFOverflow

# Undecimated IQ rate assumed only when the SDK does not report one (SAN-60 value).
IQ_FALLBACK_BASE_RATE_HZ = 125e6
# A network Device_Open that takes longer than this hit the analyzer's handshake
# stall and left a dead session (see hardware_process); normal opens take ~3 s.
NETWORK_OPEN_STALL_S = 12.0
RTA_SEND_PERIOD_S = 1 / 30      # real-time spectrum frames are merged and sent at most this often
# Largest subnet swept for network analyzers (/22 = 1022 hosts, under ~1 s)
MAX_SCAN_PREFIX = 22

# Offset of the license vector inside the SDK's private device object, keyed by
# (Get_APIVersion(), platform.machine()). Only builds verified against the SDK
# binary belong here: SDK 0.55.89 (0x3759) for 64-bit ARM, which is also the
# build the macOS port runs.
_LICENSE_VECTOR_LAYOUTS = {
    (0x3759, "aarch64"): 0x33c0000 + 21656,
    (0x3759, "arm64"): 0x33c0000 + 21656,
}


def auto_rbw_for_span(span_hz):
    """fReqon's automatic RBW: coarser resolution for wider spans."""
    if span_hz <= 15e6:
        return 10e3
    if span_hz <= 50e6:
        return 30e3
    if span_hz <= 150e6:
        return 50e3
    return 100e3


def _query_hardware_endorsements(dll, device, boot_info, interface_type="usb", ip_address=None, port=None):
    model_num = int(boot_info.DeviceInfo.Model)
    uid_num = int(boot_info.DeviceInfo.DeviceUID)
    hw_ver = int(boot_info.DeviceInfo.HardwareVersion)
    mfw_ver = int(boot_info.DeviceInfo.MFWVersion)
    ffw_ver = int(boot_info.DeviceInfo.FFWVersion)
    
    data = {
        'model': model_num,
        'model_name': f"Model {model_num}",
        'uid': f"{uid_num:016x}",
        'hw_ver': hw_ver,
        'mfw_ver': f"{mfw_ver:#x}",
        'ffw_ver': f"{ffw_ver:#x}",
        'interface': "Network" if interface_type.lower() == "network" else "USB Direct",
        'ip_address': ip_address if interface_type.lower() == "network" else None,
        'port': port if interface_type.lower() == "network" else None,
        'licenses': [],
        'hardware_features': []
    }
    
    # Query Full UID
    try:
        if hasattr(dll, 'Device_GetFullUID'):
            uid_l = ctypes.c_uint64(0)
            uid_h = ctypes.c_uint32(0)
            if dll.Device_GetFullUID(ctypes.pointer(device), ctypes.byref(uid_l), ctypes.byref(uid_h)) == 0:
                data['full_uid'] = f"{uid_h.value:08x}{uid_l.value:016x}"
    except Exception:
        pass
    if 'full_uid' not in data:
        data['full_uid'] = data['uid']

    # Query Hardware State
    try:
        class HardWareState_TypeDef(ctypes.Structure):
            _fields_ = [
                ('GNSSPeriphType', ctypes.c_int),
                ('GNSSType', ctypes.c_int),
                ('OCXOType', ctypes.c_int),
                ('InternalOCXO', ctypes.c_uint8),
                ('SignalSourceEn', ctypes.c_uint8),
                ('ADC_VariableRateEn', ctypes.c_uint8),
                ('IM3_filter', ctypes.c_uint8),
            ]
        if hasattr(dll, 'Device_GetHardwareState'):
            hw_state = HardWareState_TypeDef()
            if dll.Device_GetHardwareState(ctypes.pointer(device), ctypes.byref(hw_state)) == 0:
                # (as numbers too: GNSS peripheral and receiver type, oscillator type 0 none /
                # 1 OCXO / 2 disciplined OCXO, whether the internal reference is an OCXO)
                data['hw_state'] = {"gnss_periph": int(hw_state.GNSSPeriphType), "gnss_type": int(hw_state.GNSSType),
                                    "ocxo_type": int(hw_state.OCXOType), "internal_ocxo": int(hw_state.InternalOCXO)}
                if hw_state.IM3_filter:
                    data['hardware_features'].append('IM3 Enhancement IF Filter')
                if hw_state.GNSSType:
                    data['hardware_features'].append('GNSS Receiver Module')
                if hw_state.SignalSourceEn:
                    data['hardware_features'].append('Internal Signal Source')
                if hw_state.InternalOCXO:
                    data['hardware_features'].append('Internal OCXO Timebase')
                if hw_state.ADC_VariableRateEn:
                    data['hardware_features'].append('Variable Rate ADC')
    except Exception:
        pass

    # Read License Options from the SDK's private device state. The SDK has no
    # public license API, so this relies on its internal memory layout, which was
    # verified only for specific builds; on any other build the offset points at
    # arbitrary memory and can segfault the process, so it is skipped.
    try:
        dev_ptr = device.value if hasattr(device, 'value') else device
        layout = _LICENSE_VECTOR_LAYOUTS.get((dll.Get_APIVersion(), platform.machine().lower()))
        if dev_ptr and layout:
            vec_offset = layout
            addr = dev_ptr + vec_offset
            begin_ptr = ctypes.c_uint64.from_address(addr).value
            end_ptr = ctypes.c_uint64.from_address(addr + 8).value
            if 0 < begin_ptr < end_ptr and (end_ptr - begin_ptr) % 80 == 0:
                num = (end_ptr - begin_ptr) // 80
                for i in range(num):
                    elem_addr = begin_ptr + i * 80
                    s1_ptr = ctypes.c_uint64.from_address(elem_addr + 8).value
                    s1_len = ctypes.c_uint64.from_address(elem_addr + 16).value
                    name_str = ctypes.string_at(s1_ptr, s1_len).decode('utf-8', errors='ignore') if 0 < s1_len < 256 else ''
                    
                    s2_ptr = ctypes.c_uint64.from_address(elem_addr + 40).value
                    s2_len = ctypes.c_uint64.from_address(elem_addr + 48).value
                    lic_str = ctypes.string_at(s2_ptr, s2_len).decode('utf-8', errors='ignore') if 0 < s2_len < 256 else ''
                    
                    status = ctypes.c_int32.from_address(elem_addr + 72).value
                    if name_str or lic_str:
                        desc = name_str
                        if name_str == '100MHzBandwidth':
                            desc = '100 MHz Real-Time Bandwidth (Wide RTSA Span)'
                        elif name_str == 'PulseDet':
                            desc = 'Pulse Detection & Profiling'
                        elif name_str == 'DC':
                            desc = 'DC Frequency Extension'
                        elif name_str == 'EMI':
                            desc = 'EMI Pre-Compliance Receiver'
                            
                        data['licenses'].append({
                            'name': name_str,
                            'file': lic_str,
                            'description': desc,
                            'status': status,
                            'enabled': (status == 0)
                        })
    except Exception:
        pass

    # Check Digital Demodulation License via Demod_Open
    try:
        if hasattr(dll, 'Demod_Open'):
            demod_status = dll.Demod_Open(ctypes.pointer(device))
            demod_enabled = (demod_status == 0)
            if demod_enabled and hasattr(dll, 'Demod_Close'):
                dll.Demod_Close(ctypes.pointer(device))
            data['licenses'].append({
                'name': 'DigitalDemod',
                'file': '_demodlic.txt',
                'description': 'Digital Signal Demodulation',
                'status': demod_status,
                'enabled': demod_enabled
            })
    except Exception:
        pass

    return data

def _zero_runs(values, min_run=4):
    """Mask of samples that belong to a run of at least min_run exact zeros."""
    zero = (values == 0.0).astype(np.int8)
    if len(zero) < min_run:
        return np.zeros(len(zero), dtype=bool)
    starts = np.convolve(zero, np.ones(min_run, dtype=np.int8), mode="valid") == min_run
    return np.convolve(starts.astype(np.int8), np.ones(min_run, dtype=np.int8), mode="full") > 0


def hardware_process(command_queue, data_queue, start_freq_hz, stop_freq_hz, probe_only=False, cal_stage_dir=None, ref_level=0.0, atten=-1, preamp=0x00, ifagc=1, ifagc_target=-9.0, ifagc_period=0.01, if_out=0, interface_type="usb", ip_address="192.168.1.50", port=5000, target_model=None, target_uid=None, usb_index=0, tried_libs=()):
    # dll is imported from htra_api_wrapper
    if not dll:
        data_queue.put(("error", "Failed to load Harogic API library."))
        return
        
    boot_profile = BootProfile_TypeDef()
    boot_info = BootInfo_TypeDef()

    if interface_type.lower() == "network":
        boot_profile.PhysicalInterface = PhysicalInterface_TypeDef.ETH
        boot_profile.DevicePowerSupply = DevicePowerSupply_TypeDef.Others
        boot_profile.ETH_IPVersion = IPVersion_TypeDef.IPv4
        try:
            import socket
            # An address, or a name (the analyzer announces "<model>-<serial>.local"). The
            # connection is pinned to the interface the analyzer is on, so that a Wi-Fi
            # network sharing its subnet cannot take the traffic (core/net_route.py).
            target_str = ip_address.strip()
            from core import net_route
            try:
                local_ifcs = [i for i in DeviceController.get_local_network_interfaces() if i.get("state") == "up"]
            except Exception:
                local_ifcs = []
            resolved_ip, net_if, route_note = net_route.resolve(target_str, int(port), local_ifcs)
            if net_if and sys.platform == "darwin":
                os.environ["HTRAAPI_NET_IF"] = net_if
            else:
                os.environ.pop("HTRAAPI_NET_IF", None)
            if resolved_ip != target_str or route_note:
                data_queue.put(("status", f"Analyzer {target_str} is {resolved_ip}"
                                          + (f" via {net_if}" if net_if else "") + (f" ({route_note})" if route_note else "")))
            ip_parts = [int(p) for p in resolved_ip.split(".")]
            ip_arr = (ctypes.c_uint8 * 16)()
            for i in range(min(4, len(ip_parts))):
                ip_arr[i] = ip_parts[i]
            boot_profile.ETH_IPAddress = ip_arr
        except Exception as e:
            data_queue.put(("error", f"Invalid target IP address / Hostname: '{ip_address}' ({e})"))
            return
        boot_profile.ETH_RemotePort = int(port)
        boot_profile.ETH_ReadTimeOut = 3000
    else:
        boot_profile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort
        boot_profile.PhysicalInterface = PhysicalInterface_TypeDef.USB

    det_model = target_model
    det_uid = target_uid
    dev_num_to_open = 0
    if getattr(dll, "_missing", False) and (interface_type.lower() != "usb" or target_uid):
        data_queue.put(("error", f"Harogic SDK not available: {dll.error}"))
        data_queue.put(("connected", False))
        return

    # 1. Identify device Model & UID before opening to stage matching calibration files
    if interface_type.lower() == "usb":
        harogic_count = 0
        tinysa_index = None   # which tinySA to open, if this slot isn't a Harogic analyzer
        try:
            dev_count = ctypes.c_uint8(0)
            dev_num_list = (ctypes.c_uint8 * 256)()
            dev_info_list = (DeviceInfo_TypeDef * 256)()
            for _ in range(4):
                list_status = dll.Device_List(ctypes.pointer(boot_profile), ctypes.pointer(dev_count), dev_num_list, dev_info_list)
                if list_status == 0 and dev_count.value > 0:
                    harogic_count = dev_count.value
                    matched_idx = 0
                    if target_uid:
                        for i in range(dev_count.value):
                            if int(dev_info_list[i].DeviceUID) == target_uid:
                                matched_idx = i
                                break
                    elif 0 <= usb_index < dev_count.value:
                        matched_idx = usb_index
                    else:
                        # Opening analyzer 0 instead would hand two slots the same
                        # analyzer. USB indexes past the Harogic analyzers are tinySAs.
                        tinysa_index = usb_index - dev_count.value
                        break
                    det_model = int(dev_info_list[matched_idx].Model)
                    det_uid = int(dev_info_list[matched_idx].DeviceUID)
                    dev_num_to_open = int(dev_num_list[matched_idx])
                    break
                time.sleep(0.15)
        except Exception:
            pass
        # USB analyzers are the Harogic ones, then tinySA / tinySA Ultra units
        # (serial devices, driven by tinysa_process instead of the SDK).
        if tinysa_index is None and harogic_count == 0 and not target_uid:
            tinysa_index = usb_index
        if tinysa_index is not None:
            try:
                tinysa = find_tinysa(tinysa_index)
            except TinySAError as e:
                data_queue.put(("error", str(e)))
                data_queue.put(("connected", False))
                return
            if tinysa is not None:
                tinysa_process(command_queue, data_queue, start_freq_hz, stop_freq_hz, atten=atten,
                               preamp=preamp, probe_only=probe_only, device=tinysa)
                return
            if harogic_count:
                data_queue.put(("error", f"USB analyzer #{usb_index + 1} not found: "
                                         f"{harogic_count} Harogic USB analyzer(s) connected and no "
                                         f"tinySA #{tinysa_index + 1}."))
                data_queue.put(("connected", False))
                return
            if getattr(dll, "_missing", False):
                data_queue.put(("error", f"No tinySA found, and the Harogic SDK is not available ({dll.error})."))
                data_queue.put(("connected", False))
                return
    elif interface_type.lower() == "network" and (det_model is None or det_uid is None):
        try:
            count = ctypes.c_uint8(0)
            dev_info = (NetworkDeviceInfo_TypeDef * 64)()
            local_ip = (ctypes.c_uint8 * 4)()
            local_mask = (ctypes.c_uint8 * 4)()
            if hasattr(dll, 'Device_GetNetworkDeviceList'):
                dll.Device_GetNetworkDeviceList(ctypes.byref(count), ctypes.byref(dev_info), ctypes.byref(local_ip), ctypes.byref(local_mask))
                if count.value > 0:
                    for i in range(count.value):
                        dev_ip = '.'.join(str(b) for b in dev_info[i].IPAddress)
                        if dev_ip == ip_address.strip():
                            det_model = int(dev_info[i].Model)
                            det_uid = int(dev_info[i].DeviceUID)
                            break
        except Exception:
            pass

    # 2. If device identified, auto-deploy calibration from CalibrationManager
    if det_model is not None and det_uid is not None:
        try:
            from core.calibration_manager import CalibrationManager
            cm = CalibrationManager()
            cm.deploy_cal_files(det_model, det_uid, target_dir=cal_stage_dir)
        except Exception as e:
            print(f"[DeviceController] Calibration deployment notice: {e}")

    if probe_only:
        if det_model is not None and det_uid is not None:
            data_queue.put(("device_info", (det_model, det_uid)))
            return
            
        if interface_type.lower() == "network":
            data_queue.put(("error", f"No Harogic analyzer detected at {ip_address}:{port}."))
        else:
            data_queue.put(("error", "No Harogic analyzer detected. Please check USB connection."))
        return

    device = ctypes.c_void_p()
    dev_num = ctypes.c_int(dev_num_to_open)
    
    status = -1
    target = f"{ip_address}:{port}" if interface_type.lower() == "network" else "USB"
    is_network = interface_type.lower() == "network"
    if is_network:
        data_queue.put(("status", f"Connecting to network analyzer at {target}…"))
    stalled_opens = 0
    # Analyzer firmware and SDK builds must match (a mismatch is -49 over USB
    # but a connection reset over Ethernet), and two SDK builds cannot share a
    # process. So this process uses the one it was started with; if the open
    # fails and another build is shipped, it says so and the controller starts
    # a fresh process with that build.
    cur_lib = getattr(dll, "_htra_path", "")
    alt_lib = next((p for p in _api.available_libraries() if p != cur_lib and p not in tried_libs), None)
    max_attempts = 8 if alt_lib is None else 2
    attempt = 0
    while True:
        attempt += 1
        t_open = time.time()
        status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
        if status not in (0, -3, -4) and (status == -49 or attempt >= max_attempts):
            fw = int(boot_info.DeviceInfo.MFWVersion)
            if alt_lib is not None:
                data_queue.put(("sdk_retry", {"status": int(status), "firmware": fw, "failed": cur_lib, "next": alt_lib,
                                              "tried": list(tried_libs) + [cur_lib]}))
                return
            if status == -49:
                versions = ", ".join(_api.library_version(p) for p in list(tried_libs) + [cur_lib])
                data_queue.put(("error", f"Analyzer firmware {fw:#x} matches none of the SDK builds shipped with fReqon "
                                         f"({versions}). Update the analyzer firmware or add a matching SDK build to lib/macos/."))
                return
            break
        if status in (-3, -4):
            break
        if status == 0 and is_network and time.time() - t_open > NETWORK_OPEN_STALL_S and stalled_opens < 3:
            # A network open normally takes ~3 s. Sometimes (~1 in 4) the analyzer
            # stops answering part-way through the handshake; the SDK then
            # "succeeds" only after its read timeouts (~21 s) and the session is
            # dead (every call times out with 10060). Reconnect instead.
            stalled_opens += 1
            dll.Device_Close(ctypes.pointer(device))
            data_queue.put(("status", f"Network analyzer at {target} stalled during connection; "
                                      f"reconnecting ({stalled_opens}/3)…"))
            time.sleep(1.0)
            continue
        if status == 0:
            break
        # Each network attempt can take the full read timeout, so say what's happening
        data_queue.put(("status", f"Opening analyzer ({target}): attempt {attempt} failed "
                                  f"(Status: {status}, {time.time() - t_open:.1f} s), retrying…"))
        time.sleep(0.25)
    
    if status != 0:
        err_msg = f"Failed to open device (Status: {status})"
        if status in (-3, -4):
            cal_type = "RF" if status == -3 else "IF"
            if det_model is not None and det_uid is not None:
                err_msg = f"{cal_type} calibration file is missing for Analyzer {det_model:03d}_{det_uid:016x}."
                data_queue.put(("missing_cal", (det_model, det_uid, err_msg)))
            else:
                err_msg = f"{cal_type} calibration file is missing. Please import calibration files."
                data_queue.put(("missing_cal", (0, 0, err_msg)))
            return
        elif status == -1:
            if interface_type.lower() == "network":
                err_msg = f"Network connection failed to {ip_address}:{port}. Check network subnet, IP settings, and device power."
            else:
                err_msg = "Device USB communication failed. Please reconnect USB device."
        elif status == 10054:
            err_msg = f"Ethernet device at {ip_address} disconnected."
        elif status == 10068:
            err_msg = f"No Harogic analyzer found at IP {ip_address}:{port}."
        data_queue.put(("error", err_msg))
        return
        
    data_queue.put(("sdk_ok", cur_lib))
    # Identity always comes from the analyzer itself, on every connect.
    model = int(boot_info.DeviceInfo.Model)
    uid = int(boot_info.DeviceInfo.DeviceUID)
    # (Device_List reports a serial of 0 on some SDK builds: that is "unknown".)
    expected_uid = target_uid if target_uid else det_uid
    if expected_uid and int(expected_uid) != uid:
        data_queue.put(("status", f"Warning: expected analyzer {int(expected_uid):016x} but "
                                  f"{target} is {model:03d}_{uid:016x}; using the connected analyzer."))

    # The analyzer supplies its RF/IF calibration from flash when Device_Open finds
    # no files, and the SDK caches it in the staging CalFile/. Keep it in the
    # calibration library so the app knows this analyzer is calibrated.
    if cal_stage_dir:
        try:
            from core.calibration_manager import CalibrationManager
            prefix = f"{model:03d}_{uid:016x}_"
            cached = [str(f) for f in Path(cal_stage_dir).glob(prefix + "*.txt")]
            cm = CalibrationManager()
            if cached and not cm.is_calibrated(model, uid):
                cm.import_files(cached)
                data_queue.put(("status", f"Stored calibration provided by analyzer {model:03d}_{uid:016x}."))
        except Exception as e:
            print(f"[DeviceController] Could not store device calibration: {e}")

    data_queue.put(("device_info", (model, uid)))
    try:
        endorsements = _query_hardware_endorsements(dll, device, boot_info, interface_type, ip_address, port)
        data_queue.put(("hw_endorsements", endorsements))
    except Exception:
        pass
    data_queue.put(("connected", True))
    if interface_type.lower() == "network":
        data_queue.put(("status", f"Connected to Network Analyzer ({ip_address}:{port})."))
    else:
        data_queue.put(("status", "Device opened successfully."))
        
    def query_power():
        """Supply voltage/current per port; safe while streaming (verified for
        SWP, RTA and IQS at the top rate)."""
        if not hasattr(dll, 'Device_QueryPowerSupplyState'):
            return
        ps = PowerSupplyState_TypeDef()
        try:
            if dll.Device_QueryPowerSupplyState(ctypes.pointer(device), ctypes.pointer(ps)) == 0:
                data_queue.put(("power", {
                    "port_v": float(ps.rf_vlotage), "port_a": float(ps.rf_current),
                    "usb_v": float(ps.usb_vlotage), "usb_a": float(ps.usb_current),
                }))
        except Exception:
            pass

    ocxo_type = [None]
    try:
        ocxo_type[0] = (endorsements or {}).get("hw_state", {}).get("ocxo_type")
    except Exception:
        pass

    def _enum_int(v):
        # (SDK enum fields come back as ints or as small ctypes objects, depending on the binding)
        v = getattr(v, "value", v)
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    def query_gnss():
        """Position, lock and time from the analyzer's GNSS module (all zero without a fix)."""
        fn = getattr(dll, 'Device_GetGNSSInfo', None)
        if fn is None:
            return
        g = GNSSInfo_TypeDef()
        try:
            if fn(ctypes.pointer(device), ctypes.pointer(g)) == 0:
                info = {
                    "lat": float(g.latitude), "lon": float(g.longitude), "alt": float(g.altitude),
                    "sats": int(g.SatsNum), "lock": bool(g.GNSS_LockState), "docxo_lock": bool(g.DOCXO_LockState),
                    # the reference oscillator: disciplined to GNSS ("lock") or free-running ("hold")
                    "docxo_mode": "hold" if _enum_int(g.DOCXO_WorkMode) == 1 else "lock",
                    "antenna": "internal" if _enum_int(g.GNSSAntennaState) == 1 else "external",
                    "time": (int(g.Year), int(g.month), int(g.day), int(g.hour), int(g.minute), int(g.second)),
                }
                # Whether there is an oscillator to discipline at all (0: none, 1: OCXO, 2: disciplined OCXO)
                if ocxo_type[0] is not None:
                    info["ocxo_type"] = ocxo_type[0]
                # How far the reference clock is from GNSS time, from the latest sweep packet
                try:
                    off = float(meas_aux_info.RefClkFreqOffset)
                    if off == off and abs(off) < 1e3:
                        info["ref_offset_ppm"] = off
                except Exception:
                    pass
                # Satellites in view and their signal strength, where the SDK build has the call
                sat_fn = getattr(dll, 'Device_GetGNSS_SatDate', None)
                if sat_fn is not None and not getattr(dll, "_missing", False):
                    sd = GNSS_SatDate_TypeDef()
                    try:
                        if sat_fn(ctypes.pointer(device), ctypes.pointer(sd)) == 0:
                            info.update({"sats_in_view": int(sd.SatsNum_All), "sats_used": int(sd.SatsNum_Use),
                                         "snr_avg": int(sd.GNSS_SNR_UsePos.Avg_SatxC_No),
                                         "snr_max": int(sd.GNSS_SNR_UsePos.Max_SatxC_No),
                                         "snr_min": int(sd.GNSS_SNR_UsePos.Min_SatxC_No)})
                    except Exception:
                        pass
                data_queue.put(("gnss", info))
        except Exception:
            pass

    query_power()
    query_gnss()
    last_power_check_time = time.time()

    # Read initial temperature once while device channel is completely idle
    try:
        dev_state = DeviceState_TypeDef()
        if hasattr(dll, 'Device_QueryDeviceState_Realtime'):
            st = dll.Device_QueryDeviceState_Realtime(ctypes.pointer(device), ctypes.pointer(dev_state))
            if st == 0 and dev_state.Temperature != 0:
                data_queue.put(("temperature", float(dev_state.Temperature) / 100.0))
    except Exception:
        pass
    
    # --- Operating Modes Setup ---
    current_mode = "SWP"  # "SWP", "RTA", "DET"
    
    # 1. SWP State
    swp_profile_in = SWP_Profile_TypeDef()
    swp_profile_out = SWP_Profile_TypeDef()
    trace_info = SWP_TraceInfo_TypeDef()
    
    current_rbw_mode = RBWMode_TypeDef.RBW_Manual
    init_span = float(stop_freq_hz) - float(start_freq_hz)
    current_rbw_hz = auto_rbw_for_span(init_span)
    current_vbw_mode = VBWMode_TypeDef.VBW_Manual
    current_vbw_hz = current_rbw_hz

    dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
    swp_profile_in.StartFreq_Hz = float(start_freq_hz)
    swp_profile_in.StopFreq_Hz = float(stop_freq_hz)
    swp_profile_in.CenterFreq_Hz = (float(start_freq_hz) + float(stop_freq_hz)) / 2.0
    swp_profile_in.Span_Hz = init_span
    swp_profile_in.FreqAssignment = SWP_FreqAssignment_TypeDef.StartStop
    swp_profile_in.RBWMode = current_rbw_mode
    swp_profile_in.RBW_Hz = current_rbw_hz
    swp_profile_in.VBWMode = current_vbw_mode
    swp_profile_in.VBW_Hz = current_vbw_hz
    swp_profile_in.RefLevel_dBm = float(ref_level)
    swp_profile_in.Atten = -1 if atten < 0 else int(atten)
    swp_profile_in.Preamplifier = preamp
    swp_profile_in.EnableIFAGC = ifagc
    swp_profile_in.TraceAlign = TraceAlign_TypeDef.AlignToStart
    
    status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
    if status != 0:
        dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
        swp_profile_in.TraceAlign = TraceAlign_TypeDef.AlignToStart
        status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
    if status == 0:
        if abs(swp_profile_out.RefLevel_dBm - swp_profile_in.RefLevel_dBm) > 0.1:
            data_queue.put(("amplitude_clamped", (float(swp_profile_out.RefLevel_dBm), int(swp_profile_out.Atten))))
        data_queue.put(("hw_rbw_updated", (float(swp_profile_out.RBW_Hz), float(swp_profile_out.VBW_Hz))))
        
    full_sweep_points = trace_info.FullsweepTracePoints if status == 0 else 1001
    partial_sweep_points = trace_info.PartialsweepTracePoints if status == 0 else 1001
    total_hops = trace_info.TotalHops if status == 0 else 1
    
    max_buffer_pts = max(full_sweep_points, partial_sweep_points * total_hops, 32768)
    partial_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
    partial_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
    full_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
    full_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
    
    hop_index = ctypes.c_int(0)
    frame_index = ctypes.c_int(0)
    meas_aux_info = MeasAuxInfo_TypeDef()
    
    if status == 0 and trace_info.TraceBinBW_Hz > 0:
        freq_np = trace_info.StartFreq_Hz + np.arange(full_sweep_points, dtype=np.float64) * trace_info.TraceBinBW_Hz
    else:
        freq_np = np.linspace(swp_profile_out.StartFreq_Hz, swp_profile_out.StopFreq_Hz, full_sweep_points)
    power_np = np.full(full_sweep_points, -120.0, dtype=np.float32)
    last_valid_power = None

    # 2. RTA State
    rta_profile_in = RTA_Profile_TypeDef()
    rta_profile_out = RTA_Profile_TypeDef()
    rta_frame_info = RTA_FrameInfo_TypeDef()
    rta_plot_info = RTA_PlotInfo_TypeDef()
    rta_trigger_info = RTA_TriggerInfo_TypeDef()
    rta_spec_trace = None
    rta_spec_bitmap = None

    # 3. DET State
    det_profile_in = DET_Profile_TypeDef()
    det_profile_out = DET_Profile_TypeDef()
    det_stream_info = DET_StreamInfo_TypeDef()
    det_trigger_info = DET_TriggerInfo_TypeDef()
    det_norm_packet = None
    det_raw_stream = None

    # 4. IQS State (Demodulation)
    iqs_profile_in = IQS_Profile_TypeDef()
    iqs_profile_out = IQS_Profile_TypeDef()
    iqs_stream_info = IQS_StreamInfo_TypeDef()
    iqs_raw_stream = None

    # 5. MSCAN State (Hardware Discrete Channel Scanning)
    mscan_profiles_in = None
    mscan_profiles_out = None
    # One MSCAN_Info per scan element: the SDK may fill an entry per profile, so a
    # single struct could be overrun. Entries it leaves zeroed fall back to [0].
    mscan_infos = (MSCAN_Info_Typedef * 1)()

    def mscan_info_for(el_idx):
        if 0 <= el_idx < len(mscan_infos) and mscan_infos[el_idx].SpectrumPoints > 0:
            return mscan_infos[el_idx]
        return mscan_infos[0]
    mscan_channels = []
    mscan_running = False
    mscan_spec_buf = None
    mscan_iq_buf = None

    is_running = False
    consecutive_errors = 0
    acq_failures = 0  # consecutive failed DET/IQS acquisition cycles
    # Exit (closing the device) if the GUI process dies without telling us, so an
    # orphaned process never keeps the analyzer's USB interface claimed.
    parent = multiprocessing.parent_process()
    last_parent_check = 0.0
    if parent is not None:
        # The loop below can't notice a dead parent while it is blocked inside an
        # SDK call (e.g. a stalled network read), and an orphan would keep the
        # analyzer's only session. A watchdog thread exits the process instead;
        # the OS then closes the USB handle / network socket.
        def _parent_watchdog():
            while True:
                time.sleep(1.0)
                if not parent.is_alive():
                    os._exit(0)
        threading.Thread(target=_parent_watchdog, name="parent-watchdog", daemon=True).start()
    last_temp_check_time = 0.0

    # True while an Adaptive-mode RTA stream is running (triggered once, then read
    # continuously); it must be stopped before reconfiguring or changing modes.
    rta_streaming = False
    rta_acc, rta_acc_t = None, 0.0     # RTA bitmap hits accumulated between sends
    # SWP settings commands mark the profile dirty instead of reprogramming the
    # hardware each time; it is configured once after the queued commands are
    # drained (returning to SWP sends five settings commands in a row).
    swp_dirty = False
    swp_dirty_msg = ""        # first message of a burst is reported
    swp_dirty_fatal = False   # a failed frequency config stops acquisition
    # Continuous IQS (Adaptive trigger): one bus trigger, then gap-free packets.
    # Used for audio monitoring, where FixedPoints bursts leave audible gaps.
    iqs_continuous = False
    iqs_streaming = False

    def stop_rta_stream():
        """Stop any continuous (Adaptive) RTA or IQS stream in progress."""
        nonlocal rta_streaming, iqs_streaming
        if rta_streaming:
            try:
                dll.RTA_BusTriggerStop(ctypes.pointer(device))
            except Exception:
                pass
            rta_streaming = False
        if iqs_streaming:
            try:
                dll.IQS_BusTriggerStop(ctypes.pointer(device))
            except Exception:
                pass
            iqs_streaming = False

    def stop_mscan_if_running():
        nonlocal mscan_running
        if mscan_running:
            try:
                dll.MSCAN_Stop(ctypes.pointer(device))
            except Exception:
                pass
            if mscan_profiles_in is not None and len(mscan_channels) > 0:
                try:
                    deinit_cnt = ctypes.c_int32(len(mscan_channels))
                    dll.MSCAN_ProfileDeinit(ctypes.pointer(device), mscan_profiles_in, ctypes.pointer(deinit_cnt))
                except Exception:
                    pass
            mscan_running = False
            time.sleep(0.015)

    def apply_swp_bandwidth(span_hz):
        """Set RBW/VBW in swp_profile_in from the current UI bandwidth modes."""
        if current_rbw_mode == 1:  # Automatic: choose RBW from the span
            swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_Manual
            swp_profile_in.RBW_Hz = auto_rbw_for_span(span_hz)
        elif current_rbw_mode == 2:
            swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_OneThousandthSpan
        elif current_rbw_mode == 3:
            swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_OnePercentSpan
        else:
            swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_Manual
            if current_rbw_hz > 0:
                swp_profile_in.RBW_Hz = float(current_rbw_hz)

        vbw_modes = {
            1: VBWMode_TypeDef.VBW_EqualToRBW,
            2: VBWMode_TypeDef.VBW_TenPercentRBW,
            3: VBWMode_TypeDef.VBW_OnePercentRBW,
            4: VBWMode_TypeDef.VBW_TenTimesRBW,
        }
        swp_profile_in.VBWMode = vbw_modes.get(current_vbw_mode, VBWMode_TypeDef.VBW_Manual)
        if current_vbw_mode not in vbw_modes and current_vbw_hz > 0:
            swp_profile_in.VBW_Hz = float(current_vbw_hz)

    def rearm_swp():
        nonlocal full_sweep_points, partial_sweep_points, total_hops
        nonlocal partial_freq_ctypes, partial_spec_ctypes, full_freq_ctypes, full_spec_ctypes
        nonlocal freq_np, power_np, last_valid_power
        swp_profile_in.TraceAlign = TraceAlign_TypeDef.AlignToStart
        status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
        if status != 0:
            dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
            swp_profile_in.TraceAlign = TraceAlign_TypeDef.AlignToStart
            status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
        if status == 0:
            full_sweep_points = trace_info.FullsweepTracePoints
            partial_sweep_points = trace_info.PartialsweepTracePoints
            total_hops = trace_info.TotalHops
            max_buffer_pts = max(full_sweep_points, partial_sweep_points * total_hops, 32768)
            partial_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
            partial_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
            full_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
            full_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
            if trace_info.TraceBinBW_Hz > 0:
                freq_np = trace_info.StartFreq_Hz + np.arange(full_sweep_points, dtype=np.float64) * trace_info.TraceBinBW_Hz
            else:
                freq_np = np.linspace(swp_profile_in.StartFreq_Hz, swp_profile_in.StopFreq_Hz, full_sweep_points)
            power_np = np.full(full_sweep_points, -120.0, dtype=np.float32)
            last_valid_power = None
            data_queue.put(("trace_points", full_sweep_points))
            data_queue.put(("hw_rbw_updated", (float(swp_profile_out.RBW_Hz), float(swp_profile_out.VBW_Hz))))
            if abs(swp_profile_out.RefLevel_dBm - swp_profile_in.RefLevel_dBm) > 0.1:
                data_queue.put(("amplitude_clamped", (float(swp_profile_out.RefLevel_dBm), int(swp_profile_out.Atten))))
        return status
    
    while True:
        now = time.time()
        if parent is not None and now - last_parent_check > 0.5:
            last_parent_check = now
            if not parent.is_alive():
                # Nobody will read our queues again: don't let interpreter exit
                # block flushing them into full pipes.
                data_queue.cancel_join_thread()
                command_queue.cancel_join_thread()
                break

        # Check for commands
        try:
            cmd = command_queue.get_nowait()
            if isinstance(cmd, tuple) and cmd[0] == "close":
                stop_rta_stream()
                stop_mscan_if_running()
                break
                
            if cmd == "stop":
                stop_rta_stream()
                stop_mscan_if_running()
                break
            elif cmd == "start":
                if current_mode == "SWP" and mscan_running:
                    stop_mscan_if_running()
                    swp_dirty = True
                is_running = True
                consecutive_errors = 0
            elif cmd == "pause":
                stop_rta_stream()
                if mscan_running:
                    stop_mscan_if_running()
                is_running = False
            elif cmd == "stop_mscan":
                # Only acts if MSCAN is actually in use; otherwise leave the mode alone.
                if mscan_running or current_mode == "MSCAN":
                    stop_mscan_if_running()
                    current_mode = "SWP"
                    swp_dirty, swp_dirty_msg = True, swp_dirty_msg or "MSCAN stopped, returning to Swept Spectrum"
                
            elif isinstance(cmd, tuple) and cmd[0] == "set_mode":
                stop_rta_stream()
                target_mode, mode_params = cmd[1]
                new_mode = target_mode.upper()
                if new_mode != "MSCAN" and mscan_running:
                    stop_mscan_if_running()
                current_mode = new_mode
                is_running = True
                consecutive_errors = 0
                
                if current_mode == "SWP":
                    swp_dirty, swp_dirty_msg = True, swp_dirty_msg or "Switched to Swept Spectrum (SWP) mode"
                elif current_mode == "RTA":
                    data_queue.put(("status", "Switched to Real-Time Spectrum (RTSA) mode"))
                elif current_mode == "DET":
                    data_queue.put(("status", "Switched to Zero-Span (DET) mode"))
                elif current_mode == "IQS":
                    data_queue.put(("status", "Switched to IQ Stream (Demodulation) mode"))
                elif current_mode == "MSCAN":
                    data_queue.put(("status", "Switched to Discrete Channel Scanning (MSCAN) mode"))

            elif isinstance(cmd, tuple) and cmd[0] == "fan_config":
                fan_state, threshold_temp = cmd[1]
                try:
                    if hasattr(dll, 'Device_SetFanState'):
                        dll.Device_SetFanState(ctypes.pointer(device), ctypes.c_int(fan_state), ctypes.c_float(threshold_temp))
                        data_queue.put(("status", f"Fan state set to {fan_state} (Threshold: {threshold_temp:.1f} °C)"))
                except Exception as e:
                    data_queue.put(("error", f"Failed to set fan state: {e}"))

            elif isinstance(cmd, tuple) and cmd[0] == "timed_capture":
                # One IQ capture with its timing, for time-difference location: (centre Hz,
                # decimation, samples, reference level, trigger source, request id). With the
                # GNSS 1PPS trigger (9) the capture starts on the GPS second, so captures made
                # on different analyzers line up. The analyzer returns to sweeping afterwards.
                c_freq, dec_factor, n_samp, r_lvl, trig_src, req_id = cmd[1][:6]
                stop_rta_stream()
                stop_mscan_if_running()
                result = {"id": req_id, "center_freq": float(c_freq), "trigger_source": int(trig_src), "ok": False}
                try:
                    prof_in, prof_out, s_info = IQS_Profile_TypeDef(), IQS_Profile_TypeDef(), IQS_StreamInfo_TypeDef()
                    dll.IQS_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(prof_in))
                    prof_in.CenterFreq_Hz = float(c_freq)
                    prof_in.RefLevel_dBm = float(r_lvl)
                    prof_in.DecimateFactor = int(dec_factor)
                    prof_in.DataFormat = DataFormat_TypeDef.Complex16bit
                    prof_in.TriggerSource = int(trig_src)
                    prof_in.TriggerMode = TriggerMode_TypeDef.FixedPoints
                    prof_in.TriggerLength = int(n_samp)
                    st = dll.IQS_Configuration(ctypes.pointer(device), ctypes.pointer(prof_in), ctypes.pointer(prof_out), ctypes.pointer(s_info))
                    if st != 0:
                        raise RuntimeError(f"IQ configuration failed (SDK status {st})")
                    pkt = c_int16_p()
                    raw = (ctypes.c_int16 * (int(s_info.StreamSamples) * 2))()
                    scale = ctypes.c_float(0.0)
                    aux, trig = MeasAuxInfo_TypeDef(), TriggerInfo_TypeDef()
                    t_host = time.time()
                    if int(trig_src) == 2:                      # bus trigger: started by this call
                        dll.IQS_BusTriggerStart(ctypes.pointer(device))
                    pkt_samples, total = int(s_info.PacketSamples), int(s_info.StreamSamples)
                    for p_idx in range(int(s_info.PacketCount)):
                        st = dll.IQS_GetIQStream(ctypes.pointer(device), ctypes.pointer(pkt), ctypes.pointer(scale),
                                                 ctypes.pointer(trig), ctypes.pointer(aux))
                        if st not in ACQ_OK or not pkt:
                            raise RuntimeError(f"IQ capture failed at packet {p_idx} (SDK status {st})")
                        if p_idx == 0:
                            edges = int(trig.InPacketTriggerEdges)
                            result.update({
                                "t_host": t_host, "t_host_first_packet": time.time(),
                                "sys_timer_first": int(trig.SysTimerCountOfFirstDataPoint),
                                "trigger_edges": edges,
                                "edge_index": [int(trig.StartDataIndexOfTriggerEdges[i]) for i in range(min(edges, 25))],
                                "edge_timer": [int(trig.SysTimerCountOfEdges[i]) for i in range(min(edges, 25))],
                                "sys_timestamp": float(aux.SysTimeStamp), "abs_timestamp": float(aux.AbsoluteTimeStamp),
                                "ns_since_epoch": int(aux.nsSinceEpoch), "ref_offset_ppm": float(aux.RefClkFreqOffset),
                                "lat": float(aux.Latitude), "lon": float(aux.Longitude),
                            })
                        a = p_idx * pkt_samples * 2
                        n_copy = 2 * (pkt_samples if (p_idx + 1) * pkt_samples <= total else total - p_idx * pkt_samples)
                        raw[a:a + n_copy] = pkt[0:n_copy]
                    if int(trig_src) == 2:
                        dll.IQS_BusTriggerStop(ctypes.pointer(device))
                    arr = np.frombuffer(raw, dtype=np.int16)
                    k = float(scale.value) if scale.value > 0 else 1.97e-6
                    iq = (arr[0::2].astype(np.float32) + 1j * arr[1::2].astype(np.float32)) * np.float32(k)
                    sr = float(s_info.IQSampleRate) or IQ_FALLBACK_BASE_RATE_HZ / max(1, int(prof_out.DecimateFactor))
                    result.update({"ok": True, "sample_rate": sr, "decimate": int(prof_out.DecimateFactor),
                                   "samples": len(iq), "bandwidth": float(s_info.Bandwidth)})
                    data_queue.put(("timed_capture", (iq.astype(np.complex64), result)))
                except Exception as e:
                    result["error"] = str(e)
                    data_queue.put(("timed_capture", (None, result)))
                # Back to sweeping, whatever it was doing
                iqs_raw_stream = None
                current_mode = "SWP"
                swp_dirty, swp_dirty_msg = True, swp_dirty_msg or "Timed capture done, returning to Swept Spectrum"

            elif isinstance(cmd, tuple) and cmd[0] == "docxo_mode":
                # The reference oscillator: "lock" disciplines it to GNSS, "hold" lets it run free
                want = str(cmd[1]).lower()
                fn = getattr(dll, "Device_SetDOCXOWorkMode", None)
                try:
                    if fn is None:
                        raise RuntimeError("this SDK cannot set the reference oscillator mode")
                    mode = DOCXOWorkMode_TypeDef(1 if want == "hold" else 0)
                    st = fn(ctypes.pointer(device), mode)
                    # What the analyzer says its mode is afterwards
                    back = []
                    for name in ("Device_GetDOCXOWorkMode_Realtime", "Device_GetDOCXOWorkMode"):
                        get = getattr(dll, name, None)
                        if get is not None:
                            m = DOCXOWorkMode_TypeDef(0)
                            rs = get(ctypes.pointer(device), ctypes.pointer(m))
                            back.append(f"{'now' if 'Realtime' in name else 'stored'}: "
                                        f"{'hold' if _enum_int(m) == 1 else 'lock'}" + ("" if rs == 0 else f" (status {rs})"))
                    data_queue.put(("status", f"Reference oscillator set to {'hold' if want == 'hold' else 'discipline to GNSS'}"
                                              + ("" if st == 0 else f" failed (SDK status {st})")
                                              + (f"; reads back {', '.join(back)}" if back else "")))
                    query_gnss()
                except Exception as e:
                    data_queue.put(("error", f"Reference oscillator mode not set: {e}"))

            elif isinstance(cmd, tuple) and cmd[0] == "freq_comp":
                # Input-chain compensation (antenna/cable/amplifier): a frequency
                # table of dB added to every reading, applied by the SDK.
                freqs, vals = cmd[1]
                n = len(freqs)
                fn = getattr(dll, "Devcie_SetFreqResponseCompensation_PM1", None)
                try:
                    if fn is None:
                        raise RuntimeError("this SDK has no frequency response compensation")
                    f_arr = (ctypes.c_double * max(n, 1))(*freqs)
                    v_arr = (ctypes.c_float * max(n, 1))(*vals)
                    st = fn(ctypes.pointer(device), ctypes.c_uint8(1 if n else 0), f_arr, v_arr, ctypes.c_uint32(n))
                    data_queue.put(("freq_comp", (st, n)))
                    if st != 0:
                        data_queue.put(("error", f"Input compensation not applied (SDK status {st})"))
                    elif current_mode == "SWP":
                        swp_dirty, swp_dirty_msg = True, swp_dirty_msg or "Input compensation updated"
                except Exception as e:
                    data_queue.put(("freq_comp", (-1, n)))
                    data_queue.put(("error", f"Input compensation not applied: {e}"))

            elif isinstance(cmd, tuple) and cmd[0] == "rta_config":
                stop_rta_stream()
                stop_mscan_if_running()
                args = cmd[1]
                c_freq = args[0]
                dec_factor = args[1]
                r_lvl = args[2]
                trig_src = args[3]
                trig_mode = args[4]
                trig_time = args[5]
                preamp = args[6] if len(args) > 6 else 0x00
                atten = args[7] if len(args) > 7 else 0
                
                current_mode = "RTA"
                dll.RTA_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(rta_profile_in))
                rta_profile_in.CenterFreq_Hz = float(c_freq)
                rta_profile_in.RefLevel_dBm = float(r_lvl)
                rta_profile_in.DecimateFactor = int(dec_factor)
                rta_profile_in.TriggerSource = int(trig_src)
                rta_profile_in.TriggerMode = int(trig_mode)
                rta_profile_in.TriggerAcqTime = float(trig_time)
                rta_profile_in.Preamplifier = int(preamp)
                rta_profile_in.Atten = int(atten)
                
                status = dll.RTA_Configuration(ctypes.pointer(device), ctypes.pointer(rta_profile_in), ctypes.pointer(rta_profile_out), ctypes.pointer(rta_frame_info))
                if status == 0:
                    rta_spec_trace = (ctypes.c_uint8 * rta_frame_info.PacketValidPoints)()
                    rta_spec_bitmap = (ctypes.c_uint16 * (rta_frame_info.FrameHeight * rta_frame_info.FrameWidth))()
                    data_queue.put(("status", f"RTA active @ {c_freq/1e6:.2f} MHz (Span: {(rta_frame_info.StopFrequency_Hz-rta_frame_info.StartFrequency_Hz)/1e6:.1f} MHz)"))
                else:
                    data_queue.put(("error", f"RTA configuration failed (Status: {status})"))

            elif isinstance(cmd, tuple) and cmd[0] == "det_config":
                stop_rta_stream()
                stop_mscan_if_running()
                c_freq, dec_factor, r_lvl, trig_src, trig_mode, trig_len = cmd[1][:6]
                current_mode = "DET"
                dll.DET_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(det_profile_in))
                det_profile_in.CenterFreq_Hz = float(c_freq)
                det_profile_in.RefLevel_dBm = float(r_lvl)
                det_profile_in.DecimateFactor = int(dec_factor)
                det_profile_in.TriggerSource = int(trig_src)
                det_profile_in.TriggerMode = int(trig_mode)
                det_profile_in.TriggerLength = int(trig_len)
                
                status = dll.DET_Configuration(ctypes.pointer(device), ctypes.pointer(det_profile_in), ctypes.pointer(det_profile_out), ctypes.pointer(det_stream_info))
                if status == 0:
                    det_norm_packet = (ctypes.c_float * det_stream_info.PacketSamples)()
                    det_raw_stream = (ctypes.c_float * det_profile_out.TriggerLength)()
                    data_queue.put(("status", f"DET active @ {c_freq/1e6:.2f} MHz (Length: {trig_len} pts)"))
                else:
                    data_queue.put(("error", f"DET configuration failed (Status: {status})"))

            elif isinstance(cmd, tuple) and cmd[0] == "iqs_config":
                stop_rta_stream()
                stop_mscan_if_running()
                c_freq, dec_factor, r_lvl, trig_src, trig_len, preamp, atten = cmd[1][:7]
                iqs_continuous = bool(cmd[1][7]) if len(cmd[1]) > 7 else False
                current_mode = "IQS"
                dll.IQS_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(iqs_profile_in))
                iqs_profile_in.CenterFreq_Hz = float(c_freq)
                iqs_profile_in.RefLevel_dBm = float(r_lvl)
                iqs_profile_in.DecimateFactor = int(dec_factor)
                iqs_profile_in.DataFormat = DataFormat_TypeDef.Complex16bit
                iqs_profile_in.TriggerSource = int(trig_src)
                iqs_profile_in.TriggerMode = TriggerMode_TypeDef.Adaptive if iqs_continuous else TriggerMode_TypeDef.FixedPoints
                iqs_profile_in.TriggerLength = int(trig_len)
                iqs_profile_in.Preamplifier = int(preamp)
                iqs_profile_in.Atten = int(atten)
                
                status = dll.IQS_Configuration(ctypes.pointer(device), ctypes.pointer(iqs_profile_in), ctypes.pointer(iqs_profile_out), ctypes.pointer(iqs_stream_info))
                if status == 0:
                    altern_iq_packet = c_int16_p()
                    if iqs_continuous:
                        # Adaptive mode reports StreamSamples = 0; data arrives as an
                        # endless series of PacketSamples-sized packets.
                        iqs_raw_stream = (ctypes.c_int16 * (iqs_stream_info.PacketSamples * 2))()
                    else:
                        iqs_raw_stream = (ctypes.c_int16 * (iqs_stream_info.StreamSamples * 2))()
                    data_queue.put(("status", f"IQS Demod active @ {c_freq/1e6:.3f} MHz (Decimate: {iqs_profile_out.DecimateFactor})"))
                else:
                    data_queue.put(("error", f"IQS configuration failed (Status: {status})"))

            elif isinstance(cmd, tuple) and cmd[0] == "mscan_config":
                stop_rta_stream()
                if len(cmd[1]) >= 7:
                    channels, dwell_time, detector, r_lvl, preamp, atten, decimate = cmd[1]
                else:
                    channels, dwell_time, detector, r_lvl, preamp, atten = cmd[1]
                    decimate = 256

                if current_mode == "MSCAN" and mscan_running:
                    try:
                        dll.MSCAN_Stop(ctypes.pointer(device))
                    except Exception:
                        pass
                    mscan_running = False

                if mscan_profiles_in is not None and len(mscan_channels) > 0:
                    try:
                        deinit_cnt = ctypes.c_int32(len(mscan_channels))
                        dll.MSCAN_ProfileDeinit(ctypes.pointer(device), mscan_profiles_in, ctypes.pointer(deinit_cnt))
                    except Exception:
                        pass

                num_channels = len(channels)
                if num_channels > 0:
                    mscan_channels = channels
                    mscan_profiles_in = (MSCAN_Profile_TypeDef * num_channels)()
                    mscan_profiles_out = (MSCAN_Profile_TypeDef * num_channels)()
                    det_enum = Detector_TypeDef.Detector_PosPeak if detector == 1 else (Detector_TypeDef.Detector_Average if detector == 2 else Detector_TypeDef.Detector_RMS)
                    dec_val = int(decimate if decimate in (64, 128, 256, 512, 1024) else 256)
                    for i, ch in enumerate(channels):
                        f_hz = float(ch if isinstance(ch, (int, float)) else ch.get("freq_hz", ch.get("freq", 500e6)))
                        p = mscan_profiles_in[i]
                        p.CenterFreq_Hz = f_hz
                        p.RefLevel_dBm = float(r_lvl)
                        p.DwellTime = float(dwell_time)
                        p.DecimateFactor = dec_val
                        p.FFTSize = 512
                        p.DetectCount = 1
                        p.Detector = det_enum
                        p.IFAGC = IFAGC_TypeDef.IFAGC_Off
                        p.XPPSTrigger = XPPSTrigger_TypeDef.XPPSTrigger_Off
                        p.IQPlayBack = IQPlayBack_TypeDef.IQPlayBack_Off
                        p.Window = Window_TypeDef.LowSideLobe

                    mscan_infos = (MSCAN_Info_Typedef * num_channels)()
                    elements = ctypes.c_int32(num_channels)
                    repetitions = ctypes.c_int64(100_000_000)
                    preamp_val = PreamplifierState_TypeDef(int(preamp))
                    status = dll.MSCAN_Configuration(
                        ctypes.pointer(device),
                        mscan_profiles_in,
                        mscan_profiles_out,
                        mscan_infos,
                        ctypes.pointer(elements),
                        ctypes.pointer(repetitions),
                        ctypes.pointer(preamp_val)
                    )
                    if status == 0:
                        max_spec = max([4096] + [int(m.SpectrumPoints) * max(1, int(m.SpectrumFrames)) for m in mscan_infos])
                        max_iq = max([8192] + [int(m.IQStreamPoints) * 2 for m in mscan_infos])
                        mscan_spec_buf = (ctypes.c_uint8 * max_spec)()
                        mscan_iq_buf = (ctypes.c_int16 * max_iq)()
                        st_start = dll.MSCAN_Start(ctypes.pointer(device))
                        if st_start == 0:
                            current_mode = "MSCAN"
                            mscan_running = True
                            is_running = True
                            data_queue.put(("status", f"MSCAN active: {num_channels} channels hopping @ {dwell_time*1000:.1f}ms dwell"))
                        else:
                            data_queue.put(("error", f"MSCAN Start failed (Status: {st_start})"))
                    else:
                        data_queue.put(("error", f"MSCAN Configuration failed (Status: {status})"))
                else:
                    data_queue.put(("status", "MSCAN stopped: channel list empty"))

            # SWP settings are always stored in swp_profile_in, but only pushed to the
            # hardware while sweeping; other modes pick them up via rearm_swp() when
            # they return to SWP. (Previously these commands forced the hardware
            # back into SWP from RTA/DET/IQS/MSCAN.)
            elif isinstance(cmd, tuple) and cmd[0] == "bw_config":
                current_rbw_mode, current_rbw_hz, current_vbw_mode, current_vbw_hz = cmd[1]
                span_hz = swp_profile_in.Span_Hz if swp_profile_in.Span_Hz > 0 else float(stop_freq_hz) - float(start_freq_hz)
                apply_swp_bandwidth(span_hz)
                if current_mode == "SWP":
                    swp_dirty, swp_dirty_msg = True, swp_dirty_msg or "RBW updated"

            elif isinstance(cmd, tuple) and cmd[0] == "sweep_config":
                swt_mode, swt_time, trace_points, spur, window = cmd[1]
                swp_profile_in.SweepTimeMode = swt_mode
                swp_profile_in.SweepTime = swt_time
                if trace_points > 0:
                    swp_profile_in.TracePoints = trace_points
                swp_profile_in.SpurRejection = spur
                swp_profile_in.Window = window
                if current_mode == "SWP":
                    swp_dirty, swp_dirty_msg = True, swp_dirty_msg or "Sweep settings updated"

            elif isinstance(cmd, tuple) and cmd[0] == "detect_config":
                swp_profile_in.Detector, swp_profile_in.TraceDetector = cmd[1]
                if current_mode == "SWP":
                    swp_dirty, swp_dirty_msg = True, swp_dirty_msg or "Detector settings updated"

            elif isinstance(cmd, tuple) and cmd[0] == "config":
                start_f, stop_f, r_level, att, pamp, if_agc, ifagc_tgt, ifagc_per, if_o = cmd[1]
                dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
                swp_profile_in.StartFreq_Hz = float(start_f)
                swp_profile_in.StopFreq_Hz = float(stop_f)
                swp_profile_in.CenterFreq_Hz = (float(start_f) + float(stop_f)) / 2.0
                span_hz = float(stop_f) - float(start_f)
                swp_profile_in.Span_Hz = span_hz
                swp_profile_in.FreqAssignment = SWP_FreqAssignment_TypeDef.StartStop
                apply_swp_bandwidth(span_hz)
                swp_profile_in.RefLevel_dBm = float(r_level)
                swp_profile_in.Atten = -1 if att < 0 else int(att)
                swp_profile_in.Preamplifier = pamp
                swp_profile_in.EnableIFAGC = if_agc
                if current_mode == "SWP":
                    swp_dirty, swp_dirty_msg = True, swp_dirty_msg or f"Reconfigured to {start_f/1e6:.1f} MHz - {stop_f/1e6:.1f} MHz"
                    swp_dirty_fatal = True
        except queue.Empty:
            pass

        if swp_dirty and current_mode == "SWP":
            if not command_queue.empty():
                continue  # program the hardware once, after the pending settings
            swp_dirty = False
            status = rearm_swp()
            if status == 0:
                if swp_dirty_msg:
                    data_queue.put(("status", swp_dirty_msg))
            else:
                data_queue.put(("error", f"SWP configuration failed (Status: {status})"))
                if swp_dirty_fatal:
                    is_running = False
            swp_dirty_msg, swp_dirty_fatal = "", False
            
        # Periodic Temperature & Hardware Health Polling (Every ~2.0s when sweep is paused)
        # Device_QueryDeviceState_Realtime occupies the USB bulk control channel and must NOT collide
        # with active high-throughput SWP/RTA streaming transfers.
        now = time.time()
        if now - last_power_check_time > (5.0 if is_running else 2.0):
            last_power_check_time = now
            query_power()
            query_gnss()
        if not is_running and (now - last_temp_check_time > 2.0):
            last_temp_check_time = now
            try:
                dev_state = DeviceState_TypeDef()
                if hasattr(dll, 'Device_QueryDeviceState_Realtime'):
                    st = dll.Device_QueryDeviceState_Realtime(ctypes.pointer(device), ctypes.pointer(dev_state))
                    if st == 0 and dev_state.Temperature != 0:
                        temp_c = float(dev_state.Temperature) / 100.0
                        data_queue.put(("temperature", temp_c))
            except Exception:
                pass

        # Mode Data Acquisition Execution
        if is_running:
            if current_mode == "SWP":
                sweep_ok = False
                valid_hops = 0
                for _ in range(total_hops):
                    status = dll.SWP_GetPartialSweep(
                        ctypes.pointer(device), 
                        partial_freq_ctypes, 
                        partial_spec_ctypes, 
                        ctypes.pointer(hop_index), 
                        ctypes.pointer(frame_index), 
                        ctypes.pointer(meas_aux_info)
                    )
                    # status == 0: success, status == -12: APIRETVAL_WARNING_IFOverflow (non-fatal IF warning)
                    if status in (0, -12):
                        h_idx = hop_index.value
                        if 0 <= h_idx < total_hops:
                            start_idx = h_idx * partial_sweep_points
                            if start_idx < full_sweep_points:
                                slice_len = max(0, min(partial_sweep_points, full_sweep_points - start_idx))
                                end_idx = start_idx + slice_len
                                temp_spec = np.copy(np.frombuffer(partial_spec_ctypes, dtype=np.float32, count=slice_len))
                                
                                # DMA Buffer healing for unpopulated chunks (runs of exact
                                # 0.0) or NaNs/Infs; an isolated 0.0 dBm is a real reading
                                invalid_mask = ~np.isfinite(temp_spec) | _zero_runs(temp_spec)
                                if np.any(invalid_mask):
                                    if last_valid_power is not None and len(last_valid_power) == full_sweep_points:
                                        temp_spec[invalid_mask] = last_valid_power[start_idx:end_idx][invalid_mask]
                                    else:
                                        valid_idx = np.where(~invalid_mask)[0]
                                        if len(valid_idx) > 0:
                                            temp_spec[invalid_mask] = np.interp(np.where(invalid_mask)[0], valid_idx, temp_spec[valid_idx])
                                        else:
                                            temp_spec[invalid_mask] = -120.0
                                
                                power_np[start_idx:end_idx] = temp_spec
                                valid_hops += 1
                
                # Accept sweep when all or nearly all hops are populated
                if valid_hops >= max(1, total_hops - 1):
                    sweep_ok = True
                    last_valid_power = np.copy(power_np)
                
                if sweep_ok:
                    consecutive_errors = 0
                    try:
                        data_queue.put_nowait(("data", (np.copy(freq_np), np.copy(power_np))))
                    except Exception:
                        pass
                    time.sleep(0.005)
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 2:
                        try:
                            dll.SWP_Configuration(
                                ctypes.pointer(device),
                                ctypes.pointer(swp_profile_in),
                                ctypes.pointer(swp_profile_out),
                                ctypes.pointer(trace_info)
                            )
                        except Exception:
                            pass
                        consecutive_errors = 0
                    time.sleep(0.01)

            elif current_mode == "RTA" and rta_spec_trace is not None:
                # FixedPoints: one trigger per acquisition. Adaptive: trigger once,
                # then read the continuous stream.
                if rta_profile_out.TriggerMode == TriggerMode_TypeDef.Adaptive:
                    if not rta_streaming:
                        dll.RTA_BusTriggerStart(ctypes.pointer(device))
                        rta_streaming = True
                else:
                    dll.RTA_BusTriggerStart(ctypes.pointer(device))
                st = dll.RTA_GetRealTimeSpectrum(
                    device, rta_spec_trace, rta_spec_bitmap,
                    ctypes.pointer(rta_plot_info), ctypes.pointer(rta_trigger_info), ctypes.pointer(meas_aux_info)
                )
                if st == 0:
                    w = rta_frame_info.FrameWidth
                    h = rta_frame_info.FrameHeight
                    raw_trace_np = np.frombuffer(rta_spec_trace, dtype=np.uint8, count=w)
                    power_trace_np = raw_trace_np.astype(np.float32) * rta_plot_info.ScaleTodBm + rta_plot_info.OffsetTodBm
                    bitmap_np = np.frombuffer(rta_spec_bitmap, dtype=np.uint16, count=w * h)
                    # Frames come at >100/s but are drawn at ~30/s: add the hit
                    # counts of every frame into one bitmap per send, so nothing
                    # is dropped and the pipe carries a quarter of the data
                    if rta_acc is None or rta_acc.shape != (h, w):
                        rta_acc = np.zeros((h, w), dtype=np.uint32)
                    rta_acc += bitmap_np.reshape((h, w))
                    now_rta = time.monotonic()
                    if now_rta - rta_acc_t >= RTA_SEND_PERIOD_S:
                        rta_acc_t = now_rta
                        freq_axis = np.linspace(rta_frame_info.StartFrequency_Hz, rta_frame_info.StopFrequency_Hz, w)
                        data_queue.put(("rta_data", (freq_axis, power_trace_np, rta_acc, {
                            "start_freq": rta_frame_info.StartFrequency_Hz,
                            "stop_freq": rta_frame_info.StopFrequency_Hz,
                            "center_freq": rta_profile_out.CenterFreq_Hz,
                            "width": w,
                            "height": h,
                            "ref_level": rta_profile_out.RefLevel_dBm
                        })))
                        rta_acc = None
                    time.sleep(0.005)
                else:
                    time.sleep(0.02)

            elif current_mode == "DET" and det_norm_packet is not None:
                dll.DET_BusTriggerStart(ctypes.pointer(device))
                scale_to_v = ctypes.c_float()
                complete = True
                for p_idx in range(det_stream_info.PacketCount):
                    st = dll.DET_GetPowerStream(
                        ctypes.pointer(device), det_norm_packet, ctypes.pointer(scale_to_v),
                        ctypes.pointer(det_trigger_info), ctypes.pointer(meas_aux_info)
                    )
                    if st not in ACQ_OK:
                        complete = False  # don't emit stale buffer contents as new data
                        break
                    start_idx = p_idx * det_stream_info.PacketSamples
                    if p_idx == det_stream_info.PacketCount - 1 and det_stream_info.StreamSamples % det_stream_info.PacketSamples != 0:
                        rem = det_stream_info.StreamSamples % det_stream_info.PacketSamples
                        det_raw_stream[start_idx : start_idx + rem] = det_norm_packet[:rem]
                    else:
                        det_raw_stream[start_idx : start_idx + det_stream_info.PacketSamples] = det_norm_packet[:]
                        
                acq_failures = 0 if complete else acq_failures + 1
                if acq_failures == 10:
                    data_queue.put(("status", f"DET acquisition failing repeatedly (Status: {st})"))
                if complete:
                    raw_np = np.frombuffer(det_raw_stream, dtype=np.float32)
                    voltages = raw_np * scale_to_v.value
                    power_dbm = 10.0 * np.log10(np.maximum(20.0 * (voltages ** 2), 1e-15))
                    sample_interval_ns = 8.0 * det_profile_out.DecimateFactor
                    time_ns = np.arange(det_profile_out.TriggerLength) * sample_interval_ns
                    data_queue.put(("det_data", (time_ns, power_dbm, {
                        "center_freq": det_profile_out.CenterFreq_Hz,
                        "decimate": det_profile_out.DecimateFactor,
                        "sample_interval_ns": sample_interval_ns,
                        "trigger_length": det_profile_out.TriggerLength,
                        "ref_level": det_profile_out.RefLevel_dBm
                    })))
                time.sleep(0.02)

            elif current_mode == "IQS" and iqs_continuous and iqs_raw_stream is not None:
                try:
                    if not iqs_streaming:
                        dll.IQS_BusTriggerStart(ctypes.pointer(device))
                        iqs_streaming = True
                    scale_to_v = ctypes.c_float(0.0)
                    meas_aux = MeasAuxInfo_TypeDef()
                    trig_info = TriggerInfo_TypeDef()
                    pkt_samples = iqs_stream_info.PacketSamples
                    sr = float(iqs_stream_info.IQSampleRate)
                    decimate = max(1, iqs_profile_out.DecimateFactor)
                    if sr <= 0:
                        sr = IQ_FALLBACK_BASE_RATE_HZ / decimate
                    # Batch ~40 ms of packets per message to keep queue traffic low
                    n_packets = max(1, int(round(0.04 * sr / max(1, pkt_samples))))
                    chunks = []
                    for _ in range(n_packets):
                        st = dll.IQS_GetIQStream(
                            ctypes.pointer(device), ctypes.pointer(altern_iq_packet), ctypes.pointer(scale_to_v),
                            ctypes.pointer(trig_info), ctypes.pointer(meas_aux)
                        )
                        if st not in ACQ_OK or not altern_iq_packet:
                            break
                        chunks.append(np.ctypeslib.as_array(altern_iq_packet, shape=(pkt_samples * 2,)).copy())
                    acq_failures = 0 if chunks else acq_failures + 1
                    if acq_failures == 10:
                        data_queue.put(("status", f"IQS stream failing repeatedly (Status: {st})"))
                    if chunks:
                        raw_np = np.concatenate(chunks)
                        scale = float(scale_to_v.value) if scale_to_v.value > 0 else 1.97e-6
                        iq_complex = (raw_np[0::2].astype(np.float32) + 1j * raw_np[1::2].astype(np.float32)) * scale
                        data_queue.put(("iqs_data", (iq_complex.astype(np.complex64), sr, {
                            "center_freq": iqs_profile_out.CenterFreq_Hz,
                            "decimate": iqs_profile_out.DecimateFactor,
                            "sample_rate": sr,
                            "base_sample_rate": sr * decimate,
                            "scale_to_v": scale,
                            "ref_level": iqs_profile_out.RefLevel_dBm,
                            "continuous": True,
                        })))
                    else:
                        time.sleep(0.005)
                except Exception as e:
                    data_queue.put(("error", f"IQS stream acquisition error: {str(e)}"))
            elif current_mode == "IQS" and iqs_raw_stream is not None:
                try:
                    dll.IQS_BusTriggerStart(ctypes.pointer(device))
                    scale_to_v = ctypes.c_float(0.0)
                    meas_aux = MeasAuxInfo_TypeDef()
                    trig_info = TriggerInfo_TypeDef()
                    
                    pkt_samples = iqs_stream_info.PacketSamples
                    stream_samples = iqs_stream_info.StreamSamples
                    complete = True
                    for p_idx in range(iqs_stream_info.PacketCount):
                        st = dll.IQS_GetIQStream(
                            ctypes.pointer(device), ctypes.pointer(altern_iq_packet), ctypes.pointer(scale_to_v),
                            ctypes.pointer(trig_info), ctypes.pointer(meas_aux)
                        )
                        if st not in ACQ_OK or not altern_iq_packet:
                            complete = False  # don't emit stale buffer contents as new data
                            break
                        start_idx = p_idx * pkt_samples * 2
                        if p_idx == iqs_stream_info.PacketCount - 1 and (stream_samples % pkt_samples) != 0:
                            rem = 2 * (stream_samples % pkt_samples)
                            iqs_raw_stream[start_idx : start_idx + rem] = altern_iq_packet[0:rem]
                        else:
                            cnt = pkt_samples * 2
                            iqs_raw_stream[start_idx : start_idx + cnt] = altern_iq_packet[0:cnt]
                            
                    acq_failures = 0 if complete else acq_failures + 1
                    if acq_failures == 10:
                        data_queue.put(("status", f"IQS acquisition failing repeatedly (Status: {st})"))
                    if complete:
                        raw_np = np.frombuffer(iqs_raw_stream, dtype=np.int16)
                        scale = float(scale_to_v.value) if scale_to_v.value > 0 else 1.97e-6
                        i_data = raw_np[0::2].astype(np.float32) * scale
                        q_data = raw_np[1::2].astype(np.float32) * scale
                        iq_complex = i_data + 1j * q_data
                    
                        # The SDK reports the true IQ rate (the ADC rate differs by model,
                        # e.g. 125 MS/s on the SAN-60), already divided by the decimation.
                        decimate = max(1, iqs_profile_out.DecimateFactor)
                        sr = float(iqs_stream_info.IQSampleRate)
                        if sr <= 0:
                            sr = IQ_FALLBACK_BASE_RATE_HZ / decimate
                        data_queue.put(("iqs_data", (iq_complex, sr, {
                            "center_freq": iqs_profile_out.CenterFreq_Hz,
                            "decimate": iqs_profile_out.DecimateFactor,
                            "sample_rate": sr,
                            "base_sample_rate": sr * decimate,
                            "scale_to_v": scale,
                            "ref_level": iqs_profile_out.RefLevel_dBm
                        })))
                except Exception as e:
                    data_queue.put(("error", f"IQS stream acquisition error: {str(e)}"))
                time.sleep(0.035)
            elif current_mode == "MSCAN" and mscan_running:
                try:
                    if mscan_spec_buf is None:
                        mscan_spec_buf = (ctypes.c_uint8 * 4096)()
                    if mscan_iq_buf is None:
                        mscan_iq_buf = (ctypes.c_int16 * 8192)()

                    mscan_data = MSCAN_Data_Typedef()
                    mscan_data.SpectrumStream = ctypes.cast(mscan_spec_buf, ctypes.POINTER(ctypes.c_uint8))
                    mscan_data.IQStream = ctypes.cast(mscan_iq_buf, ctypes.POINTER(ctypes.c_int16))

                    st = dll.MSCAN_GetData(ctypes.pointer(device), ctypes.pointer(mscan_data))
                    if st == 0:
                        el_idx = int(mscan_data.ElementIndex)
                        pts = int(mscan_data.SpectrumPoints)
                        scale = float(mscan_data.ScaleTodBm)
                        offset = float(mscan_data.OffsetTodBm)
                        ch_freq = 0.0
                        ch_info = {}
                        if 0 <= el_idx < len(mscan_channels):
                            ch_obj = mscan_channels[el_idx]
                            if isinstance(ch_obj, dict):
                                ch_freq = float(ch_obj.get("freq_hz", ch_obj.get("freq", 0.0)))
                                ch_info = ch_obj
                            else:
                                ch_freq = float(ch_obj)

                        spec_dbm = None
                        peak_power = -120.0
                        if pts > 0:
                            raw_u8 = np.frombuffer(mscan_spec_buf, dtype=np.uint8, count=pts)
                            spec_dbm = raw_u8.astype(np.float32) * scale + offset
                            center_bin = pts // 2
                            el_info = mscan_info_for(el_idx)
                            span_hz = float(el_info.Span_Hz) if el_info.Span_Hz > 0 else 396730.0
                            bin_hz = span_hz / max(1, pts)
                            # Wireless mic channel mask: 150 kHz for HD modes, 200 kHz standard
                            target_mask_hz = 150e3 if (isinstance(ch_info, dict) and any(k in str(ch_info.get("name", "")).lower() or k in str(ch_info.get("group_name", "")).lower() for k in ("hd", "high density", "adhd", "d6000"))) else 200e3
                            half_bins = max(1, int(round((target_mask_hz / 2.0) / bin_hz)))
                            ch_bins = spec_dbm[max(0, center_bin - half_bins): min(pts, center_bin + half_bins + 1)]
                            peak_power = float(np.max(ch_bins)) if len(ch_bins) > 0 else float(spec_dbm[center_bin])
                        else:
                            peak_power = offset

                        data_queue.put(("mscan_data", (el_idx, ch_freq, peak_power, spec_dbm, {
                            "repeat_index": int(mscan_data.RepeatIndex),
                            "element_index": el_idx,
                            "channel_info": ch_info,
                            "temperature": float(mscan_data.Temperature) if mscan_data.Temperature != 0 else 0.0,
                            "timestamp": float(mscan_data.SysTimeStamp),
                            # spec_dbm covers ch_freq +/- span_hz/2 (for fingerprinting)
                            "span_hz": float(span_hz) if pts > 0 else 0.0,
                            "points": int(pts),
                        })))
                    elif st == -304:
                        # APIRETVAL_WARNING_DataNotReady: wait briefly for next frame
                        time.sleep(0.0002)
                    else:
                        time.sleep(0.001)
                except Exception as e:
                    data_queue.put(("error", f"MSCAN acquisition error: {e}"))
                    time.sleep(0.02)
            else:
                time.sleep(0.01)
        else:
            time.sleep(0.01)
            
    try:
        stop_mscan_if_running()
        stop_rta_stream()
        dll.Device_Close(ctypes.pointer(device))
    except Exception:
        pass

class DeviceQueueReader(QThread):
    spectrum_data_ready = pyqtSignal(np.ndarray, np.ndarray)
    rta_data_ready = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, dict)
    det_data_ready = pyqtSignal(np.ndarray, np.ndarray, dict)
    iqs_data_ready = pyqtSignal(np.ndarray, float, dict)
    mscan_data_ready = pyqtSignal(int, float, float, object, dict) # el_idx, ch_freq, peak_power, spec_dbm, info
    temperature_updated = pyqtSignal(float)
    power_updated = pyqtSignal(object)  # {"port_v", "port_a", "usb_v", "usb_a"}
    gnss_updated = pyqtSignal(object)   # {"lat", "lon", "alt", "sats", "lock", "docxo_lock", "time"}
    timed_capture_ready = pyqtSignal(object, object)   # IQ (complex64) or None, {"ok", timing fields, "error"}
    sdk_retry = pyqtSignal(object)      # the open failed with this SDK build; another is available
    sdk_ok = pyqtSignal(str)            # path of the SDK build the analyzer accepted
    status_message = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    device_info_received = pyqtSignal(int, object)
    trace_points_received = pyqtSignal(int)
    missing_cal_received = pyqtSignal(int, object, str)
    amplitude_clamped = pyqtSignal(float, int)
    bandwidth_updated = pyqtSignal(float, float)
    hw_endorsements = pyqtSignal(dict)
    input_comp_applied = pyqtSignal(int, int)   # SDK status, table points
    capabilities_received = pyqtSignal(dict)    # see device_caps.py
    sweep_plan_received = pyqtSignal(dict)      # which RF input(s) the sweep uses, and any range note

    # Display streams the GUI may skip frames of. The reader hands the GUI one frame
    # at a time and keeps only the newest while it is busy, so a slow frame (heavy
    # analysis, many threats) drops frames instead of piling them up in Qt's event
    # queue without bound (which grew memory until the OS killed the app).
    # Continuous IQ is not throttled: audio needs every sample.
    THROTTLED = ("data", "rta_data", "det_data")

    def __init__(self, data_queue, process=None):
        super().__init__()
        self._idle = {k: threading.Event() for k in self.THROTTLED}
        for ev in self._idle.values():
            ev.set()
        self._held = {}
        self.data_queue = data_queue
        self.process = process
        self.is_running = True
        # Errors before the device reports "connected" are fatal (open failed);
        # afterwards they are runtime errors and the connection stays up.
        self._device_connected = False
        # Set during an intentional shutdown so the process exit isn't reported
        # as a crash.
        self.expect_exit = False
        
    def mark_idle(self, kind: str):
        """Called on the GUI thread once it has finished with a frame of `kind`."""
        if kind in self._idle:
            self._idle[kind].set()

    def _flush_held(self):
        for kind in list(self._held):
            if self._idle[kind].is_set():
                content = self._held.pop(kind)
                self._idle[kind].clear()
                if kind == "data":
                    self.spectrum_data_ready.emit(*content)
                elif kind == "det_data":
                    self.det_data_ready.emit(*content)
                elif kind == "rta_data":
                    self.rta_data_ready.emit(*content)

    def run(self):
        while self.is_running:
            try:
                msg_type, content = self.data_queue.get(timeout=0.05)
                
                # If it's real-time streaming data, drain older pending frames to eliminate backlog lag
                if msg_type in ("data", "det_data", "rta_data", "iqs_data"):
                    target_type = msg_type
                    latest_content = content
                    while True:
                        try:
                            next_type, next_content = self.data_queue.get_nowait()
                            if next_type == target_type:
                                latest_content = next_content
                            else:
                                self._dispatch_message(next_type, next_content)
                        except queue.Empty:
                            break
                            
                    if latest_content is not None and target_type in self._idle:
                        if not self._idle[target_type].is_set():
                            self._held[target_type] = latest_content   # GUI busy: keep newest
                            latest_content = None
                        else:
                            self._idle[target_type].clear()
                    if latest_content is not None:
                        if target_type == "data":
                            freq, power = latest_content
                            self.spectrum_data_ready.emit(freq, power)
                        elif target_type == "det_data":
                            time_ns, power, info = latest_content
                            self.det_data_ready.emit(time_ns, power, info)
                        elif target_type == "rta_data":
                            freq, trace, bitmap, info = latest_content
                            self.rta_data_ready.emit(freq, trace, bitmap, info)
                        elif target_type == "iqs_data":
                            iq_c, sr, info = latest_content
                            self.iqs_data_ready.emit(iq_c, sr, info)
                else:
                    self._dispatch_message(msg_type, content)
                self._flush_held()
            except queue.Empty:
                self._flush_held()
                # The hardware process can die without a message (e.g. a crash in
                # the vendor library); report it instead of appearing connected.
                if (self._device_connected and not self.expect_exit and self.process is not None
                        and not self.process.is_alive()):
                    self._device_connected = False
                    self.status_message.emit(
                        f"Analyzer process exited unexpectedly (exit code {self.process.exitcode}).")
                    self.connection_status.emit(False)

    def _dispatch_message(self, msg_type, content):
        if msg_type == "rta_data":
            freq, trace, bitmap, info = content
            self.rta_data_ready.emit(freq, trace, bitmap, info)
        elif msg_type == "det_data":
            time_ns, power, info = content
            self.det_data_ready.emit(time_ns, power, info)
        elif msg_type == "iqs_data":
            iq_c, sr, info = content
            self.iqs_data_ready.emit(iq_c, sr, info)
        elif msg_type == "mscan_data":
            el_idx, ch_freq, peak_power, spec_dbm, info = content
            self.mscan_data_ready.emit(el_idx, ch_freq, peak_power, spec_dbm, info)
        elif msg_type == "temperature":
            self.temperature_updated.emit(float(content))
        elif msg_type == "power":
            self.power_updated.emit(content)
        elif msg_type == "gnss":
            self.gnss_updated.emit(content)
        elif msg_type == "timed_capture":
            self.timed_capture_ready.emit(content[0], content[1])
        elif msg_type == "sdk_retry":
            self.sdk_retry.emit(content)
        elif msg_type == "sdk_ok":
            self.sdk_ok.emit(str(content))
        elif msg_type == "connected":
            self._device_connected = bool(content)
            self.connection_status.emit(bool(content))
        elif msg_type == "status":
            self.status_message.emit(content)
        elif msg_type == "error":
            self.status_message.emit(content)
            if not self._device_connected:
                self.connection_status.emit(False)
        elif msg_type == "missing_cal":
            self.status_message.emit(content[2])
            self.missing_cal_received.emit(content[0], content[1], content[2])
            self.connection_status.emit(False)
        elif msg_type == "device_info":
            self.device_info_received.emit(content[0], content[1])
        elif msg_type == "trace_points":
            self.trace_points_received.emit(content)
        elif msg_type == "amplitude_clamped":
            self.amplitude_clamped.emit(float(content[0]), int(content[1]))
        elif msg_type == "hw_rbw_updated":
            self.bandwidth_updated.emit(float(content[0]), float(content[1]))
        elif msg_type == "hw_endorsements":
            self.hw_endorsements.emit(content)
        elif msg_type == "freq_comp":
            self.input_comp_applied.emit(int(content[0]), int(content[1]))
        elif msg_type == "capabilities":
            self.capabilities_received.emit(content)
        elif msg_type == "sweep_plan":
            self.sweep_plan_received.emit(content)

    def stop(self):
        self.is_running = False
        self.wait()

class DeviceController(QObject):
    spectrum_data_ready = pyqtSignal(np.ndarray, np.ndarray)
    rta_data_ready = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, dict)
    det_data_ready = pyqtSignal(np.ndarray, np.ndarray, dict)
    iqs_data_ready = pyqtSignal(np.ndarray, float, dict)
    mscan_data_ready = pyqtSignal(int, float, float, object, dict)
    temperature_updated = pyqtSignal(float)
    power_updated = pyqtSignal(object)  # {"port_v", "port_a", "usb_v", "usb_a"}
    gnss_updated = pyqtSignal(object)   # {"lat", "lon", "alt", "sats", "lock", "docxo_lock", "time"}
    timed_capture_ready = pyqtSignal(object, object)   # IQ (complex64) or None, {"ok", timing fields, "error"}
    status_message = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    device_info_received = pyqtSignal(int, object)
    trace_points_received = pyqtSignal(int)
    missing_cal_received = pyqtSignal(int, object, str)
    amplitude_clamped = pyqtSignal(float, int)
    bandwidth_updated = pyqtSignal(float, float)
    hw_endorsements = pyqtSignal(dict)
    input_comp_applied = pyqtSignal(int, int)   # SDK status, table points
    capabilities_received = pyqtSignal(dict)    # see device_caps.py
    sweep_plan_received = pyqtSignal(dict)      # which RF input(s) the sweep uses, and any range note

    def __init__(self, staging_name: str = "slot_a"):
        super().__init__()
        # Per-slot calibration staging directory (see CalibrationManager.staging_root)
        self.staging_name = staging_name
        self.is_connected = False
        self.process = None
        self.command_queue = None
        self.data_queue = None
        self.queue_reader = None
        
    def connect_device(self, start_freq_hz=1e9, stop_freq_hz=2e9, probe_only=False, ref_level=0.0, atten=-1, preamp=0x00, ifagc=1, interface_type="usb", ip_address="192.168.1.50", port=5000, target_model=None, target_uid=None, usb_index=0, serial_port=None, sdk_lib=None, tried_libs=()):
        """
        sdk_lib / tried_libs: the SDK build to start the hardware process with
        (default: the one this analyzer last accepted) and those already tried.
        interface_type: "usb" (Harogic USB analyzers, then tinySAs, by usb_index),
        "network" (Harogic Ethernet analyzer), or "tinysa" (the tinySA on
        serial_port, or the usb_index-th tinySA).
        """
        self._stop_hardware()
        self._connect_args = dict(start_freq_hz=start_freq_hz, stop_freq_hz=stop_freq_hz, probe_only=probe_only,
                                  ref_level=ref_level, atten=atten, preamp=preamp, ifagc=ifagc,
                                  interface_type=interface_type, ip_address=ip_address, port=port,
                                  target_model=target_model, target_uid=target_uid, usb_index=usb_index,
                                  serial_port=serial_port)
        self._sdk_key = f"sdk_lib/{interface_type}/{ip_address if interface_type == 'network' else usb_index}"
        if sdk_lib is None:
            remembered = QSettings("Harogic", "RF_Recon_Modern").value(self._sdk_key, "")
            sdk_lib = remembered if remembered and os.path.exists(remembered) else None

        self.command_queue = multiprocessing.Queue()
        self.data_queue = multiprocessing.Queue(maxsize=64)

        from core.calibration_manager import CalibrationManager
        stage_root = CalibrationManager.staging_root(self.staging_name)
        cal_stage_dir = stage_root / "CalFile"
        cal_stage_dir.mkdir(parents=True, exist_ok=True)

        if interface_type.lower() == "tinysa":
            self.process = multiprocessing.Process(
                target=tinysa_process,
                args=(self.command_queue, self.data_queue, start_freq_hz, stop_freq_hz,
                      serial_port, usb_index, atten, preamp, probe_only)
            )
        else:
            self.process = multiprocessing.Process(
                target=hardware_process,
                args=(
                    self.command_queue, self.data_queue, start_freq_hz, stop_freq_hz,
                    probe_only, str(cal_stage_dir), ref_level, atten, preamp, ifagc, -9.0, 0.01, 0,
                    interface_type, ip_address, port, target_model, target_uid, usb_index
                ),
                kwargs={"tried_libs": tuple(tried_libs)}
            )
        self.process.daemon = True
        # The macOS SDK (htraapi-macos) loads CalFile/ from HTRAAPI_DATA_DIR; the
        # child inherits the environment at start. On Linux the vendor SDK only reads
        # CalFile/ next to the Python executable and otherwise uses the analyzer's
        # flash calibration, so staging there is best-effort.
        # (HTRAAPI_LIB picks the SDK build the child loads: one build per process.)
        prev = os.environ.get("HTRAAPI_DATA_DIR")
        prev_lib = os.environ.get("HTRAAPI_LIB")
        os.environ["HTRAAPI_DATA_DIR"] = str(stage_root)
        if sdk_lib:
            os.environ["HTRAAPI_LIB"] = sdk_lib
        try:
            self.process.start()
        finally:
            if prev is None:
                os.environ.pop("HTRAAPI_DATA_DIR", None)
            else:
                os.environ["HTRAAPI_DATA_DIR"] = prev
            if sdk_lib:
                if prev_lib is None:
                    os.environ.pop("HTRAAPI_LIB", None)
                else:
                    os.environ["HTRAAPI_LIB"] = prev_lib
        
        self.queue_reader = DeviceQueueReader(self.data_queue, self.process)
        self.queue_reader.spectrum_data_ready.connect(self.spectrum_data_ready)
        self.queue_reader.rta_data_ready.connect(self.rta_data_ready)
        self.queue_reader.det_data_ready.connect(self.det_data_ready)
        # Connected after the forwards above, so these queued calls run once the
        # GUI has processed the frame: then the reader may send the next one.
        self.queue_reader.spectrum_data_ready.connect(self._sweep_consumed)
        self.queue_reader.rta_data_ready.connect(self._rta_consumed)
        self.queue_reader.det_data_ready.connect(self._det_consumed)
        self.queue_reader.iqs_data_ready.connect(self.iqs_data_ready)
        self.queue_reader.mscan_data_ready.connect(self.mscan_data_ready)
        self.queue_reader.temperature_updated.connect(self.temperature_updated)
        self.queue_reader.power_updated.connect(self.power_updated)
        self.queue_reader.gnss_updated.connect(self.gnss_updated)
        self.queue_reader.timed_capture_ready.connect(self.timed_capture_ready)
        self.queue_reader.sdk_retry.connect(self._on_sdk_retry)
        self.queue_reader.sdk_ok.connect(self._on_sdk_ok)
        self.queue_reader.status_message.connect(self.status_message)
        self.queue_reader.connection_status.connect(self.handle_connection_status)
        self.queue_reader.device_info_received.connect(self.device_info_received)
        self.queue_reader.trace_points_received.connect(self.trace_points_received)
        self.queue_reader.missing_cal_received.connect(self.missing_cal_received)
        self.queue_reader.amplitude_clamped.connect(self.amplitude_clamped.emit)
        self.queue_reader.bandwidth_updated.connect(self.bandwidth_updated.emit)
        self.queue_reader.hw_endorsements.connect(self.hw_endorsements.emit)
        self.queue_reader.input_comp_applied.connect(self.input_comp_applied.emit)
        self.queue_reader.capabilities_received.connect(self.capabilities_received.emit)
        self.queue_reader.sweep_plan_received.connect(self.sweep_plan_received.emit)
        self.queue_reader.start()
        
        return True

    @staticmethod
    def scan_usb_analyzers() -> list:
        """
        Every analyzer on USB, for choosing one in the Connection dialog:
        Harogic analyzers as the SDK lists them, then tinySA / tinySA Ultra
        units (see tinysa_device.scan_tinysas). Harogic entries have "kind":
        "harogic", "usb_index" (the SDK's index), "model" and "uid" (the serial
        number; None on SDK builds that do not report it before opening).
        Works the same on macOS and Linux. Takes about a second; call it off the GUI thread.
        """
        devices = []
        try:
            profile = BootProfile_TypeDef()
            profile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort
            profile.PhysicalInterface = PhysicalInterface_TypeDef.USB
            count = ctypes.c_uint8(0)
            numbers = (ctypes.c_uint8 * 256)()
            infos = (DeviceInfo_TypeDef * 256)()
            for attempt in range(3):        # the first listing after plugging in can come back empty
                status = dll.Device_List(ctypes.pointer(profile), ctypes.pointer(count), numbers, infos)
                if status == 0 and count.value > 0:
                    break
                time.sleep(0.15)
            for i in range(count.value if status == 0 else 0):
                devices.append({"kind": "harogic", "usb_index": i, "model": int(infos[i].Model),
                                "uid": int(infos[i].DeviceUID) or None})
        except Exception as e:
            print(f"[DeviceController] USB analyzer listing failed: {e}")
        try:
            from core.tinysa_device import scan_tinysas
            devices += scan_tinysas()
        except Exception as e:
            print(f"[DeviceController] tinySA scan failed: {e}")
        return devices

    @staticmethod
    def get_local_network_interfaces() -> list:
        """
        Enumerate active host network interfaces with their IPv4 address, subnet
        mask and link state. Uses Qt's QNetworkInterface, which works on Linux,
        macOS and Windows (the previous /sys/class/net + ioctl version was
        Linux-only).
        """
        from PyQt6.QtNetwork import QNetworkInterface, QAbstractSocket

        Flag = QNetworkInterface.InterfaceFlag
        interfaces = []
        for iface in QNetworkInterface.allInterfaces():
            flags = iface.flags()
            if flags & Flag.IsLoopBack:
                continue
            state = 'up' if (flags & Flag.IsUp and flags & Flag.IsRunning) else 'down'
            for entry in iface.addressEntries():
                addr = entry.ip()
                if addr.protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
                    continue
                ip_str = addr.toString()
                interfaces.append({
                    'name': iface.name(),
                    'ip': ip_str,
                    'mask': entry.netmask().toString(),
                    'state': state,
                    'display': f"{iface.name()} ({ip_str}) [{state.upper()}]"
                })
        interfaces.sort(key=lambda x: x['name'])
        return interfaces

    @staticmethod
    def scan_network_devices(target_ip: str = None, target_mask: str = None, poll_all: bool = False) -> list:
        """
        Poll network interfaces for Harogic NX/SA series network analyzers.
        If poll_all is True, iterates across all active local network interfaces.
        If target_ip is specified, polls on that specific interface.
        Uses active concurrent discovery (ARP cache + TCP sweep on ports 5000/9000)
        to discover Harogic analyzers reliably on Linux where the vendor DLL provides a dummy stub.
        """
        import socket
        import concurrent.futures

        try:
            from core.calibration_manager import CalibrationManager
            cm = CalibrationManager()
        except Exception:
            cm = None

        interfaces_to_scan = []
        if poll_all:
            interfaces_to_scan = DeviceController.get_local_network_interfaces()
        elif target_ip:
            all_ifcs = DeviceController.get_local_network_interfaces()
            matched = next((x for x in all_ifcs if x.get('ip') == target_ip), None)
            if matched:
                interfaces_to_scan = [matched]
            else:
                interfaces_to_scan = [{'name': '', 'ip': target_ip, 'mask': target_mask or '255.255.255.0'}]
        else:
            interfaces_to_scan = DeviceController.get_local_network_interfaces()

        discovered_by_ip = {}

        # 1. First attempt native vendor DLL discovery if available
        if hasattr(dll, 'Device_GetNetworkDeviceList'):
            try:
                count = ctypes.c_uint8(0)
                dev_info = (NetworkDeviceInfo_TypeDef * 64)()
                local_ip = (ctypes.c_uint8 * 4)()
                local_mask = (ctypes.c_uint8 * 4)()
                dll.Device_GetNetworkDeviceList(
                    ctypes.byref(count),
                    ctypes.byref(dev_info),
                    ctypes.byref(local_ip),
                    ctypes.byref(local_mask)
                )
                if count.value > 0:
                    for i in range(count.value):
                        dev = dev_info[i]
                        ip_str = '.'.join(str(b) for b in dev.IPAddress)
                        mask_str = '.'.join(str(b) for b in dev.SubnetMask)
                        m = int(dev.Model)
                        u = int(dev.DeviceUID)
                        is_cal = cm.is_calibrated(m, u) if cm else False
                        summary = cm.get_cal_summary(m, u) if cm else {}
                        discovered_by_ip[ip_str] = {
                            'model': m,
                            'uid': u,
                            'ip': ip_str,
                            'mask': mask_str,
                            'hostname': '',
                            'is_calibrated': is_cal,
                            'alias': summary.get('alias', f"Model {m:03d}"),
                            'interface': ''
                        }
            except Exception:
                pass

        # 2. Active network discovery across subnets
        for ifc in interfaces_to_scan:
            ip = ifc.get('ip')
            if not ip or ip.startswith('127.') or ifc.get('name') == 'lo' or ifc.get('name', '').startswith('docker'):
                continue

            mask = ifc.get('mask') or '255.255.255.0'
            try:
                network = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
            except ValueError:
                network = ipaddress.ip_network(f"{ip}/24", strict=False)
            # Sweep the interface's whole subnet, but cap very large ones (a /16
            # would be 65k probes) to the /22 around this host.
            if network.prefixlen < MAX_SCAN_PREFIX:
                network = ipaddress.ip_network(f"{ip}/{MAX_SCAN_PREFIX}", strict=False)

            def probe_harogic(tip):
                if tip == ip:
                    return None
                try:
                    s5 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s5.settimeout(0.08)
                    if s5.connect_ex((tip, 5000)) == 0:
                        s5.close()
                        # Verify Harogic System_Server or device responder
                        s9 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s9.settimeout(0.08)
                        is_harogic = (s9.connect_ex((tip, 9000)) == 0)
                        s9.close()
                        if is_harogic:
                            return tip
                    else:
                        s5.close()
                except Exception:
                    pass
                return None

            # Fast concurrent probe of all subnet hosts
            hosts_to_sweep = [str(h) for h in network.hosts() if str(h) != ip]
            with concurrent.futures.ThreadPoolExecutor(max_workers=96) as ex:
                harogic_ips = list(filter(None, ex.map(probe_harogic, hosts_to_sweep)))

            # The SDK has no network discovery (Device_GetNetworkDeviceList is a
            # stub), so a scan only finds IP addresses. Model and serial number are
            # read from the analyzer when it is connected, never guessed here.
            for tip in sorted(harogic_ips):
                if tip in discovered_by_ip:
                    continue

                m = None
                u = None
                alias = "Harogic analyzer"
                is_cal = None
                summary = {}
                hostname = ""

                discovered_by_ip[tip] = {
                    'model': m,
                    'uid': u,
                    'ip': tip,
                    'mask': mask,
                    'hostname': hostname,
                    'is_calibrated': is_cal,
                    'alias': alias,
                    'interface': ifc.get('name', ''),
                    'cal_summary': summary
                }

        # 3. Names the analyzers announce by mDNS ("<model>-<serial>.local"): they identify an
        # analyzer the address scan could only see as "something on port 5000", and a name
        # keeps working if the analyzer's address changes
        try:
            from core import net_route
            for found in net_route.browse_mdns():
                entry = discovered_by_ip.get(found["ip"])
                if entry is None:
                    if not found["ip"]:
                        continue
                    entry = discovered_by_ip[found["ip"]] = {
                        'model': None, 'uid': None, 'ip': found["ip"], 'mask': '', 'hostname': '',
                        'is_calibrated': None, 'alias': "Harogic analyzer", 'interface': found["interface"],
                        'cal_summary': {}}
                entry['hostname'] = found["hostname"]
                entry['interface'] = entry.get('interface') or found["interface"]
                if entry.get('model') is None:
                    entry['model'], entry['uid'] = found["model"], found["uid"]
                    if cm:
                        entry['is_calibrated'] = cm.is_calibrated(found["model"], found["uid"])
                        entry['cal_summary'] = cm.get_cal_summary(found["model"], found["uid"])
                    entry['alias'] = (entry.get('cal_summary') or {}).get('alias') or f"Model {found['model']:03d}"
        except Exception:
            pass

        return list(discovered_by_ip.values())

    def _on_sdk_retry(self, info):
        """The analyzer did not open with one SDK build: restart the hardware process with the next."""
        fw = info.get("firmware") or 0
        self.status_message.emit(
            f"Open failed (status {info.get('status')}{f', firmware {fw:#x}' if fw else ''}) with SDK "
            f"{_api.library_version(info.get('failed'))}; restarting with SDK {_api.library_version(info.get('next'))}…")
        self.connect_device(**self._connect_args, sdk_lib=info["next"], tried_libs=tuple(info.get("tried", ())))

    def _on_sdk_ok(self, path: str):
        if path:
            QSettings("Harogic", "RF_Recon_Modern").setValue(self._sdk_key, path)

    def _sweep_consumed(self, *_):
        if self.queue_reader:
            self.queue_reader.mark_idle("data")

    def _rta_consumed(self, *_):
        if self.queue_reader:
            self.queue_reader.mark_idle("rta_data")

    def _det_consumed(self, *_):
        if self.queue_reader:
            self.queue_reader.mark_idle("det_data")

    def handle_connection_status(self, is_connected):
        self.is_connected = is_connected
        self.connection_status.emit(is_connected)
            
    def start(self):
        if self.command_queue:
            self.command_queue.put("start")
            
    def pause(self):
        if self.command_queue:
            self.command_queue.put("pause")
            
    def configure(self, start_freq_hz, stop_freq_hz, ref_level=0.0, atten=0, preamp=0x00, ifagc=1, ifagc_target=-9.0, ifagc_period=0.01, if_out=0):
        if self.command_queue:
            self.command_queue.put(("config", (start_freq_hz, stop_freq_hz, ref_level, atten, preamp, ifagc, ifagc_target, ifagc_period, if_out)))

    def configure_rta(self, center_freq_hz: float, decimate_factor: int = 1, ref_level: float = 0.0, trig_src: int = 2, trig_mode: int = 0, trig_time: float = 0.05, preamp: int = 0x00, atten: int = 0):
        if self.command_queue:
            self.command_queue.put(("rta_config", (center_freq_hz, decimate_factor, ref_level, trig_src, trig_mode, trig_time, preamp, atten)))

    def configure_det(self, center_freq_hz: float, decimate_factor: int = 2, ref_level: float = 0.0, trig_src: int = 2, trig_mode: int = 0, trig_length: int = 16240, trig_level=None, atten=None, preamp=None):
        if self.command_queue:
            args = (center_freq_hz, decimate_factor, ref_level, trig_src, trig_mode, trig_length)
            # For analyzers whose zero span takes them (a tinySA): a trigger level in dBm, and
            # its own attenuation (-1: automatic) and pre-amplifier setting
            if (trig_level, atten, preamp) != (None, None, None):
                args += (None if trig_level is None else float(trig_level), atten, preamp)
            self.command_queue.put(("det_config", args))

    def configure_iqs(self, center_freq_hz: float, decimate_factor: int = 64, ref_level: float = 0.0, trig_src: int = 2, trig_length: int = 16384, preamp: int = 0, atten: int = 0, continuous: bool = False):
        if self.command_queue:
            self.command_queue.put(("iqs_config", (center_freq_hz, decimate_factor, ref_level, trig_src, trig_length, preamp, atten, continuous)))

    def configure_mscan(self, channels: list, dwell_time: float = 0.001, detector: int = 1, ref_level: float = 0.0, preamp: int = 0, atten: int = 0, decimate: int = 256):
        if self.command_queue:
            self.command_queue.put(("mscan_config", (channels, dwell_time, detector, ref_level, preamp, atten, decimate)))

    def stop_mscan(self):
        if self.command_queue:
            self.command_queue.put("stop_mscan")

    def set_rf_input(self, rf_input: str):
        """Which RF input to use on analyzers with several: "auto" (by frequency) or an input id."""
        if self.command_queue:
            self.command_queue.put(("rf_input", rf_input))

    def request_timed_capture(self, center_freq_hz: float, decimate: int = 64, samples: int = 32768,
                              ref_level: float = 0.0, trigger_source: int = 9, request_id=None):
        """
        One IQ capture with its timing (answered by timed_capture_ready). trigger_source 9 is
        the analyzer's GNSS 1PPS: the capture starts on the GPS second. 2 is "now".
        """
        if self.command_queue:
            self.command_queue.put(("timed_capture", (center_freq_hz, decimate, samples, ref_level, trigger_source, request_id)))

    def set_reference_mode(self, mode: str):
        """The analyzer's reference oscillator: "lock" (disciplined to GNSS) or "hold" (free-running)."""
        if self.command_queue:
            self.command_queue.put(("docxo_mode", mode))

    def set_input_compensation(self, freqs_hz: list, correction_db: list):
        """Input-chain correction table (empty lists turn it off)."""
        if self.command_queue:
            self.command_queue.put(("freq_comp", (list(freqs_hz), list(correction_db))))

    def set_operating_mode(self, mode_str: str, params: dict = None):
        if self.command_queue:
            self.command_queue.put(("set_mode", (mode_str, params or {})))
            
    def stop(self):
        if self.command_queue:
            self.command_queue.put("stop")
            
    def update_bandwidth(self, rbw_mode, rbw_hz, vbw_mode, vbw_hz):
        if self.command_queue:
            self.command_queue.put(("bw_config", (rbw_mode, rbw_hz, vbw_mode, vbw_hz)))

    def configure_sweep(self, swt_mode, swt_time, trace_points, spur, window):
        if self.command_queue:
            self.command_queue.put(("sweep_config", (swt_mode, swt_time, trace_points, spur, window)))

    def configure_detect(self, detector, trace_detector):
        if self.command_queue:
            self.command_queue.put(("detect_config", (detector, trace_detector)))

    def set_fan_state(self, fan_state: int, threshold_temp: float = 50.0):
        if self.command_queue:
            self.command_queue.put(("fan_config", (int(fan_state), float(threshold_temp))))

    def _shutdown_process(self, grace_s: float = 3.0):
        """
        Ask the hardware process to stop and wait for it to close the device
        (MSCAN_Stop / RTA_BusTriggerStop / Device_Close can take a few seconds);
        terminate only as a fallback, and kill as a last resort.
        """
        if self.process is None:
            return
        if self.process.is_alive():
            if self.command_queue:
                try:
                    self.command_queue.put("stop")
                except Exception:
                    pass
            self.process.join(timeout=grace_s)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1.0)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1.0)
        self.process = None

    def _stop_hardware(self):
        """Stop the hardware process, keeping the queue reader draining until it
        has exited (the process blocks on a full data queue otherwise)."""
        if self.queue_reader:
            self.queue_reader.expect_exit = True
        self._shutdown_process()
        if self.queue_reader:
            self.queue_reader.stop()
            self.queue_reader = None

    def disconnect_device(self):
        self._stop_hardware()
        self.is_connected = False
        self.connection_status.emit(False)
        self.status_message.emit("Device disconnected.")
