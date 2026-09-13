#include <iostream>
#include "htra_api.h"

using namespace std;

int Config_flag = 0;

// "Device_Open"
void Device_Open_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo) {
	// "0"
	if (Status == APIRETVAL_NoError)
	{
		cout << "Device opened successfully" << endl;
	}
	else {
		while (1) {
			switch (Status) {
				// "-1"
			case APIRETVAL_ERROR_BusOpenFailed:
				cout << "Error - please check the driver installation and data cable connection." << endl; break;
				//"-3"
			case APIRETVAL_ERROR_RFACalFileIsMissing:
				cout << "Error - RF calibration file is missing. Please copy the RF calibration file to the CalFile folder." << endl; break;
				// "-4"
			case APIRETVAL_ERROR_IFACalFileIsMissing:
				cout << "Error - IF calibration file is missing. Please copy the IF calibration file to the CalFile folder" << endl; break;
				// "-7"
			case APIRETVAL_ERROR_UpdateStrategyFailed:
				cout << "Error - Failed to deliver the configuration to device. Please check whether multiple programs call the device simultaneously." << endl; break;
				// "-8"
			case APIRETVAL_ERROR_BusError:
				cout << "Error - Bus transmission error. Please check the power supply of the device" << endl; break;
				// "-43"
			case APIRETVAL_ERROR_IQCalFileIsMissing:
				cout << "Error - IQ calibration file is missing. Please copy the IQ calibration file to the CalFile folder" << endl; break;
				// "-44"
			default:
				cout << "Error - Failed to open device" << endl; break;
			}
			cout << "Status = " << Status << endl;
			Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
			if (Status == APIRETVAL_NoError)
			{
				cout << "Device opened successfully" << endl;
				break;
			}
		}
	}
}

// "SWP_Configuration"
void SWP_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, SWP_Profile_TypeDef* SWP_ProfileIn, SWP_Profile_TypeDef* SWP_ProfileOut, SWP_TraceInfo_TypeDef* TraceInfo) {
	// "0"
	if (Status == APIRETVAL_NoError)
	{
		cout << "Configuration delievery succeeded." << endl;
	}
	else {
		switch (Status)
		{
			// "Error codes 10051, 10060, 10062: directly reopen the device and resend parameters"
		case APIRETVAL_ERROR_ETHTimeOut:
		case APIRETVAL_ERROR_ETHDisconnected:
		case APIRETVAL_ERROR_ETHDataError:
			cout << "Error - A network exception caused the error." << endl;
			while (1) {
				cout << "Status = " << Status << endl;
				Status = Device_Close(Device);
				cout << "Device closed, restarting..." << endl;
				Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
				Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
				Status = SWP_Configuration(Device, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
				if (Status == APIRETVAL_NoError) {
					cout << "Configuration delievery succeeded." << endl;
					break;
				}
				else {
					cout << "Error - Configuration delivery failed. Please try again." << endl;
				}
			}
			break;

		default:
			for (int i = 0; i < 10; i++) {
				switch (Status)
				{
					// "-11"
				case APIRETVAL_ERROR_BusDownLoad:
					cout << "Error - Bus configuration parameter failed." << endl;
					break;
				default:
					cout << "Error - Failed to deliver the configuration." << endl;
					break;
				}
				cout << "Status = " << Status << endl;
				Status = SWP_Configuration(Device, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
				if (Status == APIRETVAL_NoError)
				{
					Config_flag = 1;
					break;
				}
			}
			if (Config_flag == 1) {
				cout << "Configuration delievery succeeded." << endl;
				Config_flag = 0;
			}
			else {
				while (1) {
					Status = Device_Close(Device);
					cout << "Device closed, restarting..." << endl;
					Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
					Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
					Status = SWP_Configuration(Device, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
					if (Status == APIRETVAL_NoError) {
						cout << "Configuration delievery succeeded." << endl;
						break;
					}
					else {
						cout << "Error - Configuration delivery failed. Please try again." << endl;
					}
				}
			}
			break;
		}
	}
}

// "IQS_Configuration"
void IQS_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, IQS_Profile_TypeDef* IQS_ProfileIn, IQS_Profile_TypeDef* IQS_ProfileOut, IQS_StreamInfo_TypeDef* StreamInfo) {
	// "0"
	if (Status == APIRETVAL_NoError)
	{
		cout << "Configuration delievery succeeded." << endl;
	}
	else {
		switch (Status)
		{
			// "Error codes 10051, 10060, 10062: directly reopen the device and resend parameters"
		case APIRETVAL_ERROR_ETHTimeOut:
		case APIRETVAL_ERROR_ETHDisconnected:
		case APIRETVAL_ERROR_ETHDataError:
			cout << "Error - A network exception caused the error." << endl;
			while (1) {
				cout << "Status = " << Status << endl;
				Status = Device_Close(Device);
				cout << "Device closed, restarting..." << endl;
				Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
				Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
				Status = IQS_Configuration(Device, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
				if (Status == APIRETVAL_NoError) {
					cout << "Configuration delievery succeeded." << endl;
					break;
				}
				else {
					cout << "Error - Configuration delivery failed. Please try again." << endl;
				}
			}
			break;

		default:
			for (int i = 0; i < 10; i++) {
				switch (Status)
				{
					// "-11"
				case APIRETVAL_ERROR_BusDownLoad:
					cout << "Error - Bus configuration parameter failed." << endl;
					break;
				default:
					cout << "Error - Failed to deliver the configuration." << endl;
					break;
				}
				cout << "Status = " << Status << endl;
				Status = IQS_Configuration(Device, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
				if (Status == APIRETVAL_NoError)
				{
					Config_flag = 1;
					break;
				}
			}
			if (Config_flag == 1) {
				cout << "Configuration delievery succeeded." << endl;
				Config_flag = 0;
			}
			else {
				while (1) {
					Status = Device_Close(Device);
					cout << "Device closed, restarting..." << endl;
					Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
					Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
					Status = IQS_Configuration(Device, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
					if (Status == APIRETVAL_NoError) {
						cout << "Configuration delievery succeeded." << endl;
						break;
					}
					else {
						cout << "Error - Failed to deliver the configuration. Please try again." << endl;
					}
				}
			}
			break;
		}
	}
}

// "DET_Configuration"
void DET_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, DET_Profile_TypeDef* DET_ProfileIn, DET_Profile_TypeDef* DET_ProfileOut, DET_StreamInfo_TypeDef* StreamInfo) {
	// "0"
	if (Status == APIRETVAL_NoError)
	{
		cout << "Configuration delievery succeeded." << endl;
	}

	else {
		switch (Status)
		{
			// "Error codes 10051, 10060, 10062: directly reopen the device and resend parameters"
		case APIRETVAL_ERROR_ETHTimeOut:
		case APIRETVAL_ERROR_ETHDisconnected:
		case APIRETVAL_ERROR_ETHDataError:
			cout << "Error - A network exception caused the error." << endl;
			while (1) {
				cout << "Status = " << Status << endl;
				Status = Device_Close(Device);
				cout << "Device closed, restarting..." << endl;
				Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
				Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
				Status = DET_Configuration(Device, DET_ProfileIn, DET_ProfileOut, StreamInfo);
				if (Status == APIRETVAL_NoError) {
					cout << "Configuration delievery succeeded." << endl;
					break;
				}
				else {
					cout << "Error - Failed to deliver the configuration. Please try again." << endl;
				}
			}
			break;

		default:
			for (int i = 0; i < 10; i++) {
				switch (Status)
				{
					// "-11"
				case APIRETVAL_ERROR_BusDownLoad:
					cout << "Error - Bus configuration parameter failed." << endl;
					break;
				default:
					cout << "Error - Failed to deliver the configuration." << endl;
					break;
				}
				cout << "Status = " << Status << endl;
				Status = DET_Configuration(Device, DET_ProfileIn, DET_ProfileOut, StreamInfo);
				if (Status == APIRETVAL_NoError)
				{
					Config_flag = 1;
					break;
				}
			}
			if (Config_flag == 1) {
				cout << "Configuration delievery succeeded." << endl;
				Config_flag = 0;
			}
			else {
				while (1) {
					Status = Device_Close(Device);
					cout << "Device closed, restarting..." << endl;
					Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
					Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
					Status = DET_Configuration(Device, DET_ProfileIn, DET_ProfileOut, StreamInfo);
					if (Status == APIRETVAL_NoError) {
						cout << "Configuration delievery succeeded." << endl;
						break;
					}
					else {
						cout << "Error - Failed to deliver the configuration. Please try again." << endl;
					}
				}
			}
			break;
		}
	}
}

// "RTA_Configuration"
void RTA_Configuration_ErrorHandling(int Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, RTA_Profile_TypeDef* RTA_ProfileIn, RTA_Profile_TypeDef* RTA_ProfileOut, RTA_FrameInfo_TypeDef* FrameInfo) {
	// "0"
	if (Status == APIRETVAL_NoError)
	{
		cout << "Configuration delievery succeeded." << endl;
	}
	else {
		switch (Status)
		{
			// "Error codes 10051, 10060, 10062: directly reopen the device and resend parameters"
		case APIRETVAL_ERROR_ETHTimeOut:
		case APIRETVAL_ERROR_ETHDisconnected:
		case APIRETVAL_ERROR_ETHDataError:
			cout << "Error - A network exception occurred." << endl;
			while (1) {
				cout << "Status = " << Status << endl;
				Status = Device_Close(Device);
				cout << "Device closed, restarting..." << endl;
				Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
				Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
				Status = RTA_Configuration(Device, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
				if (Status == APIRETVAL_NoError) {
					cout << "Configuration delievery succeeded." << endl;
					break;
				}
				else {
					cout << "Error - Configuration delivery failed. Please try again." << endl;
				}
			}
			break;

		default:
			for (int i = 0; i < 10; i++) {
				switch (Status)
				{
					//"-11"
				case APIRETVAL_ERROR_BusDownLoad:
					cout << "Error - Failed to deliver parameters through the bus." << endl;
					break;
				default:
					cout << "Error - Failed to deliver the configuration." << endl;
					break;
				}
				cout << "Status = " << Status << endl;
				Status = RTA_Configuration(Device, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
				if (Status == APIRETVAL_NoError)
				{
					Config_flag = 1;
					break;
				}
			}
			if (Config_flag == 1) {
				cout << "Configuration delievery succeeded." << endl;
				Config_flag = 0;
			}
			else {
				while (1) {
					Status = Device_Close(Device);
					cout << "Device closed, restarting..." << endl;
					Status = Device_Open(Device, DevNum, BootProfile, BootInfo);
					Device_Open_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo);
					Status = RTA_Configuration(Device, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
					if (Status == APIRETVAL_NoError) {
						cout << "Configuration delievery succeeded." << endl;
						break;
					}
					else {
						cout << "Error - Configuration delivery failed. Please try again." << endl;
					}
				}
			}
			break;
		}
	}
}
		
//"SWP ErrorHandlingExceptOpenAndConfiguration "
void SWP_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, SWP_Profile_TypeDef* SWP_ProfileIn, SWP_Profile_TypeDef* SWP_ProfileOut, SWP_TraceInfo_TypeDef* TraceInfo) {

	if (Status != APIRETVAL_NoError)
	{
		switch (Status)
		{
			//"Warning codes -12,-14,-15,-16,-17,-18,-19,-36,-37,-38,-39" After the warning code reminder, reset the error code to zero and continue acquiring data.
		case APIRETVAL_WARNING_IFOverflow:
		case APIRETVAL_WARNING_ReconfigurationIsRecommended:
		case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
		case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
		case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
		case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
		case APIRETVAL_WARNING_ADCConfigError:
		case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
		case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
		case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
		case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
			switch (Status) {
			case APIRETVAL_WARNING_IFOverflow:
				cout << "Warning: - The midrange is saturated, it is recommended to adjust the reference level." << endl; SWP_ProfileIn->RefLevel_dBm += 5; break; //Intermediate frequency saturation is a warning, and data acquisition continues. The reference level should be gradually increased. This demonstration automatically increases the reference level by 5 steps until normal operation is restored.
			case APIRETVAL_WARNING_ReconfigurationIsRecommended:
			cout << "Warning - If the temperature has changed significantly since the last configuration, the parameters will be reapplied." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
			    cout << "Warning - The system clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
			    cout << "Warning - The ADC clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
			    cout << "Warning - The receiver IF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
			    cout << "Warning - The receiver RF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ADCConfigError:
			    cout << "Warning - The ADC is misconfigured. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
			    cout << "Warning - The system clock has been relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
			    cout << "Warning - The ADC clock has been relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
			    cout << "Warning - The receiver IF local oscillator has been relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
			    cout << "Warning - The receiver RF local oscillator has been relocked. Please replug the device." << endl; break;
			default:
				break;
			}
			cout << "Status = " << Status << endl;
			Status = SWP_Configuration(Device, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
			SWP_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
			break;

			//"Error codes 10051, 10060, and 10062 should be passed directly to Configuration_ErrorHandling to restart the device."
		case APIRETVAL_ERROR_ETHTimeOut:
		case APIRETVAL_ERROR_ETHDisconnected:
		case APIRETVAL_ERROR_ETHDataError:
			SWP_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
			break;

		default:
			cout << "Error - Get data exceptions." << endl;
			cout << "Status = " << Status << endl;
			cout << "Re-deliver the parameters" << endl;
			for (int i = 0; i < 5; i++) {
				Status = SWP_Configuration(Device, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
				if (Status == APIRETVAL_NoError)
				{
					Config_flag = 1;
					break;
				}
				SWP_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, SWP_ProfileIn, SWP_ProfileOut, TraceInfo);
			}
			if (Config_flag == 1) {
				cout << "The parameters have been configured." << endl;
				Config_flag = 0;
			}
			break;
		}
	}
}
		
// "IQS ErrorHandlingExceptOpenAndConfiguration"
void IQS_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, IQS_Profile_TypeDef* IQS_ProfileIn, IQS_Profile_TypeDef* IQS_ProfileOut, IQS_StreamInfo_TypeDef* StreamInfo) {

    if (Status != APIRETVAL_NoError)
    {
        switch (Status)
        {
            // "Warning codes -12, -14, -15, -16, -17, -18, -19, -36, -37, -38, -39" After warning code reminder, set the error code to zero and continue acquiring data
        case APIRETVAL_WARNING_IFOverflow:
        case APIRETVAL_WARNING_ReconfigurationIsRecommended:
        case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
        case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
        case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
        case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
        case APIRETVAL_WARNING_ADCConfigError:
        case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
        case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
        case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
        case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
            switch (Status) {
            case APIRETVAL_WARNING_IFOverflow:
                cout << "Warning: - The midrange is saturated, it is recommended to adjust the reference level." << endl; IQS_ProfileIn->RefLevel_dBm += 5; break; // Intermediate frequency saturation is a warning, data acquisition continues, just keep increasing reference level. Here it demonstrates an automatic step of 5 to increase reference level until it recovers.
            case APIRETVAL_WARNING_ReconfigurationIsRecommended:
				cout << "Warning - If the temperature changes greatly since the last configuration, the parameters will be re-issued." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
				cout << "Warning - The system clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
				cout << "Warning - The ADC clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
				cout << "Warning - The receiver IF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
				cout << "Warning - The receiving RF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ADCConfigError:
				cout << "Warning - The ADC is misconfigured. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
				cout << "Warning - The system clock is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
				cout << "Warning: The ADC clock is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
				cout << "Warning: The receiving IF local oscillator is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
				cout << "Warning: The receiving RF local oscillator is relocked. Please replug the device." << endl; break;
            default:
                break;
            }
            cout << "Status = " << Status << endl;
            Status = IQS_Configuration(Device, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
            IQS_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
            if (IQS_ProfileOut->TriggerSource == Bus) {
                IQS_BusTriggerStart(Device);
            }
            break;

            // "Error codes 10051, 10060, 10062 directly pass into Configuration_ErrorHandling to restart the device"
        case APIRETVAL_ERROR_ETHTimeOut:
        case APIRETVAL_ERROR_ETHDisconnected:
        case APIRETVAL_ERROR_ETHDataError:
            IQS_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
            if (IQS_ProfileOut->TriggerSource == Bus) {
                IQS_BusTriggerStart(Device);
            }
            break;

            // "-9" and "-10" Bus data error, just reissue parameters
        default:
            if (Status == APIRETVAL_ERROR_BusDataError) {
				cout << "Error - Bus data error, check if the device is turned on more." << endl;
            }
            else if (Status == APIRETVAL_WARNING_BusTimeOut) {
				cout << "Error - Get data timed out. Please reconfigure the parameters." << endl;
            }
            else {
				cout << "Error - Error in getting data." << endl;
            }
            cout << "Status = " << Status << endl;
			cout << "Re-deliver the parameters." << endl;
            for (int i = 0; i < 5; i++) {
                Status = IQS_Configuration(Device, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
                if (Status == APIRETVAL_NoError)
                {
                    Config_flag = 1;
                    break;
                }
                IQS_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, IQS_ProfileIn, IQS_ProfileOut, StreamInfo);
            }
            if (Config_flag == 1) {
				cout << "The parameters are configured." << endl;
                Config_flag = 0;
            }
            if (IQS_ProfileOut->TriggerSource == Bus) {
                IQS_BusTriggerStart(Device);
            }
            break;
        }
    }
}

//"DET ErrorHandlingExceptOpenAndConfiguration"
void DET_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, DET_Profile_TypeDef* DET_ProfileIn, DET_Profile_TypeDef* DET_ProfileOut, DET_StreamInfo_TypeDef* StreamInfo) {

	if (Status != APIRETVAL_NoError)
	{
		switch (Status)
		{
			//"Warning codes -12, -14, -15, -16, -17, -18, -19, -36, -37, -38, -39" After warning codes, set the error code to zero and continue to retrieve data
		case APIRETVAL_WARNING_IFOverflow:
		case APIRETVAL_WARNING_ReconfigurationIsRecommended:
		case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
		case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
		case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
		case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
		case APIRETVAL_WARNING_ADCConfigError:
		case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
		case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
		case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
		case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
			switch (Status) {
			case APIRETVAL_WARNING_IFOverflow:
				cout << "Warning: - The midrange is saturated, it is recommended to adjust the reference level." << endl; DET_ProfileIn->RefLevel_dBm += 5; break; // Intermediate frequency saturation is a warning, data retrieval is still ongoing, continue to raise the reference level. This example automatically increases the reference level in steps of 5 until it recovers to normal
			case APIRETVAL_WARNING_ReconfigurationIsRecommended:
				cout << "Warning - If the temperature changes greatly since the last configuration, the parameters will be re-issued." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
				cout << "Warning - The system clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
				cout << "Warning - The ADC clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
				cout << "Warning - The receiver IF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
				cout << "Warning - The receiving RF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ADCConfigError:
				cout << "Warning - The ADC is misconfigured. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
				cout << "Warning - The system clock is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
				cout << "Warning: The ADC clock is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
				cout << "Warning: The receiving IF local oscillator is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
			
				cout << "Warning: The receiving RF local oscillator is relocked. Please replug the device." << endl; break;
			default:
				break;
			}
			cout << "Status = " << Status << endl;
			Status = DET_Configuration(Device, DET_ProfileIn, DET_ProfileOut, StreamInfo);
			DET_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, DET_ProfileIn, DET_ProfileOut, StreamInfo);
			if (DET_ProfileOut->TriggerSource == Bus) {
				DET_BusTriggerStart(Device);
			}
			break;

			//"Error codes 10051, 10060, 10062 directly passed to Configuration_ErrorHandling to restart the device"
		case APIRETVAL_ERROR_ETHTimeOut:
		case APIRETVAL_ERROR_ETHDisconnected:
		case APIRETVAL_ERROR_ETHDataError:
			DET_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, DET_ProfileIn, DET_ProfileOut, StreamInfo);
			if (DET_ProfileOut->TriggerSource == Bus) {
				DET_BusTriggerStart(Device);
			}
			break;

			//"-9" and "-10" Bus data error, reapply the parameters
		default:
			if (Status == APIRETVAL_ERROR_BusDataError) {
				cout << "Error - Bus data error. Check if the device is turned on more." << endl;
			}
			else if (Status == APIRETVAL_WARNING_BusTimeOut) {
				cout << "Error - Get data timed out. Please reconfigure the parameters." << endl;
			}
			else {
				cout << "Error - Error in getting data." << endl;
			}
			cout << "Status = " << Status << endl;
			cout << "Re-deliver the parameters." << endl;
			for (int i = 0; i < 5; i++) {
				Status = DET_Configuration(Device, DET_ProfileIn, DET_ProfileOut, StreamInfo);
				if (Status == APIRETVAL_NoError)
				{
					Config_flag = 1;
					break;
				}
				DET_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, DET_ProfileIn, DET_ProfileOut, StreamInfo);
			}
			if (Config_flag == 1) {
				cout << "The parameters are configured." << endl;
				Config_flag = 0;
			}
			if (DET_ProfileOut->TriggerSource == Bus) {
				DET_BusTriggerStart(Device);
			}
			break;
		}
	}
}

//"RTA ErrorHandlingExceptOpenAndConfiguration"
void RTA_ErrorHandlingExceptOpenAndConfiguration(int& Status, void** Device, int DevNum, BootProfile_TypeDef* BootProfile, BootInfo_TypeDef* BootInfo, RTA_Profile_TypeDef* RTA_ProfileIn, RTA_Profile_TypeDef* RTA_ProfileOut, RTA_FrameInfo_TypeDef* FrameInfo) {

	if (Status != APIRETVAL_NoError)
	{
		switch (Status)
		{
			//"Warning codes -12, -14, -15, -16, -17, -18, -19, -36, -37, -38, -39" After warning codes, set the error code to zero and continue to retrieve data
		case APIRETVAL_WARNING_IFOverflow:
		case APIRETVAL_WARNING_ReconfigurationIsRecommended:
		case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
		case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
		case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
		case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
		case APIRETVAL_WARNING_ADCConfigError:
		case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
		case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
		case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
		case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
			switch (Status) {
			case APIRETVAL_WARNING_IFOverflow:
				cout << "Warning: - The midrange is saturated, it is recommended to adjust the reference level." << endl; RTA_ProfileIn->RefLevel_dBm += 5; break; // Intermediate frequency saturation is a warning, data retrieval is still ongoing, continue to raise the reference level. This example automatically increases the reference level in steps of 5 until it recovers to normal
			case APIRETVAL_WARNING_ReconfigurationIsRecommended:
				cout << "Warning - If the temperature changes greatly since the last configuration, the parameters will be re-issued." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_SYSCLK:
				cout << "Warning - The system clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_ADCCLK:
				cout << "Warning - The ADC clock is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXIFLO:
				cout << "Warning - The receiver IF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockUnlocked_RXRFLO:
				cout << "Warning - The receiving RF local oscillator is unlocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ADCConfigError:
				cout << "Warning - The ADC is misconfigured. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_SYSCLK:
				cout << "Warning - The system clock is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_ADCCLK:
				cout << "Warning: The ADC clock is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXIFLO:
				cout << "Warning: The receiving IF local oscillator is relocked. Please replug the device." << endl; break;
			case APIRETVAL_WARNING_ClockRelocked_RXRFLO:
				cout << "Warning: The receiving RF local oscillator is relocked. Please replug the device." << endl; break;
			default:
				break;
			}
			cout << "Status = " << Status << endl;
			Status = RTA_Configuration(Device, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
			RTA_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
			if (RTA_ProfileOut->TriggerSource == Bus) {
				RTA_BusTriggerStart(Device);
			}
			break;

			//"Error codes 10051, 10060, 10062 directly passed to Configuration_ErrorHandling to restart the device"
		case APIRETVAL_ERROR_ETHTimeOut:
		case APIRETVAL_ERROR_ETHDisconnected:
		case APIRETVAL_ERROR_ETHDataError:
			RTA_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
			if (RTA_ProfileOut->TriggerSource == Bus) {
				RTA_BusTriggerStart(Device);
			}
			break;

			// "-9" and "-10" Bus data error, just reconfigure the parameters
		default:
			if (Status == APIRETVAL_ERROR_BusDataError) {
				cout << "Error - Bus data error. Check if the device is turned on more." << endl;
			}
			else if (Status == APIRETVAL_WARNING_BusTimeOut) {
				cout << "Error - Get data timed out. Please reconfigure the parameters." << endl;
			}
			else {
				cout << "Error - Error in getting data." << endl;
			}
			cout << "Status = " << Status << endl;
			cout << "Re-deliver the parameters." << endl;
			for (int i = 0; i < 5; i++) {
				Status = RTA_Configuration(Device, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
				if (Status == APIRETVAL_NoError)
				{
					Config_flag = 1;
					break;
				}
				RTA_Configuration_ErrorHandling(Status, Device, DevNum, BootProfile, BootInfo, RTA_ProfileIn, RTA_ProfileOut, FrameInfo);
			}
			if (Config_flag == 1) {
				cout << "The parameters are configured." << endl;
				Config_flag = 0;
			}
			if (RTA_ProfileOut->TriggerSource == Bus) {
				RTA_BusTriggerStart(Device);
			}
			break;
		}
	}
}