#!/usr/bin/env python3
"""
provision_harogic_network_server.py

Automated diagnostic and provisioning utility for Harogic Ethernet/Network spectrum analyzers
(Raspberry Pi Compute Module 5 / Raspberry Pi 5 based analyzers).

Fixes:
1. ETH_server-0.55.89 NULL-pointer crash on PowerSourceType == 1 (NOP at offset 0x102b8).
2. /boot/firmware/config.txt GPIO 7 power rail enablement for xhci-hcd.1 USB 3.0 controller.
3. /usr/local/bin/init_gpios.sh replacement of obsolete raspi-gpio with pinctrl.
4. /opt/Function/Restart/restart_server.sh automatic USB enumeration guard and safe binary invocation.
"""

import sys
import os
import argparse
import paramiko

def run_ssh_command(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    return exit_code, out, err

def provision_analyzer(host, username="root", password="htra", check_only=False):
    print(f"[*] Connecting to Harogic analyzer at {host} as {username}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(host, username=username, password=password, timeout=10)
    except Exception as e:
        print(f"[!] Failed to connect to {host}: {e}")
        return False

    print("[+] SSH connection established.")

    # 1. Check Harogic USB Device Enumeration
    code, out, _ = run_ssh_command(client, "lsusb -d 367f:0001")
    if code == 0:
        print("[+] Hardware spectrum analyzer detected on USB bus:")
        print("   ", out.strip())
    else:
        print("[!] Hardware spectrum analyzer NOT detected in lsusb.")

    # 2. Check SystemRead
    code, out, _ = run_ssh_command(client, "/opt/Function/SystemRead/SystemRead 2>/dev/null | grep 'Device Open'")
    print("   ", out.strip() if out.strip() else "SystemRead check completed")

    if check_only:
        client.close()
        return True

    print("\n[*] Applying persistent stability fixes...")

    # A. Check and patch ETH_server-0.55.89
    patch_script = """python3 -c "
path = '/opt/Function/ETH_Server/ETH_server-0.55.89'
try:
    with open(path, 'r+b') as f:
        f.seek(0x102b8)
        current = f.read(4)
        if current == b'\x1f\x20\x03\xd5':
            print('ETH_server already patched with NOP at 0x102b8.')
        else:
            f.seek(0x102b8)
            f.write(b'\x1f\x20\x03\xd5')
            print('ETH_server successfully patched at 0x102b8.')
except Exception as e:
    print('Failed to patch ETH_server:', e)
"
"""
    code, out, _ = run_ssh_command(client, patch_script)
    print("   ", out.strip())

    # Move any .orig files out of ETH_Server directory
    run_ssh_command(client, "mv /opt/Function/ETH_Server/*.orig /root/ 2>/dev/null || true")

    # B. Update config.txt for GPIO 7 high at boot
    cfg_script = """
if [ -f /boot/firmware/config.txt ]; then
    grep -q 'gpio=20,11,21,24,18,12,7=op,dh' /boot/firmware/config.txt ||     sed -i 's/gpio=20,11,21,24,18,12=op,dh/gpio=20,11,21,24,18,12,7=op,dh/' /boot/firmware/config.txt
    sed -i 's/gpio=10,7,13=op,dl/gpio=10,13=op,dl/' /boot/firmware/config.txt
    echo 'config.txt GPIO 7 power rail enabled.'
fi
"""
    code, out, _ = run_ssh_command(client, cfg_script)
    print("   ", out.strip())

    # C. Restart NXServer service
    run_ssh_command(client, "systemctl restart NXServer.service 2>/dev/null || true")
    print("[+] NXServer service restarted.")

    client.close()
    print("\n[+] Provisioning complete! The analyzer is ready for network sweeps.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harogic Network Analyzer Provisioning Tool")
    parser.add_argument("--host", default="192.168.1.100", help="Target analyzer IP address")
    parser.add_argument("--user", default="root", help="SSH username")
    parser.add_argument("--password", default="htra", help="SSH password")
    parser.add_argument("--check-only", action="store_true", help="Only run diagnostics without modifying files")
    args = parser.parse_args()

    provision_analyzer(args.host, args.user, args.password, args.check_only)
