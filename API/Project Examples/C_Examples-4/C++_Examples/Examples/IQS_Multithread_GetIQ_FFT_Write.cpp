#include <iostream>
#include <fstream>
#include <vector>
#include <chrono>
#include <string>
#include "htra_api.h"
#include <math.h>
#include <thread>
#include <queue>
#include <mutex> 
#include <cmath>
#include <cstring>
#include <condition_variable>
#include "example.h"
using namespace std;

#define IS_USB 1 // By default, use the USB type device. If using the Ethernet type, define IS_USB as 0.

void IQS_Get(void* Device, IQS_StreamInfo_TypeDef StreamInfo);    // Acquire IQ data.
void IQS_FFT(void* DSP, IQS_StreamInfo_TypeDef StreamInfo);      // Perform FFT operation.
void IQS_Write(void* Device, IQS_StreamInfo_TypeDef StreamInfo); // Write data to file.

string filePath = "./IQ_Data.txt"; // Define output file path.
ofstream outfile;                  // Define output stream object.

queue<vector<int16_t>> IQS_instant_queue;				 // Define buffer queue.
std::mutex IQS_instant_Mtx;								 // Sync primitive for Write thread to wait for Get to write.
std::mutex Write_Mtx;									 // Sync primitive for exclusive use of the queue.
std::unique_lock<std::mutex> lck_Write(IQS_instant_Mtx); // Lock with IQS_instant_Mtx.
std::condition_variable Write_start;					 // Condition variable for Get to notify start of data acquisition.
bool Write_flag = false;								 // Set flag for Write thread to wake up.

queue<vector<int8_t>> IQS_Get_queue;			   // Data queue.
std::mutex IQS_Get_Mtx;							   // Sync primitive for FFT thread to wait for Get to write.
std::unique_lock<std::mutex> lck_FFT(IQS_Get_Mtx); // Lock with IQS_Get_Mtx.
std::condition_variable FFT_start;				   // Condition variable for Get to notify start of data acquisition.
std::mutex FFT_Mtx;								   // Sync primitive for exclusive use of the queue.


int IQS_Multithread_GetIQ_FFT_Write()
{
	int Status = 0;      // Return value of the function.
	void* Device = NULL; // Memory address of the current device.
	int DevNum = 0;      // Specify device number.

	BootProfile_TypeDef BootProfile; // Boot configuration structure, including physical interface, power supply method, etc.
	BootInfo_TypeDef BootInfo;       // Boot info structure, including device info, USB rate, etc.

	BootProfile.DevicePowerSupply = USBPortAndPowerPort; // Use both USB data port and independent power supply port.

#if IS_USB==1
	// Configure USB interface.
	BootProfile.PhysicalInterface = USB;
#else 
	// Configure ETH interface.
	BootProfile.PhysicalInterface = ETH;
	BootProfile.ETH_IPVersion = IPv4;
	BootProfile.ETH_RemotePort = 5000;
	BootProfile.ETH_ReadTimeOut = 5000;
	BootProfile.ETH_IPAddress[0] = 192;
	BootProfile.ETH_IPAddress[1] = 168;
	BootProfile.ETH_IPAddress[2] = 1;
	BootProfile.ETH_IPAddress[3] = 100;
#endif

	Status = Device_Open(&Device, DevNum, &BootProfile, &BootInfo); // Open the device.

	Device_Open_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo); // If Status is not 0, perform corresponding error handling.

	IQS_Profile_TypeDef IQS_ProfileIn;   // IQS input configuration, including start frequency, stop frequency, RBW, reference level, etc.
	IQS_Profile_TypeDef IQS_ProfileOut;  // IQS output configuration.
	IQS_StreamInfo_TypeDef StreamInfo;   // IQ data information under current configuration, including bandwidth, IQ sampling rate, etc.
	IQS_TriggerInfo_TypeDef TriggerInfo; // Trigger information.

	IQS_ProfileDeInit(&Device, &IQS_ProfileIn); // Initialize IQS mode parameters.

	IQS_ProfileIn.CenterFreq_Hz = 1e9;       // Set center frequency.
	IQS_ProfileIn.RefLevel_dBm = 0;          // Set reference level.
	IQS_ProfileIn.DataFormat = Complex16bit; // Set IQ data format.
	IQS_ProfileIn.TriggerMode = Adaptive;    // Set trigger mode.
	IQS_ProfileIn.DecimateFactor = 2;        // Set decimation factor.

	Status = IQS_Configuration(&Device, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Apply IQS configuration.

	IQS_Configuration_ErrorHandling(Status, &Device, DevNum, &BootProfile, &BootInfo, &IQS_ProfileIn, &IQS_ProfileOut, &StreamInfo); // Error handling if Status is not 0.

	outfile.open(filePath, ios::app | ios::binary);	// Open the file.
	if (!outfile)
	{
		cout << "Failed to open the file" << endl;
		exit(1);
	}

	// DSP 
	uint32_t TracePoints = 0;
	DSP_FFT_TypeDef DSP_FFT_ProfileIn; // FFT input configuration, including FFT size, window type, output spectrum cropping, etc.
	DSP_FFT_TypeDef DSP_FFT_ProfileOut; // FFT output configuration.
	double RBWRatio = 0;

	void* DSP = NULL;

	Status = DSP_Open(&DSP); // Start DSP function.

	Status = DSP_FFT_DeInit(&DSP_FFT_ProfileIn); // Initialize FFT parameters.

	DSP_FFT_ProfileIn.FFTSize = StreamInfo.PacketSamples;   // Set FFT size.
	DSP_FFT_ProfileIn.SamplePts = StreamInfo.PacketSamples; // Set number of valid sample points.

	Status = DSP_FFT_Configuration(&DSP, &DSP_FFT_ProfileIn, &DSP_FFT_ProfileOut, &TracePoints, &RBWRatio); // Configure FFT parameters.

    // Start multithreading.
	std::thread GetIQS(IQS_Get, Device, StreamInfo);  // Thread to acquire IQ data.
	std::thread FFT(IQS_FFT, DSP, StreamInfo);        // Thread to fetch IQ data from queue and perform FFT.
	std::thread Write(IQS_Write, Device, StreamInfo); // Thread to write data to file.

	GetIQS.join(); // Wait for IQ acquisition thread to finish.                  
	FFT.join();    // Wait for FFT thread to finish.
	Write.join();  // Wait for file write thread to finish.

	Status = Device_Close(&Device); 
	return 0;
}

// Thread for acquiring IQ data.
void IQS_Get(void* Device, IQS_StreamInfo_TypeDef StreamInfo)
{
	cout << "Getting data" << endl;
	int Status = 0;
	vector<int16_t> IQ(StreamInfo.PacketSamples * 2);	// Create array to store IQ data.

	uint32_t FFT_count = 500;

	IQStream_TypeDef IQStream;	                      // Container for IQ data packet, including IQ data and config info.
	uint32_t IQStreamSize = sizeof(IQStream_TypeDef); // Size in bytes of IQ data packet.
	vector<int8_t> IQ_FFT(1);						  // Temporary variable to hold IQStream.

	Status = IQS_BusTriggerStart(&Device); // Trigger the device. If using external trigger source, this is not needed.

	while (1)
	{
		for (int i = 0; i < FFT_count; i++)	// Perform FFT every FFT_count packets. With decimation=2, not fast enough to FFT every packet.
		{
			Status = IQS_GetIQStream_PM1(&Device, &IQStream);

			if (Status != APIRETVAL_NoError)
			{
				cout << "IQS_GetIQStream Status = " << Status << endl;
			}

			if (Status == APIRETVAL_NoError)
			{
				IQ_FFT.resize(IQStream.IQS_StreamInfo.PacketDataSize + IQStreamSize);	                                // Resize IQ_FFT to accommodate IQStream and its IQ data.
				memcpy(IQ_FFT.data(), &IQStream, IQStreamSize);			                                                // Deep copy IQStream to IQ_FFT.
				memcpy(IQ_FFT.data() + IQStreamSize, IQStream.AlternIQStream, IQStream.IQS_StreamInfo.PacketDataSize);	// Deep copy IQ data into the end of IQ_FFT.
				memcpy(IQ.data(), IQStream.AlternIQStream, IQStream.IQS_StreamInfo.PacketDataSize);	                    // Deep copy IQ data to IQ.
				Write_Mtx.lock();
				IQS_instant_queue.push(IQ);								                                                // Push acquired IQ data into queue.
				Write_Mtx.unlock();
				Write_flag = true;
				Write_start.notify_all();							                                                	// Notify write thread to stop waiting.
			}
		}
		FFT_Mtx.lock();
		IQS_Get_queue.push(IQ_FFT);
		FFT_Mtx.unlock();
		FFT_start.notify_all();
	}
}

// Thread to perform FFT on IQ data
void IQS_FFT(void* DSP, IQS_StreamInfo_TypeDef StreamInfo)
{
	cout << "Getting to do FFT" << endl;
	IQStream_TypeDef IQStream;                                          // Container for IQ data packet, including IQ data and config info.
	uint32_t IQStreamSize = sizeof(IQStream_TypeDef);                   // Size in bytes of IQ data packet.
	vector<int8_t> IQ_FFT(IQStreamSize + StreamInfo.PacketSamples * 2 * sizeof(int16_t));  // Container for IQ data packet and its IQ data.
	vector<double> Frequency(1);                                       // Create frequency array.
	vector<float> PowerSpec_dBm(1);                                    // Create power spectrum array.

	while (1)
	{
		if (IQS_Get_queue.empty())    // If queue is not empty.
		{
			FFT_start.wait(lck_FFT);
			continue;
		}

		// Fetch an element from the queue.
		FFT_Mtx.lock();
		IQ_FFT = IQS_Get_queue.front();
		IQS_Get_queue.pop();
		FFT_Mtx.unlock();
		
		// Assign the fetched element to IQStream.
		memcpy(&IQStream, IQ_FFT.data(), IQStreamSize);
		IQStream.AlternIQStream = IQ_FFT.data() + IQStreamSize;

		// Resize Frequency and PowerSpec_dBm to expected size.
		if (Frequency.size() < IQStream.IQS_StreamInfo.PacketSamples)
		{
			Frequency.resize(IQStream.IQS_StreamInfo.PacketSamples);
			PowerSpec_dBm.resize(IQStream.IQS_StreamInfo.PacketSamples);
		}

		// Perform FFT and convert data to spectrum.
		DSP_FFT_IQSToSpectrum(&DSP, &IQStream, Frequency.data(), PowerSpec_dBm.data());
	}
}

// Thread to write IQ data to file
void IQS_Write(void* Device, IQS_StreamInfo_TypeDef StreamInfo)
{
	// Container for each data packet fetched from queue. Each packet is 64968 bytes. With 16-bit precision = 2 bytes, and both I and Q channels, each has 16242 points.
	vector<int16_t> IQ_Write(StreamInfo.PacketSamples * 2);

	cout << "Writing data" << endl;

	while (1)
	{
		while (!Write_flag)
		{
			Write_start.wait(lck_Write);
		}

		if (!IQS_instant_queue.empty())										// If queue is not empty.
		{
			Write_Mtx.lock();
			IQ_Write = IQS_instant_queue.front();							// Fetch front data from queue.
			IQS_instant_queue.pop();
			Write_Mtx.unlock();
			for (uint32_t i = 0; i < StreamInfo.PacketSamples; i++) {
				outfile << IQ_Write[i * 2] << "\t" << IQ_Write[i * 2 + 1] << "\n";	// Write fetched data to file.
			}
		}
		else
		{
			std::this_thread::sleep_for(std::chrono::microseconds(1));
		}
	}
}
