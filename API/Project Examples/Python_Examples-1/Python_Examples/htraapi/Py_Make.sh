
A=`whoami`

if [ $A != 'root' ]; then
   echo "You have to be root to run this script"
   exit 1;
fi

file=$( ls libhtraapi.so.* )
file=$( basename $file )
version=${file#*so.}
majornum=${version%%.*}

ln -sf libhtraapi.so.${version} libhtraapi.so.${majornum}
ln -sf libhtraapi.so.${majornum} libhtraapi.so

ln -sf libusb-1.0.so.0.2.0 libusb-1.0.so.0
ln -sf libusb-1.0.so.0 libusb-1.0.so
