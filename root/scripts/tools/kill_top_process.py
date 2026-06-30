#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "💣 清理占用内存最高的非关键进程（自动缓存清理+GC）"

import os, sys, signal, gc, subprocess, glob

def get_top_process():
    exclude_pid = os.getpid()
    sys_keywords = ['init','procd','logd','ubusd','netd','ueventd','syslogd','klogd','watchdog','hotplug','ntpd',
                    'sshd','dropbear','kthreadd','ksoftirqd','kworker','bdflush','kswapd','khugepaged','kcompactd']
    procs = []
    for p in glob.glob('/proc/[0-9]*/statm'):
        try:
            pid = int(p.split('/')[2])
            if pid == exclude_pid or pid <= 10:
                continue
            with open(f'/proc/{pid}/status', 'r') as f:
                name = ''
                for line in f:
                    if line.startswith('Name:'):
                        name = line.split(':',1)[1].strip()
                        break
            if not name or name.startswith('[') or name.endswith(']'):
                continue
            if any(kw in name.lower() for kw in sys_keywords):
                continue
            with open(f'/proc/{pid}/statm', 'r') as f:
                statm = f.read().split()
                rss = int(statm[1]) * 4 if len(statm) >= 2 else 0
            if rss < 1024:
                continue
            procs.append({'pid':pid, 'name':name, 'rss_kb':rss})
        except:
            pass
    if not procs:
        return None
    procs.sort(key=lambda x: x['rss_kb'], reverse=True)
    return procs[0]

def main():
    target = get_top_process()
    if not target:
        print("❌ 未找到可清理的进程")
        sys.exit(1)
    pid, name, rss = target['pid'], target['name'], target['rss_kb']
    print(f"🔪 杀掉进程: {name} (PID: {pid})，内存占用 {rss//1024}MB")
    try:
        os.kill(pid, signal.SIGKILL)
    except Exception as e:
        print(f"❌ 杀进程失败: {e}")
        sys.exit(1)
    # 清理缓存
    subprocess.run(['sync'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open('/proc/sys/vm/drop_caches', 'w') as f:
            f.write('3')
        print("🧹 缓存已清理")
    except:
        pass
    gc.collect()
    print("♻️ Python GC 已触发")
    print("✅ 清理完成")

if __name__ == "__main__":
    main()
