#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📄 查看脚本日志"

import os, sys, json, argparse

STATUS_FILE = "/tmp/script_status.json"
SCRIPTS_DIR = "/root/scripts"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', help='脚本名')
    parser.add_argument('--list', action='store_true', help='列出所有脚本')
    args = parser.parse_args()
    
    if args.list:
        scripts = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.py') and os.path.isfile(os.path.join(SCRIPTS_DIR, f))]
        print(json.dumps(scripts))
        sys.exit(0)
    
    if not args.name:
        print("❌ 请指定脚本名 --name")
        sys.exit(1)
    
    if not os.path.exists(STATUS_FILE):
        print("❌ 状态文件不存在")
        sys.exit(1)
    
    with open(STATUS_FILE, 'r') as f:
        data = json.load(f)
    
    s = data.get(args.name, {})
    output = f"状态: {s.get('status', 'idle')}\n"
    output += f"PID: {s.get('pid', '无')}\n"
    output += f"\n--- 输出 ---\n"
    output += s.get('last_output', '暂无输出')
    print(output)

if __name__ == "__main__":
    main()
