ISA ?= rv64imafdc_zifencei_zicsr
ABI ?= lp64d
BL ?= bbl
BOARD ?= spike

topdir := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
topdir := $(topdir:/=)
srcdir := $(topdir)/repo
confdir := $(topdir)/conf
wrkdir := $(CURDIR)/build

toolchain_srcdir := $(srcdir)/riscv-gnu-toolchain
toolchain_wrkdir := $(wrkdir)/riscv-gnu-toolchain
toolchain_newlib_wrkdir := $(wrkdir)/riscv-gnu-toolchain-newlib

export SDK_TOOLCHAIN_DIR := $(CURDIR)/toolchain
PATH := $(SDK_TOOLCHAIN_DIR)/bin:$(PATH)
toolchain_headers := $(toolchain_wrkdir)/linux-headers

buildroot_srcdir := $(srcdir)/buildroot
buildroot_initramfs_wrkdir := $(wrkdir)/buildroot
buildroot_initramfs_tar := $(buildroot_initramfs_wrkdir)/images/rootfs.tar
buildroot_initramfs_config := $(confdir)/buildroot_initramfs_config
buildroot_initramfs_sysroot_stamp := $(wrkdir)/.buildroot_initramfs_sysroot
buildroot_initramfs_sysroot := $(topdir)/rootfs

linux_srcdir := $(srcdir)/linux
linux_wrkdir := $(wrkdir)/linux
linux_defconfig := $(confdir)/linux_defconfig

vmlinux := $(linux_wrkdir)/vmlinux
vmlinux_stripped := $(linux_wrkdir)/vmlinux-stripped
linux_image := $(linux_wrkdir)/arch/riscv/boot/Image

rootfs_changes := $(shell find $(buildroot_initramfs_sysroot) -newer $(vmlinux) \( -type f -o -type d \) 2>/dev/null)

DTS ?= $(abspath conf/$(BOARD).dts)
pk_srcdir := $(srcdir)/riscv-pk
pk_wrkdir := $(wrkdir)/riscv-pk
bbl := $(pk_wrkdir)/bbl
pk  := $(pk_wrkdir)/pk
pk_config := $(pk_wrkdir)/Makefile

opensbi_srcdir := $(srcdir)/opensbi
opensbi_wrkdir := $(wrkdir)/opensbi
fw_jump := $(opensbi_wrkdir)/platform/generic/firmware/fw_jump.elf

spike_srcdir := $(srcdir)/riscv-isa-sim
spike_wrkdir := $(wrkdir)/riscv-isa-sim
spike := $(SDK_TOOLCHAIN_DIR)/bin/spike

qemu_srcdir := $(srcdir)/riscv-gnu-toolchain/qemu
qemu_wrkdir := $(wrkdir)/qemu
qemu :=  $(SDK_TOOLCHAIN_DIR)/bin/qemu-system-riscv64

openocd_srcdir := $(srcdir)/riscv-openocd
openocd_wrkdir := $(wrkdir)/riscv-openocd
openocd := $(SDK_TOOLCHAIN_DIR)/bin/openocd

target_linux  := riscv64-unknown-linux-gnu
target_newlib := riscv64-unknown-elf
cross_linux   := $(SDK_TOOLCHAIN_DIR)/bin/$(target_linux)-
linux_gcc     := $(cross_linux)gcc
newlib_gcc    := $(SDK_TOOLCHAIN_DIR)/bin/$(target_newlib)-gcc

.PHONY: all
all: $(vmlinux) newlib

linux: $(linux_gcc)
newlib: $(newlib_gcc)

$(linux_gcc):
	mkdir -p $(toolchain_wrkdir)
	$(MAKE) -C $(linux_srcdir) O=$(toolchain_wrkdir)/linux ARCH=riscv INSTALL_HDR_PATH=$(toolchain_headers) headers_install
	cd $(toolchain_wrkdir); $(toolchain_srcdir)/configure \
		--prefix=$(SDK_TOOLCHAIN_DIR) \
		--with-arch=$(ISA) \
		--with-abi=$(ABI) \
		--with-linux-headers-src=$(toolchain_headers)/include
	$(MAKE) -C $(toolchain_wrkdir) linux

$(newlib_gcc): | $(linux_gcc)
	mkdir -p $(toolchain_newlib_wrkdir)
	cd $(toolchain_newlib_wrkdir); $(toolchain_srcdir)/configure \
		--prefix=$(SDK_TOOLCHAIN_DIR) \
		--enable-multilib
	$(MAKE) -C $(toolchain_newlib_wrkdir) newlib

$(buildroot_initramfs_wrkdir)/.config: $(buildroot_initramfs_config) $(buildroot_srcdir) $(linux_gcc)
	mkdir -p $(dir $@)
	cp $(buildroot_initramfs_config) $@
	$(MAKE) -C $(buildroot_srcdir) O=$(buildroot_initramfs_wrkdir) olddefconfig

$(buildroot_initramfs_tar): $(buildroot_srcdir) $(buildroot_initramfs_wrkdir)/.config $(linux_gcc)
	$(MAKE) -C $< O=$(buildroot_initramfs_wrkdir)

.PHONY: buildroot-menuconfig
buildroot-menuconfig: $(buildroot_initramfs_wrkdir)/.config
	$(MAKE) -C $(buildroot_srcdir) O=$(buildroot_initramfs_wrkdir) menuconfig
	$(MAKE) -C $(buildroot_srcdir) O=$(buildroot_initramfs_wrkdir) BR2_DEFCONFIG=$(buildroot_initramfs_config) savedefconfig
	touch $<

$(buildroot_initramfs_sysroot_stamp): $(buildroot_initramfs_tar)
	mkdir -p $(buildroot_initramfs_sysroot)
	tar -xpmf $< -C $(buildroot_initramfs_sysroot) --exclude ./dev --exclude ./usr/share/locale
	touch $@

$(linux_wrkdir)/.config: $(linux_defconfig) $(linux_srcdir) $(linux_gcc)
	mkdir -p $(dir $@)
	cp -p $< $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=$(cross_linux) olddefconfig
ifeq (,$(filter rv%c,$(ISA)))
	sed 's/^.*CONFIG_RISCV_ISA_C.*$$/CONFIG_RISCV_ISA_C=n/' -i $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=$(cross_linux) olddefconfig
endif
ifeq ($(ISA),$(filter rv32%,$(ISA)))
	sed 's/^.*CONFIG_ARCH_RV32I.*$$/CONFIG_ARCH_RV32I=y/' -i $@
	sed 's/^.*CONFIG_ARCH_RV64I.*$$/CONFIG_ARCH_RV64I=n/' -i $@
	$(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=$(cross_linux) olddefconfig
endif

$(vmlinux): $(linux_srcdir) $(linux_wrkdir)/.config $(buildroot_initramfs_sysroot_stamp) $(rootfs_changes)
	$(MAKE) -C $< O=$(linux_wrkdir) \
		CONFIG_INITRAMFS_SOURCE="$(confdir)/initramfs.txt $(buildroot_initramfs_sysroot)" \
		CONFIG_INITRAMFS_ROOT_UID=$(shell id -u) \
		CONFIG_INITRAMFS_ROOT_GID=$(shell id -g) \
		CROSS_COMPILE=$(cross_linux) \
		ARCH=riscv \
		all

$(vmlinux_stripped): $(vmlinux)
	$(cross_linux)strip -o $@ $<

$(linux_image): $(vmlinux)

.PHONY: linux-menuconfig
linux-menuconfig: $(linux_wrkdir)/.config
	$(MAKE) -C $(linux_srcdir) O=$(dir $<) ARCH=riscv CROSS_COMPILE=$(cross_linux) menuconfig
	$(MAKE) -C $(linux_srcdir) O=$(dir $<) ARCH=riscv CROSS_COMPILE=$(cross_linux) savedefconfig
	# cp $(dir $<)/defconfig conf/linux_defconfig

$(pk_config): $(pk_srcdir) $(DTS) $(linux_gcc)
	rm -rf $(pk_wrkdir)
	mkdir -p $(pk_wrkdir)
	cd $(pk_wrkdir) && $</configure \
		--host=$(target_linux) \
		--with-payload=$(vmlinux_stripped) \
		--enable-logo \
		--with-logo=$(abspath conf/logo.txt) \
		--with-dts=$(DTS)

$(pk): $(pk_config)
	CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(pk_wrkdir) pk
	$(MAKE) -C $(pk_wrkdir) install-exes install_exes=pk INSTALLDIR=$(SDK_TOOLCHAIN_DIR)

$(bbl): $(pk_config) $(vmlinux_stripped) | $(pk)
	CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(pk_wrkdir) bbl bbl.bin

$(fw_jump): $(opensbi_srcdir) $(linux_image) $(linux_gcc)
	rm -rf $(opensbi_wrkdir)
	mkdir -p $(opensbi_wrkdir)
	$(MAKE) -C $(opensbi_srcdir) FW_TEXT_START=0x80000000 FW_PAYLOAD_PATH=$(linux_image) PLATFORM=generic O=$(opensbi_wrkdir) CROSS_COMPILE=$(cross_linux)

$(spike): $(spike_srcdir) 
	rm -rf $(spike_wrkdir)
	mkdir -p $(spike_wrkdir)
	mkdir -p $(dir $@)
	cd $(spike_wrkdir) && $</configure \
		--with-target= \
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


.PHONY: linux newlib buildroot_initramfs_sysroot vmlinux bbl pk fw_image openocd
buildroot_initramfs_sysroot: $(buildroot_initramfs_sysroot_stamp)
vmlinux: $(vmlinux)
bbl: $(bbl)
pk: $(pk)
fw_image: $(fw_jump)
openocd: $(openocd)

.PHONY: clean mrproper
clean:
	rm -rf -- $(wrkdir)

mrproper:
	rm -rf -- $(wrkdir) $(SDK_TOOLCHAIN_DIR) $(topdir)/rootfs

.PHONY: spike qemu qemu-debug

ifeq ($(BL),opensbi)
spike: $(fw_jump) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm --kernel $(linux_image) $(fw_jump)

qemu: $(qemu) $(fw_jump)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(fw_jump) -kernel $(linux_image)

qemu-debug: $(qemu) $(fw_jump)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(fw_jump) -kernel $(linux_image) -s -S

else ifeq ($(BL),bbl)
spike: $(bbl) $(spike)
	$(spike) --isa=$(ISA)_zicntr_zihpm $(bbl)

qemu: $(qemu) $(bbl)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(bbl)

qemu-debug: $(qemu) $(bbl)
	$(qemu) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(bbl) -s -S
endif

SD_CARD ?= /dev/sdb
.PHONY: make_sd
make_sd: $(bbl)
	sudo dd if=$(bbl).bin of=$(SD_CARD)1 bs=4096

