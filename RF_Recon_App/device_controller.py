import ctypes
import numpy as np
import multiprocessing
import queue
import time
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from htra_api_wrapper import *

def hardware_process(command_queue, data_queue, start_freq_hz, stop_freq_hz, probe_only=False, cal_dir=None, ref_level=0.0, atten=-1, preamp=0x00, ifagc=0, ifagc_target=-9.0, ifagc_period=0.01, if_out=0):
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
    boot_profile.DevicePowerSupply = DevicePowerSupply_TypeDef.USBPortAndPowerPort
    boot_profile.PhysicalInterface = PhysicalInterface_TypeDef.USB

    if probe_only:
        dev_count = ctypes.c_uint8(0)
        dev_num_list = (ctypes.c_uint8 * 256)()
        dev_info_list = (DeviceInfo_TypeDef * 256)()
        
        for _ in range(8):
            list_status = dll.Device_List(ctypes.pointer(boot_profile), ctypes.pointer(dev_count), dev_num_list, dev_info_list)
            if list_status == 0 and dev_count.value > 0:
                model = int(dev_info_list[0].Model)
                uid = int(dev_info_list[0].DeviceUID)
                data_queue.put(("device_info", (model, uid)))
                return
            time.sleep(0.25)
            
        data_queue.put(("error", "No Harogic analyzer detected. Please check USB connection."))
        return

    device = ctypes.c_void_p()
    dev_num = ctypes.c_int(0)
    
    status = -1
    for _ in range(8):
        status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
        if status == 0:
            break
        time.sleep(0.25)
    
    if status != 0:
        err_msg = f"Failed to open device (Status: {status})"
        if status == -3:
            err_msg = "RF calibration file is missing. Please import calibration files."
        elif status == -4:
            err_msg = "IF calibration file is missing. Please import calibration files."
        elif status == -1:
            err_msg = "Device USB communication failed. Please reconnect USB device."
        data_queue.put(("error", err_msg))
        return
        
    data_queue.put(("status", "Device opened successfully."))
    
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
    current_vbw_hz = current_rbw_hz # Match VBW to RBW for clean video filtering without excessive noise

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
    swp_profile_in.Atten = -1 if atten <= 0 else atten
    swp_profile_in.Preamplifier = preamp
    swp_profile_in.EnableIFAGC = ifagc
    
    status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
    if status != 0:
        # Fallback to full native sweep configuration if sub-span parameter download was rejected
        dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
        status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
        
    if status != 0:
        data_queue.put(("error", f"SWP configuration failed (Status: {status})."))
        dll.Device_Close(ctypes.pointer(device))
        return
        
    data_queue.put(("status", "SWP configuration delivered."))
    
    full_sweep_points = trace_info.FullsweepTracePoints
    partial_sweep_points = trace_info.PartialsweepTracePoints
    total_hops = trace_info.TotalHops
    
    max_buffer_pts = max(full_sweep_points, partial_sweep_points * total_hops, 32768)
    partial_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
    partial_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
    
    hop_index = ctypes.c_int(0)
    frame_index = ctypes.c_int(0)
    meas_aux_info = MeasAuxInfo_TypeDef()
    
    freq_np = np.linspace(swp_profile_out.StartFreq_Hz, swp_profile_out.StopFreq_Hz, full_sweep_points)
    power_np = np.zeros(full_sweep_points, dtype=np.float32)

    is_running = False
    consecutive_errors = 0
    
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
            elif isinstance(cmd, tuple) and cmd[0] == "bw_config":
                rbw_m, rbw_h, vbw_m, vbw_h = cmd[1]
                current_rbw_mode = rbw_m
                current_rbw_hz = rbw_h
                current_vbw_mode = vbw_m
                current_vbw_hz = vbw_h
                status = dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
                swp_profile_in.RBWMode = rbw_m
                swp_profile_in.RBW_Hz = rbw_h
                swp_profile_in.VBWMode = vbw_m
                swp_profile_in.VBW_Hz = vbw_h
                
                status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
                if status == 0:
                    full_sweep_points = trace_info.FullsweepTracePoints
                    partial_sweep_points = trace_info.PartialsweepTracePoints
                    total_hops = trace_info.TotalHops
                    max_buffer_pts = max(full_sweep_points, partial_sweep_points * total_hops, 32768)
                    partial_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
                    partial_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
                    freq_np = np.linspace(swp_profile_in.StartFreq_Hz, swp_profile_in.StopFreq_Hz, full_sweep_points)
                    power_np = np.zeros(full_sweep_points, dtype=np.float32)
                    data_queue.put(("status", f"Bandwidth settings updated"))
                else:
                    data_queue.put(("error", "SWP reconfiguration failed for bandwidth."))
                    is_running = False

            elif isinstance(cmd, tuple) and cmd[0] == "sweep_config":
                swt_mode, swt_time, trace_points, spur, window = cmd[1]
                
                swp_profile_in.SweepTimeMode = swt_mode
                swp_profile_in.SweepTime = swt_time
                if trace_points > 0:
                    swp_profile_in.TracePoints = trace_points
                swp_profile_in.SpurRejection = spur
                swp_profile_in.Window = window
                
                status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
                if status == 0:
                    full_sweep_points = trace_info.FullsweepTracePoints
                    partial_sweep_points = trace_info.PartialsweepTracePoints
                    total_hops = trace_info.TotalHops
                    max_buffer_pts = max(full_sweep_points, partial_sweep_points * total_hops, 32768)
                    partial_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
                    partial_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
                    freq_np = np.linspace(swp_profile_in.StartFreq_Hz, swp_profile_in.StopFreq_Hz, full_sweep_points)
                    power_np = np.zeros(full_sweep_points, dtype=np.float32)
                    
                    data_queue.put(("trace_points", full_sweep_points))
                    data_queue.put(("status", "Sweep settings updated"))
                else:
                    data_queue.put(("error", "SWP reconfiguration failed for sweep settings."))
                    is_running = False

            elif isinstance(cmd, tuple) and cmd[0] == "detect_config":
                detector, trace_detector = cmd[1]
                
                swp_profile_in.Detector = detector
                swp_profile_in.TraceDetector = trace_detector
                
                status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
                if status == 0:
                    full_sweep_points = trace_info.FullsweepTracePoints
                    partial_sweep_points = trace_info.PartialsweepTracePoints
                    total_hops = trace_info.TotalHops
                    max_buffer_pts = max(full_sweep_points, partial_sweep_points * total_hops, 32768)
                    partial_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
                    partial_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
                    freq_np = np.linspace(swp_profile_in.StartFreq_Hz, swp_profile_in.StopFreq_Hz, full_sweep_points)
                    power_np = np.zeros(full_sweep_points, dtype=np.float32)
                    
                    data_queue.put(("status", "Detector settings updated"))
                else:
                    data_queue.put(("error", "SWP reconfiguration failed for detector settings."))
                    is_running = False

            elif isinstance(cmd, tuple) and cmd[0] == "config":
                start_f, stop_f, r_level, att, pamp, if_agc, ifagc_tgt, ifagc_per, if_o = cmd[1]
                dll.SWP_ProfileDeInit(ctypes.pointer(device), ctypes.pointer(swp_profile_in))
                swp_profile_in.StartFreq_Hz = float(start_f)
                swp_profile_in.StopFreq_Hz = float(stop_f)
                swp_profile_in.CenterFreq_Hz = (float(start_f) + float(stop_f)) / 2.0
                span_hz = float(stop_f) - float(start_f)
                swp_profile_in.Span_Hz = span_hz
                swp_profile_in.FreqAssignment = SWP_FreqAssignment_TypeDef.StartStop
                
                # Adaptive RBW / VBW calculation for crisp, razor-sharp traces without waviness
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
                    swp_profile_in.VBWMode = VBWMode_TypeDef.VBW_Manual
                    swp_profile_in.VBW_Hz = calc_rbw # Match VBW to RBW to eliminate high-frequency trace noise/waviness
                else:
                    swp_profile_in.RBWMode = current_rbw_mode
                    swp_profile_in.RBW_Hz = current_rbw_hz
                    swp_profile_in.VBWMode = current_vbw_mode
                    swp_profile_in.VBW_Hz = current_vbw_hz if current_vbw_hz > 0 else current_rbw_hz

                swp_profile_in.RefLevel_dBm = float(r_level)
                swp_profile_in.Atten = -1 if att <= 0 else att
                swp_profile_in.Preamplifier = pamp
                swp_profile_in.EnableIFAGC = if_agc
                
                status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
                
                if status == 0:
                    full_sweep_points = trace_info.FullsweepTracePoints
                    partial_sweep_points = trace_info.PartialsweepTracePoints
                    total_hops = trace_info.TotalHops
                    max_buffer_pts = max(full_sweep_points, partial_sweep_points * total_hops, 32768)
                    partial_freq_ctypes = (ctypes.c_double * max_buffer_pts)()
                    partial_spec_ctypes = (ctypes.c_float * max_buffer_pts)()
                    freq_np = np.linspace(swp_profile_in.StartFreq_Hz, swp_profile_in.StopFreq_Hz, full_sweep_points)
                    power_np = np.zeros(full_sweep_points, dtype=np.float32)
                    data_queue.put(("status", f"Reconfigured to {start_f/1e6:.1f} MHz - {stop_f/1e6:.1f} MHz"))
                else:
                    data_queue.put(("error", "SWP reconfiguration failed."))
                    is_running = False
        except queue.Empty:
            pass
            
        if is_running:
            valid_hops = 0
            for i in range(total_hops):
                status = dll.SWP_GetPartialSweep(
                    ctypes.pointer(device), 
                    partial_freq_ctypes, 
                    partial_spec_ctypes, 
                    ctypes.pointer(hop_index), 
                    ctypes.pointer(frame_index), 
                    ctypes.pointer(meas_aux_info)
                )
                start_idx = i * partial_sweep_points
                if start_idx < full_sweep_points:
                    slice_len = max(0, min(partial_sweep_points, full_sweep_points - start_idx))
                    end_idx = start_idx + slice_len
                    temp_spec = np.frombuffer(partial_spec_ctypes, dtype=np.float32)
                    if status == 0 or np.any(temp_spec[:slice_len] != 0):
                        power_np[start_idx:end_idx] = temp_spec[:slice_len]
                        valid_hops += 1
            
            if valid_hops > 0:
                consecutive_errors = 0
                data_queue.put(("data", (freq_np, np.copy(power_np))))
            else:
                consecutive_errors += 1
                time.sleep(0.01)
                if consecutive_errors >= 15:
                    data_queue.put(("status", "USB bus reset detected. Reconnecting to analyzer..."))
                    try:
                        dll.Device_Close(ctypes.pointer(device))
                    except Exception:
                        pass
                    time.sleep(0.5)
                    reopened = False
                    for _ in range(10):
                        status = dll.Device_Open(ctypes.pointer(device), dev_num, ctypes.pointer(boot_profile), ctypes.pointer(boot_info))
                        if status == 0:
                            reopened = True
                            break
                        time.sleep(0.2)
                    
                    if reopened:
                        cfg_status = dll.SWP_Configuration(ctypes.pointer(device), ctypes.pointer(swp_profile_in), ctypes.pointer(swp_profile_out), ctypes.pointer(trace_info))
                        if cfg_status == 0:
                            data_queue.put(("status", "Reconnected to analyzer successfully."))
                            consecutive_errors = 0
                        else:
                            consecutive_errors = 0
                    else:
                        data_queue.put(("error", "Harogic analyzer disconnected. Please check USB connection/power."))
                        is_running = False
            
    try:
        dll.Device_Close(ctypes.pointer(device))
    except Exception:
        pass

class DeviceQueueReader(QThread):
    spectrum_data_ready = pyqtSignal(np.ndarray, np.ndarray)
    status_message = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    device_info_received = pyqtSignal(int, object)
    trace_points_received = pyqtSignal(int)

    def __init__(self, data_queue):
        super().__init__()
        self.data_queue = data_queue
        self.is_running = True
        
    def run(self):
        last_emit_time = 0
        min_emit_interval = 1.0 / 60.0 # 60 FPS cap
        
        while self.is_running:
            try:
                msg_type, content = self.data_queue.get(timeout=0.1)
                
                # If it's data, drain the queue to get the latest frame
                if msg_type == "data":
                    latest_content = content
                    while True:
                        try:
                            # Try to get more data, non-blocking
                            next_type, next_content = self.data_queue.get_nowait()
                            if next_type == "data":
                                latest_content = next_content
                            else:
                                # We encountered a non-data message, we should process it!
                                # But we'd need to emit the latest data first.
                                freq, power = latest_content
                                self.spectrum_data_ready.emit(freq, power)
                                
                                # Process the non-data message
                                if next_type == "status":
                                    self.status_message.emit(next_content)
                                    if "opened successfully" in next_content:
                                        self.connection_status.emit(True)
                                elif next_type == "error":
                                    self.status_message.emit(next_content)
                                    self.connection_status.emit(False)
                                elif next_type == "device_info":
                                    self.device_info_received.emit(next_content[0], next_content[1])
                                elif next_type == "trace_points":
                                    self.trace_points_received.emit(next_content)
                                    
                                latest_content = None
                                break
                        except queue.Empty:
                            break
                            
                    # Emit the latest data if we still have it
                    if latest_content is not None:
                        current_time = time.time()
                        if current_time - last_emit_time >= min_emit_interval:
                            freq, power = latest_content
                            self.spectrum_data_ready.emit(freq, power)
                            last_emit_time = current_time
                        
                elif msg_type == "status":
                    self.status_message.emit(content)
                    if "opened successfully" in content:
                        self.connection_status.emit(True)
                elif msg_type == "error":
                    self.status_message.emit(content)
                    self.connection_status.emit(False)
                elif msg_type == "device_info":
                    self.device_info_received.emit(content[0], content[1])
                elif msg_type == "trace_points":
                    self.trace_points_received.emit(content)
            except queue.Empty:
                pass
                
    def stop(self):
        self.is_running = False
        self.wait()

class DeviceController(QObject):
    spectrum_data_ready = pyqtSignal(np.ndarray, np.ndarray)
    status_message = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    device_info_received = pyqtSignal(int, object)
    trace_points_received = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.is_connected = False
        self.process = None
        self.command_queue = None
        self.data_queue = None
        self.queue_reader = None
        
    def connect_device(self, start_freq_hz=1e9, stop_freq_hz=2e9, probe_only=False, cal_dir=None, ref_level=0.0, atten=-1, preamp=0x00, ifagc=0):
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
        self.data_queue = multiprocessing.Queue()
        
        self.process = multiprocessing.Process(target=hardware_process, args=(self.command_queue, self.data_queue, start_freq_hz, stop_freq_hz, probe_only, cal_dir, ref_level, atten, preamp, ifagc, -9.0, 0.01, 0))
        self.process.daemon = True
        self.process.start()
        
        self.queue_reader = DeviceQueueReader(self.data_queue)
        self.queue_reader.spectrum_data_ready.connect(self.spectrum_data_ready)
        self.queue_reader.status_message.connect(self.status_message)
        self.queue_reader.connection_status.connect(self.handle_connection_status)
        self.queue_reader.device_info_received.connect(self.device_info_received)
        self.queue_reader.trace_points_received.connect(self.trace_points_received)
        self.queue_reader.start()
        
        return True

    def handle_connection_status(self, is_connected):
        self.is_connected = is_connected
        self.connection_status.emit(is_connected)
            
    def start(self):
        if self.command_queue:
            self.command_queue.put("start")
            
    def pause(self):
        if self.command_queue:
            self.command_queue.put("pause")
            
    def configure(self, start_freq_hz, stop_freq_hz, ref_level=0.0, atten=0, preamp=0x00, ifagc=0, ifagc_target=-9.0, ifagc_period=0.01, if_out=0):
        if self.command_queue:
            self.command_queue.put(("config", (start_freq_hz, stop_freq_hz, ref_level, atten, preamp, ifagc, ifagc_target, ifagc_period, if_out)))
            
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
