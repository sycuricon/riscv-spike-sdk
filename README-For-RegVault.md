### Build LLVM
```bash
make llvm -j
```

### Patch Linux kernel
```bash
cd conf/linux-6.6.2-patch
bash ./patch-kernel.sh ../../repo/linux
```

### Patch Linux kernel
Back to `riscv-spike-sdk/`, then
```bash
cd repo/riscv-isa-sim
git apply ../../conf/spike.patch
```
Sorry for the inconsistency of how to patch the kernel and spike, we will fix it in the future.

### Prepare Linux kernel config
```bash
make linux-menuconfig
```
The options are inside the `Kernel features` menu, all on by default.

### Build Linux kernel
```bash
make linux prot=<flag-you-want>  -j
```
The `prot` flag specifies the data types to instrument. `ra` for return address, `fp` for function pointers, `non-ctrl` for non-control data, `full` for all data types.

### Run Linux on Spike
```bash
make spike -j
```