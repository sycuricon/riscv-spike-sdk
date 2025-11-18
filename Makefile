# RISCV should either be unset, or set to point to a directory that contains
# a toolchain install tree that was built via other means.
RISCV ?= $(CURDIR)/toolchain
PATH := $(RISCV)/bin:$(PATH)
ISA ?= rv64imafdc_zifencei_zicsr
ABI ?= lp64d
BL ?= opensbi
BOARD ?= spike
CMAKE := cmake

topdir := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
topdir := $(topdir:/=)
srcdir := $(topdir)/repo
confdir := $(topdir)/conf
wrkdir := $(CURDIR)/build
scriptdir := $(topdir)/scripts
benchdir := $(topdir)/benchmark

toolchain_dest := $(CURDIR)/toolchain

llvm_srcdir	 :=	$(srcdir)/llvm-project
llvm_wrkdir	 :=	$(wrkdir)/llvm-project
llvm_sysroot :=	$(toolchain_dest)/sysroot
LLVM_VERSION :=  Release

freebsd_srcdir := $(srcdir)/freebsd
freebsd_wrkdir := $(wrkdir)/freebsd
freebsd_wrkdir_legacy := $(freebsd_wrkdir)/$(freebsd_srcdir)/riscv.riscv64/tmp/legacy
freebsd_rootfs := $(topdir)/rootfs/freebsd_sysroot
freebsd_rootfs_img := $(freebsd_rootfs).img
freebsd_kernel := $(freebsd_rootfs)/boot/kernel/kernel
freebsd_bench := $(freebsd_rootfs)/opt

lmbench_srcdir := $(benchdir)/lmbench
unixbench_srcdir := $(benchdir)/unixbench/UnixBench

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

DTS ?= $(abspath conf/$(BOARD).dts)
pk_srcdir := $(srcdir)/riscv-pk
pk_wrkdir := $(wrkdir)/riscv-pk
bbl := $(pk_wrkdir)/bbl
pk  := $(pk_wrkdir)/pk

opensbi_srcdir := $(srcdir)/opensbi
opensbi_wrkdir := $(wrkdir)/opensbi
fw_jump := $(opensbi_wrkdir)/platform/generic/firmware/fw_jump.elf

spike_srcdir := $(srcdir)/riscv-isa-sim
spike_wrkdir := $(wrkdir)/riscv-isa-sim
spike := $(toolchain_dest)/bin/spike

qemu_srcdir := $(srcdir)/qemu
qemu_wrkdir := $(wrkdir)/qemu
qemu :=  $(toolchain_dest)/bin/qemu-system-riscv64

openocd_srcdir := $(srcdir)/riscv-openocd
openocd_wrkdir := $(wrkdir)/riscv-openocd
openocd := $(toolchain_dest)/bin/openocd

.PHONY: all
all: $(vmlinux)

.PHONY: llvm
$(toolchain_dest)/bin/clang: $(llvm_srcdir)
	mkdir -p $(llvm_wrkdir) $(toolchain_dest)
	cd $(llvm_wrkdir); $(CMAKE) -G Ninja -DLLVM_ENABLE_PROJECTS="clang;lld" \ \
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
llvm: $(toolchain_dest)/bin/clang

FREEBSD_ENV := MAKEOBJDIRPREFIX=$(freebsd_wrkdir) \
	X_COMPILER_TYPE=clang \
	CC=/usr/bin/clang \
	CXX=/usr/bin/clang++ \
	CPP=/usr/bin/clang-cpp-18 \
	STRIPBIN=/usr/bin/strip \
	XCC=$(toolchain_dest)/bin/clang \
	XCXX=$(toolchain_dest)/bin/clang++ \
	XCPP=$(toolchain_dest)/bin/clang-cpp \
	XLD=$(toolchain_dest)/bin/ld.lld

FREEBSD_TARGET := TARGET=riscv \
	TARGET_ARCH=riscv64 \
	TARGET_CPUTYPE= 

FREEBSD_WNO := "-Wno-unterminated-string-initialization -Wno-switch \
	-Wno-cast-function-type-mismatch -Wno-unused -Wno-format -Wno-parentheses \
	-Wno-string-plus-int -Wno-address-of-packed-member -Wno-tautological-pointer-compare\
	-Wno-implicit-enum-enum-cast -Wno-empty-body -Wno-incompatible-pointer-types-discards-qualifiers \
	-Wno-tautological-constant-out-of-range-compare -Wno-uninitialized"

FREEBSD_TOOL := LD=$(toolchain_dest)/bin/ld.lld \
	AR=$(toolchain_dest)/bin/llvm-ar \
	NM=$(toolchain_dest)/bin/llvm-nm \
	SIZE=$(toolchain_dest)/bin/llvm-size \
	STRIPBIN=$(toolchain_dest)/bin/llvm-strip \
	STRINGS=$(toolchain_dest)/bin/llvm-strings \
	OBJCOPY=$(toolchain_dest)/bin/llvm-objcopy \
	RANLIB=$(toolchain_dest)/bin/llvm-ranlib \
	LLVM_LINK=$(toolchain_dest)/bin/llvm-link \
	XLD=$(toolchain_dest)/bin/ld.lld \
	XAR=$(toolchain_dest)/bin/llvm-ar \
	XNM=$(toolchain_dest)/bin/llvm-nm \
	XSIZE=$(toolchain_dest)/bin/llvm-size \
	XSTRIPBIN=$(toolchain_dest)/bin/llvm-strip \
	XSTRINGS=$(toolchain_dest)/bin/llvm-strings \
	XOBJCOPY=$(toolchain_dest)/bin/llvm-objcopy \
	XRANLIB=$(toolchain_dest)/bin/llvm-ranlib \
	XLLVM_LINK=$(toolchain_dest)/bin/llvm-link

FREEBSD_OPT := -DDB_FROM_SRC -DI_REALLY_MEAN_NO_CLEAN -DNO_ROOT -DBUILD_WITH_STRICT_TMPPATH -DWITHOUT_EFI \
	-DWITHOUT_CLEAN -DWITH_TESTS -DWITHOUT_INIT_ALL_ZERO -DWITHOUT_INIT_ALL_PATTERN \
	-DWITHOUT_MAN -DWITHOUT_MAIL -DWITH_DISK_IMAGE_TOOLS_BOOTSTRAP -DWITHOUT_PROFILE \
	-DWITHOUT_OFED -DWITH_MALLOC_PRODUCTION -DWITHOUT_GCC -DWITHOUT_CLANG -DWITHOUT_LLD \
	-DWITHOUT_LLDB -DWITHOUT_GCC_BOOTSTRAP -DWITHOUT_CLANG_BOOTSTRAP -DWITHOUT_LLD_BOOTSTRAP \
	-DWITHOUT_LIB32 -DWITH_ELFTOOLCHAIN_BOOTSTRAP -DWITH_TOOLCHAIN -DWITHOUT_BINUTILS_BOOTSTRAP

FREEBSD_ARGS := $(FREEBSD_TARGET) \
	CWARNFLAGS.clang=$(FREEBSD_WNO) \
	$(FREEBSD_TOOL) \
	$(FREEBSD_OPT) -s -de

buildworld: $(freebsd_srcdir) $(toolchain_dest)/bin/clang
	mkdir -p $(freebsd_wrkdir)
	cd $(freebsd_srcdir) && env $(FREEBSD_ENV) \
	nice $(freebsd_srcdir)/tools/build/make.py -j$(shell nproc) buildworld \
		$(FREEBSD_ARGS)

buildkernel: $(freebsd_wrkdir)
	cp $(confdir)/QEMU $(freebsd_srcdir)/sys/riscv/conf/QEMU
	cd $(freebsd_srcdir) && env $(FREEBSD_ENV) \
	nice $(freebsd_srcdir)/tools/build/make.py -j$(shell nproc) buildkernel \
		'KERNCONF=QEMU' DEBUG=-g $(FREEBSD_ARGS)

installworld: $(freebsd_wrkdir)
	rm -rf $(freebsd_rootfs)/METALOG.world
	cd $(freebsd_srcdir) && env $(FREEBSD_ENV) \
		DESTDIR=$(freebsd_rootfs) METALOG=$(freebsd_rootfs)/METALOG.world \
	nice $(freebsd_srcdir)/tools/build/make.py -j$(shell nproc) installworld \
		$(FREEBSD_ARGS) DESTDIR=$(freebsd_rootfs)

installkernel: $(freebsd_wrkdir)
	rm -rf $(freebsd_rootfs)/METALOG.kernel
	cd $(freebsd_srcdir) && env $(FREEBSD_ENV) \
		DESTDIR=$(freebsd_rootfs) METALOG=$(freebsd_rootfs)/METALOG.kernel \
	nice $(freebsd_srcdir)/tools/build/make.py -j$(shell nproc) installkernel \
		'KERNCONF=QEMU' DEBUG=-g $(FREEBSD_ARGS) DESTDIR=$(freebsd_rootfs)

distribution: $(freebsd_wrkdir)
	cd $(freebsd_srcdir) && env $(FREEBSD_ENV) \
		DESTDIR=$(freebsd_rootfs) METALOG=$(freebsd_rootfs)/METALOG.world \
	nice $(freebsd_srcdir)/tools/build/make.py -j$(shell nproc) distribution \
		$(FREEBSD_ARGS) DESTDIR=$(freebsd_rootfs)

.PHONY: disk-image
$(freebsd_rootfs).img : $(freebsd_rootfs)
	cp -r $(confdir)/freebsd_conf/* $(freebsd_rootfs)
	python3 $(scriptdir)/get_mainfest.py $(freebsd_rootfs) $(freebsd_wrkdir)/METALOG.custom
	cd $(freebsd_rootfs) && $(freebsd_wrkdir_legacy)/bin/makefs -t ffs \
		-o version=2,label=root -o softupdates=1 -Z -b 2g -f 200k -R 4m -M 256m \
		-B le -N $(freebsd_rootfs)/etc  \
		$(freebsd_rootfs).root.img $(freebsd_wrkdir)/METALOG.custom
	cd $(freebsd_rootfs) && $(freebsd_wrkdir_legacy)/bin/mkimg -s gpt \
		-p efi:=$(freebsd_rootfs).efi.img \
		-p freebsd-ufs:=$(freebsd_rootfs).root.img \
		-p freebsd-swap/swap::2G \
		-o $(freebsd_rootfs).img
	rm -f $(freebsd_rootfs).root.img
	$(toolchain_dest)/bin/qemu-img info $(freebsd_rootfs).img
disk-image: $(freebsd_rootfs).img

.PHONY: lmbench
lmbench: $(lmbench_srcdir)
	make -C $(lmbench_srcdir) build \
		CC=$(toolchain_dest)/bin/clang \
		AR=$(toolchain_dest)/bin/llvm-ar \
		OS=riscv-FreeBSD \
		CFLAGS="-target riscv64-unknown-freebsd16 \
			--sysroot=$(freebsd_rootfs) -B$(toolchain_dest)/bin \
			-march=$(ISA) -mabi=$(ABI) -mno-relax -O3 \
			-Wno-error=unused-command-line-argument -Werror=implicit-function-declaration \
			-Werror=format -Werror=incompatible-pointer-types -Werror=pass-failed \
			-Werror=undefined-internal" \
		LDFLAGS="-target riscv64-unknown-freebsd16 \
			--sysroot=$(freebsd_rootfs) -B$(toolchain_dest)/bin \
			-march=$(ISA) -mabi=$(ABI) -mno-relax -fuse-ld=lld \
			--ld-path=$(toolchain_dest)/bin/ld.lld"
	mkdir -p $(freebsd_bench)/lmbench
	cp -r $(lmbench_srcdir)/bin/riscv-FreeBSD/* $(freebsd_bench)/lmbench/

.PHONY: unixbench
unixbench: $(unixbench_srcdir)
	make -C $(unixbench_srcdir) \
		CC=$(toolchain_dest)/bin/clang OSNAME=freebsd ARCHNAME=$(ISA) \
		CFLAGS="-target riscv64-unknown-freebsd16 \
			--sysroot=$(freebsd_rootfs) -B$(toolchain_dest)/bin \
			-march=$(ISA) -mabi=$(ABI) -mno-relax -O3 \
			-Wno-error=unused-command-line-argument -Werror=implicit-function-declaration \
			-Werror=format -Werror=incompatible-pointer-types -Werror=pass-failed \
			-Werror=undefined-internal" \
		LDFLAGS="-target riscv64-unknown-freebsd16 \
			--sysroot=$(freebsd_rootfs) -B$(toolchain_dest)/bin \
			-march=$(ISA) -mabi=$(ABI) -mno-relax -fuse-ld=lld \
			--ld-path=$(toolchain_dest)/bin/ld.lld"

$(buildroot_initramfs_wrkdir)/.config: $(buildroot_srcdir)
	rm -rf $(dir $@)
	mkdir -p $(dir $@)
	cp $(buildroot_initramfs_config) $@
	$(MAKE) -C $< RISCV=$(RISCV) PATH="$(PATH)" O=$(buildroot_initramfs_wrkdir) olddefconfig CROSS_COMPILE=riscv64-unknown-linux-gnu-

$(buildroot_initramfs_tar): $(buildroot_srcdir) $(buildroot_initramfs_wrkdir)/.config $(buildroot_initramfs_config)
	$(MAKE) -C $< RISCV=$(RISCV) PATH="$(PATH)" O=$(buildroot_initramfs_wrkdir)

.PHONY: buildroot_initramfs-menuconfig
buildroot-menuconfig: $(buildroot_initramfs_wrkdir)/.config $(buildroot_srcdir)
	$(MAKE) -C $(dir $<) O=$(buildroot_initramfs_wrkdir) menuconfig
	$(MAKE) -C $(dir $<) O=$(buildroot_initramfs_wrkdir) savedefconfig
	cp $(dir $<)/defconfig conf/buildroot_initramfs_config

$(buildroot_initramfs_sysroot): $(buildroot_initramfs_tar)
	mkdir -p $(buildroot_initramfs_sysroot)
	tar -xpf $< -C $(buildroot_initramfs_sysroot) --exclude ./dev --exclude ./usr/share/locale

$(linux_wrkdir)/.config: $(linux_defconfig) $(linux_srcdir) $(toolchain_dest)/bin/clang
	mkdir -p $(dir $@)
	cp -p $< $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- olddefconfig
	echo $(ISA)
	echo $(filter rv32%,$(ISA))
ifeq (,$(filter rv%c,$(ISA)))
	sed 's/^.*CONFIG_RISCV_ISA_C.*$$/CONFIG_RISCV_ISA_C=n/' -i $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- olddefconfig
endif
ifeq ($(ISA),$(filter rv32%,$(ISA)))
	sed 's/^.*CONFIG_ARCH_RV32I.*$$/CONFIG_ARCH_RV32I=y/' -i $@
	sed 's/^.*CONFIG_ARCH_RV64I.*$$/CONFIG_ARCH_RV64I=n/' -i $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- olddefconfig
endif

$(vmlinux): $(linux_srcdir) $(linux_wrkdir)/.config $(buildroot_initramfs_sysroot) 
	$(MAKE) -C $< O=$(linux_wrkdir) \
		CONFIG_INITRAMFS_SOURCE="$(confdir)/initramfs.txt $(buildroot_initramfs_sysroot)" \
		CONFIG_INITRAMFS_ROOT_UID=$(shell id -u) \
		CONFIG_INITRAMFS_ROOT_GID=$(shell id -g) \
		CROSS_COMPILE=riscv64-unknown-linux-gnu- \
		ARCH=riscv \
		HOSTCC=gcc \
		HOSTCXX=g++ \
		CC=$(toolchain_dest)/bin/clang \
		AS=$(toolchain_dest)/bin/clang \
		CXX=$(toolchain_dest)/bin/clang++ \
		LD=$(toolchain_dest)/bin/ld.lld \
		AR=$(toolchain_dest)/bin/llvm-ar \
		NM=$(toolchain_dest)/bin/llvm-nm \
		OBJCOPY=$(toolchain_dest)/bin/llvm-objcopy \
		OBJDUMP=$(toolchain_dest)/bin/llvm-objdump \
		READELF=$(toolchain_dest)/bin/readelf \
		STRIP=$(toolchain_dest)/bin/llvm-strip \
		RANLIB=$(toolchain_dest)/bin/llvm-ranlib \
		LLVM=1 LLVM_IAS=1 \
		all

$(vmlinux_stripped): $(vmlinux)
	$(toolchain_dest)/bin/llvm-strip -o $@ $<

$(linux_image): $(vmlinux)

.PHONY: linux-menuconfig
linux-menuconfig: $(linux_wrkdir)/.config
	$(MAKE) -C $(linux_srcdir) O=$(dir $<) ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- menuconfig
	$(MAKE) -C $(linux_srcdir) O=$(dir $<) ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- savedefconfig
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

$(fw_jump): $(opensbi_srcdir) $(linux_image) $(RISCV)/bin/clang
	rm -rf $(opensbi_wrkdir)
	mkdir -p $(opensbi_wrkdir)
	$(MAKE) -C $(opensbi_srcdir) FW_TEXT_START=0x80000000 \
		FW_PAYLOAD_PATH=$(linux_image) PLATFORM=generic O=$(opensbi_wrkdir) CROSS_COMPILE=riscv64-linux-gnu- \
		LLVM=$(toolchain_dest)/bin/

.PHONY: spike
$(spike): $(spike_srcdir) 
	rm -rf $(spike_wrkdir)
	mkdir -p $(spike_wrkdir)
	mkdir -p $(dir $@)
	cd $(spike_wrkdir) && $</configure \
		--prefix=$(dir $(abspath $(dir $@))) 
	$(MAKE) -C $(spike_wrkdir)
	$(MAKE) -C $(spike_wrkdir) install
	touch -c $@
spike: $(spike)

.PHONY: qemu
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
qemu: $(qemu)

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


.PHONY: buildroot_initramfs_sysroot vmlinux bbl fw_jump openocd
buildroot_initramfs_sysroot: $(buildroot_initramfs_sysroot)
vmlinux: $(vmlinux)
bbl: $(bbl)
fw_image: $(fw_jump)
openocd: $(openocd)

.PHONY: clean mrproper
clean:
	rm -rf -- $(wrkdir)

mrproper:
	rm -rf -- $(wrkdir) $(toolchain_dest) $(topdir)/rootfs

.PHONY: spike qemu-run

ifeq ($(BL),opensbi)
spike-run: $(fw_jump) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm --kernel $(linux_image) $(fw_jump)

qemu-run: $(qemu) $(fw_jump) $(freebsd_rootfs).img
	$(qemu) -M virt -m 2048 -nographic -bios $(fw_jump) \
		-kernel $(freebsd_rootfs)/boot/kernel/kernel \
		-drive if=none,file=$(freebsd_rootfs).img,id=drv,format=raw \
		-device virtio-blk-device,drive=drv \
		-device virtio-rng-pci

qemu-debug: $(qemu) $(fw_jump)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(fw_jump) -kernel $(linux_image) -s -S

else ifeq ($(BL),bbl)
spike-run: $(bbl) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm $(bbl)

qemu-run: $(qemu) $(bbl)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(bbl)

qemu-debug: $(qemu) $(bbl)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(bbl) -s -S
endif

SD_CARD ?= /dev/sdb
.PHONY: make_sd
make_sd: $(bbl)
	sudo dd if=$(bbl).bin of=$(SD_CARD)1 bs=4096

