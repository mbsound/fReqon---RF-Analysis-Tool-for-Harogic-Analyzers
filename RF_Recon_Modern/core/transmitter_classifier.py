"""
transmitter_classifier.py - Automatic Transmitter Signature Classification & RF Fingerprinting Engine
Analyzes physical layer occupied bandwidth, spectral shape factors, subcarriers/pilot tones,
and modulation features to identify unknown RF carriers (Shure Axient Digital, ADPSM modes,
Sennheiser Spectera WMAS, PSM1000, D6000, Wisycom, Sony DWX, Lectrosonics, DTV, etc.).
"""

import numpy as np

class TransmitterClassifier:
    """
    Intelligent RF Fingerprinting Classifier that analyzes physical spectrum slices
    to identify transmitter make, model, and transmission mode.
    """

    @staticmethod
    def classify_peak(freq_mhz_array, power_dbm_array, peak_freq_mhz, peak_power_dbm, region="North America"):
        """
        Classifies an RF peak into a known entertainment transmitter signature.
        Returns a dict: {
            "device": str,
            "category": str,
            "confidence": int (0-100),
            "obw_3db_khz": float,
            "obw_20db_khz": float,
            "shape_factor": float,
            "is_digital": bool,
            "color": str,
            "details": str
        }
        """
        if len(freq_mhz_array) < 10 or len(power_dbm_array) < 10:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        freqs = np.asarray(freq_mhz_array)
        powers = np.asarray(power_dbm_array)

        # Check dynamic range: must be an actual signal rising above noise
        valid_powers = powers[np.isfinite(powers)]
        if len(valid_powers) == 0:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)
            
        p_min = float(np.min(valid_powers))
        p_max = float(np.max(valid_powers))
        if p_max - p_min < 5.0 or peak_power_dbm < -95.0:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        # Slice a window around the peak
        # For wideband WMAS / DTV check, slice +/- 5.0 MHz; for narrowband, focus locally
        window_mask = (freqs >= peak_freq_mhz - 5.5) & (freqs <= peak_freq_mhz + 5.5)
        if not np.any(window_mask):
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        f_win = freqs[window_mask]
        p_win = powers[window_mask]

        # 1. Check for Wideband 6.0 MHz (US) or 8.0 MHz (EU) Channels: Sennheiser Spectera vs Broadcast DTV
        wide_result = TransmitterClassifier._check_wideband_wmas_or_dtv(f_win, p_win, peak_freq_mhz, peak_power_dbm, region)
        if wide_result:
            return wide_result

        # Narrowband slice: +/- 1.2 MHz around peak
        nb_mask = (f_win >= peak_freq_mhz - 1.2) & (f_win <= peak_freq_mhz + 1.2)
        f_nb = f_win[nb_mask]
        p_nb = p_win[nb_mask]

        if len(f_nb) < 5:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        # 2. Extract Key Physical Metrics (OBW -3dB, -10dB, -20dB, Shape Factor)
        metrics = TransmitterClassifier._extract_rf_metrics(f_nb, p_nb, peak_freq_mhz, peak_power_dbm)
        obw_3db = metrics["obw_3db_khz"]
        obw_20db = metrics["obw_20db_khz"]
        sf = metrics["shape_factor"]
        is_digital = sf < 1.85 # Steep digital roll-off vs gradual analog FM bell

        # 3. Detect Ultrasonic Pilot Tones & Subcarrier Peaks
        pilot_info = TransmitterClassifier._detect_subcarriers(f_nb, p_nb, peak_freq_mhz, peak_power_dbm)

        # 4. Multi-Dimensional Pattern Match Matrix
        return TransmitterClassifier._match_signature(
            peak_freq_mhz, peak_power_dbm, metrics, is_digital, pilot_info, region
        )

    @staticmethod
    def _extract_rf_metrics(freqs, powers, peak_f, peak_p):
        """
        Calculates -3 dB, -10 dB, -20 dB Occupied Bandwidths, Shape Factor,
        Spectral Flatness Measure (SFM), and Crest Factor (PAPR).
        """
        # Find points exceeding thresholds
        m3_mask = powers >= (peak_p - 3.0)
        m10_mask = powers >= (peak_p - 10.0)
        m20_mask = powers >= (peak_p - 20.0)

        obw_3db_khz = (freqs[m3_mask][-1] - freqs[m3_mask][0]) * 1000.0 if np.any(m3_mask) else 50.0
        obw_10db_khz = (freqs[m10_mask][-1] - freqs[m10_mask][0]) * 1000.0 if np.any(m10_mask) else 100.0
        obw_20db_khz = (freqs[m20_mask][-1] - freqs[m20_mask][0]) * 1000.0 if np.any(m20_mask) else 200.0

        # Prevent div zero
        obw_3db_khz = max(30.0, obw_3db_khz)
        shape_factor = obw_20db_khz / obw_3db_khz

        # Convert passband power from dBm to linear Watts for statistical analysis
        lin_powers = 10.0 ** (powers[m10_mask] / 10.0) if np.any(m10_mask) else np.array([1.0])
        
        # Crest Factor / PAPR (Peak-to-Average Power Ratio in dB)
        p_peak = np.max(lin_powers)
        p_avg = np.mean(lin_powers)
        papr_db = 10.0 * np.log10(max(1e-12, p_peak / max(1e-12, p_avg)))

        # Spectral Flatness Measure (SFM = Geometric Mean / Arithmetic Mean)
        # SFM near 1.0 indicates flat multi-carrier OFDM; lower indicates single-carrier or analog peak
        log_mean = np.mean(np.log(np.maximum(1e-12, lin_powers)))
        geo_mean = np.exp(log_mean)
        arith_mean = np.maximum(1e-12, np.mean(lin_powers))
        sfm = float(geo_mean / arith_mean)

        return {
            "obw_3db_khz": obw_3db_khz,
            "obw_10db_khz": obw_10db_khz,
            "obw_20db_khz": obw_20db_khz,
            "shape_factor": shape_factor,
            "papr_db": papr_db,
            "sfm": sfm
        }

    @staticmethod
    def _detect_subcarriers(freqs, powers, peak_f, peak_p):
        """
        Scans for prominent localized pilot tone spikes (19 kHz stereo, 32.0 kHz Shure, 32.768 kHz Sennheiser).
        """
        df_khz = (freqs - peak_f) * 1000.0
        
        def has_localized_spike(target_khz, tol_khz=2.5, prom_db=2.5):
            idx_target = np.where(np.abs(df_khz - target_khz) <= tol_khz)[0]
            if len(idx_target) == 0:
                return False
            
            p_target = np.max(powers[idx_target])
            # Check surrounding baseline at target +/- (4 to 10 kHz)
            idx_low = np.where((df_khz >= target_khz - 10.0) & (df_khz <= target_khz - 4.0))[0]
            idx_high = np.where((df_khz >= target_khz + 4.0) & (df_khz <= target_khz + 10.0))[0]
            
            if len(idx_low) > 0 and len(idx_high) > 0:
                baseline = (np.mean(powers[idx_low]) + np.mean(powers[idx_high])) / 2.0
                if p_target >= baseline + prom_db and p_target >= peak_p - 25.0:
                    return True
            return False

        has_19k = has_localized_spike(19.0) or has_localized_spike(-19.0)
        has_32k = has_localized_spike(32.0) or has_localized_spike(-32.0)
        has_32768k = has_localized_spike(32.768) or has_localized_spike(-32.768)

        return {
            "has_stereo_iem_19k": has_19k,
            "has_shure_32k": has_32k,
            "has_senn_32768k": has_32768k
        }

    @staticmethod
    def _check_wideband_wmas_or_dtv(freqs, powers, peak_f, peak_p, region):
        """
        Differentiates Sennheiser Spectera (WMAS Wideband) from Broadcast DTV.
        ATSC 1.0 DTV has a sharp pilot carrier at (Lower Edge + 309.44 kHz).
        Sennheiser Spectera lacks this ATSC pilot tone.
        """
        # Look for wideband pedestal across +/- 15 dB from peak
        valid_p = powers[np.isfinite(powers)]
        if len(valid_p) < 10 or (np.max(valid_p) - np.min(valid_p) < 6.0):
            return None

        m15_mask = powers >= (peak_p - 15.0)
        if not np.any(m15_mask):
            return None

        span_mhz = freqs[m15_mask][-1] - freqs[m15_mask][0]
        
        # Check if energy spans a full 4.2 MHz - 8.5 MHz channel block
        if span_mhz >= 4.2:
            lower_edge_f = freqs[m15_mask][0]
            
            # Look for ATSC 1.0 Pilot Tone (+309.44 kHz from lower edge)
            atsc_pilot_target = lower_edge_f + 0.30944
            pilot_window = (freqs >= atsc_pilot_target - 0.05) & (freqs <= atsc_pilot_target + 0.05)
            
            has_atsc_pilot = False
            if np.any(pilot_window):
                pilot_peak = np.max(powers[pilot_window])
                # In ATSC, pilot rises prominently above average channel flat top (around + 600 kHz to + 2 MHz)
                surround_window = (freqs >= atsc_pilot_target + 0.15) & (freqs <= atsc_pilot_target + 1.5)
                if np.any(surround_window):
                    surround_avg = np.mean(powers[surround_window])
                    if pilot_peak > surround_avg + 4.0:
                        has_atsc_pilot = True

            if has_atsc_pilot:
                return {
                    "device": "Broadcast DTV (ATSC 1.0 Pilot)",
                    "category": "Television Broadcast",
                    "confidence": 95,
                    "obw_3db_khz": span_mhz * 1000.0,
                    "obw_20db_khz": (span_mhz + 0.6) * 1000.0,
                    "shape_factor": 1.15,
                    "is_digital": True,
                    "color": "#e53935",
                    "details": f"ATSC 1.0 Pilot detected at {atsc_pilot_target:.3f} MHz (+309.4 kHz)"
                }
            else:
                # Flat 6/8 MHz block lacking ATSC pilot carrier -> Sennheiser Spectera WMAS
                return {
                    "device": "Sennheiser Spectera (WMAS Wideband)",
                    "category": "Wideband Multi-Channel Intercom / Mic",
                    "confidence": 92,
                    "obw_3db_khz": span_mhz * 1000.0,
                    "obw_20db_khz": (span_mhz + 0.4) * 1000.0,
                    "shape_factor": 1.10,
                    "is_digital": True,
                    "color": "#00e676",
                    "details": "Broadband flat OFDM block (6/8 MHz) without ATSC pilot"
                }

        # Check for Shure ADPSM Multi-Channel Wideband (0.8 MHz - 2.5 MHz)
        if 0.8 <= span_mhz < 4.2:
            return {
                "device": "Shure ADPSM (Wideband WMAS Mode)",
                "category": "Digital Multi-Channel IEM",
                "confidence": 90,
                "obw_3db_khz": span_mhz * 1000.0,
                "obw_20db_khz": (span_mhz + 0.3) * 1000.0,
                "shape_factor": 1.25,
                "is_digital": True,
                "color": "#9c27b0",
                "details": f"Wideband Digital Multi-Channel IEM ({span_mhz:.2f} MHz BW)"
            }

        return None

    @staticmethod
    def _match_signature(peak_f, peak_p, metrics, is_digital, pilot_info, region):
        """
        Matches narrowband RF metrics to specific manufacturer transmitter models.
        """
        obw = metrics["obw_3db_khz"]
        sf = metrics["shape_factor"]
        sfm = metrics.get("sfm", 0.5)
        papr_db = metrics.get("papr_db", 3.0)

        # ----------------------------------------------------
        # 1. DIGITAL TRANSMITTER CLASSIFICATION
        # ----------------------------------------------------
        if is_digital:
            # A. Shure Axient Digital (High Density Mode: ~125 - 166 kHz)
            if 100.0 <= obw <= 170.0 and sf <= 1.60:
                return {
                    "device": "Shure Axient Digital (High Density)",
                    "category": "Digital Wireless Mic",
                    "confidence": 96,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": metrics["obw_20db_khz"],
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#00bcd4",
                    "details": f"High-Density digital pedestal (~135 kHz | SFM: {sfm:.2f})"
                }

            # B. Shure ADPSM Single Carrier (SC) Narrowband (~180 - 265 kHz)
            if 170.0 <= obw <= 265.0 and sf <= 1.65 and not pilot_info["has_senn_32768k"]:
                conf = 94 if sfm < 0.75 else 88
                return {
                    "device": "Shure ADPSM (SC Narrowband)",
                    "category": "Digital IEM / Single Carrier",
                    "confidence": conf,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": metrics["obw_20db_khz"],
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#ba68c8",
                    "details": f"Single-Carrier Digital IEM mode (200 kHz | PAPR: {papr_db:.1f} dB)"
                }

            # C. Shure ADPSM Standard Digital Narrowband (~265 - 330 kHz)
            if 265.0 < obw <= 330.0 and sf <= 1.60:
                conf = 96 if sfm >= 0.70 else 92
                return {
                    "device": "Shure ADPSM (Narrowband Digital)",
                    "category": "Digital In-Ear Monitor",
                    "confidence": conf,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": metrics["obw_20db_khz"],
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#ab47bc",
                    "details": f"Axient Digital PSM Spatial Diversity OFDM (~300 kHz | SFM: {sfm:.2f})"
                }

            # D. Shure Axient Digital (Standard Mode: ~350 kHz)
            if 330.0 < obw <= 385.0 and sf <= 1.55:
                return {
                    "device": "Shure Axient Digital (Standard)",
                    "category": "Digital Wireless Mic",
                    "confidence": 95,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": metrics["obw_20db_khz"],
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#0288d1",
                    "details": f"Standard Axient Digital QAM profile (~350 kHz | SFM: {sfm:.2f})"
                }

            # E. Sennheiser Digital 6000 / 9000 (~385 - 460 kHz)
            if 385.0 < obw <= 480.0 and sf <= 1.50:
                return {
                    "device": "Sennheiser Digital 6000/9000",
                    "category": "Digital Wireless Mic",
                    "confidence": 93,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": metrics["obw_20db_khz"],
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#fbc02d",
                    "details": "Equidistant Intermod-Free digital plateau (~400 kHz)"
                }

            # F. Sony DWX Digital (~360 - 410 kHz)
            if 355.0 <= obw <= 420.0:
                return {
                    "device": "Sony DWX Digital",
                    "category": "Digital Wireless Mic",
                    "confidence": 85,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": metrics["obw_20db_khz"],
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#26a69a",
                    "details": "Sony DWX digital modulation envelope"
                }

        # ----------------------------------------------------
        # 2. ANALOG FM & HYBRID CLASSIFICATION
        # ----------------------------------------------------
        # A. Shure PSM 1000 / Analog Stereo IEM (19 kHz pilot / 38 kHz L-R subcarrier)
        if pilot_info["has_stereo_iem_19k"] or (180.0 <= obw <= 280.0 and sf >= 2.1):
            return {
                "device": "Shure PSM 1000 (Stereo IEM)",
                "category": "Analog FM Stereo In-Ear",
                "confidence": 94 if pilot_info["has_stereo_iem_19k"] else 86,
                "obw_3db_khz": obw,
                "obw_20db_khz": metrics["obw_20db_khz"],
                "shape_factor": sf,
                "is_digital": False,
                "color": "#ff9800",
                "details": "Stereo multiplex subcarriers (19 kHz pilot / 38 kHz L-R)"
            }

        # B. Sennheiser G3 / G4 (32.768 kHz Tone Squelch)
        if pilot_info["has_senn_32768k"]:
            return {
                "device": "Sennheiser G3/G4 (Analog FM)",
                "category": "Analog Wireless Mic / IEM",
                "confidence": 96,
                "obw_3db_khz": obw,
                "obw_20db_khz": metrics["obw_20db_khz"],
                "shape_factor": sf,
                "is_digital": False,
                "color": "#4caf50",
                "details": "32.768 kHz ultrasonic pilot tone detected"
            }

        # C. Shure UHF-R / ULX-D Analog Pilot (32.000 kHz Tone)
        if pilot_info["has_shure_32k"]:
            return {
                "device": "Shure UHF-R / ULX (Analog FM)",
                "category": "Analog Wireless Mic",
                "confidence": 93,
                "obw_3db_khz": obw,
                "obw_20db_khz": metrics["obw_20db_khz"],
                "shape_factor": sf,
                "is_digital": False,
                "color": "#03a9f4",
                "details": "32.000 kHz tone squelch detected"
            }

        # D. Wisycom MTK952 / MTK982 (Wideband Interleaved Stereo)
        if obw >= 280.0 and sf >= 2.4:
            return {
                "device": "Wisycom MTK (Interleaved FM)",
                "category": "Wideband FM Stereo Transmitter",
                "confidence": 88,
                "obw_3db_khz": obw,
                "obw_20db_khz": metrics["obw_20db_khz"],
                "shape_factor": sf,
                "is_digital": False,
                "color": "#e91e63",
                "details": "Wide dynamic FM deviation with stereo subcarrier"
            }

        # E. Wisycom MTP60 (Narrowband Mode: ~80 - 130 kHz)
        if obw <= 140.0 and sf >= 1.9:
            return {
                "device": "Wisycom MTP (Narrowband FM)",
                "category": "Analog Narrowband Wireless Mic",
                "confidence": 90,
                "obw_3db_khz": obw,
                "obw_20db_khz": metrics["obw_20db_khz"],
                "shape_factor": sf,
                "is_digital": False,
                "color": "#ff5722",
                "details": "Ultra-narrowband FM profile (~100 kHz)"
            }

        # F. Lectrosonics Digital Hybrid (Companded FM envelope)
        if 160.0 <= obw <= 240.0:
            return {
                "device": "Lectrosonics Digital Hybrid",
                "category": "Hybrid Digital/FM Wireless",
                "confidence": 84,
                "obw_3db_khz": obw,
                "obw_20db_khz": metrics["obw_20db_khz"],
                "shape_factor": sf,
                "is_digital": False,
                "color": "#795548",
                "details": "Companded hybrid envelope (~200 kHz)"
            }

        # Generic Fallback
        return {
            "device": "Generic Digital Wireless" if is_digital else "Generic Analog FM Wireless",
            "category": "Unknown Transmitter",
            "confidence": 70,
            "obw_3db_khz": obw,
            "obw_20db_khz": metrics["obw_20db_khz"],
            "shape_factor": sf,
            "is_digital": is_digital,
            "color": "#9e9e9e",
            "details": f"OBW: {obw:.0f} kHz, Shape Factor: {sf:.2f}"
        }

    @staticmethod
    def _unknown_result(peak_f, peak_p):
        return {
            "device": "Unknown Carrier",
            "category": "RF Peak",
            "confidence": 50,
            "obw_3db_khz": 0.0,
            "obw_20db_khz": 0.0,
            "shape_factor": 1.0,
            "is_digital": False,
            "color": "#888888",
            "details": "Insufficient spectral resolution"
        }
