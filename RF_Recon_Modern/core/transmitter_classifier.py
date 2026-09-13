"""
transmitter_classifier.py - Automatic Transmitter Signature Classification & RF Fingerprinting Engine
Analyzes physical layer occupied bandwidth, spectral shape factors, subcarriers/pilot tones,
and modulation features to identify unknown RF carriers:
- Shure PSM 1000 (P10T analog FM stereo IEM with 19 kHz pilot)
- Shure Axient Digital PSM (ADPSM: Narrowband Digital & Multichannel Wideband WMAS)
- Shure Axient Digital (AD1/AD2/ADX: Standard 350 kHz & High Density 135 kHz)
- Sennheiser Digital 6000 / 9000 (Intermod-free 400 kHz digital pedestal)
- Sennheiser Spectera (6/8 MHz Wideband WMAS OFDM block)
- Wisycom MTK952 / MTK982 (Wide dynamic deviation stereo FM)
- Sony UWP-D Series (Digital Processing FM with 32.382 kHz tone squelch)
- Sennheiser evolution wireless G3/G4 (Analog FM with 32.768 kHz tone squelch)
- Shure UHF-R / ULX (Analog FM with 32.000 kHz tone squelch)
- Wisycom MTP (Narrowband FM ~100 kHz)
- Broadcast DTV (ATSC 1.0 pilot tone at Lower Edge + 309.44 kHz)
"""

import numpy as np
from scipy.interpolate import interp1d

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
        if freq_mhz_array is None or power_dbm_array is None:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        if len(freq_mhz_array) < 10 or len(power_dbm_array) < 10:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        freqs = np.asarray(freq_mhz_array, dtype=np.float64)
        powers = np.asarray(power_dbm_array, dtype=np.float64)

        # Ensure freqs are in MHz (if in Hz, convert)
        if len(freqs) > 0 and freqs[0] > 1e5:
            freqs = freqs / 1e6

        # Check dynamic range: must be an actual signal rising above noise
        valid_powers = powers[np.isfinite(powers)]
        if len(valid_powers) == 0:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)
            
        p_min = float(np.min(valid_powers))
        p_max = float(np.max(valid_powers))
        if p_max - p_min < 4.0 or peak_power_dbm < -95.0:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        # ---------------------------------------------------------------------
        # 1. Check for Wideband Channels: Sennheiser Spectera vs Broadcast DTV vs ADPSM Wideband
        # ---------------------------------------------------------------------
        wb_mask = (freqs >= peak_freq_mhz - 5.5) & (freqs <= peak_freq_mhz + 5.5)
        if np.sum(wb_mask) >= 20:
            f_wb = freqs[wb_mask]
            p_wb = powers[wb_mask]
            wide_result = TransmitterClassifier._check_wideband_wmas_or_dtv(
                f_wb, p_wb, peak_freq_mhz, peak_power_dbm, region
            )
            if wide_result is not None:
                return wide_result

        # ---------------------------------------------------------------------
        # 2. Narrowband Slice & Sub-Bin Interpolation (+/- 1.2 MHz around peak)
        # ---------------------------------------------------------------------
        nb_mask = (freqs >= peak_freq_mhz - 1.2) & (freqs <= peak_freq_mhz + 1.2)
        f_nb = freqs[nb_mask]
        p_nb = powers[nb_mask]

        if len(f_nb) < 5:
            return TransmitterClassifier._unknown_result(peak_freq_mhz, peak_power_dbm)

        # Extract continuous physical metrics via 2 kHz spline interpolation
        metrics, f_fine, p_fine = TransmitterClassifier._extract_rf_metrics_interpolated(
            f_nb, p_nb, peak_freq_mhz, peak_power_dbm
        )

        # 3. Detect Ultrasonic Pilot Tones & Subcarrier Peaks
        pilot_info = TransmitterClassifier._detect_subcarriers(
            f_fine, p_fine, peak_freq_mhz, peak_power_dbm
        )

        # 4. Rigorous Digital vs. Analog Decision
        # True digital carriers (Axient Digital, ADPSM, D6000) have:
        # - Steep Nyquist/RRC skirts (shape factor SF_20/3 <= 1.50)
        # - Flat passband top (std of power in central zone <= 1.5 dB)
        # - High Spectral Flatness Measure (SFM >= 0.52)
        # - NO analog pilot tones (no 19k stereo pilot, no 32k/32.768k squelch)
        sf = metrics["shape_factor"]
        sigma_top = metrics.get("sigma_top", 3.0)
        sfm = metrics.get("sfm", 0.3)
        has_analog_pilot = (
            pilot_info["has_stereo_iem_19k"] or
            pilot_info["has_senn_32768k"] or
            pilot_info["has_shure_32k"] or
            pilot_info["has_sony_32382k"]
        )

        is_digital = bool(
            (sf <= 1.50) and
            (sigma_top <= 1.55) and
            (sfm >= 0.52) and
            not has_analog_pilot
        )

        # 5. Multi-Dimensional Pattern Match Matrix
        return TransmitterClassifier._match_signature(
            peak_freq_mhz, peak_power_dbm, metrics, is_digital, pilot_info, region
        )

    @staticmethod
    def _extract_rf_metrics_interpolated(f_slice, p_slice, peak_f, peak_p):
        """
        Interpolates narrowband slice to a fine 2 kHz grid to eliminate
        FFT bin-spacing quantization errors. Computes true continuous OBW,
        shape factor, passband flatness, and PAPR.
        """
        valid = np.isfinite(p_slice)
        f_clean = f_slice[valid]
        p_clean = p_slice[valid]

        if len(f_clean) < 4:
            return {
                "obw_3db_khz": 100.0,
                "obw_6db_khz": 150.0,
                "obw_10db_khz": 180.0,
                "obw_20db_khz": 240.0,
                "shape_factor": 2.4,
                "sigma_top": 3.0,
                "sfm": 0.3,
                "papr_db": 1.0
            }, f_clean, p_clean

        # Estimate local noise floor from outer skirts (|f - peak_f| > 0.6 MHz)
        outer_mask = np.abs(f_clean - peak_f) >= 0.6
        if np.any(outer_mask):
            p_floor = float(np.median(p_clean[outer_mask]))
        else:
            p_floor = float(np.min(p_clean))

        # Uniform 2 kHz fine grid across slice span
        f_span = f_clean[-1] - f_clean[0]
        num_points = max(200, int(f_span / 0.002))
        f_fine = np.linspace(f_clean[0], f_clean[-1], num_points)

        try:
            interp = interp1d(f_clean, p_clean, kind='cubic', fill_value='extrapolate')
            p_fine = interp(f_fine)
        except Exception:
            p_fine = np.interp(f_fine, f_clean, p_clean)

        # Continuous crossing widths
        m3_mask = p_fine >= (peak_p - 3.0)
        m6_mask = p_fine >= (peak_p - 6.0)
        m10_mask = p_fine >= (peak_p - 10.0)

        # Bound -20 dB above local noise floor so floor doesn't inflate bandwidth
        level_20 = max(peak_p - 20.0, p_floor + 2.5)
        m20_mask = p_fine >= level_20

        obw_3db_khz = (f_fine[m3_mask][-1] - f_fine[m3_mask][0]) * 1000.0 if np.any(m3_mask) else 40.0
        obw_6db_khz = (f_fine[m6_mask][-1] - f_fine[m6_mask][0]) * 1000.0 if np.any(m6_mask) else 70.0
        obw_10db_khz = (f_fine[m10_mask][-1] - f_fine[m10_mask][0]) * 1000.0 if np.any(m10_mask) else 120.0
        obw_20db_khz = (f_fine[m20_mask][-1] - f_fine[m20_mask][0]) * 1000.0 if np.any(m20_mask) else 200.0

        # Prevent divide-by-zero
        obw_3db_khz = max(30.0, obw_3db_khz)
        shape_factor = obw_20db_khz / obw_3db_khz

        # Passband Top Curvature: Standard deviation across central 50% of -3 dB region
        half_zone = max(0.015, (obw_3db_khz / 2000.0) * 0.5)
        top_mask = np.abs(f_fine - peak_f) <= half_zone
        if np.sum(top_mask) >= 3:
            sigma_top = float(np.std(p_fine[top_mask]))
        else:
            sigma_top = 2.5

        # Spectral Flatness Measure (SFM) over -10 dB region
        passband_powers = p_fine[m10_mask] if np.any(m10_mask) else p_fine[m3_mask]
        if len(passband_powers) >= 3:
            lin_powers = 10.0 ** (passband_powers / 10.0)
            log_mean = np.mean(np.log(np.maximum(1e-12, lin_powers)))
            geo_mean = np.exp(log_mean)
            arith_mean = np.maximum(1e-12, np.mean(lin_powers))
            sfm = float(geo_mean / arith_mean)

            p_peak = np.max(lin_powers)
            papr_db = 10.0 * np.log10(max(1e-12, p_peak / arith_mean))
        else:
            sfm = 0.3
            papr_db = 1.0

        metrics = {
            "obw_3db_khz": obw_3db_khz,
            "obw_6db_khz": obw_6db_khz,
            "obw_10db_khz": obw_10db_khz,
            "obw_20db_khz": obw_20db_khz,
            "shape_factor": shape_factor,
            "sigma_top": sigma_top,
            "sfm": sfm,
            "papr_db": papr_db,
            "p_floor": p_floor
        }
        return metrics, f_fine, p_fine

    @staticmethod
    def _detect_subcarriers(f_fine, p_fine, peak_f, peak_p):
        """
        Analyzes the fine interpolated spectrum for continuous pilot tones and tone squelch:
        - 19.0 kHz (+/- 3.5 kHz): Analog FM Stereo IEM Pilot Tone (PSM 1000, PSM 900, ew IEM)
        - 32.382 kHz (+/- 3.0 kHz): Sony UWP-D Tone Squelch
        - 32.768 kHz (+/- 3.0 kHz): Sennheiser G3/G4 Tone Squelch
        - 32.000 kHz (+/- 2.5 kHz): Shure UHF-R / ULX Tone Squelch
        """
        if len(f_fine) < 20:
            return {
                "has_stereo_iem_19k": False,
                "has_sony_32382k": False,
                "has_senn_32768k": False,
                "has_shure_32k": False
            }

        df_khz = (f_fine - peak_f) * 1000.0

        def check_subcarrier_energy(target_khz, tol_khz=3.5, delta_khz=9.0, min_prom_db=1.2):
            hits = 0
            for sign in (-1.0, 1.0):
                center = sign * target_khz
                idx_target = np.where(np.abs(df_khz - center) <= tol_khz)[0]
                if len(idx_target) == 0:
                    continue

                best_i = idx_target[np.argmax(p_fine[idx_target])]
                f_p = df_khz[best_i]
                p_p = p_fine[best_i]

                # Symmetric baselines at +/- delta_khz eliminate the carrier's natural slope
                idx_l = np.argmin(np.abs(df_khz - (f_p - delta_khz)))
                idx_r = np.argmin(np.abs(df_khz - (f_p + delta_khz)))
                baseline = 0.5 * (p_fine[idx_l] + p_fine[idx_r])
                prom = p_p - baseline

                if prom >= min_prom_db and p_p >= peak_p - 30.0:
                    hits += 1

            return hits >= 1

        has_19k = check_subcarrier_energy(19.0, tol_khz=3.5, delta_khz=8.0, min_prom_db=0.8)
        has_sony_32k = check_subcarrier_energy(32.382, tol_khz=3.5, delta_khz=9.0, min_prom_db=0.8)
        has_senn_32k = check_subcarrier_energy(32.768, tol_khz=3.0, delta_khz=9.0, min_prom_db=0.8)
        has_shure_32k = check_subcarrier_energy(32.000, tol_khz=2.5, delta_khz=9.0, min_prom_db=0.8)

        return {
            "has_stereo_iem_19k": has_19k,
            "has_sony_32382k": has_sony_32k,
            "has_senn_32768k": has_senn_32k,
            "has_shure_32k": has_shure_32k
        }

    @staticmethod
    def _check_wideband_wmas_or_dtv(freqs, powers, peak_f, peak_p, region):
        """
        Differentiates wideband channels:
        - Broadcast DTV (6/8 MHz with ATSC 1.0 Pilot at Lower Edge + 309.44 kHz)
        - Sennheiser Spectera WMAS (6/8 MHz continuous bidirectional OFDM block)
        - Shure Axient Digital PSM Multichannel Wideband WMAS Mode (500-750 kHz or 1.0-2.5 MHz)
        """
        valid_p = powers[np.isfinite(powers)]
        if len(valid_p) < 15 or (np.max(valid_p) - np.min(valid_p) < 8.0):
            return None

        p_floor = float(np.percentile(valid_p, 20))
        snr = peak_p - p_floor
        if snr < 10.0:
            return None

        block_threshold = max(peak_p - 12.0, p_floor + 6.0)
        in_block = powers >= block_threshold

        if not np.any(in_block):
            return None

        peak_idx = int(np.argmin(np.abs(freqs - peak_f)))
        if not in_block[peak_idx]:
            return None

        left = peak_idx
        while left > 0 and in_block[left - 1]:
            left -= 1

        right = peak_idx
        while right < len(in_block) - 1 and in_block[right + 1]:
            right += 1

        contiguous_span_mhz = freqs[right] - freqs[left]

        # Case 1: Full 4.5 MHz - 8.5 MHz Block -> Broadcast DTV vs Sennheiser Spectera WMAS
        if contiguous_span_mhz >= 4.5:
            lower_edge_f = freqs[left]
            atsc_pilot_target = lower_edge_f + 0.30944
            pilot_window = (freqs >= atsc_pilot_target - 0.05) & (freqs <= atsc_pilot_target + 0.05)
            
            has_atsc_pilot = False
            if np.any(pilot_window):
                pilot_peak = np.max(powers[pilot_window])
                surround_window = (freqs >= atsc_pilot_target + 0.15) & (freqs <= atsc_pilot_target + 1.5)
                if np.any(surround_window):
                    surround_avg = np.mean(powers[surround_window])
                    if pilot_peak > surround_avg + 4.0:
                        has_atsc_pilot = True

            if has_atsc_pilot:
                return {
                    "device": "Broadcast DTV (ATSC 1.0 Pilot)",
                    "category": "Television Broadcast",
                    "confidence": 96,
                    "obw_3db_khz": contiguous_span_mhz * 1000.0,
                    "obw_20db_khz": (contiguous_span_mhz + 0.5) * 1000.0,
                    "shape_factor": 1.12,
                    "is_digital": True,
                    "color": "#e53935",
                    "details": f"ATSC 1.0 Pilot detected at {atsc_pilot_target:.3f} MHz (+309.4 kHz)"
                }
            else:
                return {
                    "device": "Sennheiser Spectera (WMAS Wideband)",
                    "category": "Wideband Multi-Channel Intercom / Mic",
                    "confidence": 95,
                    "obw_3db_khz": contiguous_span_mhz * 1000.0,
                    "obw_20db_khz": (contiguous_span_mhz + 0.4) * 1000.0,
                    "shape_factor": 1.08,
                    "is_digital": True,
                    "color": "#00e676",
                    "details": "Broadband flat OFDM block (6/8 MHz) without ATSC pilot"
                }

        # Case 2: Shure Axient Digital PSM Multichannel Wideband Mode (500 kHz - 2.5 MHz)
        if 0.50 <= contiguous_span_mhz < 4.5:
            block_powers = powers[left:right+1]
            lin_powers = 10.0 ** (block_powers / 10.0)
            log_mean = np.mean(np.log(np.maximum(1e-12, lin_powers)))
            geo_mean = np.exp(log_mean)
            arith_mean = np.maximum(1e-12, np.mean(lin_powers))
            block_sfm = float(geo_mean / arith_mean)

            if block_sfm >= 0.65:
                return {
                    "device": "Shure ADPSM (Wideband WMAS Mode)",
                    "category": "Digital Multi-Channel IEM",
                    "confidence": 94,
                    "obw_3db_khz": contiguous_span_mhz * 1000.0,
                    "obw_20db_khz": (contiguous_span_mhz + 0.15) * 1000.0,
                    "shape_factor": 1.15,
                    "is_digital": True,
                    "color": "#ab47bc",
                    "details": f"Axient Digital PSM Multichannel Wideband ({contiguous_span_mhz*1000.0:.0f} kHz | SFM: {block_sfm:.2f})"
                }

        return None

    @staticmethod
    def _match_signature(peak_f, peak_p, metrics, is_digital, pilot_info, region):
        """
        Precision matching matrix for:
        - Shure PSM 1000 (Analog FM Stereo IEM)
        - Shure Axient Digital PSM (ADPSM: Narrowband Digital Mode)
        - Shure Axient Digital (AD1/AD2 Standard & High Density)
        - Sennheiser Digital 6000 / 9000
        - Wisycom MTK (Interleaved FM Stereo)
        - Sony UWP-D (Digital Audio Processing FM)
        - Sennheiser ew G3/G4 (Analog FM)
        - Shure UHF-R / ULX (Analog FM)
        - Wisycom MTP (Narrowband FM)
        - Lectrosonics Digital Hybrid
        """
        obw = metrics["obw_3db_khz"]
        obw20 = metrics["obw_20db_khz"]
        sf = metrics["shape_factor"]
        sfm = metrics.get("sfm", 0.3)
        papr_db = metrics.get("papr_db", 2.0)

        # ---------------------------------------------------------------------
        # 1. DIGITAL TRANSMITTER CLASSIFICATION
        # ---------------------------------------------------------------------
        if is_digital:
            # A. Shure Axient Digital (High Density Mode: ~120 - 165 kHz digital pedestal)
            if 95.0 <= obw <= 165.0 and sf <= 1.50:
                return {
                    "device": "Shure Axient Digital (High Density)",
                    "category": "Digital Wireless Mic",
                    "confidence": 96,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": obw20,
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#00bcd4",
                    "details": f"High-Density digital pedestal ({obw:.0f} kHz | SF: {sf:.2f})"
                }

            # B. Shure Axient Digital PSM - Narrowband Digital Mode (~165 - 245 kHz)
            # Certified under FCC as 181KG7E (Point-to-Point digital IEM pedestal)
            if 165.0 < obw <= 245.0 and sf <= 1.48:
                return {
                    "device": "Shure ADPSM (Narrowband Digital)",
                    "category": "Digital In-Ear Monitor",
                    "confidence": 95,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": obw20,
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#ba68c8",
                    "details": f"Axient Digital PSM Point-to-Point Digital ({obw:.0f} kHz | SFM: {sfm:.2f})"
                }

            # C. Shure Axient Digital Mic (Standard Mode: ~250 - 365 kHz, 350KD2E emission)
            if 250.0 <= obw <= 365.0 and obw20 < 380.0 and sf <= 1.50:
                return {
                    "device": "Shure Axient Digital (Standard)",
                    "category": "Digital Wireless Mic",
                    "confidence": 96,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": obw20,
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#0288d1",
                    "details": f"Standard Axient Digital QAM profile ({obw:.0f} kHz | SF: {sf:.2f})"
                }

            # D. Sennheiser Digital 6000 / 9000 (~365 - 470 kHz, 400KD2E emission)
            if ((335.0 <= obw <= 470.0 and obw20 >= 380.0) or (365.0 < obw <= 470.0)) and sf <= 1.45:
                return {
                    "device": "Sennheiser Digital 6000/9000",
                    "category": "Digital Wireless Mic",
                    "confidence": 95,
                    "obw_3db_khz": obw,
                    "obw_20db_khz": obw20,
                    "shape_factor": sf,
                    "is_digital": True,
                    "color": "#fbc02d",
                    "details": f"Equidistant Intermod-Free digital plateau ({obw:.0f} kHz | SF: {sf:.2f})"
                }

            # Generic Digital Fallback
            return {
                "device": "Generic Digital Wireless",
                "category": "Digital Transmitter",
                "confidence": 75,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": True,
                "color": "#00acc1",
                "details": f"Digital Pedestal ({obw:.0f} kHz -3dB | SF: {sf:.2f})"
            }

        # ---------------------------------------------------------------------
        # 2. ANALOG FM & HYBRID TRANSMITTER CLASSIFICATION
        # ---------------------------------------------------------------------
        # A. Shure PSM 1000 (P10T Analog FM Stereo IEM)
        is_psm1000 = (
            pilot_info["has_stereo_iem_19k"] or
            (160.0 <= obw20 <= 275.0 and sf >= 1.65 and not pilot_info["has_sony_32382k"])
        )
        if is_psm1000:
            confidence = 96 if pilot_info["has_stereo_iem_19k"] else 90
            pilot_detail = "19 kHz MPX Pilot" if pilot_info["has_stereo_iem_19k"] else "Stereo MPX Envelope"
            return {
                "device": "Shure PSM 1000 (Stereo IEM)",
                "category": "Analog FM Stereo In-Ear",
                "confidence": confidence,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": False,
                "color": "#ff9800",
                "details": f"Analog FM Stereo IEM ({pilot_detail} | {obw20:.0f} kHz Carson BW)"
            }

        # B. Wisycom MTK952 / MTK982 (Wideband Interleaved Stereo FM)
        if obw20 >= 275.0 and sf >= 2.1:
            return {
                "device": "Wisycom MTK (Interleaved FM)",
                "category": "Wideband FM Stereo Transmitter",
                "confidence": 92,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": False,
                "color": "#e91e63",
                "details": f"Wide dynamic FM stereo deviation ({obw20:.0f} kHz BW | SF: {sf:.2f})"
            }

        # C. Sony UWP-D (Digital Processing FM)
        if pilot_info["has_sony_32382k"] or (150.0 <= obw20 <= 215.0 and 1.60 <= sf <= 2.20):
            confidence = 95 if pilot_info["has_sony_32382k"] else 86
            return {
                "device": "Sony UWP-D (Digital Processing FM)",
                "category": "Hybrid DSP / FM Wireless",
                "confidence": confidence,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": False,
                "color": "#00897b",
                "details": "Sony UWP-D Series (DSP companding / 32.382 kHz tone squelch)"
            }

        # D. Sennheiser evolution wireless G3/G4 / 2000 Series (Analog FM)
        if pilot_info["has_senn_32768k"]:
            return {
                "device": "Sennheiser G3/G4 (Analog FM)",
                "category": "Analog Wireless Mic / IEM",
                "confidence": 96,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": False,
                "color": "#4caf50",
                "details": "32.768 kHz ultrasonic pilot tone detected"
            }

        # E. Shure UHF-R / ULX (Analog FM)
        if pilot_info["has_shure_32k"]:
            return {
                "device": "Shure UHF-R / ULX (Analog FM)",
                "category": "Analog Wireless Mic",
                "confidence": 94,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": False,
                "color": "#03a9f4",
                "details": "32.000 kHz tone squelch detected"
            }

        # F. Wisycom MTP60 / MTP40 (Narrowband FM Mode: ~80 - 140 kHz)
        if obw20 <= 145.0 and sf >= 1.75:
            return {
                "device": "Wisycom MTP (Narrowband FM)",
                "category": "Analog Narrowband Wireless Mic",
                "confidence": 91,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": False,
                "color": "#ff5722",
                "details": f"Ultra-narrowband FM profile ({obw20:.0f} kHz BW)"
            }

        # G. Lectrosonics Digital Hybrid Wireless
        if 160.0 <= obw20 <= 235.0:
            return {
                "device": "Lectrosonics Digital Hybrid",
                "category": "Hybrid Digital/FM Wireless",
                "confidence": 85,
                "obw_3db_khz": obw,
                "obw_20db_khz": obw20,
                "shape_factor": sf,
                "is_digital": False,
                "color": "#795548",
                "details": f"Companded hybrid envelope ({obw20:.0f} kHz BW | SF: {sf:.2f})"
            }

        # Generic Analog Fallback
        return {
            "device": "Generic Analog FM Wireless",
            "category": "Analog Transmitter",
            "confidence": 70,
            "obw_3db_khz": obw,
            "obw_20db_khz": obw20,
            "shape_factor": sf,
            "is_digital": False,
            "color": "#9e9e9e",
            "details": f"Analog FM Bell ({obw20:.0f} kHz -20dB | SF: {sf:.2f})"
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
