#!/usr/bin/env python3
# -*- coding: utf-8 -*-

beizhu = "📈 一键同步github仓库脚本到本地"

"""
===== 【OpenWrt 低内存专用优化说明 请勿删除以下轻量化逻辑】
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
屏蔽stdout/stderr输出至/dev/null，不读写闪存，无日志文件占用存储空间
"""
"""
================================================================
🐍 GitHub 脚本同步工具（独立版）
================================================================

【功能】
  从 GitHub 仓库拉取所有 .py 文件到本地指定目录
  无需 Flask，无需 requests，仅依赖 Python 标准库

【依赖】
  ✅ Python 3 (python3-light 即可)
  ✅ urllib  (标准库)
  ✅ json    (标准库)
  ✅ os      (标准库)

【使用方法】
  1. 修改下方的配置项（仓库地址、Token、目标目录）
  2. 运行: python3 sync_github.py

【配置方式】
  方式一：直接修改下方 CONFIG 字典（推荐）
  方式二：设置环境变量（可选，便于保密 Token）
    export GITHUB_TOKEN="ghp_xxxxx"
    export GITHUB_REPO="https://github.com/用户名/仓库名"
  然后运行脚本

【Cron 定时使用】
  # 每天凌晨 3 点同步一次
  0 3 * * * cd /path/to/script && python3 sync_github.py >> /var/log/sync.log 2>&1

================================================================
"""

import os
import sys
import json
import urllib.request
import urllib.error

CONFIG = {
    "repo_url": "https://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@github.com/evol5201314/exetese",
    "target_dir": "/root/scripts",
    "branch": "main",
}

ENV_REPO = os.environ.get("GITHUB_REPO")
ENV_TOKEN = os.environ.get("GITHUB_TOKEN")
if ENV_REPO:
    CONFIG["repo_url"] = ENV_REPO

def parse_github_url(raw_url):
    raw = raw_url.strip()
    if not raw:
        return None
    token = ""
    if raw.startswith("https://"):
        rest = raw[8:]
    elif raw.startswith("http://"):
        rest = raw[7:]
    else:
        rest = raw
    if "@" in rest and "github.com" in rest:
        parts = rest.split("@")
        token = parts[0]
        rest = parts[1]
    if rest.startswith("github.com/"):
        rest = rest[11:]
    elif rest.startswith("www.github.com/"):
        rest = rest[15:]
    else:
        return None
    branch = "main"
    if "/tree/" in rest:
        parts = rest.split("/tree/")
        repo_part = parts[0]
        branch = parts[1].split("/")[0]
        rest = repo_part
    parts = rest.split("/")
    if len(parts) >= 2:
        return {
            "username": parts[0],
            "repo": parts[1],
            "branch": branch,
            "token": token
        }
    return None

def fetch_github_api(url, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except:
        return None

def sync_from_github(repo_url, target_dir, branch="main"):
    parsed = parse_github_url(repo_url)
    if not parsed:
        return False
    username = parsed["username"]
    repo = parsed["repo"]
    token = parsed["token"]
    branch = parsed.get("branch", branch)
    api_url = f"https://api.github.com/repos/{username}/{repo}/contents?ref={branch}"
    resp_text = fetch_github_api(api_url, token)
    if resp_text is None:
        return False
    try:
        files = json.loads(resp_text)
    except:
        return False
    if isinstance(files, dict) and "message" in files:
        return False
    if not isinstance(files, list):
        return False
    py_files = [f for f in files if f.get("name", "").endswith(".py") and f.get("type") == "file"]
    if not py_files:
        return True
    os.makedirs(target_dir, exist_ok=True)
    for file_info in py_files:
        name = file_info["name"]
        download_url = file_info.get("download_url")
        if not download_url:
            continue
        try:
            req = urllib.request.Request(download_url)
            if token:
                req.add_header("Authorization", f"token {token}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8")
                target_path = os.path.join(target_dir, name)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
        except:
            pass
    return True

if __name__ == "__main__":
    repo = CONFIG.get("repo_url")
    target = CONFIG.get("target_dir", "/root/scripts")
    branch = CONFIG.get("branch", "main")
    if not repo:
        sys.exit(1)
    success = sync_from_github(repo, target, branch)
    sys.exit(0 if success else 1)
