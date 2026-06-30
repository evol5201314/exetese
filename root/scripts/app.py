#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📈 面板核心版 (所有功能独立为脚本)"

"""
===== 【OpenWrt 低内存专用优化说明】 =====
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
功能：脚本列表展示 + 运行/停止，其他功能通过按钮调用独立脚本（即用即释放）
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
    # 只扫描根目录，不递归 tools/
    for fn in sorted(os.listdir(SCRIPTS_DIR)):
        if fn.endswith('.py') and os.path.isfile(os.path.join(SCRIPTS_DIR, fn)):
            p = os.path.join(SCRIPTS_DIR, fn)
            st = os.stat(p)
            s = status_data.get(fn, {'status': 'idle', 'pid': None})
            scripts.append({
                'name': fn,
                'size': st.st_size,
                'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'status': s.get('status', 'idle'),
                'pid': s.get('pid'),
                'remark': extract_beizhu(p) or ''
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
    if killed:
        return jsonify({'message': f'✅ {name} 已停止 (PID: {pid})'})
    else:
        return jsonify({'message': f'ℹ️ {name} 状态已重置'})

@app.route('/api/run_tool', methods=['POST'])
def run_tool():
    data = request.json
    script = data.get('script', '')
    if not script:
        return jsonify({'error': '未指定脚本'}), 400
    if not script.endswith('.py') or '/' in script:
        return jsonify({'error': '不安全的脚本名'}), 400
    script_path = os.path.join(TOOLS_DIR, script)
    if not os.path.exists(script_path):
        return jsonify({'error': f'工具脚本 {script} 不存在'}), 404
    try:
        result = subprocess.run(['python3', script_path], capture_output=True, text=True, timeout=120)
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
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>🐍 脚本面板 精简版</title>
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
.refresh-btn{background:#fff;border:1px solid #ddd;padding:6px 16px;border-radius:8px;cursor:pointer;font-size:13px}
.refresh-btn:hover{background:#f5f5f5}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;justify-content:center;align-items:center}
.modal.active{display:flex}
.modal-box{background:#fff;border-radius:14px;padding:24px;max-width:720px;width:94%;max-height:85vh;overflow-y:auto}
.modal-box h2{font-size:17px;margin-bottom:4px}
.modal-box .meta{font-size:13px;color:#888;margin-bottom:12px}
.modal-box pre{background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:6px;font-size:12px;max-height:400px;overflow:auto;white-space:pre-wrap;word-break:break-all}
.close{float:right;font-size:24px;cursor:pointer;color:#888}.close:hover{color:#333}
input,textarea{width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin:6px 0;font-size:14px;font-family:inherit}
textarea{min-height:180px;font-family:monospace;resize:vertical}
.modal-box .form-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.modal-box .form-actions button{padding:6px 20px;border:none;border-radius:6px;cursor:pointer;font-weight:500}
.btn-primary{background:#667eea;color:#fff}.btn-primary:hover{background:#5a6fd6}
.btn-secondary{background:#eceff1;color:#333}.btn-secondary:hover{background:#d5d9de}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
</style></head>
<body>
<div class="container">
<div class="header"><h1>🐍 脚本面板 精简版</h1><div class="sub">📁 /root/scripts &nbsp;|&nbsp; ⏱ 自动刷新 10s</div></div>
<div class="stats" id="stats">
<div class="stat-card"><div class="num" id="total">0</div><div class="label">📄 总数</div></div>
<div class="stat-card"><div class="num" id="running">0</div><div class="label">🔄 运行中</div></div>
<div class="stat-card"><div class="num" id="success">0</div><div class="label">✅ 成功</div></div>
<div class="stat-card"><div class="num" id="failed">0</div><div class="label">❌ 失败</div></div>
<div class="stat-card" id="memCard"><div class="num" id="memText">-- MB</div><div class="label" id="memLabel">💾 内存使用</div><div class="mem-bar-wrap"><div class="mem-bar" id="memBar" style="width:0%;background:#4caf50"></div></div></div>
<div class="stat-card" id="cacheCard"><div class="num" id="cacheSize">-- MB</div><div class="label">📦 APK缓存</div></div>
<div class="stat-card" style="flex:0"><button class="refresh-btn" id="refreshBtn">🔄 刷新</button></div>
</div>

<!-- 按钮组1: 脚本管理 + 工具 -->
<div class="actions-bar">
<span class="group-label">📜 脚本</span>
<button class="btn-new" onclick="runTool('new_script.py', '📝 新建脚本')">➕ 新建</button>
<button class="btn-upload" onclick="runTool('upload_script.py', '📤 上传脚本')">📤 上传</button>
<button class="btn-edit" onclick="runTool('edit_script.py', '✏️ 编辑脚本')">✏️ 编辑</button>
<button class="btn-del" onclick="runTool('delete_script.py', '🗑 删除脚本')">🗑 删除</button>
<button class="btn-log" onclick="runTool('view_log.py', '📄 查看日志')">📄 日志</button>
<button class="btn-sync" onclick="runTool('sync_github.py', '📥 同步GitHub')">📥 同步</button>
<button class="btn-gc" onclick="runTool('gc_force.py', '🧹 GC')">🧹 GC</button>
<button class="btn-cron" onclick="runTool('cron_manager.py', '⏰ 定时')">⏰ 定时</button>
<button class="btn-kill" onclick="runTool('kill_top_process.py', '💣 清理')">💣 清理</button>
<button class="btn-cache" onclick="runTool('clean_apk_cache.py', '🧹 缓存')">🧹 缓存</button>
</div>

<!-- 按钮组2: 路由器工具 -->
<div class="actions-bar">
<span class="group-label">⚙️ 路由</span>
<button class="btn-luci" id="btnLuci">🌐 路由器</button>
<button class="btn-9090" id="btn9090">🔧 后端</button>
<button class="btn-reboot" id="btnReboot">🔄 重启路由</button>
</div>

<div class="grid" id="grid"></div>
</div>

<!-- 工具输出弹窗 -->
<div class="modal" id="toolModal"><div class="modal-box"><span class="close" onclick="closeToolModal()">&times;</span><h2 id="toolTitle">工具执行</h2><pre id="toolOutput" style="background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:6px;font-size:12px;max-height:400px;overflow:auto;white-space:pre-wrap;word-break:break-all">执行中...</pre><div class="form-actions"><button class="btn-secondary" onclick="closeToolModal()">关闭</button></div></div></div>

<script>
(function(){
var routerIP='';

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
            var stop=st==='running'?'<button class="btn-stop" data-name="'+s.name+'">⏹ 停止</button>':''
            html+='<div class="card '+st+'"><div class="top"><span class="name">'+s.name+'</span>'+badge(st)+'</div>'+remark+
                '<div class="info"><span class="lbl">📏</span> '+(s.size/1024).toFixed(1)+'KB &nbsp; <span class="lbl">🕐</span> '+s.mtime+'</div>'+
                '<div class="actions"><button class="btn-run" data-name="'+s.name+'" '+(st==='running'?'disabled':'')+'>▶ 运行</button>'+stop+'</div></div>'
        })
        g.innerHTML=html;updateStats(d.length,rn,su,fa);bindCardEvents()
    }).catch(()=>{})
}

function updateStats(t,r,s,f){document.getElementById('total').textContent=t;document.getElementById('running').textContent=r;document.getElementById('success').textContent=s;document.getElementById('failed').textContent=f}
function loadAll(){loadScripts();loadMem();loadApkCache()}

function bindCardEvents(){
    document.querySelectorAll('.btn-run').forEach(function(b){b.onclick=function(){var n=this.dataset.name;if(!confirm('执行 "'+n+'" ?'))return;fetch('/api/run/'+encodeURIComponent(n),{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message||d.error);loadAll()})}})
    document.querySelectorAll('.btn-stop').forEach(function(b){b.onclick=function(){var n=this.dataset.name;if(!confirm('停止 "'+n+'" ?'))return;fetch('/api/stop/'+encodeURIComponent(n),{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message||d.error);loadAll()})}})
}

function runTool(script, label){
    var modal=document.getElementById('toolModal')
    document.getElementById('toolTitle').textContent='⏳ '+label+' ...'
    document.getElementById('toolOutput').textContent='执行中...'
    openModal('toolModal')
    fetch('/api/run_tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({script:script})})
    .then(r=>r.json()).then(d=>{
        document.getElementById('toolTitle').textContent='✅ '+label+' 完成'
        document.getElementById('toolOutput').textContent=d.output||'执行完成'
        loadAll()
    }).catch(e=>{
        document.getElementById('toolTitle').textContent='❌ '+label+' 失败'
        document.getElementById('toolOutput').textContent='执行失败: '+e.message
    })
}
function closeToolModal(){closeModal('toolModal')}

// 跳转
function goLuci(){window.open('http://'+(routerIP||'192.168.1.1')+'/cgi-bin/luci','_blank')}
function go9090(){window.open('http://'+(routerIP||'192.168.1.1')+':9090/ui','_blank')}
function rebootRouter(){if(!confirm('重启路由器？'))return;if(!confirm('再次确认？'))return;alert('正在重启...');fetch('/api/restart_router',{method:'POST'})}

document.getElementById('refreshBtn').onclick=loadAll
document.getElementById('btnLuci').onclick=goLuci
document.getElementById('btn9090').onclick=go9090
document.getElementById('btnReboot').onclick=rebootRouter
document.getElementById('toolModal').onclick=function(e){if(e.target===this)closeToolModal()}

fetchRouterIP();loadAll();setInterval(loadAll,10000)
})();
</script>
</body></html>
'''

if __name__ == '__main__':
    init_files()
    kill_process_on_port(5000)
    print("🚀 面板启动在 http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
