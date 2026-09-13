"""
multi_device_manager.py - Coordinated Multi-Analyzer Subsystem for Freqon.

Supports 3 operational topologies:
1. Scenario 1 (Split Sweep / Span Stitching): Automatically partitions wide spans (e.g. 1M-1G) across 2+ analyzers on the same antenna, doubling sweep frame rate (2x speed).
2. Scenario 2 (Antenna Diversity & Comparative Analysis): Broadcasts identical spans to co-located analyzers on different antennas, providing A/B instant toggle, Dual Trace Overlay (Trace A + Trace B), and Real-Time Delta (A - B).
3. Scenario 3 (Multi-Zone Independent Roles): Analyzers run with isolated frequencies and parameters in different zones/missions, routing data directly to bound analysis modules (UHF/DTV vs DECT/ShowLink).
"""

import time
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from .device_controller import DeviceController

class MultiDeviceTopology:
    SINGLE = "single"
    SPLIT_SWEEP = "split"
    DIVERSITY = "diversity"
    INDEPENDENT = "independent"


class DeviceSlot:
    """
    Encapsulates state and hardware controller for a single physical analyzer slot.
    """
    def __init__(self, slot_id: str, default_name: str, default_alias: str = ""):
        self.slot_id = slot_id
        self.name = default_name
        self.role_alias = default_alias  # Empty on launch until declared by user
        self.interface_type = "usb"  # "usb" or "network"
        self.ip_address = "192.168.1.50" if slot_id == "slot_a" else "192.168.1.51"
        self.port = 5000
        self.usb_index = 0 if slot_id == "slot_a" else 1
        self.target_model = None
        self.target_uid = None
        self.is_enabled = True if slot_id == "slot_a" else False
        self.is_connected = False
        self.is_sweeping = False
        self.detected_model = None
        self.detected_uid = None
        
        # RF Parameters
        self.start_freq_hz = 470e6
        self.stop_freq_hz = 608e6
        self.ref_level = 0.0
        self.atten = 0
        self.preamp = 0x00
        self.ifagc = 1
        self.rbw_mode = 0
        self.rbw_hz = 30000.0
        self.vbw_mode = 0
        self.vbw_hz = 30000.0
        
        # Data Buffers
        self.last_freq = None
        self.last_power = None
        self.last_update_time = 0.0
        self.status_message = "Disconnected"
        
        # Controller
        self.controller = DeviceController()


class MultiDeviceManager(QObject):
    """
    Orchestrates multiple spectrum analyzer hardware controllers, synchronization,
    sweep aggregation, and multi-topology data routing.
    """
    # Signals
    composite_sweep_ready = pyqtSignal(np.ndarray, np.ndarray)  # freq, power (stitched or primary)
    diversity_sweep_ready = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray)  # freq, power_a, power_b, delta
    device_sweep_ready = pyqtSignal(str, np.ndarray, np.ndarray)  # slot_id, freq, power
    rta_data_ready = pyqtSignal(str, np.ndarray, np.ndarray, np.ndarray, dict) # slot_id, freq, trace, bitmap, info
    det_data_ready = pyqtSignal(str, np.ndarray, np.ndarray, dict) # slot_id, time_ns, power, info
    iqs_data_ready = pyqtSignal(str, np.ndarray, float, dict) # slot_id, iq_complex, sample_rate, info
    mscan_data_ready = pyqtSignal(str, int, float, float, object, dict) # slot_id, channel_idx, freq_hz, power_dbm, spec_data, info
    temperature_updated = pyqtSignal(str, float) # slot_id, temp_c
    slot_status_changed = pyqtSignal(str, bool, str)  # slot_id, is_connected, status_msg
    slot_info_received = pyqtSignal(str, int, object)  # slot_id, model, uid
    all_connection_status = pyqtSignal(bool)  # True if at least one active slot is connected
    topology_changed = pyqtSignal(str)  # new_topology
    focus_changed = pyqtSignal(str)  # active_focused_slot_id
    status_message = pyqtSignal(str)
    amplitude_clamped = pyqtSignal(str, float, int)  # slot_id, ref_level, atten
    bandwidth_updated = pyqtSignal(str, float, float)  # slot_id, rbw_hz, vbw_hz
    hw_endorsements = pyqtSignal(str, dict)  # slot_id, endorsements

    def __init__(self, parent=None):
        super().__init__(parent)
        self.topology = MultiDeviceTopology.SINGLE
        self.focused_slot_id = "slot_a"
        self.diversity_view_mode = "both"  # "slot_a", "slot_b", "both", "delta"
        
        # Global Virtual Sweep Range (for Single / Split / Diversity)
        self.global_start_hz = 470e6
        self.global_stop_hz = 608e6
        self.global_ref_level = 0.0
        self.global_atten = 0
        self.global_preamp = 0x00
        self.global_ifagc = 1
        self.global_rbw_mode = 0
        self.global_rbw_hz = 30000.0
        self.global_vbw_mode = 0
        self.global_vbw_hz = 30000.0
        
        # Initialize standard slots (empty role alias by default)
        self.slots = {
            "slot_a": DeviceSlot("slot_a", "Analyzer A", ""),
            "slot_b": DeviceSlot("slot_b", "Analyzer B", "")
        }
        
        # Connect slot controllers
        for slot_id, slot in self.slots.items():
            self._bind_slot_controller(slot_id, slot)

    def _bind_slot_controller(self, slot_id: str, slot: DeviceSlot):
        c = slot.controller
        c.spectrum_data_ready.connect(lambda f, p, s=slot_id: self._on_slot_sweep_data(s, f, p))
        c.rta_data_ready.connect(lambda f, t, b, inf, s=slot_id: self.rta_data_ready.emit(s, f, t, b, inf))
        c.det_data_ready.connect(lambda t_ns, p, inf, s=slot_id: self.det_data_ready.emit(s, t_ns, p, inf))
        c.iqs_data_ready.connect(lambda iq, sr, inf, s=slot_id: self.iqs_data_ready.emit(s, iq, sr, inf))
        c.mscan_data_ready.connect(lambda idx, f, p, s, inf, s_id=slot_id: self.mscan_data_ready.emit(s_id, idx, f, p, s, inf))
        c.temperature_updated.connect(lambda temp, s=slot_id: self.temperature_updated.emit(s, temp))
        c.status_message.connect(lambda msg, s=slot_id: self._on_slot_status(s, msg))
        c.connection_status.connect(lambda conn, s=slot_id: self._on_slot_connection(s, conn))
        c.device_info_received.connect(lambda m, u, s=slot_id: self._on_slot_info(s, m, u))
        c.amplitude_clamped.connect(lambda ref, att, s=slot_id: self._on_slot_amplitude_clamped(s, ref, att))
        c.bandwidth_updated.connect(lambda r, v, s=slot_id: self.bandwidth_updated.emit(s, r, v))
        c.hw_endorsements.connect(lambda data, s=slot_id: self.hw_endorsements.emit(s, data))

    def configure_rta(self, center_freq_hz: float, decimate_factor: int = 1, ref_level: float = 0.0, trig_src: int = 2, trig_mode: int = 0, trig_time: float = 0.05, preamp: int = 0x00, atten: int = 0):
        slot = self.slots.get(self.focused_slot_id) or self.slots.get("slot_a")
        if slot and slot.is_connected:
            slot.controller.configure_rta(center_freq_hz, decimate_factor, ref_level, trig_src, trig_mode, trig_time, preamp, atten)

    def configure_det(self, center_freq_hz: float, decimate_factor: int = 2, ref_level: float = 0.0, trig_src: int = 2, trig_mode: int = 0, trig_length: int = 16240):
        slot = self.slots.get(self.focused_slot_id) or self.slots.get("slot_a")
        if slot and slot.is_connected:
            slot.controller.configure_det(center_freq_hz, decimate_factor, ref_level, trig_src, trig_mode, trig_length)

    def configure_iqs(self, center_freq_hz: float, decimate_factor: int = 64, ref_level: float = 0.0, trig_src: int = 2, trig_length: int = 16384, preamp: int = 0, atten: int = 0):
        slot = self.slots.get(self.focused_slot_id) or self.slots.get("slot_a")
        if slot and slot.is_connected:
            slot.controller.configure_iqs(center_freq_hz, decimate_factor, ref_level, trig_src, trig_length, preamp, atten)

    def configure_mscan(self, channels: list, dwell_time: float = 0.001, detector: int = 1, ref_level: float = 0.0, preamp: int = 0, atten: int = 0, decimate: int = 256):
        slot = self.slots.get(self.focused_slot_id) or self.slots.get("slot_a")
        if slot and slot.is_connected:
            slot.controller.configure_mscan(channels, dwell_time, detector, ref_level, preamp, atten, decimate)

    def set_operating_mode(self, mode_str: str, params: dict = None):
        slot = self.slots.get(self.focused_slot_id) or self.slots.get("slot_a")
        if slot and slot.is_connected:
            slot.controller.set_operating_mode(mode_str, params)

    # --- Topology Management ---
    def set_topology(self, topology: str):
        if topology in (MultiDeviceTopology.SINGLE, MultiDeviceTopology.SPLIT_SWEEP, 
                        MultiDeviceTopology.DIVERSITY, MultiDeviceTopology.INDEPENDENT):
            self.topology = topology
            self._recalculate_frequency_plans()
            self.topology_changed.emit(self.topology)

    def set_focused_slot(self, slot_id: str):
        if slot_id in self.slots:
            self.focused_slot_id = slot_id
            self.focus_changed.emit(slot_id)

    def set_diversity_view_mode(self, mode: str):
        # "slot_a", "slot_b", "both", "delta"
        self.diversity_view_mode = mode

    # --- Connection Operations ---
    def connect_all_enabled(self):
        """
        Initiates connection for all enabled slots according to active topology.
        """
        self._recalculate_frequency_plans()
        any_started = False
        for slot_id, slot in self.slots.items():
            if slot.is_enabled or self.topology != MultiDeviceTopology.SINGLE:
                self._connect_slot(slot_id)
                any_started = True
            elif self.topology == MultiDeviceTopology.SINGLE and slot_id == "slot_a":
                slot.is_enabled = True
                self._connect_slot(slot_id)
                any_started = True
        return any_started

    def _connect_slot(self, slot_id: str):
        slot = self.slots.get(slot_id)
        if not slot: return
        
        slot.controller.connect_device(
            start_freq_hz=slot.start_freq_hz,
            stop_freq_hz=slot.stop_freq_hz,
            ref_level=slot.ref_level,
            atten=slot.atten,
            preamp=slot.preamp,
            ifagc=slot.ifagc,
            interface_type=slot.interface_type,
            ip_address=slot.ip_address,
            port=slot.port,
            target_model=slot.target_model,
            target_uid=slot.target_uid,
            usb_index=slot.usb_index
        )

    def disconnect_slot(self, slot_id: str):
        slot = self.slots.get(slot_id)
        if slot:
            slot.controller.disconnect_device()
            slot.is_connected = False
            slot.is_sweeping = False
            self.slot_status_changed.emit(slot_id, False, "Disconnected")
            self._update_all_connection_state()

    def disconnect_all(self):
        for slot in self.slots.values():
            slot.controller.disconnect_device()
            slot.is_connected = False
            slot.is_sweeping = False
        self._update_all_connection_state()
        self.status_message.emit("All analyzers disconnected.")

    def start_sweeping_all(self):
        for slot in self.slots.values():
            if slot.is_connected:
                slot.controller.start()
                slot.is_sweeping = True

    def pause_sweeping_all(self):
        for slot in self.slots.values():
            if slot.is_connected:
                slot.controller.pause()
                slot.is_sweeping = False

    def stop_sweeping_all(self):
        for slot in self.slots.values():
            if slot.is_connected:
                slot.controller.stop()
                slot.is_sweeping = False

    # --- Parameter Dispatches ---
    def set_global_sweep_range(self, start_hz: float, stop_hz: float):
        self.global_start_hz = float(start_hz)
        self.global_stop_hz = float(stop_hz)
        self._recalculate_frequency_plans()

    def set_slot_sweep_range(self, slot_id: str, start_hz: float, stop_hz: float):
        slot = self.slots.get(slot_id)
        if slot:
            slot.start_freq_hz = float(start_hz)
            slot.stop_freq_hz = float(stop_hz)
            if slot.is_connected:
                slot.controller.configure(
                    slot.start_freq_hz, slot.stop_freq_hz,
                    slot.ref_level, slot.atten, slot.preamp, slot.ifagc
                )

    def set_amplitude_params(self, ref_level: float, atten: int, preamp: int, ifagc: int, 
                             ifagc_target=-9.0, ifagc_period=0.01, if_out=0, target_slot_id: str = None):
        if target_slot_id and target_slot_id in self.slots:
            # Dispatch to specific slot in Independent mode
            slot = self.slots[target_slot_id]
            slot.ref_level = ref_level
            slot.atten = atten
            slot.preamp = preamp
            slot.ifagc = ifagc
            if slot.is_connected:
                slot.controller.configure(
                    slot.start_freq_hz, slot.stop_freq_hz,
                    ref_level, atten, preamp, ifagc, ifagc_target, ifagc_period, if_out
                )
        else:
            # Dispatch globally
            self.global_ref_level = ref_level
            self.global_atten = atten
            self.global_preamp = preamp
            self.global_ifagc = ifagc
            for slot in self.slots.values():
                slot.ref_level = ref_level
                slot.atten = atten
                slot.preamp = preamp
                slot.ifagc = ifagc
                if slot.is_connected:
                    slot.controller.configure(
                        slot.start_freq_hz, slot.stop_freq_hz,
                        ref_level, atten, preamp, ifagc, ifagc_target, ifagc_period, if_out
                    )

    def set_bandwidth_params(self, rbw_mode, rbw_hz, vbw_mode, vbw_hz, target_slot_id: str = None):
        if target_slot_id and target_slot_id in self.slots:
            slot = self.slots[target_slot_id]
            slot.rbw_mode = rbw_mode
            slot.rbw_hz = rbw_hz
            slot.vbw_mode = vbw_mode
            slot.vbw_hz = vbw_hz
            if slot.is_connected:
                slot.controller.update_bandwidth(rbw_mode, rbw_hz, vbw_mode, vbw_hz)
        else:
            self.global_rbw_mode = rbw_mode
            self.global_rbw_hz = rbw_hz
            self.global_vbw_mode = vbw_mode
            self.global_vbw_hz = vbw_hz
            for slot in self.slots.values():
                slot.rbw_mode = rbw_mode
                slot.rbw_hz = rbw_hz
                slot.vbw_mode = vbw_mode
                slot.vbw_hz = vbw_hz
                if slot.is_connected:
                    slot.controller.update_bandwidth(rbw_mode, rbw_hz, vbw_mode, vbw_hz)

    def set_sweep_params(self, swt_mode, swt_time, spur=0, window=0, target_slot_id: str = None):
        if target_slot_id and target_slot_id in self.slots:
            slot = self.slots[target_slot_id]
            if slot.is_connected:
                slot.controller.configure_sweep(swt_mode, swt_time, 0, spur, window)
        else:
            for slot in self.slots.values():
                if slot.is_connected:
                    slot.controller.configure_sweep(swt_mode, swt_time, 0, spur, window)

    def set_detect_params(self, detector, trace_detector, target_slot_id: str = None):
        if target_slot_id and target_slot_id in self.slots:
            slot = self.slots[target_slot_id]
            if slot.is_connected:
                slot.controller.configure_detect(detector, trace_detector)
        else:
            for slot in self.slots.values():
                if slot.is_connected:
                    slot.controller.configure_detect(detector, trace_detector)

    def set_fan_state(self, fan_state: int, threshold_temp: float = 50.0, target_slot_id: str = None):
        if target_slot_id and target_slot_id in self.slots:
            slot = self.slots[target_slot_id]
            if slot.is_connected:
                slot.controller.set_fan_state(fan_state, threshold_temp)
        else:
            for slot in self.slots.values():
                if slot.is_connected:
                    slot.controller.set_fan_state(fan_state, threshold_temp)

    # --- Frequency Plan Calculation ---
    def _recalculate_frequency_plans(self):
        active_slots = [s for s in self.slots.values() if s.is_enabled or self.topology != MultiDeviceTopology.SINGLE]
        
        if self.topology == MultiDeviceTopology.SPLIT_SWEEP and len(active_slots) >= 2:
            # Divide global span evenly across active analyzers
            total_span = self.global_stop_hz - self.global_start_hz
            span_per_dev = total_span / len(active_slots)
            for i, slot in enumerate(active_slots):
                sub_start = self.global_start_hz + i * span_per_dev
                sub_stop = self.global_start_hz + (i + 1) * span_per_dev if i < len(active_slots) - 1 else self.global_stop_hz
                slot.start_freq_hz = sub_start
                slot.stop_freq_hz = sub_stop
                if slot.is_connected:
                    slot.controller.configure(
                        sub_start, sub_stop, slot.ref_level, slot.atten, slot.preamp, slot.ifagc
                    )
        elif self.topology in (MultiDeviceTopology.DIVERSITY, MultiDeviceTopology.SINGLE):
            # Broadcast same global span to both analyzers
            for slot in self.slots.values():
                slot.start_freq_hz = self.global_start_hz
                slot.stop_freq_hz = self.global_stop_hz
                if slot.is_connected:
                    slot.controller.configure(
                        self.global_start_hz, self.global_stop_hz, slot.ref_level, slot.atten, slot.preamp, slot.ifagc
                    )
        elif self.topology == MultiDeviceTopology.INDEPENDENT:
            # Keep independent frequencies intact
            for slot in self.slots.values():
                if slot.is_connected:
                    slot.controller.configure(
                        slot.start_freq_hz, slot.stop_freq_hz, slot.ref_level, slot.atten, slot.preamp, slot.ifagc
                    )

    # --- Data & Status Routing ---
    def _on_slot_status(self, slot_id: str, msg: str):
        slot = self.slots.get(slot_id)
        if slot:
            slot.status_message = msg
        slot_label = (slot.role_alias.strip() or slot.name) if slot else slot_id
        self.status_message.emit(f"[{slot_label}] {msg}")

    def _on_slot_connection(self, slot_id: str, is_connected: bool):
        slot = self.slots.get(slot_id)
        if slot:
            slot.is_connected = is_connected
            self.slot_status_changed.emit(slot_id, is_connected, slot.status_message)
        self._update_all_connection_state()

    def _on_slot_info(self, slot_id: str, model: int, uid: object):
        slot = self.slots.get(slot_id)
        if slot:
            slot.detected_model = model
            slot.detected_uid = uid
        self.slot_info_received.emit(slot_id, model, uid)

    def _on_slot_amplitude_clamped(self, slot_id: str, ref: float, att: int):
        slot = self.slots.get(slot_id)
        if slot:
            slot.ref_level = ref
            if att >= 0:
                slot.atten = att
        self.amplitude_clamped.emit(slot_id, ref, att)

    def _update_all_connection_state(self):
        any_connected = any(s.is_connected for s in self.slots.values())
        self.all_connection_status.emit(any_connected)

    def _on_slot_sweep_data(self, slot_id: str, freq: np.ndarray, power: np.ndarray):
        slot = self.slots.get(slot_id)
        if not slot: return
        
        slot.last_freq = freq
        slot.last_power = power
        slot.last_update_time = time.time()
        
        # Always emit per-device sweep for dedicated module routing
        self.device_sweep_ready.emit(slot_id, freq, power)
        
        # Route according to topology
        if self.topology == MultiDeviceTopology.SINGLE:
            if slot_id == "slot_a" or slot.is_enabled:
                self.composite_sweep_ready.emit(freq, power)
                
        elif self.topology == MultiDeviceTopology.SPLIT_SWEEP:
            self._handle_split_sweep_stitching()
            
        elif self.topology == MultiDeviceTopology.DIVERSITY:
            self._handle_diversity_routing()
            
        elif self.topology == MultiDeviceTopology.INDEPENDENT:
            # Emit focused device sweep to main view
            if slot_id == self.focused_slot_id:
                self.composite_sweep_ready.emit(freq, power)

    def _handle_split_sweep_stitching(self):
        """
        Combines partial sub-band sweeps from Slot A and Slot B into a seamless continuous composite trace.
        """
        slot_a = self.slots.get("slot_a")
        slot_b = self.slots.get("slot_b")
        
        if slot_a and slot_b and slot_a.last_freq is not None and slot_b.last_freq is not None:
            # Check for non-empty traces
            if len(slot_a.last_freq) > 0 and len(slot_b.last_freq) > 0:
                # Merge arrays in frequency order
                if slot_a.last_freq[0] <= slot_b.last_freq[0]:
                    stitched_f = np.concatenate([slot_a.last_freq, slot_b.last_freq])
                    stitched_p = np.concatenate([slot_a.last_power, slot_b.last_power])
                else:
                    stitched_f = np.concatenate([slot_b.last_freq, slot_a.last_freq])
                    stitched_p = np.concatenate([slot_b.last_power, slot_a.last_power])
                self.composite_sweep_ready.emit(stitched_f, stitched_p)
        elif slot_a and slot_a.last_freq is not None:
            self.composite_sweep_ready.emit(slot_a.last_freq, slot_a.last_power)
        elif slot_b and slot_b.last_freq is not None:
            self.composite_sweep_ready.emit(slot_b.last_freq, slot_b.last_power)

    def _handle_diversity_routing(self):
        """
        Synchronizes Antenna A and Antenna B traces and computes the delta trace.
        """
        slot_a = self.slots.get("slot_a")
        slot_b = self.slots.get("slot_b")
        
        if slot_a and slot_b and slot_a.last_freq is not None and slot_b.last_power is not None:
            freq = slot_a.last_freq
            power_a = slot_a.last_power
            power_b = slot_b.last_power
            
            # Match lengths if different trace points
            if len(power_b) != len(power_a):
                power_b_resampled = np.interp(freq, slot_b.last_freq, power_b)
            else:
                power_b_resampled = power_b
                
            delta = power_a - power_b_resampled
            self.diversity_sweep_ready.emit(freq, power_a, power_b_resampled, delta)
            
            # Emit primary composite based on user focus or view mode
            if self.diversity_view_mode == "slot_b":
                self.composite_sweep_ready.emit(freq, power_b_resampled)
            elif self.diversity_view_mode == "delta":
                self.composite_sweep_ready.emit(freq, delta)
            else:
                self.composite_sweep_ready.emit(freq, power_a)
        elif slot_a and slot_a.last_freq is not None:
            self.composite_sweep_ready.emit(slot_a.last_freq, slot_a.last_power)
        elif slot_b and slot_b.last_freq is not None:
            self.composite_sweep_ready.emit(slot_b.last_freq, slot_b.last_power)
