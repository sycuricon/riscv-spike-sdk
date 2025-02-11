# RISCV should either be unset, or set to point to a directory that contains
# a toolchain install tree that was built via other means.
export RISCV ?= $(CURDIR)/toolchain
PATH := $(RISCV)/bin:$(PATH)
ISA ?= rv64imafdc_zifencei_zicsr_sscofpmf
ABI ?= lp64d
BL ?= bbl
BOARD ?= spike
CMAKE := cmake

topdir := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
topdir := $(topdir:/=)
srcdir := $(topdir)/repo
confdir := $(topdir)/conf
wrkdir := $(CURDIR)/build

toolchain_srcdir := $(srcdir)/riscv-gnu-toolchain
toolchain_wrkdir := $(wrkdir)/riscv-gnu-toolchain
toolchain_dest := $(CURDIR)/toolchain

buildroot_srcdir := $(srcdir)/buildroot
buildroot_initramfs_wrkdir := $(topdir)/rootfs/buildroot_initramfs
buildroot_initramfs_tar := $(buildroot_initramfs_wrkdir)/images/rootfs.tar
buildroot_initramfs_config := $(confdir)/buildroot_initramfs_config
buildroot_initramfs_sysroot_stamp := $(wrkdir)/.buildroot_initramfs_sysroot
buildroot_initramfs_sysroot := $(topdir)/rootfs/buildroot_initramfs_sysroot

linux_srcdir := $(srcdir)/linux
linux_wrkdir := $(wrkdir)/linux
linux_defconfig := $(confdir)/linux_defconfig

vmlinux := $(linux_wrkdir)/vmlinux
vmlinux_stripped := $(linux_wrkdir)/vmlinux-stripped
linux_image := $(linux_wrkdir)/arch/riscv/boot/Image

prot ?= none
KBUILD_CFLAGS_KERNEL-none     := -g -fexperimental-new-pass-manager
KBUILD_CFLAGS_KERNEL-fp       := $(KBUILD_CFLAGS_KERNEL-none) -mfpscan
KBUILD_CFLAGS_KERNEL-ra       := $(KBUILD_CFLAGS_KERNEL-none) -mllvm -ppp-rap
KBUILD_CFLAGS_KERNEL-non-ctrl := $(KBUILD_CFLAGS_KERNEL-none) -mrandcont
KBUILD_CFLAGS_KERNEL-full     := $(KBUILD_CFLAGS_KERNEL-none) -mfpscan -mrandcont -mllvm -ppp-rap

DTS ?= $(abspath conf/$(BOARD).dts)
pk_srcdir := $(srcdir)/riscv-pk
pk_wrkdir := $(wrkdir)/riscv-pk
bbl := $(pk_wrkdir)/bbl
pk  := $(pk_wrkdir)/pk

opensbi_srcdir := $(srcdir)/opensbi
opensbi_wrkdir := $(wrkdir)/opensbi
opensbi_platform := generic
opensbi_defconfig := $(confdir)/opensbi_defconfig
opensbi_wrkconfig := $(opensbi_wrkdir)/platform/$(opensbi_platform)/Kconfig/.config
fw_jump := $(opensbi_wrkdir)/platform/generic/firmware/fw_jump.elf

spike_srcdir := $(srcdir)/riscv-isa-sim
spike_wrkdir := $(wrkdir)/riscv-isa-sim
spike := $(toolchain_dest)/bin/spike

qemu_srcdir := $(srcdir)/riscv-gnu-toolchain/qemu
qemu_wrkdir := $(wrkdir)/qemu
qemu :=  $(toolchain_dest)/bin/qemu-system-riscv64

openocd_srcdir := $(srcdir)/riscv-openocd
openocd_wrkdir := $(wrkdir)/riscv-openocd
openocd := $(toolchain_dest)/bin/openocd

target_linux  := riscv64-unknown-linux-gnu
target_newlib := riscv64-unknown-elf

benchmark_srcdir	:= $(CURDIR)/benchmark
benchmark_wrkdir	:= $(wrkdir)/benchmark
benchmark_scripts   := $(benchmark_srcdir)/scripts
benchmark_patch		:= $(benchmark_srcdir)/patch

unixbench_srcdir := $(benchmark_srcdir)/byte-unixbenchmark/UnixBench
unixbench_wrkdir := $(benchmark_wrkdir)/UnixBench

libtirpc_srcdir  := $(benchmark_srcdir)/libtirpc
libtirpc_wrkdir  := $(wrkdir)/libtirpc
libtirpc_lib	 := $(buildroot_initramfs_sysroot)/lib/libtirpc.so

lmbench_srcdir 		:= $(benchmark_srcdir)/lmbench-3.0-a9
lmbench_wrkdir 		:= $(benchmark_wrkdir)/LmBench

regvault_srcdir		:= $(benchmark_srcdir)/regvault
regvault_wrkdir		:= $(benchmark_wrkdir)/regvault

.PHONY: all
all: spike

newlib: $(RISCV)/bin/$(target_newlib)-gcc


ifneq ($(RISCV),$(toolchain_dest))
$(RISCV)/bin/$(target_linux)-gcc:
	$(error The RISCV environment variable was set, but is not pointing at a toolchain install tree)
endif

$(toolchain_dest)/bin/$(target_linux)-gcc:
	mkdir -p $(toolchain_wrkdir)
	$(MAKE) -C $(linux_srcdir) O=$(toolchain_wrkdir) ARCH=riscv INSTALL_HDR_PATH=$(abspath $(toolchain_srcdir)/linux-headers) headers_install
	cd $(toolchain_wrkdir); $(toolchain_srcdir)/configure \
		--prefix=$(toolchain_dest) \
		--with-arch=$(ISA) \
		--with-abi=$(ABI) 
	$(MAKE) -C $(toolchain_wrkdir) linux
	# sed 's/^#define LINUX_VERSION_CODE.*/#define LINUX_VERSION_CODE 329226/' -i $(toolchain_dest)/sysroot/usr/include/linux/version.h

$(toolchain_dest)/bin/$(target_newlib)-gcc:
	mkdir -p $(toolchain_wrkdir)
	cd $(toolchain_wrkdir); $(toolchain_srcdir)/configure \
		--prefix=$(toolchain_dest) \
		--enable-multilib
	$(MAKE) -C $(toolchain_wrkdir) 

llvm_srcdir	 :=	$(toolchain_srcdir)/llvm
llvm_wrkdir	 :=	$(wrkdir)/llvm
llvm_sysroot :=	$(toolchain_dest)/sysroot
LLVM_VERSION :=  Release
clang        := $(toolchain_dest)/bin/clang
opt          := $(toolchain_dest)/bin/opt

.PHONY: llvm
$(clang): $(llvm_srcdir)
	mkdir -p $(llvm_wrkdir) $(toolchain_dest)
	cd $(llvm_wrkdir); $(CMAKE) -G Ninja -DLLVM_ENABLE_PROJECTS="clang" \
		-DCMAKE_BUILD_TYPE:String=$(LLVM_VERSION)  -DLLVM_ENABLE_ASSERTIONS=True \
		-DLLVM_USE_SPLIT_DWARF=True \
		-DLLVM_OPTIMIZED_TABLEGEN=True \
		-DCMAKE_INSTALL_PREFIX=$(toolchain_dest) \
		-DLLVM_DEFAULT_TARGET_TRIPLE=riscv64-unknown-linux-gnu \
		-DLLVM_TARGETS_TO_BUILD="RISCV" \
		-DDEFAULT_SYSROOT=$(llvm_sysroot) \
		$(llvm_srcdir)/llvm
	free -h
	$(CMAKE) --build $(llvm_wrkdir) --target install

llvm: $(clang)

$(buildroot_initramfs_wrkdir)/.config: $(buildroot_srcdir)
	rm -rf $(dir $@)
	mkdir -p $(dir $@)
	cp $(buildroot_initramfs_config) $@
	$(MAKE) -C $< RISCV=$(RISCV) PATH="$(PATH)" O=$(buildroot_initramfs_wrkdir) olddefconfig CROSS_COMPILE=riscv64-unknown-linux-gnu-

$(buildroot_initramfs_tar): $(buildroot_srcdir) $(buildroot_initramfs_wrkdir)/.config $(RISCV)/bin/$(target_linux)-gcc $(buildroot_initramfs_config)
	$(MAKE) -C $< RISCV=$(RISCV) PATH="$(PATH)" O=$(buildroot_initramfs_wrkdir)

.PHONY: buildroot_initramfs-menuconfig
buildroot-menuconfig: $(buildroot_initramfs_wrkdir)/.config $(buildroot_srcdir)
	$(MAKE) -C $(dir $<) O=$(buildroot_initramfs_wrkdir) menuconfig
	$(MAKE) -C $(dir $<) O=$(buildroot_initramfs_wrkdir) savedefconfig
	cp $(dir $<)/defconfig conf/buildroot_initramfs_config

$(buildroot_initramfs_sysroot): $(buildroot_initramfs_tar)
	mkdir -p $(buildroot_initramfs_sysroot)
	tar -xpf $< -C $(buildroot_initramfs_sysroot) --exclude ./dev --exclude ./usr/share/locale

$(linux_wrkdir)/.config: $(linux_defconfig) $(linux_srcdir) $(toolchain_dest)/bin/$(target_linux)-gcc
	mkdir -p $(dir $@)
	cp -p $< $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-unknown-linux-gnu- olddefconfig
	echo $(ISA)
	echo $(filter rv32%,$(ISA))
ifeq (,$(filter rv%c,$(ISA)))
	sed 's/^.*CONFIG_RISCV_ISA_C.*$$/CONFIG_RISCV_ISA_C=n/' -i $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-unknown-linux-gnu- olddefconfig
endif
ifeq ($(ISA),$(filter rv32%,$(ISA)))
	sed 's/^.*CONFIG_ARCH_RV32I.*$$/CONFIG_ARCH_RV32I=y/' -i $@
	sed 's/^.*CONFIG_ARCH_RV64I.*$$/CONFIG_ARCH_RV64I=n/' -i $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-unknown-linux-gnu- olddefconfig
endif

.PHONY: linux
# $(vmlinux): $(linux_srcdir) $(linux_wrkdir)/.config $(buildroot_initramfs_sysroot) 
# 	$(MAKE) -C $< O=$(linux_wrkdir) \
# 		CONFIG_INITRAMFS_SOURCE="$(confdir)/initramfs.txt $(buildroot_initramfs_sysroot)" \
# 		CONFIG_INITRAMFS_ROOT_UID=$(shell id -u) \
# 		CONFIG_INITRAMFS_ROOT_GID=$(shell id -g) \
# 		CROSS_COMPILE=riscv64-unknown-linux-gnu- \
# 		ARCH=riscv \
# 		all
$(vmlinux): $(linux_srcdir) $(buildroot_initramfs_sysroot) $(linux_wrkdir)/.config
	mkdir -p $(linux_wrkdir)
	$(MAKE) -C $< O=$(linux_wrkdir) \
		CONFIG_INITRAMFS_SOURCE="$(confdir)/initramfs.txt $(buildroot_initramfs_sysroot)" \
		CONFIG_INITRAMFS_ROOT_UID=$(shell id -u) \
		CONFIG_INITRAMFS_ROOT_GID=$(shell id -g) \
		CROSS_COMPILE=riscv64-unknown-linux-gnu- \
		ARCH=riscv \
		CC=clang \
		KBUILD_CFLAGS_KERNEL="$(KBUILD_CFLAGS_KERNEL-$(prot))" LLVM_IAS=1 \
		all

$(vmlinux_stripped): $(vmlinux)
	$(target_linux)-strip -o $@ $<

$(linux_image): $(vmlinux)
linux: $(linux_image)

linux-perf:$(linux_srcdir)
	mkdir -p $(linux_wrkdir)/perf
	$(MAKE) -C $</tools/perf O=$(linux_wrkdir)/perf \
		CROSS_COMPILE=riscv64-unknown-linux-gnu- \
		ARCH=riscv \
		all NO_LIBELF=1 NO_LIBTRACEEVENT=1 EXTRA_CFLAGS="-Wno-error=alloc-size -Wno-error=calloc-transposed-args"
	cp $(linux_wrkdir)/perf/perf $(buildroot_initramfs_sysroot)/bin

.PHONY: linux-menuconfig
linux-menuconfig: $(linux_wrkdir)/.config
	$(MAKE) -C $(linux_srcdir) O=$(dir $<) ARCH=riscv CROSS_COMPILE=riscv64-unknown-linux-gnu- menuconfig
	$(MAKE) -C $(linux_srcdir) O=$(dir $<) ARCH=riscv CROSS_COMPILE=riscv64-unknown-linux-gnu- savedefconfig
	# cp $(dir $<)/defconfig conf/linux_defconfig

$(bbl): $(pk_srcdir) $(vmlinux_stripped) $(DTS)
	rm -rf $(pk_wrkdir)
	mkdir -p $(pk_wrkdir)
	cd $(pk_wrkdir) && $</configure \
		--host=$(target_linux) \
		--with-payload=$(vmlinux_stripped) \
		--enable-logo \
		--with-logo=$(abspath conf/logo.txt) \
		--with-dts=$(DTS)
	CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(pk_wrkdir)


$(pk): $(pk_srcdir) $(RISCV)/bin/$(target_newlib)-gcc
	rm -rf $(pk_wrkdir)
	mkdir -p $(pk_wrkdir)
	cd $(pk_wrkdir) && $</configure \
		--host=$(target_newlib) \
		--prefix=$(abspath $(toolchain_dest))
	CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(pk_wrkdir)
	$(MAKE) -C $(pk_wrkdir) install

$(fw_jump): $(opensbi_srcdir) $(linux_image) $(RISCV)/bin/$(target_linux)-gcc
	mkdir -p $(opensbi_wrkdir)
	$(MAKE) -C $(opensbi_srcdir) FW_TEXT_START=0x80000000 FW_PAYLOAD_PATH=$(linux_image) PLATFORM=$(opensbi_platform)\
		O=$(opensbi_wrkdir) CROSS_COMPILE=riscv64-unknown-linux-gnu-

.PHONY: opensbi-menuconfig
opensbi-menuconfig:
	rm -rf $(opensbi_wrkdir)
	mkdir -p $(opensbi_wrkdir)
	$(MAKE) -C $(opensbi_srcdir) PLATFORM=$(opensbi_platform) O=$(opensbi_wrkdir) CROSS_COMPILE=riscv64-unknown-linux-gnu- menuconfig
	$(MAKE) -C $(opensbi_srcdir) PLATFORM=$(opensbi_platform) O=$(opensbi_wrkdir) CROSS_COMPILE=riscv64-unknown-linux-gnu- savedefconfig

$(spike): $(spike_srcdir) 
	rm -rf $(spike_wrkdir)
	mkdir -p $(spike_wrkdir)
	mkdir -p $(dir $@)
	cd $(spike_wrkdir) && $</configure \
		--prefix=$(dir $(abspath $(dir $@))) 
	$(MAKE) -C $(spike_wrkdir)
	$(MAKE) -C $(spike_wrkdir) install
	touch -c $@

$(qemu): $(qemu_srcdir)
	rm -rf $(qemu_wrkdir)
	mkdir -p $(qemu_wrkdir)
	mkdir -p $(dir $@)
	cd $(qemu_wrkdir) && $</configure \
		--disable-docs \
		--prefix=$(dir $(abspath $(dir $@))) \
		--target-list=riscv64-linux-user,riscv64-softmmu
	$(MAKE) -C $(qemu_wrkdir)
	$(MAKE) -C $(qemu_wrkdir) install
	touch -c $@

$(openocd): $(openocd_srcdir)
	rm -rf $(openocd_wrkdir)
	mkdir -p $(openocd_wrkdir)
	mkdir -p $(dir $@)
	cd $(openocd_srcdir) && $</bootstrap
	cd $(openocd_wrkdir) && $</configure \
		--enable-remote-bitbang \
		--prefix=$(dir $(abspath $(dir $@)))
	$(MAKE) -C $(openocd_wrkdir)
	$(MAKE) -C $(openocd_wrkdir) install
	touch -c $@

$(unixbench_wrkdir):$(unixbench_srcdir)
	rm -rf $(unixbench_wrkdir) 
	mkdir -p $(unixbench_wrkdir) 
	make -C $(unixbench_srcdir) clean
	make -C $(unixbench_srcdir)
	cp $(unixbench_srcdir)/pgms/* $(unixbench_wrkdir)
	cp $(unixbench_srcdir)/testdir/sort.src $(unixbench_wrkdir)

$(libtirpc_lib):$(libtirpc_srcdir)
	rm -rf $(libtirpc_wrkdir)
	mkdir -p $(libtirpc_wrkdir)
	cd $(libtirpc_wrkdir); $(libtirpc_srcdir)/configure --host=riscv64-unknown-linux-gnu --prefix=$(toolchain_dest)/sysroot/usr --disable-gssapi
	make -C $(libtirpc_wrkdir)
	make -C $(libtirpc_wrkdir) install
	cd $(libtirpc_wrkdir); $(libtirpc_srcdir)/configure --host=riscv64-unknown-linux-gnu --prefix=$(buildroot_initramfs_sysroot) --disable-gssapi
	make -C $(libtirpc_wrkdir) install

$(lmbench_wrkdir): $(lmbench_srcdir) $(libtirpc_lib)
	rm -rf $(lmbench_wrkdir) 
	mkdir -p $(lmbench_wrkdir) 
	make -C $(lmbench_srcdir) clean
	make -C $(lmbench_srcdir)
	cp $(lmbench_srcdir)/bin/riscv-linux/* $(lmbench_wrkdir)

$(regvault_wrkdir): $(regvault_srcdir) $(vmlinux)
	rm -rf $(regvault_wrkdir)
	mkdir -p $(regvault_wrkdir)
	make -C $(regvault_srcdir) clean
	make -C $(regvault_srcdir)
	cp $(regvault_srcdir)/rgvlt_test.ko $(regvault_wrkdir)

.PHONY: buildroot_initramfs_sysroot vmlinux bbl fw_jump openocd
buildroot_initramfs_sysroot: $(buildroot_initramfs_sysroot)
vmlinux: $(vmlinux)
bbl: $(bbl)
fw_image: $(fw_jump)
openocd: $(openocd)

.PHONY: benchmark benchmark_patch
benchmark: $(unixbench_wrkdir) $(lmbench_wrkdir) $(regvault_wrkdir) $(buildroot_initramfs_sysroot)
	cp -r $(unixbench_wrkdir) $(buildroot_initramfs_sysroot)/
	cp -r $(lmbench_wrkdir) $(buildroot_initramfs_sysroot)/
	cp -r $(regvault_wrkdir) $(buildroot_initramfs_sysroot)/

benchmark_patch:$(benchmark_patch)
	cd $(unixbench_srcdir); git apply $(benchmark_patch)/UnixBench.patch
	cd $(lmbench_srcdir); git apply $(benchmark_patch)/LmBench.patch

.PHONY: clean mrproper
clean:
	rm -rf -- $(wrkdir)

mrproper:
	rm -rf -- $(wrkdir) $(toolchain_dest) $(topdir)/rootfs

.PHONY: spike spike-debug qemu qemu-debug

ifeq ($(BL),opensbi)
spike: $(fw_jump) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm --kernel $(linux_image) $(fw_jump)

spile-debug: $(bbl) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm -H --rbb-port=9824 --kernel $(linux_image) $(fw_jump)

qemu: $(qemu) $(fw_jump)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(fw_jump) -kernel $(linux_image)

qemu-debug: $(qemu) $(fw_jump)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(fw_jump) -kernel $(linux_image) -s -S

else ifeq ($(BL),bbl)
spike: $(bbl) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm $(bbl)

spile-debug: $(bbl) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm -H --rbb-port=9824 $(bbl)

qemu: $(qemu) $(bbl)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(bbl)

qemu-debug: $(qemu) $(bbl)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(bbl) -s -S
endif

SD_CARD ?= /dev/sdb
.PHONY: make_sd
make_sd: $(bbl)
	sudo dd if=$(bbl).bin of=$(SD_CARD)1 bs=4096
