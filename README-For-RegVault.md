### Change LLVM submodule
After cloning the repository, you need to change the LLVM submodule to the one we forked.
```bash
cd riscv-spike-sdk
git submodule update --init --recursive --progress
cp conf/riscv-gnu-toolchain-gitmodules repo/riscv-gnu-toolchain/.gitmodules
git submodule sync --recursive
cd repo/riscv-gnu-toolchain/llvm
git remote -v
# if the origin is not our forked repository, then
cd ..
git submodule set-url llvm/ https://github.com/RegulusGuo/llvm-project.git
# after all the mess...
cd llvm
git fetch
git checkout regvault-rv
```

### Patch Linux kernel
```bash
cd conf/linux-6.6.2-patch
bash ./patch-kernel.sh ../../repo/linux
```

### Patch Spike
Back to `riscv-spike-sdk/`, then
```bash
cd repo/riscv-isa-sim
git apply ../../conf/spike.patch
```
Sorry for the inconsistency of how to patch the kernel and spike, we will fix it in the future.

### Build LLVM
Back to `riscv-spike-sdk/`, then
```bash
make llvm -j
```

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