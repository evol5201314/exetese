#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "▶ 运行指定脚本（包装脚本，用于显示输出）"

import os, sys, subprocess, argparse

SCRIPTS_DIR = "/root/scripts"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True, help='脚本名')
    args = parser.parse_args()
    
    script_path = os.path.join(SCRIPTS_DIR, args.name)
    if not os.path.exists(script_path):
        print(f"❌ 脚本 {args.name} 不存在")
        sys.exit(1)
    
    try:
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            print(f"⚠️ 脚本退出码: {result.returncode}")
        print(output)
        sys.exit(result.returncode)
    except subprocess.TimeoutExpired:
        print("⏱ 执行超时（300秒）")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 执行异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
