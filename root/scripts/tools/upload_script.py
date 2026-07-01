#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📤 上传脚本到 /root/scripts/"

import os, sys, argparse

SCRIPTS_DIR = "/root/scripts"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--filename', help='要上传的文件名')
    parser.add_argument('--content', help='文件内容')
    args = parser.parse_args()
    
    if not args.filename:
        print("❌ 缺少文件名")
        sys.exit(1)
    
    if not args.filename.endswith('.py'):
        print("❌ 只支持 .py 文件")
        sys.exit(1)
    
    if not args.content:
        print("❌ 文件内容为空")
        sys.exit(1)
    
    path = os.path.join(SCRIPTS_DIR, args.filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(args.content)
        print(f"✅ {args.filename} 上传成功")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
