#!/bin/bash

NJOB=4

git submodule update --init --jobs $NJOB buildroot riscv-gnu-toolchain riscv-pk riscv-isa-sim

cd riscv-gnu-toolchain
git submodule update --init --jobs $NJOB riscv-binutils riscv-gcc riscv-glibc riscv-newlib riscv-gdb
cd -

curl https://mirrors.edge.kernel.org/pub/linux/kernel/v5.x/linux-5.8.1.tar.gz | tar xzf -
mv linux-5.8.1 linux

