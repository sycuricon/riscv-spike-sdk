#!/usr/bin/env bash

cd "$HOME/riscv-spike-sdk" || exit 1
trap 'echo "已停止重试"; exit 130' INT TERM

attempt=1

while true; do
    echo
    echo "[$(date '+%F %T')] 第 ${attempt} 次尝试"

    if git \
        -c http.version=HTTP/1.1 \
        -c 'url.https://github.com/gregkh/linux.git.insteadOf=https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git' \
        submodule update --init --depth 1 --progress -- repo/linux
    then
        echo "[$(date '+%F %T')] Linux 子模块下载、检出成功"
        git submodule status -- repo/linux
        break
    fi

    echo "本次失败，60 秒后重试"
    attempt=$((attempt + 1))
    sleep 60
done
