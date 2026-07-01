#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📈 面板核心（轻量化，附属功能独立脚本，弹窗动态加载）"
"""
================================================================
⚠️ 面板核心原则：轻量化是绝对核心 请勿删除或违反以下规则
================================================================

【硬件环境】
  路由可用内存仅≈30M，精简python3，峰值内存控制最小化

【核心原则】
  1. 面板本身只保留：脚本列表展示 + 运行/停止 + 内存/缓存显示
  2. 所有附属功能（新建/编辑/删除/上传/日志/同步/定时/清理运存/清理缓存/清理脚本）
     必须通过「独立脚本」实现，点击时临时启动，执行完毕立即释放内存
  3. 严禁将任何附属功能的代码合并到主面板 app.py 中
  4. 主面板 app.py 只负责：路由 + 调用独立脚本 + 显示结果
  5. 所有独立脚本放在 /root/scripts/tools/ 目录下

【弹窗动态加载规则】（重要！新增功能请遵守）
  1. 所有弹窗的 HTML 代码必须放在 /root/scripts/static/modal_content.html 中
  2. 主面板 app.py 中不包含任何弹窗的 HTML 代码（只有按钮和空容器）
  3. 点击按钮时通过 fetch('/static/modal_content.html') 动态加载弹窗
  4. 加载后只显示当前需要的弹窗，其他隐藏（display:none）
  5. 关闭弹窗时彻底移除 DOM（container.innerHTML = ''），释放内存
  6. 严禁在主面板中直接写弹窗 HTML，必须动态加载

【修改代码时请注意】
  ❌ 不要将 tools/ 下的独立脚本代码合并到 app.py
  ❌ 不要在主面板中新增常驻内存的业务逻辑
  ❌ 不要在主面板中直接写弹窗 HTML
  ✅ 新增功能请以独立脚本方式实现，通过 /api/run_tool 调用
  ✅ 新增弹窗请在 modal_content.html 中添加，通过动态加载方式使用
  ✅ 保持面板常驻内存 ≤ 10MB

【面板常驻内存包含】
  - Flask 框架
  - 脚本列表展示
  - 运行/停止功能
  - 内存/缓存显示
  - 工具调用接口 (/api/run_tool)
  - 动态加载弹窗的容器（空容器，不包含 HTML）

【面板常驻内存不包含】
  - 任何弹窗 HTML（动态加载，用完释放）
  - 任何独立脚本（点击时启动，用完释放）
  - 任何编辑/删除/上传/日志/同步/定时/清理等功能的业务代码

【已有功能清单及实现方式】
  ┌─────────────┬──────────────────┬─────────────────────────────┐
  │ 功能        │ 实现方式         │ 代码位置                    │
  ├─────────────┼──────────────────┼─────────────────────────────┤
  │ 脚本列表    │ 面板常驻         │ app.py                      │
  │ 运行/停止   │ 面板常驻         │ app.py                      │
  │ 内存/缓存   │ 面板常驻         │ app.py                      │
  │ 新建脚本    │ 独立脚本+动态弹窗 │ tools/new_script.py         │
  │ 编辑脚本    │ 独立脚本+动态弹窗 │ tools/edit_script.py        │
  │ 删除脚本    │ 独立脚本+动态弹窗 │ tools/delete_script.py      │
  │ 上传脚本    │ 独立脚本+动态弹窗 │ tools/upload_script.py      │
  │ 查看日志    │ 独立脚本+动态弹窗 │ tools/view_log.py           │
  │ 同步GitHub  │ 独立脚本+动态弹窗 │ tools/sync_github.py        │
  │ 定时任务    │ 独立脚本+动态弹窗 │ tools/cron_manager.py       │
  │ 清理运存    │ 独立脚本         │ tools/kill_top_process.py   │
  │ 清理缓存    │ 独立脚本         │ tools/clean_apk_cache.py    │
  │ 清理脚本(GC)│ 独立脚本         │ tools/gc_force.py           │
  └─────────────┴──────────────────┴─────────────────────────────┘

【动态加载弹窗流程】
  1. 用户点击按钮（如「同步」）
  2. loadModal('syncModal') 被调用
  3. fetch('/static/modal_content.html') 加载所有弹窗 HTML
  4. 只显示 id="syncModal" 的弹窗，其他隐藏
  5. 用户操作完成后关闭弹窗
  6. container.innerHTML = '' 彻底移除 DOM，释放内存

【新增功能请遵循】
  1. 如需弹窗 → 在 modal_content.html 中添加
  2. 如需后端逻辑 → 在 tools/ 下新建独立脚本
  3. 如需调用 → 通过 /api/run_tool 接口
  4. 不要在主面板中添加任何常驻业务代码
  5. 弹窗必须动态加载，不能写死在主面板中

================================================================
"""



import os, sys, json, subprocess, threading, signal, gc
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

SCRIPTS_DIR = "/root/scripts"
TOOLS_DIR = "/root/scripts/tools"
STATUS_FILE = "/tmp/script_status.json"

def init_files():
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs(TOOLS_DIR, exist_ok=True)
    os.makedirs("/root/scripts/static", exist_ok=True)
    if not os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'w') as f:
            json.dump({}, f)

def extract_beizhu(fp):
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                if line.strip().startswith('beizhu ='):
                    v = line.split('=', 1)[1].strip()
                    if v.startswith('"') and v.endswith('"'): return v[1:-1]
                    if v.startswith("'") and v.endswith("'"): return v[1:-1]
                    return v
    except:
        pass
    return None

def get_meminfo():
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            if ':' in line:
                k, v = line.split(':', 1)
                mem[k] = int(v.strip().split()[0])
        total = mem.get('MemTotal', 0)
        avail = mem.get('MemAvailable', mem.get('MemFree', 0))
        used = total - avail if total > avail else 0
        return {'total_kb': total, 'used_kb': used, 'available_kb': avail,
                'percent': round((used / total * 100) if total > 0 else 0, 1)}
    except:
        return {'total_kb': 0, 'used_kb': 0, 'available_kb': 0, 'percent': 0}

def get_apk_cache_size():
    cache_dir = "/var/cache/apk/"
    if not os.path.exists(cache_dir):
        return 0
    total = 0
    try:
        for root, _, files in os.walk(cache_dir):
            for f in files:
                p = os.path.join(root, f)
                if os.path.exists(p):
                    total += os.path.getsize(p)
    except:
        pass
    return round(total / (1024*1024), 2)

def get_scripts():
    scripts = []
    if not os.path.exists(SCRIPTS_DIR):
        return scripts
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    for fn in sorted(os.listdir(SCRIPTS_DIR)):
        full_path = os.path.join(SCRIPTS_DIR, fn)
        if fn.endswith('.py') and os.path.isfile(full_path):
            st = os.stat(full_path)
            s = status_data.get(fn, {'status': 'idle', 'pid': None})
            scripts.append({
                'name': fn,
                'size': st.st_size,
                'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'status': s.get('status', 'idle'),
                'pid': s.get('pid'),
                'remark': extract_beizhu(full_path) or ''
            })
    return scripts

def kill_process_on_port(port=5000):
    try:
        for cmd in [f"netstat -tulpn 2>/dev/null | grep ':{port} ' | awk '{{print $7}}' | cut -d'/' -f1",
                    f"lsof -t -i:{port} 2>/dev/null"]:
            pids = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip().split()
            if pids:
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except:
                        pass
                return True
    except:
        pass
    return True

def get_router_ip():
    try:
        ip = subprocess.run(["uci", "get", "network.lan.ipaddr"], capture_output=True, text=True, timeout=2).stdout.strip()
        if ip and '/' in ip:
            ip = ip.split('/')[0]
        return ip or "192.168.1.1"
    except:
        return "192.168.1.1"

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/scripts')
def api_scripts():
    return jsonify(get_scripts())

@app.route('/api/meminfo')
def api_meminfo():
    return jsonify(get_meminfo())

@app.route('/api/apk_cache_size')
def api_apk_cache_size():
    return jsonify({'size_mb': get_apk_cache_size()})

@app.route('/api/router_ip')
def api_router_ip():
    return jsonify({'ip': get_router_ip()})

# ========== 运行脚本 ==========
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
        proc = subprocess.Popen(['python3', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
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
                    output = output[:500 * 1024] + "\n... (截断)"
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                output = stdout + stderr
                returncode = -1
            except Exception as e:
                output = f"异常: {e}"
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

        threading.Thread(target=bg_monitor, daemon=True).start()
        return jsonify({'message': f'✅ {name} 已启动 (PID: {pid})'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== 停止脚本（面板常驻，只负责调用独立脚本） ==========
@app.route('/api/stop/<name>', methods=['POST'])
def stop_script(name):
    # 调用独立脚本 stop_script.py
    try:
        script_path = os.path.join(TOOLS_DIR, 'stop_script.py')
        if not os.path.exists(script_path):
            return jsonify({'error': 'stop_script.py 不存在'}), 500
        result = subprocess.run(
            ['python3', script_path, '--name', name],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout + result.stderr
        return jsonify({'message': output.strip() or '执行完成'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== 获取脚本内容（编辑用，面板常驻） ==========
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

# ========== 统一工具调用（所有附属功能通过此接口调用独立脚本） ==========
# ⚠️ 重要：禁止在此接口中添加任何业务逻辑！只负责调用独立脚本并返回输出
@app.route('/api/run_tool', methods=['POST'])
def run_tool():
    data = request.json
    script = data.get('script', '')
    args = data.get('args', [])
    if not script:
        return jsonify({'error': '未指定脚本'}), 400
    if not script.endswith('.py') or '/' in script:
        return jsonify({'error': '不安全的脚本名'}), 400

    # 清理运存时，自动传递面板 PID 作为排除项
    if script == 'kill_top_process.py':
        if '--exclude' not in str(args):
            args = ['--exclude', str(os.getpid())] + args

    script_path = os.path.join(TOOLS_DIR, script)
    if not os.path.exists(script_path):
        return jsonify({'error': f'工具脚本 {script} 不存在'}), 404
    try:
        cmd = ['python3', script_path] + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        if not output.strip():
            output = '✅ 执行完成（无输出）'
        return jsonify({'output': output})
    except subprocess.TimeoutExpired:
        return jsonify({'output': '⏱ 执行超时（120秒）'})
    except Exception as e:
        return jsonify({'output': f'❌ 执行失败: {e}'})

@app.route('/api/restart_router', methods=['POST'])
def restart_router():
    try:
        subprocess.Popen(['reboot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'message': '✅ 路由器正在重启...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== HTML 模板 ====================
HTML = r'''
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>🐍 脚本面板</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;padding:16px}
.container{max-width:1200px;margin:0 auto}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px 24px;border-radius:12px;margin-bottom:20px}
.header h1{font-size:22px}.header .sub{opacity:.8;font-size:13px;margin-top:4px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.stat-card{background:#fff;padding:12px 20px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.06);flex:1;min-width:70px}
.stat-card .num{font-size:24px;font-weight:700;color:#333}
.stat-card .label{font-size:12px;color:#999}
.stat-card .mem-bar-wrap{width:100%;height:4px;background:#e0e0e0;border-radius:2px;margin-top:6px;overflow:hidden}
.stat-card .mem-bar{height:100%;border-radius:2px;transition:width 0.3s}
.actions-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;padding:8px 12px;background:#f8f9fa;border-radius:8px}
.actions-bar button{padding:6px 14px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500}
.actions-bar .group-label{font-size:11px;color:#999;font-weight:600;display:flex;align-items:center;margin-right:2px}
.btn-new{background:#667eea;color:#fff}.btn-new:hover{background:#5a6fd6}
.btn-upload{background:#4caf50;color:#fff}.btn-upload:hover{background:#43a047}
.btn-edit{background:#ff9800;color:#fff}.btn-edit:hover{background:#f57c00}
.btn-del{background:#f44336;color:#fff}.btn-del:hover{background:#d32f2f}
.btn-log{background:#00897b;color:#fff}.btn-log:hover{background:#00695c}
.btn-sync{background:#ff6b6b;color:#fff}.btn-sync:hover{background:#e55a5a}
.btn-gc{background:#607d8b;color:#fff}.btn-gc:hover{background:#455a64}
.btn-cron{background:#00838f;color:#fff}.btn-cron:hover{background:#006064}
.btn-kill{background:#7b1fa2;color:#fff}.btn-kill:hover{background:#4a148c}
.btn-cache{background:#00695c;color:#fff}.btn-cache:hover{background:#004d40}
.btn-luci{background:#1565c0;color:#fff}.btn-luci:hover{background:#0d47a1}
.btn-9090{background:#e65100;color:#fff}.btn-9090:hover{background:#bf360c}
.btn-reboot{background:#c62828;color:#fff}.btn-reboot:hover{background:#b71c1c}
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
.remark-line{font-size:16px;font-weight:normal;color:#333;border:1px solid #d0d0d0;border-radius:20px;padding:2px 16px;display:inline-block;margin:4px 0 2px 0;background:#fafafa}
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
.btn-run{background:#667eea;color:#fff}.btn-run:hover{background:#5a6fd6}
.btn-run:disabled{opacity:.5;cursor:not-allowed}
.btn-stop{background:#f44336;color:#fff}.btn-stop:hover{background:#d32f2f}
.empty{padding:60px 20px;text-align:center;color:#999}

/* ====== 刷新按钮新样式 ====== */
.refresh-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
    border: none;
    padding: 8px 20px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    letter-spacing: 0.5px;
}
.refresh-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
    background: linear-gradient(135deg, #5a6fd6 0%, #6a4292 100%);
}
.refresh-btn:active {
    transform: translateY(0px);
    box-shadow: 0 1px 4px rgba(102, 126, 234, 0.2);
}

.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;justify-content:center;align-items:center}
.modal.active{display:flex}
.modal-box{background:#fff;border-radius:14px;padding:24px;max-width:720px;width:94%;max-height:85vh;overflow-y:auto}
.modal-box h2{font-size:17px;margin-bottom:4px}
.modal-box .meta{font-size:13px;color:#888;margin-bottom:12px}
.modal-box pre{background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:6px;font-size:12px;max-height:400px;overflow:auto;white-space:pre-wrap;word-break:break-all}
.close{float:right;font-size:24px;cursor:pointer;color:#888}.close:hover{color:#333}
input,textarea,select{width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin:6px 0;font-size:14px;font-family:inherit}
textarea{min-height:180px;font-family:monospace;resize:vertical}
select{appearance:auto;background:#fff}
.modal-box .form-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.modal-box .form-actions button{padding:6px 20px;border:none;border-radius:6px;cursor:pointer;font-weight:500}
.btn-primary{background:#667eea;color:#fff}.btn-primary:hover{background:#5a6fd6}
.btn-secondary{background:#eceff1;color:#333}.btn-secondary:hover{background:#d5d9de}
.btn-success{background:#4caf50;color:#fff}.btn-success:hover{background:#43a047}
.btn-danger{background:#f44336;color:#fff}.btn-danger:hover{background:#d32f2f}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
</style></head>
<body>
<div class="container">
<div class="header"><h1>🐍 脚本面板</h1><div class="sub">📁 /root/scripts &nbsp;|&nbsp; ⏱ 自动刷新 10s</div></div>
<div class="stats" id="stats">
<div class="stat-card"><div class="num" id="total">0</div><div class="label">📄 总数</div></div>
<div class="stat-card"><div class="num" id="running">0</div><div class="label">🔄 运行中</div></div>
<div class="stat-card"><div class="num" id="success">0</div><div class="label">✅ 成功</div></div>
<div class="stat-card"><div class="num" id="failed">0</div><div class="label">❌ 失败</div></div>
<div class="stat-card" id="memCard"><div class="num" id="memText">-- MB</div><div class="label" id="memLabel">💾 内存使用</div><div class="mem-bar-wrap"><div class="mem-bar" id="memBar" style="width:0%;background:#4caf50"></div></div></div>
<div class="stat-card" id="cacheCard"><div class="num" id="cacheSize">-- MB</div><div class="label">📦 APK缓存</div></div>
<div class="stat-card" style="flex:0"><button class="refresh-btn" id="refreshBtn">↻ 刷新</button></div>
</div>

<!-- 按钮组1: 脚本管理 -->
<div class="actions-bar">
<span class="group-label">📜 脚本</span>
<button class="btn-new" id="btnNew">➕ 新建</button>
<button class="btn-upload" id="btnUpload">📤 上传</button>
<button class="btn-edit" id="btnEdit">✏️ 编辑</button>
<button class="btn-del" id="btnDel">🗑 删除</button>
<button class="btn-log" id="btnLog">📄 日志</button>
<button class="btn-sync" id="btnSync">📥 同步</button>
<button class="btn-gc" id="btnGc">🧹 清理脚本</button>
</div>

<!-- 按钮组2: 路由器工具 -->
<div class="actions-bar">
<span class="group-label">⚙️ 路由</span>
<button class="btn-luci" id="btnLuci">🌐 路由器</button>
<button class="btn-9090" id="btn9090">🔧 后端</button>
<button class="btn-cron" id="btnCron">⏰ 定时</button>
<button class="btn-reboot" id="btnReboot">🔄 重启路由</button>
<button class="btn-kill" id="btnKill">💣 清理运存</button>
<button class="btn-cache" id="btnCache">🧹 清理缓存</button>
</div>

<!-- 弹窗容器 -->
<div id="modalContainer"></div>

<div class="grid" id="grid"></div>
</div>

<!-- 工具执行输出弹窗（常驻） -->
<div class="modal" id="toolModal"><div class="modal-box">
<span class="close" onclick="closeModal('toolModal')">&times;</span>
<h2 id="toolTitle">工具执行</h2>
<pre id="toolOutput" style="background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:6px;font-size:12px;max-height:400px;overflow:auto;white-space:pre-wrap;word-break:break-all">执行中...</pre>
<div class="form-actions"><button class="btn-secondary" onclick="closeModal('toolModal')">关闭</button></div>
</div></div>

<script>
var routerIP = '';
var modalLoaded = false;

function st(s){var map={idle:'待执行',running:'运行中',success:'成功',failed:'失败',timeout:'超时',error:'错误',stopped:'已停止'};return map[s]||s}
function badge(s){return'<span class="badge '+s+'">'+st(s)+'</span>'}
function openModal(id){document.getElementById(id).classList.add('active')}
function closeModal(id){document.getElementById(id).classList.remove('active')}

function fetchRouterIP(){
    fetch('/api/router_ip').then(r=>r.json()).then(d=>{routerIP=d.ip||window.location.hostname||'192.168.1.1'}).catch(()=>{routerIP=window.location.hostname||'192.168.1.1'})
}

function loadMem(){
    fetch('/api/meminfo').then(r=>r.json()).then(d=>{
        var total=d.total_kb||0, used=d.used_kb||0, p=d.percent||0
        document.getElementById('memText').textContent=(used/1024).toFixed(0)+'/'+(total/1024).toFixed(0)+' MB'
        document.getElementById('memLabel').textContent='💾 内存使用 '+p+'%'
        var bar=document.getElementById('memBar')
        bar.style.width=Math.min(p,100)+'%'
        bar.style.background=p>85?'#f44336':p>70?'#ff9800':'#4caf50'
    }).catch(()=>{})
}

function loadApkCache(){
    fetch('/api/apk_cache_size').then(r=>r.json()).then(d=>{document.getElementById('cacheSize').textContent=(d.size_mb||0).toFixed(1)+' MB'}).catch(()=>{document.getElementById('cacheSize').textContent='-- MB'})
}

function loadScripts(){
    fetch('/api/scripts').then(r=>r.json()).then(d=>{
        var g=document.getElementById('grid')
        if(!d||!d.length){g.innerHTML='<div class="empty">📂 暂无脚本</div>';updateStats(0,0,0,0);return}
        var rn=0,su=0,fa=0,html=''
        d.forEach(function(s){
            var st=s.status||'idle'
            if(st==='running')rn++;if(st==='success')su++;if(['failed','timeout','error'].indexOf(st)!==-1)fa++
            var remark=s.remark?'<div class="remark-line">'+s.remark+'</div>':''
            var stopBtn = st==='running'?'<button class="btn-stop" data-name="'+s.name+'" onclick="stopScript(\''+s.name+'\')">⏹ 停止</button>':''
            html+='<div class="card '+st+'"><div class="top"><span class="name">'+s.name+'</span>'+badge(st)+'</div>'+remark+
                '<div class="info"><span class="lbl">📏</span> '+(s.size/1024).toFixed(1)+'KB &nbsp; <span class="lbl">🕐</span> '+s.mtime+'</div>'+
                '<div class="actions"><button class="btn-run" data-name="'+s.name+'" '+(st==='running'?'disabled':'')+'>▶ 运行</button>'+stopBtn+'</div></div>'
        })
        g.innerHTML=html;updateStats(d.length,rn,su,fa);bindCardEvents()
    }).catch(()=>{})
}

function updateStats(t,r,s,f){document.getElementById('total').textContent=t;document.getElementById('running').textContent=r;document.getElementById('success').textContent=s;document.getElementById('failed').textContent=f}
function loadAll(){loadScripts();loadMem();loadApkCache()}

function bindCardEvents(){
    document.querySelectorAll('.btn-run').forEach(function(b){b.onclick=function(){var n=this.dataset.name;if(!confirm('执行 "'+n+'" ?'))return;fetch('/api/run/'+encodeURIComponent(n),{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message||d.error);loadAll()})}})
}

// ========== 停止脚本 ==========
function stopScript(name){
    if(!confirm('停止 "'+name+'" ?'))return
    doRunTool('stop_script.py', ['--name', name], '⏹ 停止脚本')
}

// ========== 通用工具调用 ==========
function doRunTool(script, args, label) {
    var modal=document.getElementById('toolModal')
    document.getElementById('toolTitle').textContent='⏳ '+label+' ...'
    document.getElementById('toolOutput').textContent='执行中...'
    openModal('toolModal')
    fetch('/api/run_tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({script:script, args:args})})
    .then(r=>r.json()).then(d=>{
        document.getElementById('toolTitle').textContent='✅ '+label+' 完成'
        document.getElementById('toolOutput').textContent=d.output||'执行完成'
        loadAll()
        setTimeout(function(){closeModal('toolModal')}, 2000)
    }).catch(e=>{
        document.getElementById('toolTitle').textContent='❌ '+label+' 失败'
        document.getElementById('toolOutput').textContent='执行失败: '+e.message
    })
}

function runSimpleTool(script, label){ doRunTool(script, [], label) }

// ========== 通用弹窗加载器 ==========
function loadModal(name) {
    var container = document.getElementById('modalContainer');
    if (modalLoaded) {
        document.querySelectorAll('#modalContainer .modal').forEach(function(el) {
            el.style.display = 'none';
        });
        var target = document.getElementById(name);
        if (target) {
            target.style.display = 'flex';
            if (name === 'editModal') populateEditSelect();
            if (name === 'delModal') populateDelSelect();
            if (name === 'logModal') populateLogSelect();
            if (name === 'cronModal') { loadScriptsForCron(); cronRefreshList(); }
            if (name === 'syncModal') loadSyncConfig();
        }
        return;
    }
    fetch('/static/modal_content.html')
        .then(r => r.text())
        .then(html => {
            container.innerHTML = html;
            modalLoaded = true;
            document.querySelectorAll('#modalContainer .modal').forEach(function(el) {
                el.style.display = 'none';
            });
            var target = document.getElementById(name);
            if (target) {
                target.style.display = 'flex';
                if (name === 'editModal') populateEditSelect();
                if (name === 'delModal') populateDelSelect();
                if (name === 'logModal') populateLogSelect();
                if (name === 'cronModal') { loadScriptsForCron(); cronRefreshList(); }
                if (name === 'syncModal') loadSyncConfig();
            }
        })
        .catch(e => { alert('加载模块失败: '+e.message); });
}

function closeModalByName(name) {
    var el = document.getElementById(name);
    if (el) {
        el.style.display = 'none';
        var container = document.getElementById('modalContainer');
        container.innerHTML = '';
        modalLoaded = false;
    }
}

// ========== 新建脚本 ==========
document.getElementById('btnNew').onclick = function() { loadModal('newModal'); };

function createScript() {
    var name = document.getElementById('newName').value.trim();
    var content = document.getElementById('newContent').value;
    if (!name) { alert('请输入文件名'); return; }
    if (!content) { alert('代码内容不能为空'); return; }
    doRunTool('new_script.py', ['--name', name, '--content', content], '📝 新建脚本');
    closeModalByName('newModal');
}

// ========== 编辑脚本 ==========
document.getElementById('btnEdit').onclick = function() { loadModal('editModal'); };

function populateEditSelect() {
    fetch('/api/scripts').then(r=>r.json()).then(d=>{
        var sel=document.getElementById('editSelect');
        if (!sel) return;
        sel.innerHTML='<option value="">-- 选择脚本 --</option>';
        if(d) d.forEach(function(s){var opt=document.createElement('option');opt.value=s.name;opt.textContent=s.name;sel.appendChild(opt)});
    }).catch(()=>{});
}
function loadEditContent(){
    var name=document.getElementById('editSelect').value;
    if(!name)return;
    fetch('/api/get/'+encodeURIComponent(name)).then(r=>r.json()).then(d=>{
        if(d.error){alert(d.error);return}
        document.getElementById('editContent').value=d.content||'';
    }).catch(()=>{});
}
function saveEdit(){
    var name=document.getElementById('editSelect').value;
    var content=document.getElementById('editContent').value;
    if(!name){alert('请选择脚本');return}
    if(!content){alert('内容不能为空');return}
    doRunTool('edit_script.py', ['--name', name, '--content', content], '✏️ 编辑脚本');
    closeModalByName('editModal');
}

// ========== 删除脚本 ==========
document.getElementById('btnDel').onclick = function() { loadModal('delModal'); };

function populateDelSelect() {
    fetch('/api/scripts').then(r=>r.json()).then(d=>{
        var sel=document.getElementById('delSelect');
        if (!sel) return;
        sel.innerHTML='<option value="">-- 选择脚本 --</option>';
        if(d) d.forEach(function(s){var opt=document.createElement('option');opt.value=s.name;opt.textContent=s.name;sel.appendChild(opt)});
    }).catch(()=>{});
}
function deleteScript(){
    var name=document.getElementById('delSelect').value;
    if(!name){alert('请选择脚本');return}
    if(!confirm('确定删除 "'+name+'" 吗？'))return;
    doRunTool('delete_script.py', ['--name', name], '🗑 删除脚本');
    closeModalByName('delModal');
}

// ========== 上传脚本（base64编码防止特殊字符问题） ==========
function doUpload() {
    var input = document.getElementById('uploadFileInput');
    if (!input.files || !input.files.length) {
        alert('请选择文件');
        return;
    }
    var file = input.files[0];
    if (!file.name.endsWith('.py')) {
        alert('只支持 .py 文件');
        return;
    }
    var output = document.getElementById('uploadOutput');
    output.style.display = 'block';
    output.textContent = '⏳ 读取文件...';
    var reader = new FileReader();
    reader.onload = function(e) {
        var content = e.target.result;
        // 将内容转为 base64
        var base64 = btoa(content);
        output.textContent = '⏳ 上传中...';
        fetch('/api/run_tool', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                script: 'upload_script.py',
                args: ['--filename', file.name, '--content', base64]
            })
        })
        .then(r => r.json())
        .then(d => {
            output.textContent = d.output || '执行完成';
            if (d.output && d.output.indexOf('✅') !== -1) {
                loadAll();
                input.value = ''; // 清空文件选择
            }
        })
        .catch(e => {
            output.textContent = '❌ 上传失败: ' + e.message;
        });
    };
    reader.onerror = function() {
        output.textContent = '❌ 读取文件失败';
    };
    reader.readAsText(file);
}

// ========== 查看日志（独立脚本 + 动态弹窗） ==========
document.getElementById('btnLog').onclick = function() { loadModal('logModal'); };

function populateLogSelect() {
    fetch('/api/run_tool', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script: 'view_log.py', args: ['--list']})
    })
    .then(r => r.json())
    .then(d => {
        try {
            var list = JSON.parse(d.output);
            var sel = document.getElementById('logSelect');
            if (!sel) return;
            sel.innerHTML = '<option value="">-- 选择脚本 --</option>';
            if (list && list.length) {
                list.forEach(function(name) {
                    var opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = name;
                    sel.appendChild(opt);
                });
            }
        } catch(e) {}
    })
    .catch(() => {});
}

function loadLog() {
    var name = document.getElementById('logSelect').value;
    if (!name) {
        document.getElementById('logContent').textContent = '请选择脚本';
        return;
    }
    document.getElementById('logContent').textContent = '⏳ 加载中...';
    fetch('/api/run_tool', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script: 'view_log.py', args: ['--name', name]})
    })
    .then(r => r.json())
    .then(d => {
        document.getElementById('logContent').textContent = d.output || '暂无输出';
    })
    .catch(e => {
        document.getElementById('logContent').textContent = '❌ 加载失败: ' + e.message;
    });
}

// ========== 同步（独立脚本 + 动态弹窗，支持自动保存配置） ==========
document.getElementById('btnSync').onclick = function() { loadModal('syncModal'); };

function loadSyncConfig() {
    // 通过 run_tool 获取当前保存的配置（0 内存增加）
    fetch('/api/run_tool', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script: 'sync_github.py', args: ['--get-config']})
    })
    .then(r => r.json())
    .then(d => {
        var input = document.getElementById('syncRepoInput');
        if (input) {
            input.value = d.output.trim() || 'https://github.com/evol5201314/exetest';
        }
    })
    .catch(e => {
        var input = document.getElementById('syncRepoInput');
        if (input) {
            input.value = 'https://github.com/evol5201314/exetest';
        }
    });
}

function doSync() {
    var repo = document.getElementById('syncRepoInput').value.trim();
    if (!repo) {
        alert('请输入仓库地址');
        return;
    }
    var output = document.getElementById('syncOutput');
    output.style.display = 'block';
    output.textContent = '⏳ 同步中...';
    fetch('/api/run_tool', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script: 'sync_github.py', args: ['--repo', repo]})
    })
    .then(r => r.json())
    .then(d => {
        output.textContent = d.output || '执行完成';
        if (d.output && d.output.indexOf('✅') !== -1) {
            loadAll();
        }
    })
    .catch(e => {
        output.textContent = '❌ 同步失败: ' + e.message;
    });
}

// ========== 定时任务 ==========
document.getElementById('btnCron').onclick = function() { loadModal('cronModal'); };

function loadScriptsForCron() {
    fetch('/api/scripts').then(r=>r.json()).then(d=>{
        var sel=document.getElementById('cronCommandSelect');
        if (!sel) return;
        sel.innerHTML='<option value="">-- 选择脚本 --</option>';
        if(d) d.forEach(function(s){var opt=document.createElement('option');opt.value='python3 /root/scripts/'+s.name;opt.textContent=s.name;sel.appendChild(opt)});
    }).catch(()=>{});
}

function cronModeChange() {
    var mode = document.getElementById('cronMode').value;
    document.getElementById('cronDaily').style.display = (mode === 'daily') ? 'block' : 'none';
    document.getElementById('cronWeekly').style.display = (mode === 'weekly') ? 'block' : 'none';
    document.getElementById('cronHourly').style.display = (mode === 'hourly') ? 'block' : 'none';
    document.getElementById('cronMinutes').style.display = (mode === 'minutes') ? 'block' : 'none';
    document.getElementById('cronCustom').style.display = (mode === 'custom') ? 'block' : 'none';
    updateCronSchedule();
}

function updateCronSchedule() {
    var mode = document.getElementById('cronMode').value;
    var schedule = '';
    switch(mode) {
        case 'daily':
            var hour = document.getElementById('cronDailyHour').value;
            var minute = document.getElementById('cronDailyMinute').value;
            schedule = minute + ' ' + hour + ' * * *';
            break;
        case 'weekly':
            var hour = document.getElementById('cronWeeklyHour').value;
            var minute = document.getElementById('cronWeeklyMinute').value;
            var day = document.getElementById('cronWeeklyDay').value;
            schedule = minute + ' ' + hour + ' * * ' + day;
            break;
        case 'hourly':
            var minute = document.getElementById('cronHourlyMinute').value;
            schedule = minute + ' * * * *';
            break;
        case 'minutes':
            var interval = document.getElementById('cronMinutesInterval').value;
            schedule = '*/' + interval + ' * * * *';
            break;
        case 'custom':
        default:
            return;
    }
    document.getElementById('cronSchedule').value = schedule;
}

function cronRefreshList() {
    var container=document.getElementById('cronListContainer');
    if (!container) return;
    container.innerHTML='<div style="color:#999;padding:20px;text-align:center;">⏳ 加载中...</div>';
    fetch('/api/run_tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({script:'cron_manager.py', args:['--list-json']})})
    .then(r=>r.json()).then(d=>{
        try{
            var jobs=JSON.parse(d.output);
            if(!jobs||!jobs.length){container.innerHTML='<div style="color:#999;padding:20px;text-align:center;">📭 暂无定时任务</div>';return}
            var html='';
            jobs.forEach(function(job){
                var escaped=job.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                var isScript=job.indexOf('/root/scripts/')!==-1 && job.indexOf('.py')!==-1;
                var label=isScript?'📜':'⚙️';
                var parts=job.split(' ');
                var schedule=parts.slice(0,5).join(' ');
                var cmd=parts.slice(5).join(' ');
                html+='<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid #f0f0f0;">'+
                    '<span style="font-family:monospace;font-size:13px;color:#333;background:#f5f5f5;padding:2px 10px;border-radius:4px;flex-shrink:0;">'+schedule+'</span>'+
                    '<span style="font-size:13px;color:#555;word-break:break-all;flex:1;margin:0 10px;">'+label+' '+cmd+'</span>'+
                    '<button onclick="cronDelete(\''+escaped+'\')" style="background:#f44336;color:#fff;border:none;border-radius:4px;padding:2px 12px;cursor:pointer;font-size:12px;flex-shrink:0;">🗑</button>'+
                    '</div>';
            });
            container.innerHTML=html;
        }catch(e){container.innerHTML='<div style="color:#f44336;padding:20px;text-align:center;">❌ 解析失败</div>';}
    }).catch(e=>{container.innerHTML='<div style="color:#f44336;padding:20px;text-align:center;">❌ 加载失败</div>'});
}

function cronDelete(fullLine){
    if(!confirm('确定删除该定时任务吗？'))return;
    fetch('/api/run_tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({script:'cron_manager.py', args:['--delete', fullLine]})})
    .then(r=>r.json()).then(d=>{alert(d.output||'执行完成');cronRefreshList()})
    .catch(e=>{alert('删除失败: '+e.message)});
}

function cronAdd() {
    var mode = document.getElementById('cronMode').value;
    var schedule = '';
    switch(mode) {
        case 'daily':
            var hour = document.getElementById('cronDailyHour').value;
            var minute = document.getElementById('cronDailyMinute').value;
            schedule = minute + ' ' + hour + ' * * *';
            break;
        case 'weekly':
            var hour = document.getElementById('cronWeeklyHour').value;
            var minute = document.getElementById('cronWeeklyMinute').value;
            var day = document.getElementById('cronWeeklyDay').value;
            schedule = minute + ' ' + hour + ' * * ' + day;
            break;
        case 'hourly':
            var minute = document.getElementById('cronHourlyMinute').value;
            schedule = minute + ' * * * *';
            break;
        case 'minutes':
            var interval = document.getElementById('cronMinutesInterval').value;
            schedule = '*/' + interval + ' * * * *';
            break;
        case 'custom':
        default:
            schedule = document.getElementById('cronSchedule').value.trim();
            break;
    }
    var cmdSelect = document.getElementById('cronCommandSelect').value;
    var customCmd = document.getElementById('cronCustomCmd').value.trim();
    var command = cmdSelect || customCmd;
    if (!schedule) { alert('请输入执行时间'); return; }
    if (!command) { alert('请选择脚本或输入自定义命令'); return; }
    if (schedule.split(/\s+/).length !== 5) {
        alert('Cron 格式错误，应为: 分 时 日 月 周');
        return;
    }
    fetch('/api/run_tool', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script: 'cron_manager.py', args: ['--add', schedule, command]})
    })
    .then(r => r.json())
    .then(d => {
        alert(d.output || '执行完成');
        if (d.output && d.output.indexOf('✅') !== -1) {
            document.getElementById('cronCustomCmd').value = '';
            cronRefreshList();
        }
    })
    .catch(e => { alert('添加失败: ' + e.message); });
}

// ========== 跳转 ==========
function goLuci(){window.open('http://'+(routerIP||'192.168.1.1')+'/cgi-bin/luci','_blank')}
function go9090(){window.open('http://'+(routerIP||'192.168.1.1')+':9090/ui','_blank')}
function rebootRouter(){if(!confirm('重启路由器？'))return;if(!confirm('再次确认？'))return;alert('正在重启...');fetch('/api/restart_router',{method:'POST'})}

// ========== 绑定按钮 ==========
document.getElementById('refreshBtn').onclick=loadAll
document.getElementById('btnLuci').onclick=goLuci
document.getElementById('btn9090').onclick=go9090
document.getElementById('btnReboot').onclick=rebootRouter
document.getElementById('btnGc').onclick=function(){runSimpleTool('gc_force.py','🧹 清理脚本')}
document.getElementById('btnKill').onclick=function(){runSimpleTool('kill_top_process.py','💣 清理运存')}
document.getElementById('btnCache').onclick=function(){runSimpleTool('clean_apk_cache.py','🧹 清理缓存')}

document.getElementById('toolModal').onclick=function(e){if(e.target===this)closeModal('toolModal')}

fetchRouterIP();loadAll();setInterval(loadAll,10000)
</script>
</body></html>
'''

if __name__ == '__main__':
    init_files()
    kill_process_on_port(5000)
    print("🚀 面板启动在 http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
