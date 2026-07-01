#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "⏹ 停止指定脚本（通过 PID）"

import os, sys, json, signal, argparse

STATUS_FILE = "/tmp/script_status.json"

parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
args = parser.parse_args()

name = args.name.strip()
if not name:
    print("❌ 脚本名不能为空")
    sys.exit(1)

if not os.path.exists(STATUS_FILE):
    print("❌ 状态文件不存在")
    sys.exit(1)

with open(STATUS_FILE, 'r') as f:
    status_data = json.load(f)

entry = status_data.get(name)
if not entry:
    print(f"❌ 脚本 {name} 不在状态文件中")
    sys.exit(1)

pid = entry.get('pid')
if not pid:
    print(f"ℹ️ 脚本 {name} 没有运行的进程")
    sys.exit(0)

try:
    os.kill(pid, 0)
    os.kill(pid, signal.SIGKILL)
    print(f"✅ 已停止脚本 {name} (PID: {pid})")
except OSError:
    print(f"⚠️ 进程 {pid} 已不存在，清理状态")
finally:
    entry['status'] = 'stopped'
    entry['pid'] = None
    entry['last_output'] = f'已手动停止 (PID: {pid})' if pid else '已停止'
    with open(STATUS_FILE, 'w') as f:
        json.dump(status_data, f)
