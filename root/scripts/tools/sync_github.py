#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📥 从 GitHub 同步脚本（镜像同步 /root/scripts/ 结构）"

"""
同步规则：
  - 仓库根目录 .py → /root/scripts/
  - 仓库 /tools/ 子目录 .py → /root/scripts/tools/
"""
import os, sys, json, urllib.request, urllib.error

DEBUG = False

CONFIG = {
    "repo_url": "https://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/evol5201314/exetese",
    "branch": "main",
}

def log(msg):
    if DEBUG:
        print(msg)

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
        return {"username": parts[0], "repo": parts[1], "branch": branch, "token": token}
    return None

def fetch_api(url, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        log(f"请求失败: {e}")
        return None

def sync_dir(repo_url, target_dir, sub_path=""):
    parsed = parse_github_url(repo_url)
    if not parsed:
        return False, "解析失败"
    username, repo, token, branch = parsed["username"], parsed["repo"], parsed["token"], parsed["branch"]
    if sub_path:
        api_url = f"https://api.github.com/repos/{username}/{repo}/contents/{sub_path}?ref={branch}"
    else:
        api_url = f"https://api.github.com/repos/{username}/{repo}/contents?ref={branch}"
    log(f"📡 请求: {api_url}")
    resp = fetch_api(api_url, token)
    if resp is None:
        return False, "API请求失败"
    try:
        files = json.loads(resp)
    except:
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
                log(f"  ✅ {name}")
        except Exception as e:
            log(f"  ❌ {name}: {e}")
    return True, f"下载 {downloaded} 个文件"

if __name__ == "__main__":
    repo = CONFIG.get("repo_url")
    if not repo:
        print("❌ 未设置仓库地址")
        sys.exit(1)
    print("========================================")
    print("🐍 GitHub 同步工具 (镜像同步)")
    print("========================================")
    ok1, msg1 = sync_dir(repo, "/root/scripts", "")
    print(f"📁 /root/scripts/: {msg1}")
    ok2, msg2 = sync_dir(repo, "/root/scripts/tools", "tools")
    print(f"📁 /root/scripts/tools/: {msg2}")
    print("========================================")
    sys.exit(0 if ok1 and ok2 else 1)
