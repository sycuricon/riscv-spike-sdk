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
|    repo/buildroot    |    Build initramfs     |  2026.08.x  |
|      repo/linux      |      Linux Kernel      |    v7.2.11    |
| repo/riscv-gnu-toolchain | GNU Compiler Toolchain |  gcc 16.1.0 ld 2.47 glibc 2.44  |
| repo/riscv-(isa-sim,pk)  | Simulator & Bootloader |    master   |
| repo/opensbi  | Supervisor / Bootloader |    v1.9   |
| repo/riscv-openocd  | JTAG Debugger |    master   |
|         conf        |     config for SDK     |             |

Build outputs are placed in `build/` (toolchain, kernel, bootloader and simulator objects), `toolchain/` (installed toolchain, spike, qemu, openocd) and `rootfs/` (buildroot output and the initramfs sysroot).

## Quickstart
Build dependencies on Ubuntu 24.04/26.04:
```bash
$ sudo apt-get install device-tree-compiler autoconf automake autotools-dev    \
curl libmpc-dev libmpfr-dev libgmp-dev gawk build-essential bison flex texinfo \
gperf libtool patchutils bc zlib1g-dev libexpat-dev python3-dev python3-venv  \
unzip libglib2.0-dev libpixman-1-dev libncurses-dev ninja-build git rsync wget cpio
```
```bash
git clone https://github.com/sycuricon/riscv-spike-sdk.git

# For people who only want to have a try
sh quickstart.sh
# For people who want to develop the whole system
git submodule update --init --recursive --progress

#	NOTICE: 
# 		If you already have a riscv toolchain, please notice ** DO NOT SET
#		 $RISCV and MAKE SURE NO ORIGIN RISCV TOOLCHAIN IN YOUR $PATH **
make          # build toolchain, rootfs and vmlinux
make spike    # build bootloader and spike, then boot Linux on spike
```

Common make targets:

| Target | Description |
| :----: | :---------- |
| `make` / `make vmlinux` | Build Linux toolchain, buildroot rootfs and the kernel |
| `make spike` | Boot Linux on spike (bootloader selected by `BL`) |
| `make qemu` / `make qemu-debug` | Boot Linux on QEMU, `qemu-debug` waits for gdb on port 1234 |
| `make newlib` | Build the newlib (bare-metal) cross-compiler |
| `make buildroot-menuconfig` | Configure buildroot, saved back to `conf/buildroot_initramfs_config` |
| `make linux-menuconfig` | Configure the kernel in `build/linux/.config` |
| `make openocd` | Build openocd for JTAG debugging |
| `make clean` | Remove `build/` |
| `make mrproper` | Remove `build/`, `toolchain/` and `rootfs/`, including files you added to the sysroot |

Common variables: `BL` (`bbl` or `opensbi`, default `bbl`), `ISA` (default `rv64imafdc_zifencei_zicsr`), `ABI` (default `lp64d`), `BOARD` (`spike` or `starship`, selects `conf/<BOARD>.dts`).

## Software Development

The default process will only build Linux cross-compiler, which has prefix "riscv64-unknown-linux-gnu", if you want using newlib, you can use `make newlib` to build, then you can use pk as a kernel to run your program.

To add your test program, copy your elfs into `rootfs/buildroot_initramfs_sysroot`, then run `touch rootfs/buildroot_initramfs_sysroot && make` so the kernel repacks the initramfs.

**NOTICE**: The test program should use Linux cross-compiler to compile , instead of Newlib cross-compiler.

If the benchmark you choose need some package, you can use `make buildroot-menuconfig` to reconfigure buildroot (the change is saved back to `conf/buildroot_initramfs_config`) and `make` to rebuild. 

Same to linux, if you want to add driver for new devices, `make linux-menuconfig` to reconfigure and `make` to rebuild. The change only lives in `build/linux/.config`; a minimal defconfig is written to `build/linux/defconfig`, copy it to `conf/linux_defconfig` if you want to keep it. Editing `conf/linux_defconfig` regenerates `build/linux/.config` and drops changes made only in menuconfig.

## If you want to build step by step ...

1. Build RISC-V GNU Toolchain

   The key to build the dynamic link elf is using the correspond kernel version header to build the gnu toolchain. The Makefile installs the headers of `repo/linux` into `build/riscv-gnu-toolchain/linux-headers` and builds the toolchain against them. And if you want to use this SDK to do some development on your own chip, you may also need to change ISA and ABI.

2.  Build rootfs

	Using `buildroot` to help you to build a rootfs, you can add config in `conf/buildroot_initramfs_config` to add package, and you can copy your pre-compiled elf to `rootfs/buildroot_initramfs_sysroot` to access in Spike.
	And remember, the basic idea of this SDK is to deconfig all the device, because spike is very limited support for devices, specically the Ethernet, so you should not open DHCP.

3. Compile Linux

   You can find config in `conf/linux_defconfig`, the full config used for the build is `build/linux/.config`.

4. Bootloader

   You can choose between `bbl` or `opensbi` to use as bootloader to launch the simulation. Either edit the default in the Makefile or launch
   ```bash
   # default
   make spike BL=bbl
   # or
   make spike BL=opensbi
   ```

5. Spike

   The default account is root, [here](conf/boot.log) is a terminal log from Linux 5.8.0.

6. Debug via JTAG (for starship)

	You can use the openocd to debug our FPGA by the following openocd configuration file `conf/starship.cfg`
	```
		adapter speed 1000
		adapter driver ftdi
		ftdi vid_pid 0x0403 0x6010
		ftdi channel 0
		ftdi layout_init 0x00e8 0x60eb
		reset_config none
		transport select jtag
		set _CHIPNAME riscv
		jtag newtap $_CHIPNAME cpu -irlen 5

		set _TARGETNAME $_CHIPNAME.cpu

		target create $_TARGETNAME.0 riscv -chain-position $_TARGETNAME
		$_TARGETNAME.0 configure -work-area-phys 0x80000000 -work-area-size 10000 -work-area-backup 1
		riscv use_bscan_tunnel 0
	```
	
	This configuration has been proved validly on VC707 and FTDI2332. 
	The vid_pid is the vendor id and product id of the FTDI device, and you can get this paramter by run `lsusb`
	The ftdi channel is the channel id of the jtag channel while the ftdi USB device has 4 channel
	If your connection between jtag port and debug board is correct, when you run `openocd -f conf/starship.cfg`, the following output means your openocd connects the fpga debug module successfully.
	```
		Open On-Chip Debugger 0.12.0+dev-g4559b4790 (2023-12-14-15:22)
		Licensed under GNU GPL v2
		For bug reports, read
				http://openocd.org/doc/doxygen/bugs.html
		Info : Nested Tap based Bscan Tunnel Selected
		Info : Listening on port 6666 for tcl connections
		Info : Listening on port 4444 for telnet connections
		Info : clock speed 1000 kHz
		Info : JTAG tap: riscv.cpu tap/device found: 0x00000001 (mfg: 0x000 (<invalid>), part: 0x0000, ver: 0x0)
		Info : [riscv.cpu.0] datacount=2 progbufsize=16
		Info : [riscv.cpu.0] Disabling abstract command reads from CSRs.
		Info : [riscv.cpu.0] Disabling abstract command writes to CSRs.
		Info : [riscv.cpu.0] Examined RISC-V core; found 1 harts
		Info : [riscv.cpu.0]  XLEN=64, misa=0x800000000094112d
		[riscv.cpu.0] Target successfully examined.
		Info : starting gdb server for riscv.cpu.0 on 3333
		Info : Listening on port 3333 for gdb connections
	```
	Then you can use gdb to debug fpga by remote connecting the 3333 port.

Finally, if you have any suggestions for this SDK, please *push* it !
