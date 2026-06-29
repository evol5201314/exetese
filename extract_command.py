#!/usr/bin/python3
import os

LUCI_FILE = '/etc/config/luci'
COMMAND_FILE = '/etc/config/command'

def extract_command():
    if not os.path.exists(LUCI_FILE):
        print(f"Error: {LUCI_FILE} not found")
        return

    with open(LUCI_FILE, 'r') as f:
        lines = f.readlines()

    extracted = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('config command'):
            # 记录整个段落
            extracted.append(line)
            i += 1
            while i < len(lines):
                if lines[i].strip().startswith('config '):
                    break
                extracted.append(lines[i])
                i += 1
            # 不加额外的空行，保持原样
        else:
            i += 1

    # 写入 command 文件（覆盖）
    with open(COMMAND_FILE, 'w') as f:
        f.writelines(extracted)

    print(f"Extracted {len(extracted)} lines to {COMMAND_FILE}")

if __name__ == '__main__':
    extract_command()
