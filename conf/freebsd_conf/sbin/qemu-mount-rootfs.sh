#!/bin/sh
set -xe
kind="${1:-smb}"
if [ -n "$(ls -A "/nfsroot")" ]; then
    echo "/nfsroot is not empty. Already mounted?"
    exit 0
fi

if [ "$kind" = "smb" ]; then
    # rootfs is provided as the fourth SMB mount, but we now have named smb mounts:
    mkdir -p /nfsroot && mount_smbfs -I 10.0.2.4 -N //10.0.2.4/rootfs /nfsroot
    # Also try mounting the non-cheri/hybrid/purecap rootfs
    if [ -n "$(ls -A "/outputroot")" ]; then
        echo "/outputroot is not empty. Already mounted?"
    else
        mkdir -p /outputroot && mount_smbfs -I 10.0.2.4 -N //10.0.2.4/output_root /outputroot
    fi
    test -L /nfsroot-nocheri || ln -sfnv "/outputroot/rootfs-riscv64" /nfsroot-nocheri
    test -L /nfsroot-hybrid  || ln -sfnv "/outputroot/rootfs-riscv64-hybrid" /nfsroot-hybrid
    test -L /nfsroot-purecap || ln -sfnv "/outputroot/rootfs-riscv64-purecap" /nfsroot-purecap
elif [ "$kind" = "nfs" ]; then
    mkdir -p /nfsroot && mount "10.0.2.2:/home/zyy/sigcheri/cheri/output/rootfs-riscv64-purecap" /nfsroot/
else
    echo "usage: $0 [smb|nfs]"
fi
# I previously mounted this in /rootfs but that is annoying because tab completion
# will give /root first. Use /nfsroot instead and add a symlink for the old path.
test -L /rootfs || ln -sfnv /nfsroot /rootfs
