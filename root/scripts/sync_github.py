#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📈 独立版：一键同步 GitHub 仓库（镜像同步 /root/scripts/）"

"""
===== 【OpenWrt 低内存专用优化说明】 =====
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
屏蔽stdout/stderr输出至/dev/null，不读写闪存，无日志文件占用存储空间
"""

"""
================================================================
🐍 GitHub 独立同步工具（镜像同步版）
================================================================

【功能】
  从 GitHub 仓库同步 .py 文件到路由器
  完全镜像仓库结构：
    - 仓库根目录 .py → /root/scripts/
    - 仓库 /tools/ 子目录 .py → /root/scripts/tools/

【依赖】
  ✅ Python 3 (python3-light 即可)
  ✅ urllib (标准库)
  ✅ json   (标准库)
  ✅ os     (标准库)

【使用方法】
  1. 修改下方的 CONFIG（仓库地址、Token）
  2. 运行: python3 sync_github.py

================================================================
"""

import os
import sys
import json
import urllib.request
import urllib.error

# ========== 配置区域（请修改） ==========
CONFIG = {
    "repo_url": "https://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/evol5201314/exetese",
    "branch": "main",
}

# 环境变量覆盖（可选）
ENV_REPO = os.environ.get("GITHUB_REPO")
ENV_TOKEN = os.environ.get("GITHUB_TOKEN")
if ENV_REPO:
    CONFIG["repo_url"] = ENV_REPO

# ==========================================

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
        token, rest = rest.split("@", 1)
    if rest.startswith("github.com/"):
        rest = rest[11:]
    elif rest.startswith("www.github.com/"):
        rest = rest[15:]
    else:
        return None
    branch = "main"
    if "/tree/" in rest:
        repo_part, branch = rest.split("/tree/", 1)
        branch = branch.split("/")[0]
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

def fetch_api(url, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None

def sync_dir(repo_url, target_dir, sub_path=""):
    """同步指定子目录的 .py 文件"""
    parsed = parse_github_url(repo_url)
    if not parsed:
        return False, "解析失败"
    username = parsed["username"]
    repo = parsed["repo"]
    token = parsed["token"]
    branch = parsed.get("branch", "main")
    
    if sub_path:
        api_url = f"https://api.github.com/repos/{username}/{repo}/contents/{sub_path}?ref={branch}"
    else:
        api_url = f"https://api.github.com/repos/{username}/{repo}/contents?ref={branch}"
    
    resp = fetch_api(api_url, token)
    if resp is None:
        return False, "API请求失败"
    
    try:
        files = json.loads(resp)
    except Exception:
        return False, "JSON解析失败"
    
    if isinstance(files, dict) and "message" in files:
        return False, files["message"]
    if not isinstance(files, list):
        return False, "响应格式异常"
    
    py_files = [f for f in files if f.get("name", "").endswith(".py") and f.get("type") == "file"]
    if not py_files:
        return True, "无 .py 文件"
    
    os.makedirs(target_dir, exist_ok=True)
    downloaded = 0
    for f in py_files:
        name = f["name"]
        download_url = f.get("download_url")
        if not download_url:
            continue
        try:
            req = urllib.request.Request(download_url)
            if token:
                req.add_header("Authorization", f"token {token}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8")
                path = os.path.join(target_dir, name)
                with open(path, "w", encoding="utf-8") as out:
                    out.write(content)
                downloaded += 1
        except Exception:
            pass
    return True, f"下载 {downloaded} 个文件"

if __name__ == "__main__":
    repo = CONFIG.get("repo_url")
    if not repo:
        print("❌ 未设置仓库地址")
        sys.exit(1)
    
    print("========================================")
    print("🐍 GitHub 独立同步工具 (镜像同步)")
    print("========================================")
    
    # 仓库根目录 → /root/scripts/
    ok1, msg1 = sync_dir(repo, "/root/scripts", "")
    print(f"📁 /root/scripts/: {msg1}")
    
    # 仓库 /tools/ 子目录 → /root/scripts/tools/
    ok2, msg2 = sync_dir(repo, "/root/scripts/tools", "tools")
    print(f"📁 /root/scripts/tools/: {msg2}")
    
    print("========================================")
    sys.exit(0 if ok1 and ok2 else 1)
