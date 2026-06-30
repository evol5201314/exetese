#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📝 新建脚本（交互式）"

import os, sys
SCRIPTS_DIR = "/root/scripts"

print("📝 新建脚本")
name = input("文件名（.py）: ").strip()
if not name:
    print("❌ 文件名不能为空")
    sys.exit(1)
if not name.endswith('.py'):
    name += '.py'
if '/' in name or '\\' in name:
    print("❌ 文件名不合法")
    sys.exit(1)
path = os.path.join(SCRIPTS_DIR, name)
if os.path.exists(path):
    print(f"❌ 文件 {name} 已存在")
    sys.exit(1)
print("请输入代码内容（输入 EOF 结束）:")
lines = []
while True:
    try:
        line = input()
        if line == 'EOF':
            break
        lines.append(line)
    except EOFError:
        break
with open(path, 'w') as f:
    f.write('\n'.join(lines))
print(f"✅ 脚本 {name} 创建成功")
