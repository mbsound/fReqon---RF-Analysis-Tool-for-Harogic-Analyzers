/**
 * \file htra_api_emi.h
 * 
 * \~english \brief API for frequency band pre-scan and frequency point measurement used in EMI functions.
 *
 * \~english During pre-scan, the device acquires the trace of the frequency band in Sweep mode. During frequency point measurement, the device analyzes the power (voltage) of the frequency point in IQS mode.
 * 
 */


#ifndef HTRA_API_EMI_H
#define HTRA_API_EMI_H

#include <stdint.h>
#include "htra_api.h"

/** \~english The EMI license file is missing. Please place the name_emi.lic file (for example: 057_20303232424850110024002e_emi.lic) into the /CalFile/ folder. */
#define APIRETVAL_ERROR_EMILicFileIsMissing -53

/** \~english The EMI license file content is invalid. This is usually caused by modifications to the license file. Please contact technical support. */
#define APIRETVAL_ERROR_EMILicFileIsIncorrect -54

/** \~english The EMI license file has expired. Please contact technical support. */
#define APIRETVAL_ERROR_EMILicFileIsExpired -55

#ifdef __cplusplus
extern "C" {
#endif

#if defined _WIN32 || defined __CYGWIN__
#ifdef HTRA_API_EXPORTS
#define HTRA_API __declspec(dllexport) // Note: actually gcc seems to also supports this syntax.
#else
#define HTRA_API
#endif
#else
#ifdef HTRA_API_EXPORTS
#if __GNUC__ >= 4
#define HTRA_API __attribute__ ((visibility ("default")))
#else
#define HTRA_API
#endif
#else
#define HTRA_API
#endif
#endif

/**
 * @brief Maximum number of SIGNALs detected per single search.
 */
#define EMI_MAX_SIGNALS 256

/**
 * @brief Detector enumeration for EMI pre-scan.
 */
enum emi_detector : uint8_t 
{
    EMI_SAMPLE_DETECTOR = 0x01,
    EMI_MAX_DETECTOR = 0x02,
    EMI_RMS_DETECTOR = 0x04,
    EMI_MIN_DETECTOR = 0x08,
    EMI_ALL_DETECTOR = 0x0f
};

/**
 * @brief Window function for EMI pre-scan.
 */
enum emi_window : uint8_t 
{
    CISPR = 0x01,
};

/**
 * @brief Search method.
 */
enum search_mode
{
    SPUR, // Search for points relative to the limit line
    PEAK  // Search for points relative to the local noise floor
};

/**
 * @brief EMI pre-scan configuration parameters.
 */
typedef struct
{
    /** Scan start frequency, in Hz */
    double start;

    /** Scan stop frequency, in Hz */
    double stop;

    /** Reference level, with unit specified by unit */
    float ref_level;

    /** Resolution Bandwidth (RBW), in Hz */
    double rbw;

    /** RBW definition point, typically 6 dB for EMI/CISPR */
    float filter_dB;

    /** Video Bandwidth (VBW), in Hz */
    double vbw;

    /** Dwell time per frequency point, in seconds (s) */
    float dwell_time;

    /** Amplitude unit */
    dB_unit unit;

    /** Sweep Detector, can be bitwise combined by emi_detector */
    uint8_t detector;

    /** FFT window type */
    emi_window window;

}emi_scan_profile;

/**
 * @brief EMI pre-scan return information.
 */
typedef struct
{
    /** Frequency of the first point of the trace, in Hz */
    double first_freq;

    /** Frequency of the last point of the trace, in Hz */
    double last_freq;

    /** Total number of points in the complete trace */
	uint32_t total_points;
  
    /** Number of sweep sections */
	uint32_t sections;

    /** Number of points in a standard section */
    uint32_t section_points;    
 
    /** Number of points in the last section */
    uint32_t last_section_points;

}emi_scan_info;

/**
 * @brief EMI signal search results.
 */
typedef struct
{
    /** Frequency of the highest power point within the over-threshold segment, in Hz */
    double freq;

    /** Amplitude of the highest power point within the over-threshold segment, unit is consistent with the input trace */
    float level;

    /** Bandwidth of the continuous over-threshold segment, in Hz */
    double bw;

    /** Amplitude by which the highest power point exceeds the detection threshold, in dB */
    float over_db;

} spur;

/**
 * @brief EMI frequency point measurement configuration parameters.
 */
typedef struct
{
    /** Measurement center frequency, in Hz */
    double center;

    /** Reference level, unit specified by unit */
    float ref_level;

    /** Measurement bandwidth, in Hz */
    double bw;
 
    /** RBW definition point, typically 6 dB for EMI/CISPR */
    float filter_dB;

    /** Quasi-Peak detector charge time, in s */
    float charge_time;

    /** Quasi-peak detector discharge time, in s */
    float decay_time;

    /** Measurement time, in s */
    float measure_time;

    /** Amplitude unit */
    dB_unit unit;

    /** Measurement Mode: 0 - measure based on measure_time; -1 - adaptive measurement, default is 2s but not exceeding 5s  */
    int8_t mode;

}emi_measure_profile;

/**
 * @brief Configure EMI pre-scan frequency band parameters.
 *
 * @param[in]  device          Device handle
 * @param[in]  scan_profile_i  Input pre-scan configuration parameters
 * @param[out] scan_profile_o  Return the actual effective pre-scan configuration parameters
 * @param[out] scan_info_o     Return the pre-scan trace information
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API int emi_config_scan(void** device, const emi_scan_profile* scan_profile_i, emi_scan_profile* scan_profile_o, emi_scan_info* scan_info_o);

/**
 * @brief Retrieve the EMI pre-scan segmented trace.
 *
 * @param[in]  device        Device handle
 * @param[out] freq_o        Return the frequency axis, in Hz
 * @param[out] amp_peak_o    Return the Peak power axis, with unit specified by scan_profile_i.unit
 * @param[out] amp_rms_o     Return the RMS power axis, with unit specified by scan_profile_i.unit
 * @param[out] amp_min_o     Return the Min power axis, with unit specified by scan_profile_i.unit
 * @param[out] amp_sample_o  Return the Sample power axis, with unit specified by scan_profile_i.unit
 * @param[out] index_o       Return the current segment index, used for stitching the complete trace
 * @param[out] aux_info_o    Return auxiliary measurement information
 * @param[out] completed_o   Return the frequency band scan completion flag, where 1 indicates completed
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API int emi_get_partial_trace(void** device, double freq_o[], float amp_peak_o[], float amp_rms_o[], float amp_min_o[], float amp_sample_o[], int* index_o, MeasAuxInfo_TypeDef* aux_info_o, uint8_t* completed_o);

/**
 * @brief Compare the pre-scan trace with the EMI standard to search for anomalous signals.
 * If the standard limit is a Peak or QP standard, please pass the Peak power axis.
 * If the standard limit is an RMS or linAvg standard, please pass the RMS power axis.
 *
 * @param[in] mode            Search mode
 * @param[in] freq            Trace frequency array
 * @param[in] amplitude       Trace amplitude array
 * @param[in] points          Number of trace points
 * @param[in] limit_freq      Limit line frequency array in SPUR mode, ignored in PEAK mode
 * @param[in] limit_amplitude Limit line amplitude array in SPUR mode, ignored in PEAK mode (same unit as the trace)
 * @param[in] limit_points    Number of limit line points
 * @param[in] margin          In SPUR mode, limit+margin is used as the search threshold (recommended range: -20 to 20 dB);
 *                            in PEAK mode, noise floor+margin is used as the search threshold (recommended range: 6 to 42 dB).
 * @param[out] result_o       Detection results array, with a maximum capacity of 256
 * @param[out] signalnums_o   Actual number of output results
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API void emi_search(search_mode mode, double freq[], float amplitude[], uint32_t points, double limit_freq[], float limit_amplitude[], uint32_t limit_points, float margin, spur result_o[], uint32_t* signalnums_o);

/**
 * @brief Configure EMI frequency point measurement parameters.
 *
 * @param[in]  device          Device handle
 * @param[in]  meas_profile_i  Input frequency point measurement configuration parameters
 * @param[out] meas_profile_o  Return the actual effective frequency point measurement configuration parameters
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API int emi_config_measure(void** device, const emi_measure_profile* meas_profile_i, emi_measure_profile* meas_profile_o);

/**
 * @brief Retrieve EMI frequency point measurement results.
 *
 * @param[in]  device          Device handle
 * @param[out] peak_o          Return the peak detection result, with unit specified by measprofile_i.unit
 * @param[out] rms_avg_o       Return the RMS detection result, with unit specified by measprofile_i.unit
 * @param[out] lin_avg_o       Return the linear average detection result, with unit specified by measprofile_i.unit
 * @param[out] quasi_peak_o    Return the quasi-peak detection result, with unit specified by measprofile_i.unit
 * @param[out] measure_time_o  Return the elapsed measurement time, in s
 * @param[out] aux_info_o      Return auxiliary measurement information
 * @param[out] completed_o     Return the frequency point measurement completion flag, where 1 indicates completed
 *
 * @note Each invocation updates the detection results based on the valid data up to the current moment; when completed_o is 1, it represents the final result of this round of measurement.
 * @note When mode is -1, the final result is the maximum value of each detection result across 20 or 50 statistical windows of 100 ms each.
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API int emi_get_measure_result(void** device, float* peak_o, float* rms_avg_o, float* lin_avg_o, float* quasi_peak_o, float* measure_time_o, MeasAuxInfo_TypeDef* aux_info_o, uint8_t* completed_o);

/**
 * @brief Start EMI frequency point measurement.
 *
 * @param[in] device  Device handle
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API int emi_start_measure(void** device);

/**
 * @brief Stop EMI frequency point measurement.
 *
 * @param[in] device  Device handle
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API int emi_stop_measure(void** device);

/**
 * @brief Reset EMI frequency point measurement.
 *
 * @param[in] device  Device handle
 *
 * @return 0 on success, non-zero on failure
 */
HTRA_API int emi_reset_measure(void** device);

#ifdef __cplusplus
}
#endif

#endif
