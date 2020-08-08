![logo](./conf/logo.png)

# RISC-V Spike Simulator SDK

In the recent version of the riscv-tools and freedom-u-sdk, both of them removed the support of the spike simulator, and tutorials about running Linux on spike is using static compiled busybox, which is not suitable for real test environments. Spike is the simplest simulator of RISC-V, it has a very clear description of the instructions, you can apply your ideas and check it for a quick try. The **R**ISC-V **S**pike **S**imulator SDK wants to help people to test design with 64-bit Linux environment on Spike easily, the basic framework is based on Freedom U SDK version 1.0.

This SDK will provide great convenience for the following people who:

* want to run upstream version Linux on Spike
* want to test design in Linux environment with modified spike, gcc and other extension in toolchain
* want to have a overview about embedded system development

This SDK follows the newest Linux Kernel, GNU toolchain and Spike, the functions of each folder in the project are as follows:

|       Folder        |      Description       |   Version   |
| :-----------------: | :--------------------: | :---------: |
|      buildroot      |    Build initramfs     |  2020.05.x  |
|        linux        |      Linux Kernel      |    5.8.0    |
| riscv-gnu-toolchain | GNU Compiler Toolchain |  gcc 10.1.0 ld 2.3.4  |
|     riscv-tools     | Simulator & Bootloader |    master (will be replace)   |
|        conf         |     config for SDK     |             |

## Quickstart
Build dependencies on Ubuntu 16.04/18.04:
```bash
$ sudo apt-get install device-tree-compiler autoconf automake autotools-dev    \
curl libmpc-dev libmpfr-dev libgmp-dev gawk build-essential bison flex texinfo \
gperf libtool patchutils bc zlib1g-dev libexpat-dev python-dev python3-dev
```
```bash
git clone https://github.com/Phantom1003/riscv-rss-sdk.git
git submodule update --init --recursive --progress
#	NOTICE: 
# 		If you already have a riscv toolchain, please notice ** DO NOT SET
#		 $RISCV and MAKE SURE NO ORIGIN RISCV TOOLCHAIN IN YOUR $PATH **
make
```

## Software Development

The default process will only build Linux cross-compiler, which has prefix "riscv64-unknown-linux", if you want using newlib, you can use `make newlib` to build, then you can use pk as a kernel to run your program.

The main compile process will run vmlinux on spike directly, to add your test program, you should add your elfs in `./work/buildroot_initramfs_sysroot` and `make` again.

​	**NOTICE**: The test program should use Linux cross-compiler to compile , instead of Newlib cross-compiler.

If the benchmark you choose need some package, you can use `make buildroot-menuconfig` to reconfigure buildroot and `touch buildroot && make` to rebuild. 

Same to linux, if you want to add driver for new devices, `make buildroot-menuconfig` to reconfigure, `touch linux && make` to rebuild.

## If you want to build step by step ...

1. Build RISC-V GNU Toolchain

   The key to build the dynamic link elf is using the correspond kernel version header to build the gnu toolchain, and more kernel version information you can find in `./riscv-gnu-toolchain/linux-headers/include/linux/version.h`, the macro `LINUX_VERSION_CODE` present the kernel version, for example, you can find in this SDK, its value is 328712 = 0x050408, which means 5.4.8. 

2.  Build rootfs   
   Using `buildroot` to help you to build a rootfs, you can add config in `conf/buildroot_initramfs_config` to add package, and you can copy your pre-compiled elf in `work/initramfs_sysroot` to access in Spike.
   And remember, the basic idea of this SDK is to deconfig all the device, because spike is very limited support for devices, specically the Ethernet, so you should not open DHCP.

3. Compile Linux  
   You can find config in `work/linux_defconfig`.

4. Spike  
   The default account is root, following is the terminal log on Linux 5.8.0.

```
bbl loader

		  RISC-V Spike Simulator SDK
	  This SDK is based on SiFive Freedom U SDK.                    
	      ___           ___           ___     
	     /\  \         /\  \         /\  \    
	    /  \  \       /  \  \       /  \  \   
	   / /\ \  \     / /\ \  \     / /\ \  \  
	  /  \~\ \  \   _\ \~\ \  \   _\ \~\ \  \ 
	 / /\ \ \ \__\ /\ \ \ \ \__\ /\ \ \ \ \__\
	 \/_|  \/ /  / \ \ \ \ \/__/ \ \ \ \ \/__/
	    | |  /  /   \ \ \ \__\    \ \ \ \__\  
	    | |\/__/     \ \/ /  /     \ \/ /  /  
	    | |  |        \  /  /       \  /  /   
	     \|__|         \/__/         \/__/ 
     
     
[    0.000000] OF: fdt: No chosen node found, continuing without
[    0.000000] OF: fdt: Ignoring memory range 0x80000000 - 0x80200000
[    0.000000] Linux version 5.8.0 (phantom@ubuntu-phantom) (riscv64-unknown-linux-gnu-gcc (GCC) 10.1.0, GNU ld (GNU Binutils) 2.34) #1 SMP Sun Aug 9 00:00:03 CST 2020
[    0.000000] Zone ranges:
[    0.000000]   DMA32    [mem 0x0000000080200000-0x00000000ffffffff]
[    0.000000]   Normal   empty
[    0.000000] Movable zone start for each node
[    0.000000] Early memory node ranges
[    0.000000]   node   0: [mem 0x0000000080200000-0x00000000ffffffff]
[    0.000000] Initmem setup node 0 [mem 0x0000000080200000-0x00000000ffffffff]
[    0.000000] software IO TLB: mapped [mem 0xfa3fb000-0xfe3fb000] (64MB)
[    0.000000] SBI specification v0.1 detected
[    0.000000] riscv: ISA extensions acdfim
[    0.000000] riscv: ELF capabilities acdfim
[    0.000000] percpu: Embedded 14 pages/cpu s24664 r0 d32680 u57344
[    0.000000] Built 1 zonelists, mobility grouping on.  Total pages: 516615
[    0.000000] Kernel command line: 
[    0.000000] Dentry cache hash table entries: 262144 (order: 9, 2097152 bytes, linear)
[    0.000000] Inode-cache hash table entries: 131072 (order: 8, 1048576 bytes, linear)
[    0.000000] Sorting __ex_table...
[    0.000000] mem auto-init: stack:off, heap alloc:off, heap free:off
[    0.000000] Memory: 1982360K/2095104K available (3640K kernel code, 2736K rwdata, 2048K rodata, 4916K init, 259K bss, 112744K reserved, 0K cma-reserved)
[    0.000000] SLUB: HWalign=64, Order=0-3, MinObjects=0, CPUs=4, Nodes=1
[    0.000000] rcu: Hierarchical RCU implementation.
[    0.000000] rcu: 	RCU event tracing is enabled.
[    0.000000] rcu: 	RCU restricting CPUs from NR_CPUS=8 to nr_cpu_ids=4.
[    0.000000] rcu: RCU calculated value of scheduler-enlistment delay is 10 jiffies.
[    0.000000] rcu: Adjusting geometry for rcu_fanout_leaf=16, nr_cpu_ids=4
[    0.000000] NR_IRQS: 64, nr_irqs: 64, preallocated irqs: 0
[    0.000000] riscv-intc: 64 local interrupts mapped
[    0.000000] riscv_timer_init_dt: Registering clocksource cpuid [0] hartid [0]
[    0.000000] clocksource: riscv_clocksource: mask: 0xffffffffffffffff max_cycles: 0x24e6a1710, max_idle_ns: 440795202120 ns
[    0.000005] sched_clock: 64 bits at 10MHz, resolution 100ns, wraps every 4398046511100ns
[    0.011900] printk: console [hvc0] enabled
[    0.012150] Calibrating delay loop (skipped), value calculated using timer frequency.. 20.00 BogoMIPS (lpj=100000)
[    0.012755] pid_max: default: 32768 minimum: 301
[    0.013100] Mount-cache hash table entries: 4096 (order: 3, 32768 bytes, linear)
[    0.013535] Mountpoint-cache hash table entries: 4096 (order: 3, 32768 bytes, linear)
[    0.014735] rcu: Hierarchical SRCU implementation.
[    0.015270] smp: Bringing up secondary CPUs ...
[    0.016900] smp: Brought up 1 node, 4 CPUs
[    0.017455] devtmpfs: initialized
[    0.018045] random: get_random_bytes called from setup_net+0x38/0x186 with crng_init=0
[    0.018085] clocksource: jiffies: mask: 0xffffffff max_cycles: 0xffffffff, max_idle_ns: 19112604462750000 ns
[    0.019110] futex hash table entries: 1024 (order: 4, 65536 bytes, linear)
[    0.019670] NET: Registered protocol family 16
[    0.022850] vgaarb: loaded
[    0.023135] SCSI subsystem initialized
[    0.023575] usbcore: registered new interface driver usbfs
[    0.023910] usbcore: registered new interface driver hub
[    0.024280] usbcore: registered new device driver usb
[    0.024945] clocksource: Switched to clocksource riscv_clocksource
[    0.026170] NET: Registered protocol family 2
[    0.026690] tcp_listen_portaddr_hash hash table entries: 1024 (order: 2, 16384 bytes, linear)
[    0.027200] TCP established hash table entries: 16384 (order: 5, 131072 bytes, linear)
[    0.027845] TCP bind hash table entries: 16384 (order: 6, 262144 bytes, linear)
[    0.028465] TCP: Hash tables configured (established 16384 bind 16384)
[    0.028880] UDP hash table entries: 1024 (order: 3, 32768 bytes, linear)
[    0.029300] UDP-Lite hash table entries: 1024 (order: 3, 32768 bytes, linear)
[    0.029795] NET: Registered protocol family 1
[    0.030055] PCI: CLS 0 bytes, default 64
[    0.043200] workingset: timestamp_bits=62 max_order=19 bucket_order=0
[    0.047435] io scheduler mq-deadline registered
[    0.047700] io scheduler kyber registered
[    0.088725] Serial: 8250/16550 driver, 4 ports, IRQ sharing disabled
[    0.090115] libphy: Fixed MDIO Bus: probed
[    0.090550] ehci_hcd: USB 2.0 'Enhanced' Host Controller (EHCI) Driver
[    0.090930] ehci-pci: EHCI PCI platform driver
[    0.091230] usbcore: registered new interface driver usb-storage
[    0.091720] usbcore: registered new interface driver usbhid
[    0.092045] usbhid: USB HID core driver
[    0.092405] NET: Registered protocol family 17
[    0.093925] Freeing unused kernel memory: 4916K
[    0.095115] Run /init as init process
Starting syslogd: OK
Starting klogd: OK
Running sysctl: OK
Starting network: OK

Welcome to Buildroot
buildroot login: root
root
# cd /
cd /
# ls
ls
bin      init     linuxrc  opt      run      tmp
dev      lib      media    proc     sbin     usr
etc      lib64    mnt      root     sys      var
# poweroff
poweroff
# Stopping network: OK
Stopping klogd: OK
Stopping syslogd: OK
umount: can't unmount /: Invalid argument
The system is going down NOW!
Sent SIGTERM to all processes
Sent SIGKILL to all processes
Requesting system poweroff
[   14.925145] reboot: Power down
```

Finally, if you have any suggestions for this SDK, please *push* it !
