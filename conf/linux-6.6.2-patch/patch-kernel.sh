#~/bin/sh
declare -A map
linux_path=$1
map["entry.S"]=$linux_path"/arch/riscv/kernel/entry.S"
map["head.S"]=$linux_path"/arch/riscv/kernel/head.S"
map["vmlinux.lds.S"]=$linux_path"/arch/riscv/kernel/vmlinux.lds.S"
map["riscv-kernel-Makefile"]=$linux_path"/arch/riscv/kernel/Makefile"
map["riscv-kernel-Kconfig"]=$linux_path"/arch/riscv/Kconfig"
map["context.c"]=$linux_path"/arch/riscv/mm/context.c"
map["init.c"]=$linux_path"/arch/riscv/mm/init.c"
map["smpboot.c"]=$linux_path"/arch/riscv/kernel/smpboot.c"
map["PEC.h"]=$linux_path"/arch/riscv/include/asm/PEC.h"
map["pgalloc.h"]=$linux_path"/arch/riscv/include/asm/pgalloc.h"
map["pgtable.h"]=$linux_path"/include/linux/pgtable.h"
map["main.c"]=$linux_path"/init/main.c"
map["fork.c"]=$linux_path"/kernel/fork.c"
map["fault.c"]=$linux_path"/arch/riscv/mm/fault.c"
map["aes_generic.c"]=$linux_path"/crypto/aes_generic.c"
map["aes.h"]=$linux_path"/include/crypto/aes.h"
map["lib-aes.c"]=$linux_path"/lib/crypto/aes.c"
map["mpi-pow.c"]=$linux_path"/lib/crypto/mpi/mpi-pow.c"
map["rsa.c"]=$linux_path"/crypto/rsa.c"
map["module.c"]=$linux_path"/kernel/module.c"
map["thread_info.h"]=$linux_path"/arch/riscv/include/asm/thread_info.h"
map["asm-offsets.c"]=$linux_path"/arch/riscv/kernel/asm-offsets.c"
map["tcp_input.c"]=$linux_path"/net/ipv4/tcp_input.c"
map["tcp_ipv4.c"]=$linux_path"/net/ipv4/tcp_ipv4.c"
map["sock.c"]=$linux_path"/net/core/sock.c"
map["sock.h"]=$linux_path"/include/net/sock.h"
map["PPPatch.c"]=$linux_path"/arch/riscv/kernel/PPPatch.c"

for file in ${!map[*]}; do
	cp $file ${map[$file]}
	#cp ${map[$file]} $file
done