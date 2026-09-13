/**
 * \file htra_api_demod.h
 *
 *
 *
 * \~english \brief Digital Demodulation API (Optional)
 *
 * \~english The digital demodulation API for HTRA spectrum analyzers, including both analog and digital demodulation of IQ data captured by the device, with outputs such as demodulation results, constellation diagrams, EVM, and other parameters.
 */


#ifndef HTRA_API_DEMOD_H
#define HTRA_API_DEMOD_H

#include <stdint.h>
#include "htra_api.h"

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


/** \~english Demodulation license file is missing, please place the xx._demodlic.txt file in the /CalFile/ directory */ 
#define APIRETVAL_ERROR_DemodLicFileIsMissing -60

/** \~english The content of the demodulation license file is incorrect, usually due to modifications to the license content, please contact technical support */
#define APIRETVAL_ERROR_DemodLicFileIsIncorrect -61

/** \~english Please place DigitalSigDemod.dll (Windows) or libDigitalSigDemod.so (Linux) in the same directory as the htra_api library*/
#define APIRETVAL_ERROR_NoDemodLib -62

/** \~english Failed to open the demodulation function, this error usually does not occur, please contact technical support if it does*/
#define APIRETVAL_ERROR_DemodOpenFailed -63

/** \~english The number of sample points is less than 16384, please set the sample points to 16384 or above*/
#define APIRETVAL_ERROR_DemodSamplePoints_LessThan_16384  -64

/** \~english The number of sample points is greater than 320000, please set the sample points to 320000 or below*/
#define APIRETVAL_ERROR_DemodSamplePoints_MoreThan_320000  -65

/** \~english The sample rate/symbol rate ratio is less than 4, please set the ratio to 4 or above */
#define APIRETVAL_ERROR_DemodSampleRateSymbolRateRatio_LessThan_4  -66

/** \~english The sample rate/symbol rate ratio is greater than 64, please set the ratio to 64 or below*/
#define APIRETVAL_ERROR_DemodSampleRateSymbolRateRatio_LessThan_64  -67

/** \~english The input symbol rate is lower than the minimum value */
#define APIRETVAL_ERROR_DemodSymbolRate_LessThan_Min  -68

/** \~english The entered symbol rate exceeds the maximum allowed value.*/
#define APIRETVAL_ERROR_DemodSymbolRate_MoreThan_Max -69

/** \~english No demodulated data is available. Demodulation may fail if the input IQ data contains a large number of zero values. */
#define APIRETVAL_ERROR_DemodNoOutputData -70

/** \~english Demodulation failed */
#define APIRETVAL_ERROR_DemodExecuteFailed -71

/** \~english The number of sampling points is less than the recommended value. The recommended value will be returned. */
#define APIRETVAL_ERROR_DemodSamplePoints_LessThan_RecommendedValue -72

/** \~english The filter coefficient is outside the valid range [0.01, 0.99]. Values below the minimum will be automatically set to 0.1, and values above the maximum will be automatically set to 0.99. */
#define APIRETVAL_ERROR_FilterAlpha_OutOfRange -73

/** \~english The current sampling rate is not supported. It has been automatically adjusted to the available sampling rate. */
#define APIRETVAL_ERROR_DemodSampleRate_SetError -74

/** \~english Demodulation license expired */
#define APIRETVAL_ERROR_DemodLicExpired -75

/**
 * \enum Demod_ModType_TypeDef
 * \~english \brief Modulation types
 */
typedef enum
{
    /** \~english 2-Frequency Shift Keying */
    FSK2 = 1,

    /** \~english 4-Frequency Shift Keying*/
    FSK4,

    /** \~english Gaussian Minimum Shift Keying */
    GMSK,

    /** \~english Binary Phase Shift Keying */
    BPSK,

    /** \~english Quadrature Phase Shift Keying */
    QPSK,

    /** \~english 8-Phase Shift Keying */
    PSK8,

    /** \~english 16-Quadrature Amplitude Modulatio */
    QAM16,

    /** \~english 2-Amplitude Shift Keying */
    ASK2,

    /** \~english 64-Quadrature Amplitude Modulation */
    QAM64,

    /** \~english Amplitude Modulation */
    AM,

    /** \~english Frequency Modulation */
    FM,

    /** \~english Phase Modulation */
    PM,

    /** \~english Continuous Wave */
    CW,

    /** \~english Lower Sideband */
    LowerSideband,

    /** \~english Upper Sideband */
    UpperSideband,

	/** \~english 128QAM */
	QAM128,

	/** \~english 256QAM */
	QAM256,

	/** \~english 32QAM */
	QAM32

}Demod_ModType_TypeDef;

/**
 * \enum Demod_FilterType_TypeDef
 * \~english \brief Filter types
 */
typedef enum
{
    /** \~english Root-Raised Cosine filter */
    RootRaisedCosine = 1,

    /** \~english Raised Cosine filter */
    RaisedCosine,

    /** \~english Gaussian filter */
    Gaussian,

    /** \~english Rectangular filter */
    Rectangular,

    /** \~english Half-sine filter */
    HalfSine

}Demod_FilterType_TypeDef;

/**
 * \struct Demod_Profile_TypeDef
 * \~english \brief Demodulation configuration structure
 */
typedef struct
{
    /** \~english Sample points */
    uint64_t SamplePoints;

    /** \~english Sample rate (Hz) */
    double SampleRate;

    /** \~english Symbol rate (symbols per second) */
    double SymbolRate;

    /** \~english Modulation type */
    Demod_ModType_TypeDef ModType;

    /** \~english Only available for 16APSK (currently unavailable, set to 0) */
    double APSK16_Gamma;

    /** \~english Filter type, currently only supports RootRaisedCosine */
    Demod_FilterType_TypeDef FilterType;

    /** \~english Filter roll-off factor (currently only supports Root Raised Cosine, 0.01 <= Alpha <= 0.99) */
    double FilterAlpha;

}Demod_Profile_TypeDef;

/**
 * \struct DemodInfo_TypeDef
 * \~english \brief Demodulation information structure, including: eye diagram, constellation diagram, EVM, etc. Note: All pointer variables in the structure will point to internal function space, and no external memory allocation is needed by the user.
 */
typedef struct
{
    /** \~english Eye diagram data start memory address */
    double* eDiagram;
    
    /** \~english Eye diagram data length */
    uint32_t eDiagram_Len;

    /** \~english I-channel constellation data start memory address */
    double* I_constellation;

    /** \~english Q-channel constellation data start memory address */
    double* Q_constellation;

    /** \~english Constellation data length */
    uint32_t  constellation_Len;

    /** \~english Bit stream data start memory address */
    int32_t* bitStream;

    /** \~english Bit stream data length */
    uint32_t bitStream_Len;

    /** \~english Symbol stream data start memory address */
    int32_t* symbol;

    /** \~english Symbol stream data length */
    uint32_t symbol_Len;

    /** \~english EVM data start memory address (also used for FSK Error, ASK Error %) */
    double* EVM;

    /** \~english EVM data length */
    uint32_t EVM_Len;

    /** \~english Root Mean Square EVM (%) */
    double EVM_RMS;

    /** \~english Peak EVM (%) */
    double EVM_MAX;

    /** \~english Phase error data start memory address, in degrees */
    double* PhaseError;

    /** \~english Phase error data length */
    uint32_t PhaseError_Len;

    /** \~english RMS phase error, in degrees */
    double PhaseError_RMS;

    /** \~english Peak phase error, in degrees */
    double PhaseError_MAX;

    /** \~english Magnitude error data start memory address (%) */
    double* MagError;

    /** \~english Magnitude error data length */
    uint32_t MagError_Len;

    /** \~english RMS magnitude error (%) */
    double MagError_RMS;

    /** \~english Peak magnitude error (%) */
    double MagError_MAX;

    /** \~english Frequency error, carrier relative to center frequency, in Hz */
    double FreqError;

    /** \~english IQ offset (in dB, only for PSK and QAM) */
    double IQ_Offset;

    /** \~english Signal-to-Noise Ratio (SNR, in dB, only for PSK and QAM) */
    double SNR;

    /** \~english IQ gain imbalance (in dB, only for PSK and QAM) */
    double GainImb;

    /** \~english IQ quadrature tilt error (in degrees, only for PSK and QAM) */
    double QuadError;

    /** \~english FSK frequency deviation (in Hz) */
    double FSK_Deviation;

    /** \~english Carrier power (in dBm, only for ASK) */
    double CarrPower;

    /** \~english ASK modulation depth (%) */
    double ASK_Depth;

    /** \~english AM modulation depth (%) */
    double AM_Depth;

    /** \~english FM modulation frequency offset, (in Hz) */
    double FM_Deviation;

    /** \~english PM demodulation data start memory address */
    double* Phase;

    /** \~english PM demodulation data length */
    uint32_t Phase_Len;

    /** \~english FM demodulation data start memory address */
    double* Freq;

    /** \~english FM demodulation data length */
    uint32_t Freq_Len;

    /** \~english AM demodulation data start memory address */
    double* Amp;

    /** \~english AM demodulation data length */
    uint32_t Amp_Len;

    /** \~english SSB demodulation data start memory address, (used for both upper and lower sidebands) */
    double* SSB;

    /** \~english SSB demodulation data length */
    uint32_t SSB_Len;

}DemodInfo_TypeDef;

/**
 * \struct Demod_SymbolMap_TypeDef
 * \~english \brief Symbol mapping table structure, I is the x-axis, Q is the y-axis
 */
typedef struct
{
    /** \~english x-axis coordinate */
    float I;

    /** \~english y-axis coordinate */
    float Q;
}Demod_SymbolMap_TypeDef;

/**
 * \~english Check if the demodulation library exists
 * \~english @return Function call status, 0 exists, -1 does not exist
 */
 HTRA_API int Demod_Check();

/**
 *
 * \~english Open demodulation functionality, checks for the existence of licenses and allocates necessary memory
 * \~english @param[in] Device Device pointer
 * \~english @return Function call status, 0 normal, non-zero refer to related macros
 */
HTRA_API int Demod_Open(void** Device);

/**
 *
 * \~english Close demodulation functionality
 * \~english @param[in] Device Device pointer
 * \~english @return Function call status, 0 normal, non-zero refer to related macros
 */
HTRA_API int Demod_Close(void** Device);

/**
 *
 * \~english Reset demodulation functionality, necessary to call Demod_Reset before each Demod_Execute if IQ data is not continuous
 * \~english @param[in] Device Device pointer
 * \~english @return Function call status, 0 normal, non-zero refer to related macros
 */
HTRA_API int Demod_Reset(void** Device);

/**
 *
 * \~english Get demodulation API version
 * \~english @param[in] Device Device pointer
 * \~english @param[out] Demodulation API version
 * \~english @return Length of the returned version string
 */
HTRA_API int Demod_GetVersion(void** Device, char version[]);

/**
 *
 * \~english Initialize demodulation configuration structure and assign initial values to all parameters
 * \~english @param[out] DemodProfile Demodulation configuration structure
 */
HTRA_API void Demod_DeInit(Demod_Profile_TypeDef* DemodProfile);

/**
 *
 * \~english Configure demodulation parameters
 * \~english @param[in] Device Device pointer
 * \~english @param[in] DemodProfileIn Input demodulation configuration structure
 * \~english @param[out] DemodProfileOut Output demodulation configuration structure
 * \~english @return Function call status, 0 normal, non-zero refer to related macros
 */
HTRA_API int Demod_Configuration(void** Device, const Demod_Profile_TypeDef* DemodProfileIn, Demod_Profile_TypeDef* DemodProfileOut);

/**
 *
 * \~english Execute demodulation functionality
 * \~english @param[in] Device Device pointer
 * \~english @param[in] IQStream Input IQ data structure
 * \~english @param[out] DemodInfo Output demodulation information structure
 * \~english @return Function call status, 0 normal, non-zero refer to related macros
 */
HTRA_API int Demod_Execute(void** Device, const IQStream_TypeDef* IQStream, DemodInfo_TypeDef* DemodInfo);

/**
 *
 * \~english Generate symbol mapping table
 * \~english @param[in] ModType Modulation type
 * \~english @param[out] SymbolMap Symbol mapping table
 * \~english @param[out] MapNum Number of symbols available in the symbol map
 */
HTRA_API void Demod_GenSymbolMap(Demod_ModType_TypeDef ModType, Demod_SymbolMap_TypeDef SymbolMap[1024], uint32_t* MapNum);

#ifdef __cplusplus
}
#endif

#endif
