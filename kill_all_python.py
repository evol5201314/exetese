#!/usr/bin/env python3
beizhu = "📈 关闭并清理python进程 面板也关闭"
"""
===== 【OpenWrt 低内存专用优化说明 请勿删除以下轻量化逻辑】
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
屏蔽stdout/stderr输出至/dev/null，不读写闪存，无日志文件占用存储空间
保留下方备注方便查看脚本详情
"""
import os
import subprocess
import signal
import time

def kill_all_python():
    my_pid = os.getpid()
    
    # 获取所有 python3 进程（包括自己）
    result = subprocess.run(
        "ps | grep python3 | grep -v grep | awk '{print $1}'",
        shell=True, capture_output=True, text=True
    )
    pids = result.stdout.strip().split()
    if not pids:
        print("⚠️ 未找到任何 Python 进程")
        return

    print(f"找到 {len(pids)} 个 Python 进程: {pids}")

    # 杀掉所有其他进程
    for pid_str in pids:
        pid = int(pid_str)
        if pid == my_pid:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            print(f"✅ 已杀掉 Python 进程 (PID: {pid})")
        except Exception as e:
            print(f"❌ 杀进程 {pid} 失败: {e}")

    # 等待一下，让进程完全退出
    time.sleep(1)

    # 清理内存缓存（同步并释放缓存）
    print("🧹 清理内存缓存...")
    os.system("sync && echo 3 > /proc/sys/vm/drop_caches")
    print("✅ 内存缓存已清理")

    # 最后自杀
    print("🔥 现在杀死自己...")
    try:
        os.kill(my_pid, signal.SIGKILL)
    except Exception:
        pass

if __name__ == "__main__":
    kill_all_python()
