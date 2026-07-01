#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📤 上传脚本到 /root/scripts/ (支持base64)"

import os, sys, argparse
import base64

SCRIPTS_DIR = "/root/scripts"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--filename', required=True, help='要上传的文件名')
    parser.add_argument('--content', help='文件内容（base64编码）')
    args = parser.parse_args()
    
    if not args.filename.endswith('.py'):
        print("❌ 只支持 .py 文件")
        sys.exit(1)
    
    if '/' in args.filename or '\\' in args.filename:
        print("❌ 文件名不合法")
        sys.exit(1)
    
    # 获取内容：优先使用 --content（base64解码），否则从 stdin 读取
    if args.content:
        try:
            content = base64.b64decode(args.content).decode('utf-8')
        except Exception as e:
            print(f"❌ base64解码失败: {e}")
            sys.exit(1)
    else:
        content = sys.stdin.read()
    
    if not content:
        print("❌ 文件内容为空")
        sys.exit(1)
    
    path = os.path.join(SCRIPTS_DIR, args.filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {args.filename} 上传成功")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
