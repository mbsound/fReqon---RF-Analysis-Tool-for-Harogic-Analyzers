#"TARG" is x86_64 or aarch64 or armv7.
#"Example" is SWP_GetSpectrum_Standard, IQS_GetIQ_FixedPoints, etc.
#"CXX" is a compiler used, please modify "CXX" according to the actual compiler file location.

ifeq ($(TARG),aarch64)
	CXX = aarch64-linux-gnu-g++
else ifeq ($(TARG),armv7)
	CXX = arm-linux-gnueabihf-g++
else
	TARG = x86_64
	CXX = g++
endif

CXXFLAG = -std=c++11 -I/opt/htraapi/inc -L/opt/htraapi/lib/$(TARG)
LDFLAG = -lhtraapi -Wl,-rpath='/opt/htraapi/lib/$(TARG)'
LDFLAG = -lhtraapi -lliquid -Wl,-rpath='/opt/htraapi/lib/$(TARG)'

release:
	$(CXX) -o bin/$(Example) Examples/$(Example).cpp Examples/main.cpp Examples/Error_handling.cpp $(CXXFLAG) $(LDFLAG)


