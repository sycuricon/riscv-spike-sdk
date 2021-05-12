#!/bin/sh

# set -x

# subrepo_fetch_loop(repo, extra update option)
subrepo_fetch_loop() {
depth=10
step=100
until git submodule update --init ${2} --depth $depth --progress ${1}
do
	depth=$(($depth + $step))
	echo "[v] Set depth to $depth ..."
done
}

# fetch_repo(parent directory, repo list, extra update option)
fetch_repo() {

echo "[*] Update repositories under ${1}"
cd ${1}

for repo in ${2}
do
	commit=$(git submodule status | grep -oe "\([0-9a-z]*\) $repo" | grep -oe "^\([0-9a-z]*\)")
	echo "[-] $repo -> $commit"
	subrepo_fetch_loop $repo "${3}"
done

cd $root
}

root="$(dirname "$(readlink -f "$0")")"
NJOB=4

root_repo_list=${ROOT_LIST:-"buildroot riscv-gnu-toolchain riscv-pk linux riscv-isa-sim"}
toolchain_repo_list=${TOOLCHAIN_LIST:-"riscv-binutils riscv-gcc riscv-glibc riscv-newlib riscv-gdb"}

fetch_repo "$root" "$root_repo_list" "--jobs $NJOB"
fetch_repo "$root/riscv-gnu-toolchain" "$toolchain_repo_list" "--recursive --jobs $NJOB"

echo "[*] done"


