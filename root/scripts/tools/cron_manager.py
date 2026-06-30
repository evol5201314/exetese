#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "⏰ Cron 定时任务管理（交互式）"

import os, sys, subprocess
CRONTAB_FILE = "/etc/crontabs/root"

def list_crons():
    if not os.path.exists(CRONTAB_FILE):
        print("📭 暂无定时任务")
        return
    with open(CRONTAB_FILE, 'r') as f:
        lines = f.readlines()
    jobs = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
    if not jobs:
        print("📭 暂无定时任务")
    else:
        print("📋 当前定时任务:")
        for i, job in enumerate(jobs, 1):
            print(f"  {i}. {job}")

def add_cron():
    schedule = input("执行时间（分 时 日 月 周）: ").strip()
    if len(schedule.split()) != 5:
        print("❌ 格式错误，应为: 分 时 日 月 周")
        return
    command = input("执行命令: ").strip()
    if not command:
        print("❌ 命令不能为空")
        return
    with open(CRONTAB_FILE, 'a') as f:
        f.write(f"{schedule} {command}\n")
    subprocess.run(['/etc/init.d/cron', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ 任务已添加")

def delete_cron():
    if not os.path.exists(CRONTAB_FILE):
        print("❌ 没有任务可删除")
        return
    with open(CRONTAB_FILE, 'r') as f:
        lines = f.readlines()
    jobs = [l for l in lines if l.strip() and not l.startswith('#')]
    if not jobs:
        print("❌ 没有任务可删除")
        return
    print("📋 当前任务:")
    for i, job in enumerate(jobs, 1):
        print(f"  {i}. {job.strip()}")
    try:
        idx = int(input("选择要删除的编号: ")) - 1
        if idx < 0 or idx >= len(jobs):
            print("❌ 无效编号")
            return
        del lines[lines.index(jobs[idx])]
        with open(CRONTAB_FILE, 'w') as f:
            f.writelines(lines)
        subprocess.run(['/etc/init.d/cron', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ 任务已删除")
    except:
        print("❌ 无效输入")

if __name__ == "__main__":
    while True:
        print("\n⏰ Cron 管理")
        print("1. 查看任务")
        print("2. 添加任务")
        print("3. 删除任务")
        print("4. 退出")
        choice = input("请选择: ").strip()
        if choice == '1':
            list_crons()
        elif choice == '2':
            add_cron()
        elif choice == '3':
            delete_cron()
        elif choice == '4':
            break
        else:
            print("❌ 无效选择")
