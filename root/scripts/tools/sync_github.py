#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📥 同步 GitHub（支持自动保存仓库地址到自身）"

import os, sys, json, urllib.request, urllib.error, argparse

CONFIG = {
    "repo_url": "https://github.com/evol5201314/exetest",
    "branch": "main",
}

def save_repo_to_self(new_repo):
    script_path = os.path.abspath(__file__)
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = []
        in_config = False
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('CONFIG = {'):
                in_config = True
                new_lines.append(line)
                continue
            if in_config and '"repo_url"' in stripped:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f'{indent}"repo_url": "{new_repo}",\n')
            elif in_config and '}' in stripped and not stripped.startswith('"'):
                in_config = False
                new_lines.append(line)
            else:
                new_lines.append(line)
        with open(script_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"⚠️ 保存配置失败: {e}")
        return False

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
    except Exception:
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
    target_files = [f for f in files if f.get("name", "").endswith(('.py', '.html')) and f.get("type") == "file"]
    if not target_files:
        return True, "无 .py 或 .html 文件"
    os.makedirs(target_dir, exist_ok=True)
    downloaded = 0
    for f in target_files:
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', help='GitHub 仓库地址')
    parser.add_argument('--get-config', action='store_true', help='获取当前配置的仓库地址')
    args = parser.parse_args()

    if args.get_config:
        print(CONFIG.get("repo_url", ""))
        sys.exit(0)

    repo = args.repo if args.repo else CONFIG.get("repo_url")
    if not repo:
        print("❌ 未设置仓库地址")
        sys.exit(1)

    if args.repo and args.repo != CONFIG.get("repo_url"):
        if save_repo_to_self(args.repo):
            print(f"✅ 仓库地址已保存: {args.repo}")
        else:
            print("⚠️ 仓库地址保存失败，本次仍使用新地址同步")

    print("========================================")
    print("🐍 GitHub 同步工具")
    print(f"🔗 {repo}")
    print("========================================")
    ok1, msg1 = sync_dir(repo, "/root/scripts", "root/scripts")
    print(f"📁 /root/scripts/: {msg1}")
    ok2, msg2 = sync_dir(repo, "/root/scripts/tools", "root/scripts/tools")
    print(f"📁 /root/scripts/tools/: {msg2}")
    print("========================================")
    sys.exit(0 if ok1 and ok2 else 1)
