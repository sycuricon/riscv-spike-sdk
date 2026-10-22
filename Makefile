# RISC-V Spike Simulation SDK
# Copyright (C) 2020-2026 by phantom
# Email: phantom@zju.edu.cn
# This project is under MIT License

TOP			:= $(CURDIR)
SRC			:= $(TOP)/repo
BUILD		:= $(TOP)/build
CONFIG		:= $(TOP)/conf
ROOTFS		:= $(TOP)/rootfs
TOOLCHAIN 	:= $(TOP)/toolchain

export PATH := $(TOOLCHAIN)/bin:$(PATH)
export RSS_SDK_TOOLCHAIN := $(TOOLCHAIN)

ISA			?= rv64imafdc_zifencei_zicsr
ABI			?= lp64d
BL			?= bbl
BOARD		?= spike
DTS 		?= $(CONFIG)/$(BOARD).dts

all: vmlinux toolchain_newlib


#######################################
#
#         Toolchain
#
#######################################

TOOLCHAIN_SRC 			:= $(SRC)/riscv-gnu-toolchain
TOOLCHAIN_LINUX_BUILD 	:= $(BUILD)/riscv-gnu-toolchain
TOOLCHAIN_HEADERS 		:= $(TOOLCHAIN_LINUX_BUILD)/linux-headers
TOOLCHAIN_NEWLIB_BUILD 	:= $(BUILD)/riscv-gnu-toolchain-newlib

TOOLCHAIN_LINUX_TRIPLE 	:= riscv64-unknown-linux-gnu
TOOLCHAIN_LINUX_GCC 	:= $(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)-gcc
TOOLCHAIN_NEWLIB_TRIPLE := riscv64-unknown-elf
TOOLCHAIN_NEWLIB_GCC 	:= $(TOOLCHAIN)/bin/$(TOOLCHAIN_NEWLIB_TRIPLE)-gcc

$(TOOLCHAIN_LINUX_GCC):
	mkdir -p $(TOOLCHAIN_LINUX_BUILD)
	$(MAKE) -C $(LINUX_SRC) O=$(TOOLCHAIN_LINUX_BUILD)/linux ARCH=riscv INSTALL_HDR_PATH=$(TOOLCHAIN_HEADERS) headers_install
	cd $(TOOLCHAIN_LINUX_BUILD); $(TOOLCHAIN_SRC)/configure \
		--prefix=$(TOOLCHAIN) \
		--with-arch=$(ISA) \
		--with-abi=$(ABI) \
		--with-linux-headers-src=$(TOOLCHAIN_HEADERS)/include
	$(MAKE) -C $(TOOLCHAIN_LINUX_BUILD) linux

# The newlib toolchain uses its own build directory so that it does not
# reconfigure the Linux toolchain build. Both install into $(TOOLCHAIN);
# the order-only prerequisite serializes the two installs under make -j.
$(TOOLCHAIN_NEWLIB_GCC): | $(TOOLCHAIN_LINUX_GCC)
	mkdir -p $(TOOLCHAIN_NEWLIB_BUILD)
	cd $(TOOLCHAIN_NEWLIB_BUILD); $(TOOLCHAIN_SRC)/configure \
		--prefix=$(TOOLCHAIN) \
		--enable-multilib
	$(MAKE) -C $(TOOLCHAIN_NEWLIB_BUILD) newlib

toolchain_linux: $(TOOLCHAIN_LINUX_GCC)
toolchain_newlib: $(TOOLCHAIN_NEWLIB_GCC)


#######################################
#
#         Buildroot & Rootfs
#
#######################################

BUILDROOT_SRC 		:= $(SRC)/buildroot
BUILDROOT_BUILD 	:= $(BUILD)/buildroot
BUILDROOT_DEFCONFIG := $(CONFIG)/buildroot_initramfs_config
BUILDROOT_CONFIG 	:= $(BUILDROOT_BUILD)/.config
ROOTFS_TAR 			:= $(BUILDROOT_BUILD)/images/rootfs.tar
ROOTFS_STAMP 		:= $(BUILD)/.rootfs

$(BUILDROOT_CONFIG): $(BUILDROOT_DEFCONFIG) $(BUILDROOT_SRC) $(TOOLCHAIN_LINUX_GCC)
	mkdir -p $(dir $@)
	cp $< $@
	$(MAKE) -C $(BUILDROOT_SRC) O=$(BUILDROOT_BUILD) olddefconfig

$(ROOTFS_TAR): $(BUILDROOT_SRC) $(BUILDROOT_CONFIG) $(TOOLCHAIN_LINUX_GCC)
	$(MAKE) -C $< O=$(BUILDROOT_BUILD)

$(ROOTFS_STAMP): $(ROOTFS_TAR)
	mkdir -p $(ROOTFS)
	tar -xpmf $< -C $(ROOTFS) --exclude ./dev --exclude ./usr/share/locale
	touch $@

buildroot_menuconfig: $(BUILDROOT_CONFIG)
	$(MAKE) -C $(BUILDROOT_SRC) O=$(BUILDROOT_BUILD) menuconfig
	$(MAKE) -C $(BUILDROOT_SRC) O=$(BUILDROOT_BUILD) BR2_DEFCONFIG=$(BUILDROOT_DEFCONFIG) savedefconfig
	touch $<

rootfs: $(ROOTFS_STAMP)


#######################################
#
#         Linux Kernel
#
#######################################

LINUX_SRC			:= $(SRC)/linux
LINUX_BUILD			:= $(BUILD)/linux
LINUX_DEFCONFIG		:= $(CONFIG)/linux_defconfig
LINUX_CONFIG		:= $(LINUX_BUILD)/.config
VMLINUX_ELF			:= $(LINUX_BUILD)/vmlinux
VMLINUX_STRIP		:= $(LINUX_BUILD)/vmlinux-stripped
VMLINUX_IMAGE		:= $(LINUX_BUILD)/arch/riscv/boot/Image

ROOTFS_CHANGES 	:= $(shell find $(ROOTFS) -newer $(VMLINUX_ELF) \( -type f -o -type d \) 2>/dev/null)

$(LINUX_CONFIG): $(LINUX_DEFCONFIG) $(LINUX_SRC) $(TOOLCHAIN_LINUX_GCC)
	mkdir -p $(dir $@)
	cp -p $< $@
	$(MAKE) -C $(LINUX_SRC) O=$(LINUX_BUILD) ARCH=riscv CROSS_COMPILE=$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)- olddefconfig
ifeq (,$(filter rv%c,$(ISA)))
	sed 's/^.*CONFIG_RISCV_ISA_C.*$$/CONFIG_RISCV_ISA_C=n/' -i $@
	$(MAKE) -C $(LINUX_SRC) O=$(LINUX_BUILD) ARCH=riscv CROSS_COMPILE=$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)- olddefconfig
endif
ifeq ($(ISA),$(filter rv32%,$(ISA)))
	sed 's/^.*CONFIG_ARCH_RV32I.*$$/CONFIG_ARCH_RV32I=y/' -i $@
	sed 's/^.*CONFIG_ARCH_RV64I.*$$/CONFIG_ARCH_RV64I=n/' -i $@
	$(MAKE) -C $(LINUX_SRC) O=$(LINUX_BUILD) ARCH=riscv CROSS_COMPILE=$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)- olddefconfig
endif

$(VMLINUX_ELF): $(LINUX_SRC) $(LINUX_CONFIG) $(ROOTFS_STAMP) $(ROOTFS_CHANGES)
	$(MAKE) -C $< O=$(LINUX_BUILD) \
		CROSS_COMPILE=$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)- \
		CONFIG_INITRAMFS_SOURCE="$(CONFIG)/initramfs.txt $(ROOTFS)" \
		CONFIG_INITRAMFS_ROOT_UID=$(shell id -u) \
		CONFIG_INITRAMFS_ROOT_GID=$(shell id -g) \
		ARCH=riscv \
		all

$(VMLINUX_STRIP): $(VMLINUX_ELF)
	$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)-strip -o $@ $<

$(VMLINUX_IMAGE): $(VMLINUX_ELF)

linux_menuconfig: $(LINUX_CONFIG)
	$(MAKE) -C $(LINUX_SRC) O=$(LINUX_BUILD) ARCH=riscv CROSS_COMPILE=$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)- menuconfig
	$(MAKE) -C $(LINUX_SRC) O=$(LINUX_BUILD) ARCH=riscv CROSS_COMPILE=$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)- savedefconfig
	# cp $(LINUX_BUILD)/defconfig $(LINUX_DEFCONFIG)

vmlinux: $(VMLINUX_ELF)
vmlinux_strip: $(VMLINUX_STRIP)
vmlinux_image: $(VMLINUX_IMAGE)


#######################################
#
#         Bootloader
#
#######################################

PK_SRC 			:= $(SRC)/riscv-pk
PK_BUILD 		:= $(BUILD)/riscv-pk
PK_CONFIG 		:= $(PK_BUILD)/Makefile
PK 				:= $(PK_BUILD)/pk
BBL 			:= $(PK_BUILD)/bbl

$(PK_CONFIG): $(PK_SRC) $(DTS) $(TOOLCHAIN_LINUX_GCC)
	mkdir -p $(PK_BUILD)
	cd $(PK_BUILD) && $</configure \
		--host=$(TOOLCHAIN_LINUX_TRIPLE) \
		--enable-logo --with-logo=$(CONFIG)/logo.txt \
		--with-payload=$(VMLINUX_STRIP) --with-dts=$(DTS)

$(PK): $(PK_CONFIG)
	CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(PK_BUILD) pk
	$(MAKE) -C $(PK_BUILD) install-exes install_exes=pk INSTALLDIR=$(TOOLCHAIN)

$(BBL): $(PK_CONFIG) $(VMLINUX_STRIP) | $(PK)
	CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(PK_BUILD) bbl bbl.bin

pk: $(PK)
bbl: $(BBL)

OPENSBI_SRC 	:= $(SRC)/opensbi
OPENSBI_BUILD 	:= $(BUILD)/opensbi
FW_JUMP			:= $(OPENSBI_BUILD)/platform/generic/firmware/fw_jump.elf

$(FW_JUMP): $(OPENSBI_SRC) $(VMLINUX_IMAGE) $(TOOLCHAIN_LINUX_GCC)
	mkdir -p $(OPENSBI_BUILD)
	$(MAKE) -C $< O=$(OPENSBI_BUILD) \
		CROSS_COMPILE=$(TOOLCHAIN)/bin/$(TOOLCHAIN_LINUX_TRIPLE)- \
		FW_TEXT_START=0x80000000 FW_PAYLOAD_PATH=$(VMLINUX_IMAGE) \
		PLATFORM=generic 

fw_image: $(FW_JUMP)


#######################################
#
#         Simulator & Debugger
#
#######################################

SPIKE_SRC 		:= $(SRC)/riscv-isa-sim
SPIKE_BUILD 	:= $(BUILD)/riscv-isa-sim
SPIKE 			:= $(TOOLCHAIN)/bin/spike

QEMU_SRC 		:= $(TOOLCHAIN_SRC)/qemu
QEMU_BUILD 		:= $(BUILD)/qemu
QEMU 			:= $(TOOLCHAIN)/bin/qemu-system-riscv64

OPENOCD_SRC 	:= $(SRC)/riscv-openocd
OPENOCD_BUILD 	:= $(BUILD)/riscv-openocd
OPENOCD 		:= $(TOOLCHAIN)/bin/openocd

$(SPIKE): $(SPIKE_SRC)
	rm -rf $(SPIKE_BUILD)
	mkdir -p $(SPIKE_BUILD)
	mkdir -p $(dir $@)
	cd $(SPIKE_BUILD) && $</configure \
		--with-target= \
		--prefix=$(TOOLCHAIN)
	$(MAKE) -C $(SPIKE_BUILD)
	$(MAKE) -C $(SPIKE_BUILD) install

$(QEMU): $(QEMU_SRC)
	rm -rf $(QEMU_BUILD)
	mkdir -p $(QEMU_BUILD)
	mkdir -p $(dir $@)
	cd $(QEMU_BUILD) && $</configure \
		--disable-docs \
		--prefix=$(TOOLCHAIN) \
		--target-list=riscv64-linux-user,riscv64-softmmu
	$(MAKE) -C $(QEMU_BUILD)
	$(MAKE) -C $(QEMU_BUILD) install

$(OPENOCD): $(OPENOCD_SRC)
	rm -rf $(OPENOCD_BUILD)
	mkdir -p $(OPENOCD_BUILD)
	mkdir -p $(dir $@)
	cd $(OPENOCD_SRC) && $</bootstrap
	cd $(OPENOCD_BUILD) && $</configure \
		--enable-remote-bitbang \
		--prefix=$(TOOLCHAIN)
	$(MAKE) -C $(OPENOCD_BUILD)
	$(MAKE) -C $(OPENOCD_BUILD) install

openocd: $(OPENOCD)

ifeq ($(BL),opensbi)
spike: $(FW_JUMP) $(SPIKE)
	$(SPIKE) --isa=$(ISA)_zicntr_zihpm --kernel $(VMLINUX_IMAGE) $(FW_JUMP)

qemu: $(QEMU) $(FW_JUMP)
	$(QEMU) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(FW_JUMP) -kernel $(VMLINUX_IMAGE)

qemu_debug: $(QEMU) $(FW_JUMP)
	$(QEMU) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(FW_JUMP) -kernel $(VMLINUX_IMAGE) -s -S

else ifeq ($(BL),bbl)
spike: $(BBL) $(SPIKE)
	$(SPIKE) --isa=$(ISA)_zicntr_zihpm $(BBL)

qemu: $(QEMU) $(BBL)
	$(QEMU) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(BBL)

qemu_debug: $(QEMU) $(BBL)
	$(QEMU) -nographic -machine virt -cpu rv64,sv57=on -m 2048M -bios $(BBL) -s -S
endif


#######################################
#
#         Misc
#
#######################################

SD_CARD ?= /dev/sdb
make_sd: $(BBL)
	sudo dd if=$(BBL).bin of=$(SD_CARD)1 bs=4096

clean:
	rm -rf -- $(BUILD)

mrproper:
	rm -rf -- $(BUILD) $(TOOLCHAIN) $(ROOTFS)

.PHONY: all toolchain_linux toolchain_newlib rootfs vmlinux vmlinux_image vmlinux_strip pk bbl fw_image openocd \
	buildroot_menuconfig linux_menuconfig spike qemu qemu_debug make_sd clean mrproper
