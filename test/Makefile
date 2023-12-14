# General Purpose Makefile for Linux Kernel module

ARCH := riscv # set if cross-compile  
RISCV := /home/grr/riscv-spike-sdk/toolchain/bin
CROSS_COMPILE := $(RISCV)/riscv64-unknown-linux-gnu- # set if cross-compile

KERNEL_DIR := /home/grr/riscv-spike-sdk/build/linux/
		
obj-m := rgvlt_test.o

default:
	$(MAKE) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) -C $(KERNEL_DIR) M=$(CURDIR) modules

clean:                                     
	$(MAKE) -C $(KERNEL_DIR) M=$(CURDIR) clean