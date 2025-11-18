#!/usr/bin/env python3


import os
import stat
import sys

def get_file_metadata(file_path):
    """
    获取文件的元数据：所有者、组、权限、文件类型等。
    如果是符号链接，使用 lstat 以避免解析符号链接。
    """
    try:
        # 使用 lstat() 获取文件的状态信息（对于符号链接会返回符号链接本身的元数据）
        file_stat = os.lstat(file_path)

        # 获取所有者、组、权限
        owner = 'root'  # 获取当前登录用户（你可以根据需要修改为实际的 owner 和 group）
        group = 'wheel'  # 固定为 wheel，或者根据需求修改
        permissions = oct(file_stat.st_mode)[-3:]  # 获取文件权限（最后三位）

        return owner, group, permissions, file_stat
    except Exception as e:
        print(f"Error getting metadata for {file_path}: {e}")
        return None

def generate_manifest(directory):
    """
    遍历目录，并根据文件类型生成相应的 manifest 内容，返回一个元组列表。
    """
    manifest_lines = []

    # 遍历目录中的所有文件
    for dirpath, dirnames, filenames in os.walk(directory):
        # 对每一个文件和目录处理
        for name in dirnames + filenames:
            file_path = os.path.join(dirpath, name)

            # 获取文件元数据
            metadata = get_file_metadata(file_path)
            if not metadata:
                continue

            owner, group, permissions, file_stat = metadata

            # 获取相对路径
            relative_path = os.path.relpath(file_path, directory)
            relative_path = f'./{relative_path}'  # 确保以 ./ 开头

            # 判断文件类型，并构建元数据
            if stat.S_ISDIR(file_stat.st_mode):
                # 对于目录类型
                manifest_line = f"type=dir uname={owner} gname={group} mode={permissions}"
                # 根据路径添加特定标签
                if relative_path.startswith("boot"):
                    manifest_line += " tags=package=bootloader"
                elif relative_path.startswith("dtb"):
                    manifest_line += " tags=package=runtime"
            elif stat.S_ISLNK(file_stat.st_mode):
                # 对于符号链接类型
                link_target = os.readlink(file_path)
                manifest_line = f"type=link uname={owner} gname={group} mode={permissions} link={link_target}"
            elif stat.S_ISREG(file_stat.st_mode):
                # 对于普通文件类型（文件）
                manifest_line = f"type=file uname={owner} gname={group} mode={permissions}"

            # 将相对路径和元数据存入元组
            manifest_lines.append((relative_path, manifest_line))

    # 按照相对路径对元组列表进行排序
    manifest_lines.sort(key=lambda x: x[0])

    return manifest_lines

def main():
    # 输入根目录路径
    assert len(sys.argv) >= 2, "Please provide the root directory path as an argument."
    root_directory = sys.argv[1]

    # 生成 manifest
    manifest_lines = generate_manifest(root_directory)

    # 输出到文件
    output_file = sys.argv[2]
    with open(output_file, 'w') as f:
        for relative_path, manifest_data in manifest_lines:
            f.write(f"{relative_path} {manifest_data}\n")

    print(f"Manifest file generated: {output_file}")

if __name__ == "__main__":
    main()