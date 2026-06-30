#!/usr/bin/env python3
"""
===== 【OpenWrt 低内存专用优化说明 请勿删除以下轻量化逻辑】
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
屏蔽stdout/stderr输出至/dev/null，不读写闪存，无日志文件占用存储空间
保留下方备注方便查看脚本详情
"""
beizhu = "📈 恢复command脚本数据"

import os

LUCI_FILE = '/etc/config/luci'
COMMAND_FILE = '/etc/config/command'

def restore_command():
    if not os.path.exists(COMMAND_FILE) or not os.path.exists(LUCI_FILE):
        return

    # 读取备份的 command 段落
    with open(COMMAND_FILE, 'r') as f:
        backup_lines = f.readlines()

    # 读取原 luci 文件并过滤掉所有 config command 段落
    with open(LUCI_FILE, 'r') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped.startswith('config command'):
            # 跳过该段落
            i += 1
            while i < len(lines):
                if lines[i].lstrip().startswith('config '):
                    break
                i += 1
            # 循环结束后，i 指向下一个 config 行或文件末尾，但外层循环会继续处理
            continue
        else:
            new_lines.append(line)
            i += 1

    # 如果原文件末尾非空，补一个换行
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines.append('\n')
    elif new_lines and new_lines[-1].strip() == '':
        # 如果已经是空行，不额外加
        pass
    else:
        # 如果原文件为空，可以不加换行直接追加
        pass

    # 追加备份内容
    new_lines.extend(backup_lines)

    # 写回文件
    with open(LUCI_FILE, 'w') as f:
        f.writelines(new_lines)

if __name__ == '__main__':
    restore_command()
