/**
 * \file htra_api_pulse.h
 *
 * \~english \brief Pulse detection API (Optional)
 *
 * \~english Pulse detection on time-domain data (dBm or V) collected by the HTRA spectrum analyzer based on the set threshold, with outputs including pulse width, period, duty cycle, and other parameters.
 */


#ifndef HTRA_API_PULSE_H
#define HTRA_API_PULSE_H

#include <stdint.h>

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


/** \~english Pulse detection license file is missing, please place name_pulsedet.lic (e.g., 057_20303232424850110024002e_pulsedet.lic) in the /CalFile/ directory. */
#define APIRETVAL_ERROR_PulseDetLicFileIsMissing -50

/** \~english The content of the pulse detection license file is incorrect, usually due to modifications to the license content, please contact technical support for assistance. */
#define APIRETVAL_ERROR_PulseDetLicFileIsIncorrect -51

/** \~english  The pulse detection license file has expired, please contact technical support */
#define APIRETVAL_ERROR_PulseDetLicFileIsExpired -52

/** \~english  The expected number of pulses is 0, no pulse detection will be performed */
#define APIRETVAL_ERROR_ExpPulseNumIsZero -53

/** \~english The expected number of pulses exceeds the limit, execution will proceed based on the limit */
#define APIRETVAL_WARNING_ExpPulseNum_MoreThan_Max 50

/** \~english The number of pulse detection data points is less than the lower limit, pulse detection will not be performed */
#define APIRETVAL_ERROR_PulseSize_LessThan_Min -54

/** \~english The number of pulse detection data points exceeds the upper limit, execution will proceed based on the limit */
#define APIRETVAL_WARNING_PulseSize_MoreThan_Max 51

/** \~english Minimum value of the expected number of pulses */
#define APIRETVAL_ExpPulseNumMin 1

/** \~english Maximum value of the expected number of pulses*/
#define APIRETVAL_ExpPulseNumMax 500000

/** \~english Lower limit of pulse detection data points */
#define APIRETVAL_ERROR_PulseMinSize 10

/** \~english Upper limit of pulse detection data points */
#define APIRETVAL_ERROR_PulseMaxSize 500000000

/**
 * \enum Unit_TypeDef
 * \~english \brief Unit types for data, dBm or V
 */
typedef enum
{
    /** \~english Voltage V */
    Voltage_V,

    /** \~english Power dBm */
    Power_dBm

}Unit_TypeDef;

/**
 * \struct Pulse_Profile_TypeDef
 * \~english \brief Pulse detection input data structure, including the data to be detected, thresholds, etc.
 */
typedef struct
{
    /** \~english Expected number of pulses */
    uint32_t ExpPulseNum;

    /** \~english Pulse data unit, dBm or V */
    Unit_TypeDef unit;

    /** \~english Start memory address of pulse data, unit depends on the unit field */
    float* Pulse;

    /** \~english Length of pulse data */
    uint64_t PulseSize;

    /** \~english Time resolution of pulse data, in seconds */
    double TimeResolution_s;

    /** \~english Pulse detection threshold, unit is consistent with data */
    double DetThreshold;

}Pulse_Profile_TypeDef;

/**
 * \struct PulseTDParam_TypeDef
 * \~english \brief Pulse detection time-domain parameters structure, including pulse width, period, duty cycle, etc., all in seconds.
 */
typedef struct
{
    /** \~english Rise time */
    double RiseTime;

    /** \~english Rise edge */
    double RiseEdge;

    /** \~english Fall time */
    double FallTime;

    /** \~english Fall edge */
    double FallEdge;

    /** \~english Pulse width */
    double Width;

    /** \~english Period */
    double Period;

    /** \~english Duty cycle (%) */
    float DutyCycle;

}PulseTDParam_TypeDef;

/**
 * \struct PulseAMPParam_TypeDef
 * \~english \brief Pulse detection amplitude parameters structure, including peak level, reference level, peak-to-base ratio, etc.
 */
typedef struct
{
    /** \~english Peak level in dBm */
    float TopLevel_dBm;

    /** \~english Peak level in V */
    float TopLevel_V;

    /** \~english Reference level in dBm */
    float BaseLevel_dBm;

    /** \~english Reference level in V */
    float BaseLevel_V;

    /** \~english Peak-to-base ratio in dB */
    float TopToBaseRatio_dB;

    /** \~english Peak-to-base difference in V */
    float TopToBaseDiff_V;

    /** \~english Droop in dB */
    float Droop_dB;

    /** \~english Droop in V */
    float Droop_V;

    /** \~english Overshoot in dB */
    float Overshoot_dB;

    /** \~english Overshoot in V */
    float Overshoot_V;

    /** \~english Ripple in dB */
    float Ripple_dB;

    /** \~english Ripple in V */
    float Ripple_V;

}PulseAMPParam_TypeDef;

/**
 * \struct PulseEstParam_TypeDef
 * \~english \brief Pulse detection estimation parameters structure
 */
typedef struct
{
    /** \~english Array indices of the 10% level value, 0 for the rise edge, 1 for the fall edge */
    double Level_10pct_Index[2];

    /** \~english Array indices of the 50% level value, 0 for the rise edge, 1 for the fall edge */
    double Level_50pct_Index[2];

    /** \~english Array indices of the 90% level value, 0 for the rise edge, 1 for the fall edge */
    double Level_90pct_Index[2];

    /** \~english Array indices of the 95% level value, 0 for the rise edge, 1 for the fall edge */
    double Level_95pct_Index[2];

    /** \~english Array index of the 25% pulse width position */
    double Width_25pct_Index;

    /** \~english Array index of the 75% pulse width position */
    double Width_75pct_Index;

    /** \~english Starting index of the estimated signal and noise data */
    uint64_t Start_Index;

    /** \~english Length of the estimated signal and noise data */
    uint64_t Size;

    /** \~english Starting memory address of the estimated noise data in dBm */
    float* Noise_dBm;

    /** \~english Starting memory address of the estimated noise data in V */
    float* Noise_V;

    /** \~english Starting memory address of the estimated signal data in dBm */
    float* Signal_dBm;

    /** \~english Starting memory address of the estimated signal data in V */
    float* Signal_V;

}PulseEstParam_TypeDef;

/**
 * \struct PulseStatsParam_TypeDef
 * \~english \brief Pulse detection statistical parameters structure, including minimum, maximum, average period, etc., all in seconds.
 */
typedef struct
{
    /** \~english Minimum period */
    double MinPRI;

    /** \~english Maximum period */
    double MaxPRI;

    /** \~english Average period */
    double MeanPRI;

    /** \~english Minimum pulse width */
    double MinPW;

    /** \~english Maximum pulse width */
    double MaxPW;

    /** \~english Average pulse width */
    double MeanPW;

    /** \~english Period deviation percentage % */
    float PRIDeviationPercent;

    /** \~english Pulse width deviation percentage % */
    float PWDeviationPercent;

}PulseStatsParam_TypeDef;

/**
 * \struct PulseInfo_TypeDef
 * \~english \brief Pulse detection result structure, summary of all pulse detection parameters
 */
typedef struct
{
    /** \~english Actual number of pulses detected, based on this number, each pulse's result can be retrieved from pointer variables */
    uint32_t ActPulseNum;

    /** \~english Starting memory address of pulse detection time-domain parameters */
    PulseTDParam_TypeDef* PulseTDParam;

    /** \~english Starting memory address of pulse detection amplitude parameters */
    PulseAMPParam_TypeDef* PulseAMPParam;

    /** \~english Starting memory address of pulse detection estimation parameters */
    PulseEstParam_TypeDef* PulseEstParam;

    /** \~english Pulse detection statistical parameters */
    PulseStatsParam_TypeDef PulseStats;

}PulseInfo_TypeDef;

/**
 * \struct PulseFreqPhaseParam_TypeDef
 * \~english \brief Frequency and phase information of the pulse
 */
typedef struct
{
	/** \~english Mean frequenc */
	double FreqMean;

	/** \~english RMS frequency error */
	double FreqErrorRMS;

	/** \~english Mean phase */
	double PhaseMean;

	/** \~english RMS phase error */
	double PhaseErrorRMS;
}PulseFreqPhaseParam_TypeDef;

/**
 * \struct PulseInfoPM1_TypeDef
 * \~english \brief Pulse detection result structure, containing all pulse detection parameters
 */
typedef struct
{
	/** \~english Actual number of detected pulses. The detection results of each pulse can be obtained through the pointer variables according to this number */
	uint32_t ActPulseNum;

	/** \~english Starting memory address of the pulse detection time-domain parameters */
	PulseTDParam_TypeDef* PulseTDParam;

	/** \~english Starting memory address of the pulse detection amplitude parameters */
	PulseAMPParam_TypeDef* PulseAMPParam;

	/** \~english Starting memory address of the pulse detection plotting parameters */
	PulseEstParam_TypeDef* PulseEstParam;

	/** \~english Pulse detection statistical parameters */
	PulseStatsParam_TypeDef PulseStats;

	/** \~english Pulse modulation type. 0 indicates CW, 1 indicates LFM */
	uint8_t* Mod;

	/** \~english Frequency and phase information of the pulse */
	PulseFreqPhaseParam_TypeDef* PulseFreqPhase;

}PulseInfoPM1_TypeDef;

/**
 * \~english \brief Open pulse detection functionality, checks for the existence of licenses and allocates required memory
 * \~english @param[in] Device Device pointer
 * \~english @return Function call status, 0 for normal, non-zero for errors
 */
HTRA_API int Pulse_Open(void** Device);

/**
 * \~english \brief Execute pulse detection functionality
 * \~english @param[in] Device Device pointer
 * \~english @param[in] Pulse_Profile Input pulse detection data, including data to detect, thresholds, etc.
 * \~english @param[out] PulseInfo Output pulse detection results, including pulse width, period, duty cycle, etc.
 * \~english @return Function call status, 0 for normal, non-zero for errors (see macro definitions).
 */
HTRA_API int Pulse_Detect(void** Device, const Pulse_Profile_TypeDef* Pulse_Profile, PulseInfo_TypeDef* PulseInfo);

/**
 * \~english \brief Perform pulse detection on IQ data
 * \~english @param[in] Device Device handle pointer
 * \~english @param[in] Pulse_Profile Pulse detection configuration, including input data and detection threshold
 * \~english @param[out] PulseInfoPM1 Pulse detection results, including pulse width, period, duty cycle, and other parameters
 * \~english @return Function execution status. 0 indicates success; non-zero values refer to the corresponding macro definitions
 */
HTRA_API int Pulse_Detect_PM1(void** Device, const Pulse_Profile_TypeDef* Pulse_Profile, PulseInfoPM1_TypeDef* PulseInfoPM1);

/**
 * \~english \brief Close pulse detection functionality and free memory
 * \~english @param[in] Device Device pointer
 * \~english @return Function call status, 0 for normal, non-zero for errors (see macro definitions).
 */
HTRA_API int Pulse_Close(void** Device);



#ifdef __cplusplus
}
#endif

#endif