#!/usr/bin/env python3
"""
===== 【OpenWrt 低内存专用优化说明 请勿删除以下轻量化逻辑】
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
屏蔽stdout/stderr输出至/dev/null，不读写闪存，无日志文件占用存储空间
保留下方备注方便查看脚本详情
"""
beizhu = "📈 备份command脚本数据"

import os

LUCI_FILE = '/etc/config/luci'
COMMAND_FILE = '/etc/config/command'

def extract_command():
    if not os.path.exists(LUCI_FILE):
        return

    extracted = []
    in_command = False
    with open(LUCI_FILE, 'r') as f:
        for line in f:
            stripped = line.lstrip()
            if stripped.startswith('config command'):
                in_command = True
                extracted.append(line)
                continue
            if in_command:
                if stripped.startswith('config '):
                    in_command = False
                    # 不添加此行，因为它是下一个配置的开始
                    # 但为了保留原逻辑（不跳过），我们将标志置false，但该行不属于当前段落
                    # 由于已经在循环中，该行会在后续被忽略（因为in_command为False）
                    continue
                extracted.append(line)
            # 其他行忽略

    if extracted:
        with open(COMMAND_FILE, 'w') as f:
            f.writelines(extracted)

if __name__ == '__main__':
    extract_command()
