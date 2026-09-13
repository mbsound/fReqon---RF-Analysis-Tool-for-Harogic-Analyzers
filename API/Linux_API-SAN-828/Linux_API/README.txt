1. Run the .sh file, install the required configuration files, .so library files and .h header files.
Refer to the following command:
sudo sh ./install_htraapi_lib.sh

2. Some versions of Linux systems require a declaration after installing a new library.
Run the "sudo ldconfig" command to ensure that the system correctly knows that the new lib library has been installed.