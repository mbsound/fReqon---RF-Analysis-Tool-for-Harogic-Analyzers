#include "example.h"

int main()
{
    int Status = 0;

    Status = Device_GetDeviceInfo();
    //Status = Device_SysPowerState();

    //Status = SWP_GetSpectrum_Standard();
    //Status = SWP_MaxHold_MinHold();
    //Status = SWP_TraceAverage();
    //Status = SWP_AutoSetMeasure();
    //Status = SWP_SetFreqCompensation();
    //Status = SWP_PickMaxPower();
    //Status = SWP_GetSpectrum_SigAndSpur();
    //Status = SWP_GetSpectrum_Trigger();
    //Status = SWP_GetSpectrum_TraceAlign();
    //Status = SWP_Fixedtime_GetFrames();
    //Status = SWP_CalibrateRefClock();


    //Status = IQS_GetIQ_Standard();
    //Status = IQS_ScaleIQDataToVolts();
    //Status = IQS_ConfigandGetIQ_Time();
    //Status = IQS_GetIQToTxt();
    //Status = IQS_GNSS_1PPS();
    //Status = IQS_MultiDevSync_fixed();
    //Status = IQS_ExternalTrigger();
    //Status = IQS_TimerTrigger();
    //Status = IQS_LevelTrigger();
    //Status = IQS_Enable_GNSS_10MHz();


    //Status = DSP_IQSToSpectrum();
    //Status = DSP_DDC();
    //Status = DSP_LPF();


    //Status = DETMode_Standard();


    //Status = RTAMode_Standard();
    //Status = RTAMode_Standard_perframe();


    //Status = ASG_SignalOutput();

    return Status;

}
