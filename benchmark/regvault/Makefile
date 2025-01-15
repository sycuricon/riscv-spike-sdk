# General Purpose Makefile for Linux Kernel module

ARCH := riscv # set if cross-compile  
CROSS_COMPILE := $(RISCV)/bin/riscv64-unknown-linux-gnu- # set if cross-compile

KERNEL_DIR := $(CURDIR)/../build/linux/
		
obj-m := rgvlt_test.o

default:
	$(MAKE) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) -C $(KERNEL_DIR) M=$(CURDIR) modules

clean:                                     
	$(MAKE) -C $(KERNEL_DIR) M=$(CURDIR) clean