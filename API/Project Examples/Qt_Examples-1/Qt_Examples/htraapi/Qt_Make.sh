
A=`whoami`
if [ $A != 'root' ]; then
    echo "You have to be root to run this script"
    exit 1
fi

# Extract the version info of libhtraapi
file=$(ls libhtraapi.so.* | grep -v "\\.so$" | head -n 1)
file=$(basename $file)
version=${file#*so.}
majornum=${version%%.*}

# Create symlinks for libhtraapi only if they don't already exist
[ ! -e libhtraapi.so.${majornum} ] && ln -sf libhtraapi.so.${version} libhtraapi.so.${majornum}
[ ! -e libhtraapi.so ] && ln -sf libhtraapi.so.${majornum} libhtraapi.so

# Create symlinks for libusb
[ ! -e libusb-1.0.so.0 ] && ln -sf libusb-1.0.so.0.2.0 libusb-1.0.so.0
[ ! -e libusb-1.0.so ] && ln -sf libusb-1.0.so.0 libusb-1.0.so

# Create symlinks for libgomp
#[ ! -e libgomp.so.1 ] && ln -sf libgomp.so.1.0.0 libgomp.so.1
#[ ! -e libgomp.so ] && ln -sf libgomp.so.1 libgomp.so

echo "All necessary symlinks created (or already exist)."

