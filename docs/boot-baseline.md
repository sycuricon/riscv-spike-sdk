# Baseline A1: 普通启动基线

本页保存同学交付 A1 时的历史验证状态，不代表当前 KVM 集成进度。
当前操作入口和验证结果见 [kvm-guide.md](kvm-guide.md)。

## 当前状态
- **已验证**：OpenSBI -> Linux 6.17.2 -> initramfs -> root shell 的启动链跑通。
- **已验证**：新 rootfs 的 devtmpfs 挂载和设备节点正常。
- **未验证**：PMP.Virt 模拟器扩展、KVM 模块加载与 guest 启动。

## 组件版本
- QEMU: v10.1.0 (独立于本 SDK 编译)
- Linux: v6.17.2 (Image.config 内嵌已确认，源码提交来源待核实)
- OpenSBI: v1.7
- 工具链: 编译内核与系统时的外部工具链 (GCC 版本待核实)
- Buildroot: 2025.08 (提交 3386677f0a4d1c0150e772eb07cede05e88a2d6d)

## 构建与启动
请优先使用当前 KVM 操作指南中的 Makefile 入口。

原基线脚本已移除。当前构建和启动方法见 [KVM 操作指南](kvm-guide.md)。本页仅记录 A1 交付时的状态

*注：目前为已验证的启动基线，尚未完成从源码重建的验证。*

baseline-a1-inputs.sha256 保存同学提供的原始镜像校验值，其中路径是当时的存放位置，不适用于当前重新构建的产物。

