QT       += core gui

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

CONFIG += c++11

DESTDIR = $$clean_path($$PWD/../bin)

# You can make your code fail to compile if it uses deprecated APIs.
# In order to do so, uncomment the following line.
#DEFINES += QT_DISABLE_DEPRECATED_BEFORE=0x060000    # disables all the APIs deprecated before Qt 6.0.0

SOURCES += \
    ASG_SignalOutput.cpp \
    DETMode_Standard.cpp \
    DSP_DDC.cpp \
    DSP_IQSToSpectrum.cpp \
    DSP_LPF.cpp \
    Device_GetDeviceInfo.cpp \
    Device_SysPowerState.cpp \
    Error_handling.cpp \
    IQS_ConfigandGetIQ_Time.cpp \
    IQS_Enable_GNSS_10MHz.cpp \
    IQS_ExternalTrigger.cpp \
    IQS_GNSS_1PPS.cpp \
    IQS_GetIQToTxt.cpp \
    IQS_GetIQ_Standard.cpp \
    IQS_LevelTrigger_PreTrigger.cpp \
    IQS_LevelTrigger_TriggerDelay.cpp \
    IQS_MultiDevSync_fixed.cpp \
    IQS_ScaleIQDataToVolts.cpp \
    IQS_TimerTrigger.cpp \
    RTAMode_Standard.cpp \
    RTAMode_Standard_perframe.cpp \
    SWP_AutoSetMeasure.cpp \
    SWP_CalibrateRefClock.cpp \
    SWP_Fixedtime_GetFrames.cpp \
    SWP_GetSpectrum_SigAndSpur.cpp \
    SWP_GetSpectrum_Standard.cpp \
    SWP_GetSpectrum_TraceAlign.cpp \
    SWP_GetSpectrum_Trigger.cpp \
    SWP_MaxHold_MinHold.cpp \
    SWP_PickMaxPower.cpp \
    SWP_SetFreqCompensation.cpp \
    SWP_TraceAverage.cpp \
    main.cpp \
    mainwindow.cpp

HEADERS += \
    example.h \
    mainwindow.h

FORMS += \
    mainwindow.ui

# Default rules for deployment.
qnx: target.path = /tmp/$${TARGET}/bin
else: unix:!android: target.path = /opt/$${TARGET}/bin
!isEmpty(target.path): INSTALLS += target


unix:!macx: LIBS += -L$$PWD/../htraapi/ -lhtraapi -lliquid -lusb-1.0 -lgomp

INCLUDEPATH += $$PWD/../htraapi
DEPENDPATH += $$PWD/../htraapi
