#!/bin/sh
set -xe
kind="${1:-smb}"
if [ -n "$(ls -A "/home/zyy/sigcheri/cheri")" ]; then
    echo "/home/zyy/sigcheri/cheri is not empty. Already mounted?"
    exit 0
fi

if [ "$kind" = "smb" ]; then
    # rootfs is provided as the first SMB mount, but we now have named smb mounts:
    # mkdir -p /nfsroot && mount_smbfs -I 10.0.2.4 -N //10.0.2.4/qemu1 /nfsroot
    mkdir -p "/home/zyy/sigcheri/cheri" && mount_smbfs -I 10.0.2.4 -N //10.0.2.4/source_root "/home/zyy/sigcheri/cheri"
elif [ "$kind" = "nfs" ]; then
    mkdir -p "/home/zyy/sigcheri/cheri" && mount -o ro "10.0.2.2:/home/zyy/sigcheri/cheri" "/home/zyy/sigcheri/cheri"
else
    echo "usage: $0 [smb|nfs]"
fi
