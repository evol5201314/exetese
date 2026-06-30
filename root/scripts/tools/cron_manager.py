#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "⏰ Cron 管理（支持命令行参数）"

import os, sys, subprocess, argparse

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
        for job in jobs:
            print(job)

def add_cron(schedule, command):
    try:
        if not os.path.exists(CRONTAB_FILE):
            with open(CRONTAB_FILE, 'w') as f:
                f.write("# OpenWrt crontab\n")
        with open(CRONTAB_FILE, 'r') as f:
            lines = f.readlines()
        for line in lines:
            if line.strip() == f"{schedule} {command}":
                print("⚠️ 该任务已存在")
                return
        with open(CRONTAB_FILE, 'a') as f:
            f.write(f"{schedule} {command}\n")
        subprocess.run(['/etc/init.d/cron', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ 任务已添加")
    except Exception as e:
        print(f"❌ 添加失败: {e}")

def delete_cron(full_line):
    try:
        with open(CRONTAB_FILE, 'r') as f:
            lines = f.readlines()
        new_lines = []
        deleted = False
        for line in lines:
            if line.strip() == full_line.strip():
                deleted = True
                continue
            new_lines.append(line)
        if not deleted:
            print("❌ 未找到该任务")
            return
        with open(CRONTAB_FILE, 'w') as f:
            f.writelines(new_lines)
        subprocess.run(['/etc/init.d/cron', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ 任务已删除")
    except Exception as e:
        print(f"❌ 删除失败: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true', help='列出所有任务')
    parser.add_argument('--add', nargs=2, metavar=('SCHEDULE', 'COMMAND'), help='添加任务')
    parser.add_argument('--delete', metavar='LINE', help='删除任务（输入完整行）')
    args = parser.parse_args()

    if args.list:
        list_crons()
    elif args.add:
        add_cron(args.add[0], args.add[1])
    elif args.delete:
        delete_cron(args.delete)
    else:
        # 无参数则进入交互模式（兼容旧版）
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
                schedule = input("执行时间（分 时 日 月 周）: ").strip()
                if len(schedule.split()) != 5:
                    print("❌ 格式错误")
                    continue
                command = input("执行命令: ").strip()
                if command:
                    add_cron(schedule, command)
            elif choice == '3':
                list_crons()
                line = input("输入要删除的完整任务行: ").strip()
                if line:
                    delete_cron(line)
            elif choice == '4':
                break
            else:
                print("❌ 无效选择")
