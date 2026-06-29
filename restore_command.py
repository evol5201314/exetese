#!/usr/bin/python3
import os
beizhu = "📈 恢复command脚本数据"
LUCI_FILE = '/etc/config/luci'
COMMAND_FILE = '/etc/config/command'

def restore_command():
    if not os.path.exists(COMMAND_FILE):
        print(f"Error: {COMMAND_FILE} not found")
        return

    with open(COMMAND_FILE, 'r') as f:
        new_command_lines = f.readlines()

    if not os.path.exists(LUCI_FILE):
        print(f"Error: {LUCI_FILE} not found")
        return

    with open(LUCI_FILE, 'r') as f:
        lines = f.readlines()

    # 删除所有现有的 config command 段落
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('config command'):
            i += 1
            while i < len(lines):
                if lines[i].strip().startswith('config '):
                    break
                i += 1
            # 跳过整个段落，不添加到 new_lines
        else:
            new_lines.append(line)
            i += 1

    # 追加新的 command 段落（如果文件末尾非空，先加一个换行）
    if new_lines and new_lines[-1].strip() != '':
        new_lines.append('\n')
    new_lines.extend(new_command_lines)

    # 写回 luci 文件
    with open(LUCI_FILE, 'w') as f:
        f.writelines(new_lines)

    print(f"Restored command sections from {COMMAND_FILE} to {LUCI_FILE}")

if __name__ == '__main__':
    restore_command()
