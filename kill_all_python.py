#!/usr/bin/env python3
# /root/scripts/kill_all_python.py
# 功能：杀掉所有 python3 进程（包括面板、监控脚本、以及这个清理脚本自己）

import os
import subprocess
import signal

def kill_all_python():
    # 获取当前脚本自己的 PID（先不杀自己，等最后杀）
    my_pid = os.getpid()
    
    # 获取所有 python3 进程的 PID（包括自己）
    result = subprocess.run(
        "ps | grep python3 | grep -v grep | awk '{print $1}'",
        shell=True, capture_output=True, text=True
    )
    pids = result.stdout.strip().split()
    if not pids:
        print("⚠️ 未找到任何 Python 进程")
        return

    print(f"找到 {len(pids)} 个 Python 进程: {pids}")

    # 先杀掉除了自己以外的所有进程
    for pid_str in pids:
        pid = int(pid_str)
        if pid == my_pid:
            continue  # 先留着
        try:
            os.kill(pid, signal.SIGKILL)
            print(f"✅ 已杀掉 Python 进程 (PID: {pid})")
        except Exception as e:
            print(f"❌ 杀进程 {pid} 失败: {e}")

    # 最后杀掉自己（面板和这个脚本的父进程已经被干掉了）
    print("🔥 现在杀死自己...")
    try:
        os.kill(my_pid, signal.SIGKILL)
    except Exception:
        pass  # 杀死自己后，后面的代码不会执行

if __name__ == "__main__":
    kill_all_python()
