#!/usr/bin/env python3
"""
===== 【OpenWrt 低内存专用优化说明 请勿删除以下轻量化逻辑】
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
屏蔽stdout/stderr输出至/dev/null，不读写闪存，无日志文件占用存储空间
保留下方备注方便查看脚本详情
"""
beizhu = "📈 关闭并清理python进程 面板也关闭"

import os
import signal
import time

def kill_all_python():
    my_pid = os.getpid()
    # 使用 ps 获取所有 python3 进程 PID
    try:
        pids = []
        # 读取 /proc 目录更轻量，但为了兼容，保留ps
        # 使用 os.popen 或 subprocess，但需要静默
        output = os.popen("ps | grep python3 | grep -v grep | awk '{print $1}'").read()
        if output:
            pids = output.strip().split()
    except:
        pass
    
    for pid_str in pids:
        pid = int(pid_str)
        if pid == my_pid:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except:
            pass
    
    # 等待进程退出
    time.sleep(0.5)  # 稍等一会儿
    # 清理内存缓存
    os.system("sync && echo 3 > /proc/sys/vm/drop_caches >/dev/null 2>&1")
    # 自杀
    try:
        os.kill(my_pid, signal.SIGKILL)
    except:
        pass

if __name__ == "__main__":
    kill_all_python()
