import ctypes
import numpy as np
import multiprocessing
import queue
import time
from PyQt6.QtCore import QThread, pyqtSignal, QObject
try:
    from .htra_api_wrapper import *
except ImportError:
    from htra_api_wrapper import *

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

    # Read License Options directly from on-board memory vector
    try:
        dev_ptr = device.value if hasattr(device, 'value') else device
        if dev_ptr:
            vec_offset = 0x33c0000 + 21656
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

def hardware_process(command_queue, data_queue, start_freq_hz, stop_freq_hz, probe_only=False, cal_dir=None, ref_level=0.0, atten=-1, preamp=0x00, ifagc=1, ifagc_target=-9.0, ifagc_period=0.01, if_out=0, interface_type="usb", ip_address="192.168.1.50", port=5000, target_model=None, target_uid=None, usb_index=0):
    if cal_dir:
        import os
        try:
            os.chdir(cal_dir)
        except Exception as e:
            data_queue.put(("error", f"Failed to change directory to calibration folder: {e}"))
            return
            
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
            # Resolve hostname or standard IPv4 string
            target_str = ip_address.strip()
            resolved_ip = socket.gethostbyname(target_str)
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

    # 1. Identify device Model & UID before opening to stage matching calibration files
    if interface_type.lower() == "usb":
        try:
            dev_count = ctypes.c_uint8(0)
            dev_num_list = (ctypes.c_uint8 * 256)()
            dev_info_list = (DeviceInfo_TypeDef * 256)()
            for _ in range(4):
                list_status = dll.Device_List(ctypes.pointer(boot_profile), ctypes.pointer(dev_count), dev_num_list, dev_info_list)
                if list_status == 0 and dev_count.value > 0:
                    matched_idx = 0
                    if target_uid is not None:
                        for i in range(dev_count.value):
                            if int(dev_info_list[i].DeviceUID) == target_uid:
                                matched_idx = i
                                break
                    elif 0 <= usb_index < dev_count.value:
                        matched_idx = usb_index
                    det_model = int(dev_info_list[matched_idx].Model)
                    det_uid = int(dev_info_list[matched_idx].DeviceUID)
                    dev_num_to_open = int(dev_num_list[matched_idx])
                    break
                time.sleep(0.15)
        except Exception:
            pass
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
            cm.deploy_cal_files(det_model, det_uid)
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
    for _ in range(8):
        status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
        if status == 0:
            break
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
        
    model = int(boot_info.DeviceInfo.Model)
    uid = int(boot_info.DeviceInfo.DeviceUID)
    
    # Touch calibration metadata on successful connection
    try:
        from core.calibration_manager import CalibrationManager
        cm = CalibrationManager()
        cm.deploy_cal_files(model, uid)
    except Exception:
        pass
        
    data_queue.put(("device_info", (model, uid)))
    try:
        endorsements = _query_hardware_endorsements(dll, device, boot_info, interface_type, ip_address, port)
        data_queue.put(("hw_endorsements", endorsements))
    except Exception as e:
        pass
    data_queue.put(("connected", True))
    if interface_type.lower() == "network":
        data_queue.put(("status", f"Connected to Network Analyzer ({ip_address}:{port})."))
    else:
        data_queue.put(("status", "Device opened successfully."))
        
    # Read initial temperature once while device channel is completely idle
    try:
        dev_state = DeviceState_TypeDef()
        if hasattr(dll, 'Device_QueryDeviceState_Realtime'):
            st = dll.Device_QueryDeviceState_Realtime(ctypes.pointer(device), ctypes.pointer(dev_state))
            if st == 0 and dev_state.Temperature != 0:
                data_queue.put(("temperature", float(dev_state.Temperature) / 100.0))
    except Exception:
        pass
    
    # Check hardware supported functions
    supported_funcs = 0
    if hasattr(dll, 'Device_GetSupportedFunctions'):
        try:
            supp_c = ctypes.c_uint64(0)
            if dll.Device_GetSupportedFunctions(ctypes.pointer(device), ctypes.pointer(supp_c)) == 0:
                supported_funcs = supp_c.value
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
    if init_span <= 15e6:
        current_rbw_hz = 10e3
    elif init_span <= 50e6:
        current_rbw_hz = 30e3
    elif init_span <= 150e6:
        current_rbw_hz = 50e3
    else:
        current_rbw_hz = 100e3
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
    iqs_raw_packet = None
    iqs_raw_stream = None

    # 5. MSCAN State (Hardware Discrete Channel Scanning)
    mscan_profiles_in = None
    mscan_profiles_out = None
    mscan_info = MSCAN_Info_Typedef()
    mscan_channels = []
    mscan_running = False
    mscan_spec_buf = None
    mscan_iq_buf = None

    is_running = False
    consecutive_errors = 0
    last_temp_check_time = 0.0
    
    while True:
        # Check for commands
        try:
            cmd = command_queue.get_nowait()
            if isinstance(cmd, tuple) and cmd[0] == "close":
                break
                
            if cmd == "stop":
                break
            elif cmd == "start":
                is_running = True
                consecutive_errors = 0
            elif cmd == "pause":
                is_running = False
                
            elif isinstance(cmd, tuple) and cmd[0] == "set_mode":
                target_mode, mode_params = cmd[1]
                current_mode = target_mode.upper()
                is_running = True
                consecutive_errors = 0
                
                if current_mode == "SWP":
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
                    data_queue.put(("status", "Switched to Swept Spectrum (SWP) mode"))
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

            elif isinstance(cmd, tuple) and cmd[0] == "rta_config":
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
                c_freq, dec_factor, r_lvl, trig_src, trig_mode, trig_len = cmd[1]
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
                c_freq, dec_factor, r_lvl, trig_src, trig_len, preamp, atten = cmd[1]
                current_mode = "IQS"
                dll.IQS_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(iqs_profile_in))
                iqs_profile_in.CenterFreq_Hz = float(c_freq)
                iqs_profile_in.RefLevel_dBm = float(r_lvl)
                iqs_profile_in.DecimateFactor = int(dec_factor)
                iqs_profile_in.DataFormat = DataFormat_TypeDef.Complex16bit
                iqs_profile_in.TriggerSource = int(trig_src)
                iqs_profile_in.TriggerMode = TriggerMode_TypeDef.FixedPoints
                iqs_profile_in.TriggerLength = int(trig_len)
                iqs_profile_in.Preamplifier = int(preamp)
                iqs_profile_in.Atten = int(atten)
                
                status = dll.IQS_Configuration(ctypes.pointer(device), ctypes.pointer(iqs_profile_in), ctypes.pointer(iqs_profile_out), ctypes.pointer(iqs_stream_info))
                if status == 0:
                    altern_iq_packet = c_int16_p()
                    iqs_raw_stream = (ctypes.c_int16 * (iqs_stream_info.StreamSamples * 2))()
                    data_queue.put(("status", f"IQS Demod active @ {c_freq/1e6:.3f} MHz (Decimate: {iqs_profile_out.DecimateFactor})"))
                else:
                    data_queue.put(("error", f"IQS configuration failed (Status: {status})"))

            elif isinstance(cmd, tuple) and cmd[0] == "mscan_config":
                channels, dwell_time, detector, r_lvl, preamp, atten = cmd[1]
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
                    for i, ch in enumerate(channels):
                        f_hz = float(ch if isinstance(ch, (int, float)) else ch.get("freq_hz", ch.get("freq", 500e6)))
                        p = mscan_profiles_in[i]
                        p.CenterFreq_Hz = f_hz
                        p.RefLevel_dBm = float(r_lvl)
                        p.DwellTime = float(dwell_time)
                        p.DecimateFactor = 1
                        p.FFTSize = 512
                        p.DetectCount = 1
                        p.Detector = det_enum
                        p.IFAGC = IFAGC_TypeDef.IFAGC_Off
                        p.XPPSTrigger = XPPSTrigger_TypeDef.XPPSTrigger_Off
                        p.IQPlayBack = IQPlayBack_TypeDef.IQPlayBack_Off
                        p.Window = Window_TypeDef.Blackman

                    elements = ctypes.c_int32(num_channels)
                    repetitions = ctypes.c_int64(100_000_000)
                    preamp_val = PreamplifierState_TypeDef(int(preamp))
                    status = dll.MSCAN_Configuration(
                        ctypes.pointer(device),
                        mscan_profiles_in,
                        mscan_profiles_out,
                        ctypes.pointer(mscan_info),
                        ctypes.pointer(elements),
                        ctypes.pointer(repetitions),
                        ctypes.pointer(preamp_val)
                    )
                    if status == 0:
                        max_spec = max(4096, int(mscan_info.SpectrumPoints) * max(1, int(mscan_info.SpectrumFrames)))
                        max_iq = max(8192, int(mscan_info.IQStreamPoints) * 2)
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

            elif isinstance(cmd, tuple) and cmd[0] == "bw_config":
                current_mode = "SWP"
                rbw_m, rbw_h, vbw_m, vbw_h = cmd[1]
                current_rbw_mode = rbw_m
                current_rbw_hz = rbw_h
                current_vbw_mode = vbw_m
                current_vbw_hz = vbw_h

                span_hz = swp_profile_in.Span_Hz if hasattr(swp_profile_in, 'Span_Hz') and swp_profile_in.Span_Hz > 0 else 138e6
                if rbw_m == 1: # Auto
                    if span_hz <= 15e6:
                        calc_rbw = 10e3
                    elif span_hz <= 50e6:
                        calc_rbw = 30e3
                    elif span_hz <= 150e6:
                        calc_rbw = 50e3
                    else:
                        calc_rbw = 100e3
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_Manual
                    swp_profile_in.RBW_Hz = calc_rbw
                elif rbw_m == 2: # 0.001*Span
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_OneThousandthSpan
                elif rbw_m == 3: # 0.01*Span
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_OnePercentSpan
                else: # Manual
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_Manual
                    if rbw_h > 0:
                        swp_profile_in.RBW_Hz = float(rbw_h)

                if vbw_m == 1: # VBW = RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_EqualToRBW
                elif vbw_m == 2: # 0.1 * RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_TenPercentRBW
                elif vbw_m == 3: # 0.01 * RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_OnePercentRBW
                elif vbw_m == 4: # 10 * RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_TenTimesRBW
                else: # Manual
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_Manual
                    if vbw_h > 0:
                        swp_profile_in.VBW_Hz = float(vbw_h)
                
                swp_profile_in.TraceAlign = TraceAlign_TypeDef.AlignToStart
                status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
                if status == 0:
                    if abs(swp_profile_out.RefLevel_dBm - swp_profile_in.RefLevel_dBm) > 0.1:
                        data_queue.put(("amplitude_clamped", (float(swp_profile_out.RefLevel_dBm), int(swp_profile_out.Atten))))
                    data_queue.put(("hw_rbw_updated", (float(swp_profile_out.RBW_Hz), float(swp_profile_out.VBW_Hz))))
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
                    data_queue.put(("status", f"RBW set to {swp_profile_out.RBW_Hz/1e3:.1f} kHz ({full_sweep_points} pts)"))
                else:
                    data_queue.put(("error", f"SWP RBW configuration failed (Status: {status})"))

            elif isinstance(cmd, tuple) and cmd[0] == "sweep_config":
                current_mode = "SWP"
                swt_mode, swt_time, trace_points, spur, window = cmd[1]
                swp_profile_in.SweepTimeMode = swt_mode
                swp_profile_in.SweepTime = swt_time
                if trace_points > 0:
                    swp_profile_in.TracePoints = trace_points
                swp_profile_in.SpurRejection = spur
                swp_profile_in.Window = window
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
                    data_queue.put(("status", "Sweep settings updated"))
                else:
                    data_queue.put(("error", f"SWP sweep configuration failed (Status: {status})"))

            elif isinstance(cmd, tuple) and cmd[0] == "detect_config":
                current_mode = "SWP"
                detector, trace_detector = cmd[1]
                swp_profile_in.Detector = detector
                swp_profile_in.TraceDetector = trace_detector
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
                    data_queue.put(("status", "Detector settings updated"))
                else:
                    data_queue.put(("error", f"SWP detector configuration failed (Status: {status})"))

            elif isinstance(cmd, tuple) and cmd[0] == "config":
                current_mode = "SWP"
                start_f, stop_f, r_level, att, pamp, if_agc, ifagc_tgt, ifagc_per, if_o = cmd[1]
                dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
                swp_profile_in.StartFreq_Hz = float(start_f)
                swp_profile_in.StopFreq_Hz = float(stop_f)
                swp_profile_in.CenterFreq_Hz = (float(start_f) + float(stop_f)) / 2.0
                span_hz = float(stop_f) - float(start_f)
                swp_profile_in.Span_Hz = span_hz
                swp_profile_in.FreqAssignment = SWP_FreqAssignment_TypeDef.StartStop
                
                if current_rbw_mode == RBWMode_TypeDef.RBW_Auto or current_rbw_mode == 1:
                    if span_hz <= 15e6:
                        calc_rbw = 10e3
                    elif span_hz <= 50e6:
                        calc_rbw = 30e3
                    elif span_hz <= 150e6:
                        calc_rbw = 50e3
                    else:
                        calc_rbw = 100e3
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_Manual
                    swp_profile_in.RBW_Hz = calc_rbw
                elif current_rbw_mode == 2: # 0.001*Span
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_OneThousandthSpan
                elif current_rbw_mode == 3: # 0.01*Span
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_OnePercentSpan
                else:
                    swp_profile_in.RBWMode = RBWMode_TypeDef.RBW_Manual
                    swp_profile_in.RBW_Hz = current_rbw_hz

                if current_vbw_mode == 1: # VBW = RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_EqualToRBW
                elif current_vbw_mode == 2: # 0.1 * RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_TenPercentRBW
                elif current_vbw_mode == 3: # 0.01 * RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_OnePercentRBW
                elif current_vbw_mode == 4: # 10 * RBW
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_TenTimesRBW
                else: # Manual
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_Manual
                    if current_vbw_hz > 0:
                        swp_profile_in.VBW_Hz = float(current_vbw_hz)

                swp_profile_in.RefLevel_dBm = float(r_level)
                swp_profile_in.Atten = -1 if att < 0 else int(att)
                swp_profile_in.Preamplifier = pamp
                swp_profile_in.EnableIFAGC = if_agc
                swp_profile_in.TraceAlign = TraceAlign_TypeDef.AlignToStart
                
                status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
                if status == 0:
                    if abs(swp_profile_out.RefLevel_dBm - swp_profile_in.RefLevel_dBm) > 0.1:
                        data_queue.put(("amplitude_clamped", (float(swp_profile_out.RefLevel_dBm), int(swp_profile_out.Atten))))
                    data_queue.put(("hw_rbw_updated", (float(swp_profile_out.RBW_Hz), float(swp_profile_out.VBW_Hz))))
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
                    data_queue.put(("status", f"Reconfigured to {start_f/1e6:.1f} MHz - {stop_f/1e6:.1f} MHz"))
                else:
                    data_queue.put(("error", "SWP reconfiguration failed."))
                    is_running = False
        except queue.Empty:
            pass
            
        # Periodic Temperature & Hardware Health Polling (Every ~2.0s when sweep is paused)
        # Device_QueryDeviceState_Realtime occupies the USB bulk control channel and must NOT collide
        # with active high-throughput SWP/RTA streaming transfers.
        now = time.time()
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
                                
                                # DMA Buffer healing for unpopulated 0.0 dBm chunks or NaNs/Infs
                                invalid_mask = np.isnan(temp_spec) | np.isinf(temp_spec) | (temp_spec == 0.0)
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
                    bitmap_np = np.frombuffer(rta_spec_bitmap, dtype=np.uint16, count=w * h).reshape((h, w))
                    freq_axis = np.linspace(rta_frame_info.StartFrequency_Hz, rta_frame_info.StopFrequency_Hz, w)
                    data_queue.put(("rta_data", (freq_axis, power_trace_np, bitmap_np, {
                        "start_freq": rta_frame_info.StartFrequency_Hz,
                        "stop_freq": rta_frame_info.StopFrequency_Hz,
                        "center_freq": rta_profile_out.CenterFreq_Hz,
                        "width": w,
                        "height": h,
                        "ref_level": rta_profile_out.RefLevel_dBm
                    })))
                    time.sleep(0.005)
                else:
                    time.sleep(0.02)

            elif current_mode == "DET" and det_norm_packet is not None:
                dll.DET_BusTriggerStart(ctypes.pointer(device))
                scale_to_v = ctypes.c_float()
                for p_idx in range(det_stream_info.PacketCount):
                    st = dll.DET_GetPowerStream(
                        ctypes.pointer(device), det_norm_packet, ctypes.pointer(scale_to_v),
                        ctypes.pointer(det_trigger_info), ctypes.pointer(meas_aux_info)
                    )
                    start_idx = p_idx * det_stream_info.PacketSamples
                    if p_idx == det_stream_info.PacketCount - 1 and det_stream_info.StreamSamples % det_stream_info.PacketSamples != 0:
                        rem = det_stream_info.StreamSamples % det_stream_info.PacketSamples
                        det_raw_stream[start_idx : start_idx + rem] = det_norm_packet[:rem]
                    else:
                        det_raw_stream[start_idx : start_idx + det_stream_info.PacketSamples] = det_norm_packet[:]
                        
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

            elif current_mode == "IQS" and iqs_raw_stream is not None:
                try:
                    dll.IQS_BusTriggerStart(ctypes.pointer(device))
                    scale_to_v = ctypes.c_float(0.0)
                    meas_aux = MeasAuxInfo_TypeDef()
                    trig_info = TriggerInfo_TypeDef()
                    
                    pkt_samples = iqs_stream_info.PacketSamples
                    stream_samples = iqs_stream_info.StreamSamples
                    for p_idx in range(iqs_stream_info.PacketCount):
                        st = dll.IQS_GetIQStream(
                            ctypes.pointer(device), ctypes.pointer(altern_iq_packet), ctypes.pointer(scale_to_v),
                            ctypes.pointer(trig_info), ctypes.pointer(meas_aux)
                        )
                        start_idx = p_idx * pkt_samples * 2
                        if p_idx == iqs_stream_info.PacketCount - 1 and (stream_samples % pkt_samples) != 0:
                            rem = 2 * (stream_samples % pkt_samples)
                            iqs_raw_stream[start_idx : start_idx + rem] = altern_iq_packet[0:rem]
                        else:
                            cnt = pkt_samples * 2
                            iqs_raw_stream[start_idx : start_idx + cnt] = altern_iq_packet[0:cnt]
                            
                    raw_np = np.frombuffer(iqs_raw_stream, dtype=np.int16)
                    scale = float(scale_to_v.value) if scale_to_v.value > 0 else 1.97e-6
                    i_data = raw_np[0::2].astype(np.float32) * scale
                    q_data = raw_np[1::2].astype(np.float32) * scale
                    iq_complex = i_data + 1j * q_data
                    
                    sr = 100e6 / max(1, iqs_profile_out.DecimateFactor)
                    data_queue.put(("iqs_data", (iq_complex, sr, {
                        "center_freq": iqs_profile_out.CenterFreq_Hz,
                        "decimate": iqs_profile_out.DecimateFactor,
                        "sample_rate": sr,
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
                        spec_dbm = None
                        peak_power = -120.0
                        if pts > 0:
                            raw_u8 = np.frombuffer(mscan_spec_buf, dtype=np.uint8, count=pts)
                            spec_dbm = raw_u8.astype(np.float32) * scale + offset
                            peak_power = float(np.max(spec_dbm))
                        else:
                            peak_power = offset

                        ch_freq = 0.0
                        ch_info = {}
                        if 0 <= el_idx < len(mscan_channels):
                            ch_obj = mscan_channels[el_idx]
                            if isinstance(ch_obj, dict):
                                ch_freq = float(ch_obj.get("freq_hz", ch_obj.get("freq", 0.0)))
                                ch_info = ch_obj
                            else:
                                ch_freq = float(ch_obj)

                        data_queue.put(("mscan_data", (el_idx, ch_freq, peak_power, spec_dbm, {
                            "repeat_index": int(mscan_data.RepeatIndex),
                            "element_index": el_idx,
                            "channel_info": ch_info,
                            "temperature": float(mscan_data.Temperature) if mscan_data.Temperature != 0 else 0.0,
                            "timestamp": float(mscan_data.SysTimeStamp)
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
        if current_mode == "MSCAN" and mscan_running:
            dll.MSCAN_Stop(ctypes.pointer(device))
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
    status_message = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    device_info_received = pyqtSignal(int, object)
    trace_points_received = pyqtSignal(int)
    missing_cal_received = pyqtSignal(int, object, str)
    amplitude_clamped = pyqtSignal(float, int)
    bandwidth_updated = pyqtSignal(float, float)
    hw_endorsements = pyqtSignal(dict)

    def __init__(self, data_queue):
        super().__init__()
        self.data_queue = data_queue
        self.is_running = True
        
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
            except queue.Empty:
                pass

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
        elif msg_type == "connected":
            self.connection_status.emit(bool(content))
        elif msg_type == "status":
            self.status_message.emit(content)
            if "opened successfully" in content or "Connected to Network Analyzer" in content:
                self.connection_status.emit(True)
        elif msg_type == "error":
            self.status_message.emit(content)
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
    status_message = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    device_info_received = pyqtSignal(int, object)
    trace_points_received = pyqtSignal(int)
    missing_cal_received = pyqtSignal(int, object, str)
    amplitude_clamped = pyqtSignal(float, int)
    bandwidth_updated = pyqtSignal(float, float)
    hw_endorsements = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.is_connected = False
        self.process = None
        self.command_queue = None
        self.data_queue = None
        self.queue_reader = None
        
    def connect_device(self, start_freq_hz=1e9, stop_freq_hz=2e9, probe_only=False, cal_dir=None, ref_level=0.0, atten=-1, preamp=0x00, ifagc=1, interface_type="usb", ip_address="192.168.1.50", port=5000, target_model=None, target_uid=None, usb_index=0):
        if self.queue_reader:
            self.queue_reader.stop()
            self.queue_reader = None
        if self.process and self.process.is_alive():
            if self.command_queue:
                try:
                    self.command_queue.put("stop")
                except Exception:
                    pass
            self.process.join(timeout=0.5)
            if self.process.is_alive():
                self.process.terminate()
            self.process = None

        self.command_queue = multiprocessing.Queue()
        self.data_queue = multiprocessing.Queue(maxsize=4)
        
        self.process = multiprocessing.Process(
            target=hardware_process,
            args=(
                self.command_queue, self.data_queue, start_freq_hz, stop_freq_hz,
                probe_only, cal_dir, ref_level, atten, preamp, ifagc, -9.0, 0.01, 0,
                interface_type, ip_address, port, target_model, target_uid, usb_index
            )
        )
        self.process.daemon = True
        self.process.start()
        
        self.queue_reader = DeviceQueueReader(self.data_queue)
        self.queue_reader.spectrum_data_ready.connect(self.spectrum_data_ready)
        self.queue_reader.rta_data_ready.connect(self.rta_data_ready)
        self.queue_reader.det_data_ready.connect(self.det_data_ready)
        self.queue_reader.iqs_data_ready.connect(self.iqs_data_ready)
        self.queue_reader.mscan_data_ready.connect(self.mscan_data_ready)
        self.queue_reader.temperature_updated.connect(self.temperature_updated)
        self.queue_reader.status_message.connect(self.status_message)
        self.queue_reader.connection_status.connect(self.handle_connection_status)
        self.queue_reader.device_info_received.connect(self.device_info_received)
        self.queue_reader.trace_points_received.connect(self.trace_points_received)
        self.queue_reader.missing_cal_received.connect(self.missing_cal_received)
        self.queue_reader.amplitude_clamped.connect(self.amplitude_clamped.emit)
        self.queue_reader.bandwidth_updated.connect(self.bandwidth_updated.emit)
        self.queue_reader.hw_endorsements.connect(self.hw_endorsements.emit)
        self.queue_reader.start()
        
        return True

    @staticmethod
    def get_local_network_interfaces() -> list:
        """
        Enumerate all active host network interfaces, their assigned IP addresses,
        subnet masks, and operational link state.
        """
        import os
        import socket
        import fcntl
        import struct

        interfaces = []
        try:
            if_names = os.listdir('/sys/class/net')
        except Exception:
            if_names = []

        for ifname in sorted(if_names):
            if ifname == 'lo':
                continue
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                if_bytes = ifname[:15].encode('utf-8')
                # SIOCGIFADDR (0x8915)
                addr_res = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', if_bytes))
                ip_str = socket.inet_ntoa(addr_res[20:24])

                # SIOCGIFNETMASK (0x891b)
                mask_res = fcntl.ioctl(s.fileno(), 0x891b, struct.pack('256s', if_bytes))
                mask_str = socket.inet_ntoa(mask_res[20:24])

                # Operational link state
                state = 'unknown'
                try:
                    with open(f'/sys/class/net/{ifname}/operstate') as f:
                        state = f.read().strip()
                except Exception:
                    pass

                interfaces.append({
                    'name': ifname,
                    'ip': ip_str,
                    'mask': mask_str,
                    'state': state,
                    'display': f"{ifname} ({ip_str}) [{state.upper()}]"
                })
            except Exception:
                pass
            finally:
                s.close()
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
                res = dll.Device_GetNetworkDeviceList(
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
            parts = [int(p) for p in ip.split('.')]
            base = f"{parts[0]}.{parts[1]}.{parts[2]}"

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
            hosts_to_sweep = [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" != ip]
            with concurrent.futures.ThreadPoolExecutor(max_workers=96) as ex:
                harogic_ips = list(filter(None, ex.map(probe_harogic, hosts_to_sweep)))

            # Resolve device metadata for each discovered analyzer
            for tip in sorted(harogic_ips):
                if tip in discovered_by_ip:
                    continue

                m = 67
                u = 0
                alias = "Model 067"
                is_cal = False
                summary = {}
                if cm:
                    for dev_meta in cm.get_all_devices():
                        if dev_meta.get('model') == 67:
                            m = dev_meta['model']
                            u = dev_meta['uid']
                            alias = dev_meta.get('alias') or f"Model {m:03d}"
                            is_cal = cm.is_calibrated(m, u)
                            summary = cm.get_cal_summary(m, u)
                            break

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

        return list(discovered_by_ip.values())

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

    def configure_det(self, center_freq_hz: float, decimate_factor: int = 2, ref_level: float = 0.0, trig_src: int = 2, trig_mode: int = 0, trig_length: int = 16240):
        if self.command_queue:
            self.command_queue.put(("det_config", (center_freq_hz, decimate_factor, ref_level, trig_src, trig_mode, trig_length)))

    def configure_iqs(self, center_freq_hz: float, decimate_factor: int = 64, ref_level: float = 0.0, trig_src: int = 2, trig_length: int = 16384, preamp: int = 0, atten: int = 0):
        if self.command_queue:
            self.command_queue.put(("iqs_config", (center_freq_hz, decimate_factor, ref_level, trig_src, trig_length, preamp, atten)))

    def configure_mscan(self, channels: list, dwell_time: float = 0.001, detector: int = 1, ref_level: float = 0.0, preamp: int = 0, atten: int = 0):
        if self.command_queue:
            self.command_queue.put(("mscan_config", (channels, dwell_time, detector, ref_level, preamp, atten)))

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

    def disconnect_device(self):
        self.stop()
        if self.queue_reader:
            self.queue_reader.stop()
        if self.process:
            self.process.join(timeout=2.0)
            if self.process.is_alive():
                self.process.terminate()
        self.is_connected = False
        self.connection_status.emit(False)
        self.status_message.emit("Device disconnected.")
