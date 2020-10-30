#!/bin/bash

NJOB=4

git submodule update --init --jobs $NJOB buildroot riscv-gnu-toolchain linux riscv-pk riscv-isa-sim

cd riscv-gnu-toolchain
git submodule update --init --jobs $NJOB riscv-binutils riscv-gcc riscv-glibc riscv-newlib riscv-gdb
cd -

