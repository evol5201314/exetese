#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📈 面板程序 (优化版)"
"""
============================================================
🐍 脚本面板 - 内存优化版（无自动保存同步框，备注为边框样式）
============================================================
"""

import os
import sys
import json
import subprocess
import threading
import shutil
import time
import socket
import signal
import gc
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

SCRIPTS_DIR = "/root/scripts"
STATUS_FILE = "/tmp/script_status.json"
HISTORY_FILE = "/tmp/script_history.json"

# ========== 同步框默认内容（仅作为默认值，修改不会自动保存） ==========
tongbukuang = "https://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@github.com/evol5201314/exetest"

def init_files():
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs("/root/dashboard", exist_ok=True)
    for f in [STATUS_FILE, HISTORY_FILE]:
        if not os.path.exists(f):
            with open(f, 'w') as fp:
                json.dump({}, fp)

# ========== 提取 beizhu ==========
def extract_beizhu(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                line = line.strip()
                if line.startswith('beizhu ='):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        value = parts[1].strip()
                        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                            return value[1:-1]
                        else:
                            return value
        return None
    except:
        return None

# ========== GitHub 地址解析 ==========
def parse_github_url(raw_url):
    raw = raw_url.strip()
    if not raw:
        return None
    token = ''
    if raw.startswith('https://'):
        rest = raw[8:]
    elif raw.startswith('http://'):
        rest = raw[7:]
    else:
        rest = raw
    if '@' in rest and 'github.com' in rest:
        parts = rest.split('@')
        token = parts[0]
        rest = parts[1]
    if rest.startswith('github.com/'):
        rest = rest[11:]
    elif rest.startswith('www.github.com/'):
        rest = rest[15:]
    else:
        return None
    branch = 'main'
    if '/tree/' in rest:
        parts = rest.split('/tree/')
        repo_part = parts[0]
        branch = parts[1].split('/')[0]
        rest = repo_part
    parts = rest.split('/')
    if len(parts) >= 2:
        return {
            'username': parts[0],
            'repo': parts[1],
            'branch': branch,
            'token': token
        }
    return None

# ========== 端口清理 ==========
def kill_process_on_port(port=5000):
    try:
        cmd = f"netstat -tulpn 2>/dev/null | grep ':{port} ' | awk '{{print $7}}' | cut -d'/' -f1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        pids = result.stdout.strip().split()
        if not pids:
            cmd = f"lsof -t -i:{port} 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            pids = result.stdout.strip().split()
        if pids:
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"✅ 已清理占用端口 {port} 的残留进程 (PID: {pid})")
                except:
                    pass
            return True
        else:
            print(f"✅ 端口 {port} 空闲")
            return True
    except Exception as e:
        print(f"⚠️ 端口检测跳过: {e}")
        return True

# ========== 获取脚本列表 ==========
def get_scripts():
    scripts = []
    if not os.path.exists(SCRIPTS_DIR):
        return scripts
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    with open(HISTORY_FILE, 'r') as f:
        history_data = json.load(f)
    for fn in sorted(os.listdir(SCRIPTS_DIR)):
        if fn.endswith('.py'):
            p = os.path.join(SCRIPTS_DIR, fn)
            st = os.stat(p)
            s = status_data.get(fn, {'status': 'idle', 'pid': None})
            h = history_data.get(fn, [])
            last_run = h[-1]['time'] if h else None
            remark = extract_beizhu(p) or ''
            scripts.append({
                'name': fn,
                'size': st.st_size,
                'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'status': s.get('status', 'idle'),
                'pid': s.get('pid'),
                'last_run': last_run,
                'history_count': len(h),
                'remark': remark
            })
    return scripts

# ========== Flask 路由 ==========
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/scripts')
def api_scripts():
    return jsonify(get_scripts())

@app.route('/api/sync_config')
def sync_config():
    return jsonify({'tongbukuang': tongbukuang})

# ========== 运行脚本（优化内存和资源释放） ==========
@app.route('/api/run/<name>', methods=['POST'])
def run_script(name):
    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.exists(path):
        return jsonify({'error': '脚本不存在'}), 404
    
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    old_pid = status_data.get(name, {}).get('pid')
    if old_pid:
        try:
            os.kill(old_pid, 0)
            return jsonify({'error': f'脚本 {name} 正在运行中 (PID: {old_pid})'}), 400
        except OSError:
            pass
    
    status_data[name] = {'status': 'running', 'pid': None}
    with open(STATUS_FILE, 'w') as f:
        json.dump(status_data, f)
    
    try:
        proc = subprocess.Popen(
            ['python3', path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        pid = proc.pid
        with open(STATUS_FILE, 'r') as f:
            status_data = json.load(f)
        status_data[name]['pid'] = pid
        with open(STATUS_FILE, 'w') as f:
            json.dump(status_data, f)
        
        def bg_monitor():
            try:
                stdout, stderr = proc.communicate(timeout=300)
                output = stdout + stderr
                if len(output) > 500 * 1024:
                    output = output[:500 * 1024] + "\n... (输出已截断)"
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                output = stdout + stderr
                returncode = -1
            except Exception as e:
                output = f"脚本执行异常: {e}"
                returncode = -2
            finally:
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
                gc.collect()
            
            with open(STATUS_FILE, 'r') as f:
                status_data = json.load(f)
            status_data[name]['status'] = 'success' if returncode == 0 else 'failed'
            status_data[name]['pid'] = None
            status_data[name]['last_output'] = output[:10000]
            with open(STATUS_FILE, 'w') as f:
                json.dump(status_data, f)
            
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            history.setdefault(name, []).append({
                'time': datetime.now().isoformat(),
                'status': 'success' if returncode == 0 else 'failed',
                'output': output[:500]
            })
            if len(history[name]) > 50:
                history[name] = history[name][-50:]
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f)
        
        threading.Thread(target=bg_monitor, daemon=True).start()
        return jsonify({'message': f'✅ {name} 已启动 (PID: {pid})'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== 停止脚本（强效清理） ==========
@app.route('/api/stop/<name>', methods=['POST'])
def stop_script(name):
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    entry = status_data.get(name)
    if not entry:
        return jsonify({'error': '脚本不存在'}), 404
    pid = entry.get('pid')
    killed = False
    if pid:
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
            killed = True
        except OSError:
            pass
    entry['status'] = 'stopped' if killed else 'idle'
    entry['pid'] = None
    entry['last_output'] = f'已手动停止{" (PID: "+str(pid)+")" if pid else ""}'
    with open(STATUS_FILE, 'w') as f:
        json.dump(status_data, f)
    with open(HISTORY_FILE, 'r') as f:
        history = json.load(f)
    history.setdefault(name, []).append({
        'time': datetime.now().isoformat(),
        'status': 'stopped' if killed else 'reset',
        'output': f'手动停止{" (PID: "+str(pid)+")" if pid else ""}'
    })
    if len(history[name]) > 50:
        history[name] = history[name][-50:]
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)
    if killed:
        return jsonify({'message': f'✅ {name} 已停止 (PID: {pid})'})
    else:
        return jsonify({'message': f'ℹ️ {name} 状态已重置 (进程不存在或已结束)'})

# ========== 日志 ==========
@app.route('/api/log/<name>')
def get_log(name):
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    s = status_data.get(name, {})
    return jsonify({
        'status': s.get('status', 'idle'),
        'output': s.get('last_output', '暂无输出')
    })

# ========== 新建脚本 ==========
@app.route('/api/new', methods=['POST'])
def new_script():
    data = request.json
    name = data.get('name', '').strip()
    content = data.get('content', '')
    if not name:
        return jsonify({'error': '文件名不能为空'}), 400
    if not name.endswith('.py'):
        name += '.py'
    if '/' in name or '\\' in name:
        return jsonify({'error': '文件名不合法'}), 400
    path = os.path.join(SCRIPTS_DIR, name)
    if os.path.exists(path):
        return jsonify({'error': f'文件 {name} 已存在'}), 400
    with open(path, 'w') as f:
        f.write(content)
    return jsonify({'message': f'✅ 脚本 {name} 创建成功'})

# ========== 获取脚本内容 ==========
@app.route('/api/get/<name>')
def get_script(name):
    if '/' in name or '\\' in name:
        return jsonify({'error': '文件名不合法'}), 400
    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.exists(path):
        return jsonify({'error': '脚本不存在'}), 404
    with open(path, 'r') as f:
        content = f.read()
    return jsonify({'name': name, 'content': content})

# ========== 编辑脚本 ==========
@app.route('/api/edit/<name>', methods=['POST'])
def edit_script(name):
    if '/' in name or '\\' in name:
        return jsonify({'error': '文件名不合法'}), 400
    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.exists(path):
        return jsonify({'error': '脚本不存在'}), 404
    content = request.json.get('content', '')
    with open(path, 'w') as f:
        f.write(content)
    return jsonify({'message': f'✅ {name} 保存成功'})

# ========== 删除脚本 ==========
@app.route('/api/delete/<name>', methods=['POST'])
def delete_script(name):
    if '/' in name or '\\' in name:
        return jsonify({'error': '文件名不合法'}), 400
    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.exists(path):
        return jsonify({'error': '脚本不存在'}), 404
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    pid = status_data.get(name, {}).get('pid')
    if pid:
        try:
            os.kill(pid, signal.SIGKILL)
        except:
            pass
    os.remove(path)
    status_data.pop(name, None)
    with open(STATUS_FILE, 'w') as f:
        json.dump(status_data, f)
    return jsonify({'message': f'✅ {name} 已删除'})

# ========== 上传脚本 ==========
@app.route('/api/upload', methods=['POST'])
def upload_script():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    if not file.filename.endswith('.py'):
        return jsonify({'error': '只允许上传 .py 文件'}), 400
    if '/' in file.filename or '\\' in file.filename:
        return jsonify({'error': '文件名不合法'}), 400
    path = os.path.join(SCRIPTS_DIR, file.filename)
    if os.path.exists(path):
        return jsonify({'error': f'文件 {file.filename} 已存在'}), 400
    file.save(path)
    return jsonify({'message': f'✅ {file.filename} 上传成功'})

# ========== GitHub 同步（已移除自动保存功能） ==========
@app.route('/api/sync_github', methods=['POST'])
def sync_github():
    data = request.json or {}
    tongbukuang_new = data.get('tongbukuang', '').strip()
    if not tongbukuang_new:
        return jsonify({'error': '请输入仓库地址'}), 400
    parsed = parse_github_url(tongbukuang_new)
    if not parsed:
        return jsonify({'error': '无法解析仓库地址'}), 400
    username = parsed['username']
    repo = parsed['repo']
    branch = parsed.get('branch', 'main')
    token = parsed.get('token', '')
    api_url = f"https://api.github.com/repos/{username}/{repo}/contents?ref={branch}"
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    try:
        import requests as reqs
        response = reqs.get(api_url, headers=headers, timeout=30)
        if response.status_code != 200:
            return jsonify({'error': f'API请求失败: {response.status_code}'}), 500
        files = response.json()
        py_files = [f for f in files if f.get('name', '').endswith('.py') and f.get('type') == 'file']
        if not py_files:
            return jsonify({'message': '⚠️ 未找到 .py 文件'})
        downloaded = []
        for file_info in py_files:
            file_name = file_info['name']
            download_url = file_info['download_url']
            if not download_url:
                continue
            try:
                file_resp = reqs.get(download_url, headers=headers, timeout=30)
                if file_resp.status_code == 200:
                    target_path = os.path.join(SCRIPTS_DIR, file_name)
                    with open(target_path, 'w', encoding='utf-8') as f:
                        f.write(file_resp.text)
                    downloaded.append(file_name)
            except Exception as e:
                print(f"下载 {file_name} 出错: {e}")
        if downloaded:
            # 不再自动保存 tongbukuang，也不重启面板
            return jsonify({'message': f'✅ 同步成功，共 {len(downloaded)} 个脚本'})
        else:
            return jsonify({'message': '⚠️ 未成功下载任何文件'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== 手动垃圾回收 ==========
@app.route('/api/gc', methods=['POST'])
def force_gc():
    gc.collect()
    return jsonify({'message': '✅ 垃圾回收已执行'})

# ==================== HTML 模板（备注改为边框样式） ====================
HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐍 脚本面板</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;padding:16px}
.container{max-width:1200px;margin:0 auto}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px 24px;border-radius:12px;margin-bottom:20px}
.header h1{font-size:22px}.header .sub{opacity:.8;font-size:13px;margin-top:4px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.stat-card{background:#fff;padding:12px 20px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.06);flex:1;min-width:80px}
.stat-card .num{font-size:24px;font-weight:700;color:#333}
.stat-card .label{font-size:12px;color:#999}
.actions-bar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.actions-bar button{padding:8px 18px;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:500}
.btn-new{background:#667eea;color:#fff}.btn-new:hover{background:#5a6fd6}
.btn-upload{background:#4caf50;color:#fff}.btn-upload:hover{background:#43a047}
.btn-sync{background:#ff6b6b;color:#fff}.btn-sync:hover{background:#e55a5a}
.btn-gc{background:#607d8b;color:#fff}.btn-gc:hover{background:#455a64}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 1px 4px rgba(0,0,0,.06);border-left:4px solid #ddd}
.card.idle{border-left-color:#90a4ae}
.card.running{border-left-color:#ff9800;animation:pulse 1.2s infinite}
.card.success{border-left-color:#4caf50}
.card.failed{border-left-color:#f44336}
.card.timeout{border-left-color:#ff5722}
.card.error{border-left-color:#9c27b0}
.card.stopped{border-left-color:#78909c}
@keyframes pulse{0%,100%{border-left-color:#ff9800}50%{border-left-color:#ffcc80}}
.card .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px}
.card .name{font-weight:600;font-size:15px;word-break:break-all}
/* --- 备注行样式（边框，无背景色） --- */
.remark-line {
    font-size: 16px;
    font-weight: normal;
    color: #333;
    border: 1px solid #d0d0d0;
    border-radius: 20px;
    padding: 2px 16px;
    display: inline-block;
    margin: 4px 0 2px 0;
    background: #fafafa;
}
.badge{font-size:11px;padding:2px 12px;border-radius:20px;font-weight:500;flex-shrink:0;margin-left:10px}
.badge.idle{background:#eceff1;color:#546e7a}
.badge.running{background:#fff3e0;color:#e65100}
.badge.success{background:#e8f5e9;color:#1b5e20}
.badge.failed{background:#fce4ec;color:#b71c1c}
.badge.timeout{background:#fbe9e7;color:#bf360c}
.badge.error{background:#f3e5f5;color:#4a148c}
.badge.stopped{background:#eceff1;color:#455a64}
.card .info{margin-top:10px;font-size:13px;color:#666;line-height:1.6}
.card .info .lbl{color:#999}
.card .actions{margin-top:12px;display:flex;gap:6px;flex-wrap:wrap}
.card .actions button{padding:5px 14px;border:none;border-radius:6px;font-size:13px;cursor:pointer;font-weight:500}
.btn-run{background:#667eea;color:#fff}
.btn-run:hover{background:#5a6fd6}
.btn-run:disabled{opacity:.5;cursor:not-allowed}
.btn-stop{background:#f44336;color:#fff}
.btn-stop:hover{background:#d32f2f}
.btn-edit{background:#ff9800;color:#fff}
.btn-edit:hover{background:#f57c00}
.btn-del{background:#f44336;color:#fff}
.btn-del:hover{background:#d32f2f}
.btn-log{background:#eceff1;color:#333}
.btn-log:hover{background:#d5d9de}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;justify-content:center;align-items:center}
.modal.active{display:flex}
.modal-box{background:#fff;border-radius:14px;padding:24px;max-width:720px;width:94%;max-height:85vh;overflow-y:auto}
.modal-box h2{font-size:17px;margin-bottom:4px}
.modal-box .meta{font-size:13px;color:#888;margin-bottom:12px}
.modal-box pre{background:#1e1e1e;color:#d4d4d4;padding:14px;border-radius:8px;font-size:12px;line-height:1.5;max-height:400px;overflow:auto;white-space:pre-wrap;word-break:break-all}
.close{float:right;font-size:24px;cursor:pointer;color:#888}
.close:hover{color:#333}
.empty{padding:60px 20px;text-align:center;color:#999}
.refresh-btn{background:#fff;border:1px solid #ddd;padding:6px 16px;border-radius:8px;cursor:pointer;font-size:13px}
.refresh-btn:hover{background:#f5f5f5}
input, textarea{width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin:6px 0;font-size:14px;font-family:inherit}
textarea{min-height:180px;font-family:monospace;resize:vertical}
.modal-box .form-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.modal-box .form-actions button{padding:6px 20px;border:none;border-radius:6px;cursor:pointer;font-weight:500}
.btn-primary{background:#667eea;color:#fff}
.btn-primary:hover{background:#5a6fd6}
.btn-secondary{background:#eceff1;color:#333}
.btn-secondary:hover{background:#d5d9de}
.sync-input-group{display:flex;flex-direction:column;gap:4px;margin:8px 0}
.sync-input-group label{font-weight:500;font-size:14px;color:#555}
.sync-input-group input{width:100%;padding:8px 12px;border:1px solid #ddd;border-radius:6px;font-size:14px;font-family:monospace}
.sync-input-group .hint{font-size:12px;color:#999;margin-top:2px}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🐍 脚本面板</h1>
<div class="sub">📁 /root/scripts &nbsp;|&nbsp; ⏱ 自动刷新 10s</div>
</div>
<div class="stats" id="stats">
<div class="stat-card"><div class="num" id="total">0</div><div class="label">📄 总数</div></div>
<div class="stat-card"><div class="num" id="running">0</div><div class="label">🔄 运行中</div></div>
<div class="stat-card"><div class="num" id="success">0</div><div class="label">✅ 成功</div></div>
<div class="stat-card"><div class="num" id="failed">0</div><div class="label">❌ 失败</div></div>
<div class="stat-card" style="flex:0"><button class="refresh-btn" onclick="load()">🔄 刷新</button></div>
</div>
<div class="actions-bar">
<button class="btn-new" onclick="showNewModal()">➕ 新建</button>
<button class="btn-upload" onclick="document.getElementById('fileInput').click()">📤 上传</button>
<button class="btn-sync" onclick="showSyncModal()">📥 同步</button>
<button class="btn-gc" onclick="forceGC()">🧹 GC</button>
<input type="file" id="fileInput" accept=".py" style="display:none" onchange="uploadFile(this)">
</div>
<div class="grid" id="grid"></div>
</div>

<!-- 新建脚本弹窗 -->
<div class="modal" id="newModal"><div class="modal-box">
<span class="close" onclick="closeNew()">&times;</span>
<h2>📝 新建脚本</h2>
<div style="margin:12px 0"><label>文件名（.py）</label><input type="text" id="newName" placeholder="例如: monitor.py"></div>
<div><label>代码内容</label><textarea id="newContent" placeholder="# 在此编写 Python 代码"></textarea></div>
<div class="form-actions"><button class="btn-primary" onclick="createScript()">💾 保存</button><button class="btn-secondary" onclick="closeNew()">取消</button></div>
</div></div>

<!-- 编辑脚本弹窗 -->
<div class="modal" id="editModal"><div class="modal-box">
<span class="close" onclick="closeEdit()">&times;</span>
<h2>✏️ 编辑脚本</h2>
<div style="margin:12px 0"><label id="editFileName">文件名</label><textarea id="editContent"></textarea></div>
<div class="form-actions"><button class="btn-primary" onclick="saveEdit()">💾 保存</button><button class="btn-secondary" onclick="closeEdit()">取消</button></div>
</div></div>

<!-- 同步脚本弹窗 -->
<div class="modal" id="syncModal"><div class="modal-box">
<span class="close" onclick="closeSync()">&times;</span>
<h2>📥 从 GitHub 同步脚本</h2>
<div class="sync-input-group">
<label>仓库地址（含 Token）</label>
<input type="text" id="syncTongbukuang" placeholder="https://token@github.com/用户名/仓库名">
<div class="hint">💡 格式：https://{token}@github.com/{用户名}/{仓库名} 或直接输入仓库地址</div>
</div>
<div class="form-actions"><button class="btn-primary" onclick="doSync()">📥 开始同步</button><button class="btn-secondary" onclick="closeSync()">取消</button></div>
</div></div>

<!-- 日志弹窗 -->
<div class="modal" id="modal"><div class="modal-box"><span class="close" onclick="closeModal()">&times;</span><h2 id="mTitle">日志</h2><div class="meta" id="mMeta"></div><pre id="mContent">暂无</pre></div></div>

<script>
function st(s){const map={idle:'待执行',running:'运行中',success:'成功',failed:'失败',timeout:'超时',error:'错误',stopped:'已停止'};return map[s]||s}
function badge(s){return`<span class="badge ${s}">${st(s)}</span>`}
function load(){fetch('/api/scripts').then(r=>r.json()).then(data=>{
const g=document.getElementById('grid')
if(!data||!data.length){g.innerHTML='<div class="empty">📂 暂无脚本<br><small>点击 "新建"、"上传" 或 "同步" 添加脚本</small></div>';updateStats(0,0,0,0);return}
let rn=0,su=0,fa=0
g.innerHTML=data.map(s=>{const st=s.status||'idle';if(st==='running')rn++;if(st==='success')su++;if(['failed','timeout','error'].includes(st))fa++
return`<div class="card ${st}">
<div class="top">
<span class="name">${s.name}</span>
${badge(st)}
</div>
${s.remark ? `<div class="remark-line">${s.remark}</div>` : ''}
<div class="info">
<span class="lbl">📏</span> ${(s.size/1024).toFixed(1)}KB &nbsp; <span class="lbl">🕐</span> ${s.mtime}<br>
<span class="lbl">⏱</span> ${s.last_run||'从未运行'} &nbsp; <span class="lbl">📋</span> ${s.history_count||0}次
</div>
<div class="actions">
<button class="btn-run" onclick="run('${s.name}')" ${st==='running'?'disabled':''}>▶ 运行</button>
${st==='running' ? `<button class="btn-stop" onclick="stop('${s.name}')">⏹ 停止</button>` : ''}
<button class="btn-edit" onclick="showEdit('${s.name}')">✏️ 编辑</button>
<button class="btn-del" onclick="del('${s.name}')">🗑 删除</button>
<button class="btn-log" onclick="log('${s.name}')">📄 日志</button>
</div>
</div>`
}).join('')
updateStats(data.length,rn,su,fa)
})}
function updateStats(total,rn,su,fa){document.getElementById('total').textContent=total;document.getElementById('running').textContent=rn;document.getElementById('success').textContent=su;document.getElementById('failed').textContent=fa}
function run(n){if(!confirm(`确定执行 "${n}" ?`))return;fetch(`/api/run/${encodeURIComponent(n)}`,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message||d.error);load()})}
function stop(n){if(!confirm(`确定停止 "${n}" 吗？`))return;fetch(`/api/stop/${encodeURIComponent(n)}`,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message||d.error);load()})}
function log(n){fetch(`/api/log/${encodeURIComponent(n)}`).then(r=>r.json()).then(d=>{document.getElementById('mTitle').textContent='📄 '+n;document.getElementById('mMeta').textContent='状态: '+st(d.status);document.getElementById('mContent').textContent=d.output||'暂无输出';document.getElementById('modal').classList.add('active')})}
function closeModal(){document.getElementById('modal').classList.remove('active')}
document.getElementById('modal').addEventListener('click',function(e){if(e.target===this)closeModal()})

function showNewModal(){document.getElementById('newModal').classList.add('active')}
function closeNew(){document.getElementById('newModal').classList.remove('active')}
function createScript(){
const name=document.getElementById('newName').value.trim()
const content=document.getElementById('newContent').value
if(!name){alert('请输入文件名');return}
if(!content){alert('代码内容不能为空');return}
fetch('/api/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,content})})
.then(r=>r.json()).then(d=>{alert(d.message||d.error);if(d.message){closeNew();document.getElementById('newName').value='';document.getElementById('newContent').value='';load()}})
}

let editingName=''
function showEdit(name){
editingName=name
document.getElementById('editFileName').textContent='📄 '+name
fetch(`/api/get/${encodeURIComponent(name)}`).then(r=>r.json()).then(d=>{
if(d.error){alert(d.error);return}
document.getElementById('editContent').value=d.content||''
document.getElementById('editModal').classList.add('active')
}).catch(err=>alert('获取脚本失败: '+err.message))
}
function closeEdit(){document.getElementById('editModal').classList.remove('active');editingName=''}
function saveEdit(){
const content=document.getElementById('editContent').value
if(!content){alert('内容不能为空');return}
fetch(`/api/edit/${encodeURIComponent(editingName)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})})
.then(r=>r.json()).then(d=>{alert(d.message||d.error);if(d.message){closeEdit();load()}})
}

function del(name){if(!confirm(`确定删除 "${name}" 吗？`))return;fetch(`/api/delete/${encodeURIComponent(name)}`,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message||d.error);load()})}

function uploadFile(input){
if(!input.files.length)return
const file=input.files[0]
const formData=new FormData()
formData.append('file',file)
fetch('/api/upload',{method:'POST',body:formData})
.then(r=>r.json()).then(d=>{alert(d.message||d.error);if(d.message)load()})
input.value=''
}

function showSyncModal(){
document.getElementById('syncModal').classList.add('active')
fetch('/api/sync_config').then(r=>r.json()).then(data=>{
document.getElementById('syncTongbukuang').value=data.tongbukuang||''
})
}
function closeSync(){document.getElementById('syncModal').classList.remove('active')}
function doSync(){
const val=document.getElementById('syncTongbukuang').value.trim()
if(!val){alert('请输入仓库地址');return}
if(!confirm(`将从以下地址同步脚本:\\n${val}\\n确定吗？`))return
fetch('/api/sync_github',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tongbukuang:val})})
.then(r=>r.json()).then(d=>{
alert(d.message||d.error)
if(d.message){
closeSync()
load()
if(d.restart){
setTimeout(function(){window.location.reload()}, 2000)
}
}
})
}

function forceGC(){
if(!confirm('执行垃圾回收，可能会短暂卡顿，确定吗？'))return
fetch('/api/gc',{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message);load()})
}

load();setInterval(load,10000)
</script>
</body>
</html>
'''

if __name__ == '__main__':
    init_files()
    print("🔍 检测端口 5000...")
    kill_process_on_port(5000)
    print("🚀 面板启动在 http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
