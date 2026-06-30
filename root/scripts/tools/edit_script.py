#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "✏️ 编辑脚本（交互式）"

import os, sys
SCRIPTS_DIR = "/root/scripts"

scripts = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.py') and os.path.isfile(os.path.join(SCRIPTS_DIR, f))]
if not scripts:
    print("❌ 没有可编辑的脚本")
    sys.exit(1)
print("📋 可用脚本:")
for i, s in enumerate(scripts):
    print(f"  {i+1}. {s}")
try:
    idx = int(input("选择脚本编号: ")) - 1
    name = scripts[idx]
except:
    print("❌ 无效选择")
    sys.exit(1)
path = os.path.join(SCRIPTS_DIR, name)
with open(path, 'r') as f:
    content = f.read()
print(f"\n当前内容:\n{'-'*40}\n{content}\n{'-'*40}")
print("输入新内容（输入 EOF 结束，空则保持原样）:")
lines = []
while True:
    try:
        line = input()
        if line == 'EOF':
            break
        lines.append(line)
    except EOFError:
        break
if lines:
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"✅ {name} 已更新")
else:
    print("ℹ️ 内容未变更")
