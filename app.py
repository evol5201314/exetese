#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===== 【OpenWrt 低内存专用优化说明 请勿删除以下轻量化逻辑】
硬件环境：路由可用内存仅≈30M，精简python3，峰值内存控制最小化
屏蔽stdout/stderr输出至/dev/null，不读写闪存，无日志文件占用存储空间
保留下方备注方便查看脚本详情
"""
beizhu = "📈 面板程序 (系统工具增强版 + Cron管理 + APK缓存清理)"
"""
============================================================
🐍 脚本面板 - 系统工具增强版
功能：脚本管理、内存显示、Cron定时任务、APK缓存清理、进程清理
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
import glob
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

SCRIPTS_DIR = "/root/scripts"
STATUS_FILE = "/tmp/script_status.json"
HISTORY_FILE = "/tmp/script_history.json"
CRONTAB_FILE = "/etc/crontabs/root"

# ========== 同步框默认内容 ==========
tongbukuang = "https://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/evol5201314/exetest"

def init_files():
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs("/root/dashboard", exist_ok=True)
    for f in [STATUS_FILE, HISTORY_FILE]:
        if not os.path.exists(f):
            with open(f, 'w') as fp:
                json.dump({}, fp)
    if not os.path.exists(CRONTAB_FILE):
        with open(CRONTAB_FILE, 'w') as f:
            f.write("# OpenWrt crontab\n")

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
                except:
                    pass
            return True
    except:
        pass
    return True

# ========== 获取路由器IP（修复：去掉/24后缀） ==========
def get_router_ip():
    try:
        result = subprocess.run(["uci", "get", "network.lan.ipaddr"], capture_output=True, text=True, timeout=2)
        ip = result.stdout.strip()
        if ip:
            if '/' in ip:
                ip = ip.split('/')[0]
            return ip
    except:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if '/' in ip:
            ip = ip.split('/')[0]
        return ip
    except:
        pass
    return "192.168.1.1"

# ========== 获取内存信息 ==========
def get_meminfo():
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        meminfo = {}
        for line in lines:
            if ':' in line:
                key, val = line.split(':', 1)
                val = val.strip().split()[0]
                meminfo[key] = int(val)
        total = meminfo.get('MemTotal', 0)
        available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
        used = total - available if total > available else 0
        return {
            'total_kb': total,
            'used_kb': used,
            'available_kb': available,
            'percent': round((used / total * 100) if total > 0 else 0, 1)
        }
    except:
        return {'total_kb': 0, 'used_kb': 0, 'available_kb': 0, 'percent': 0}

# ========== APK 缓存管理 ==========
def get_apk_cache_size():
    cache_dir = "/var/cache/apk/"
    if not os.path.exists(cache_dir):
        return 0
    total_size = 0
    try:
        for root, dirs, files in os.walk(cache_dir):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
    except:
        pass
    return round(total_size / (1024 * 1024), 2)

# ========== 获取高内存进程（用于清理） ==========
def get_top_memory_processes(exclude_pid=None, limit=10):
    processes = []
    exclude_pid = exclude_pid or os.getpid()
    sys_keywords = ['init', 'procd', 'logd', 'ubusd', 'netd', 'ueventd', 
                    'syslogd', 'klogd', 'watchdog', 'hotplug', 'ntpd',
                    'sshd', 'dropbear', 'kthreadd', 'ksoftirqd', 'kworker',
                    'bdflush', 'kswapd', 'khugepaged', 'kcompactd']
    try:
        for pid_path in glob.glob('/proc/[0-9]*/statm'):
            try:
                pid = int(pid_path.split('/')[2])
                if pid == exclude_pid or pid <= 10:
                    continue
                try:
                    with open(f'/proc/{pid}/status', 'r') as f:
                        status_lines = f.readlines()
                    name = ''
                    for line in status_lines:
                        if line.startswith('Name:'):
                            name = line.split(':', 1)[1].strip()
                            break
                except:
                    continue
                if name.startswith('[') and name.endswith(']'):
                    continue
                skip = False
                for kw in sys_keywords:
                    if kw in name.lower():
                        skip = True
                        break
                if skip:
                    continue
                try:
                    with open(f'/proc/{pid}/cmdline', 'rb') as f:
                        cmdline_bytes = f.read()
                    cmdline = cmdline_bytes.replace(b'\x00', b' ').decode('utf-8', errors='ignore').strip()
                    if not cmdline:
                        cmdline = name
                except:
                    cmdline = name
                if cmdline in ['sh', 'bash', 'ps', 'grep', 'awk', 'sed', 'cut', 'top', 'netstat', 'lsof']:
                    continue
                rss_kb = 0
                try:
                    with open(f'/proc/{pid}/statm', 'r') as f:
                        statm = f.read().split()
                        if len(statm) >= 2:
                            rss_kb = int(statm[1]) * 4
                except:
                    pass
                if rss_kb < 1024:
                    continue
                is_script = '/root/scripts/' in cmdline
                processes.append({
                    'pid': pid,
                    'name': name,
                    'cmdline': cmdline[:200],
                    'rss_kb': rss_kb,
                    'is_script': is_script
                })
            except:
                continue
        processes.sort(key=lambda x: x['rss_kb'], reverse=True)
        return processes[:limit]
    except Exception as e:
        return []

def kill_process(pid):
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except:
        return False

# ========== Cron 操作 ==========
def get_cron_jobs():
    jobs = []
    try:
        if not os.path.exists(CRONTAB_FILE):
            return jobs
        with open(CRONTAB_FILE, 'r') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 6:
                schedule = ' '.join(parts[:5])
                command = ' '.join(parts[5:])
                is_script = '/root/scripts/' in command and '.py' in command
                script_name = None
                if is_script:
                    for part in command.split():
                        if '/root/scripts/' in part and part.endswith('.py'):
                            script_name = os.path.basename(part)
                            break
                jobs.append({
                    'schedule': schedule,
                    'command': command,
                    'is_script': is_script,
                    'script_name': script_name,
                    'full_line': line
                })
    except:
        pass
    return jobs

def add_cron_job(schedule, command):
    try:
        if not os.path.exists(CRONTAB_FILE):
            with open(CRONTAB_FILE, 'w') as f:
                f.write("# OpenWrt crontab\n")
        with open(CRONTAB_FILE, 'r') as f:
            lines = f.readlines()
        for line in lines:
            if line.strip() == f"{schedule} {command}":
                return False, "该定时任务已存在"
        with open(CRONTAB_FILE, 'a') as f:
            f.write(f"{schedule} {command}\n")
        subprocess.run(['/etc/init.d/cron', 'restart'], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return True, "添加成功"
    except Exception as e:
        return False, str(e)

def delete_cron_job(full_line):
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
            return False, "未找到该任务"
        with open(CRONTAB_FILE, 'w') as f:
            f.writelines(new_lines)
        subprocess.run(['/etc/init.d/cron', 'restart'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return True, "删除成功"
    except Exception as e:
        return False, str(e)

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

@app.route('/api/meminfo')
def api_meminfo():
    return jsonify(get_meminfo())

@app.route('/api/router_ip')
def api_router_ip():
    return jsonify({'ip': get_router_ip()})

@app.route('/api/apk_cache_size')
def api_apk_cache_size():
    return jsonify({'size_mb': get_apk_cache_size()})

@app.route('/api/top_processes')
def api_top_processes():
    procs = get_top_memory_processes(limit=10)
    return jsonify([{
        'pid': p['pid'],
        'name': p['name'],
        'cmdline': p['cmdline'],
        'rss_mb': round(p['rss_kb'] / 1024, 1),
        'is_script': p['is_script']
    } for p in procs])

# ========== Cron 路由 ==========
@app.route('/api/cron_jobs')
def api_cron_jobs():
    return jsonify(get_cron_jobs())

@app.route('/api/cron_add', methods=['POST'])
def api_cron_add():
    data = request.json
    schedule = data.get('schedule', '').strip()
    command = data.get('command', '').strip()
    if not schedule or not command:
        return jsonify({'error': '请填写完整信息'}), 400
    parts = schedule.split()
    if len(parts) != 5:
        return jsonify({'error': 'Cron 格式错误，应为: 分 时 日 月 周'}), 400
    success, msg = add_cron_job(schedule, command)
    if success:
        return jsonify({'message': f'✅ {msg}'})
    else:
        return jsonify({'error': msg}), 500

@app.route('/api/cron_delete', methods=['POST'])
def api_cron_delete():
    data = request.json
    full_line = data.get('full_line', '').strip()
    if not full_line:
        return jsonify({'error': '请指定要删除的任务'}), 400
    success, msg = delete_cron_job(full_line)
    if success:
        return jsonify({'message': f'✅ {msg}'})
    else:
        return jsonify({'error': msg}), 500

# ========== APK 缓存清理 ==========
@app.route('/api/apk_clean_cache', methods=['POST'])
def api_apk_clean_cache():
    try:
        result = subprocess.run(
            ['apk', 'cache', 'clean'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            new_size = get_apk_cache_size()
            return jsonify({
                'message': f'✅ 缓存已清理，当前缓存 {new_size}MB',
                'size_mb': new_size
            })
        else:
            result = subprocess.run(
                ['apk', 'cache', 'purge'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                new_size = get_apk_cache_size()
                return jsonify({
                    'message': f'✅ 缓存已清理（purge），当前缓存 {new_size}MB',
                    'size_mb': new_size
                })
            else:
                return jsonify({'error': f'清理失败: {result.stderr}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

# ========== 停止脚本 ==========
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
        return jsonify({'message': f'ℹ️ {name} 状态已重置'})

# ========== 清理高内存进程 ==========
@app.route('/api/kill_top_process', methods=['POST'])
def kill_top_process():
    exclude_pid = os.getpid()
    top_procs = get_top_memory_processes(exclude_pid=exclude_pid, limit=10)
    if not top_procs:
        return jsonify({'error': '未找到可清理的进程'}), 404
    target = top_procs[0]
    pid = target['pid']
    name = target['name']
    rss_mb = round(target['rss_kb'] / 1024, 1)
    is_script = target['is_script']
    if not kill_process(pid):
        return jsonify({'error': f'杀进程 {pid} 失败'}), 500
    result_msg = f'🔪 已杀掉进程 PID:{pid} ({name})，内存占用 {rss_mb}MB'
    try:
        subprocess.run(['sync'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        with open('/proc/sys/vm/drop_caches', 'w') as f:
            f.write('3')
        result_msg += '；🧹 缓存已清理'
    except:
        pass
    gc.collect()
    result_msg += '；♻️ 内存回收完成'
    restarted = False
    script_name = None
    if is_script:
        for part in target['cmdline'].split():
            if '/root/scripts/' in part and part.endswith('.py'):
                script_name = os.path.basename(part)
                break
        if script_name:
            script_path = os.path.join(SCRIPTS_DIR, script_name)
            if os.path.exists(script_path):
                with app.test_client() as client:
                    resp = client.post(f'/api/run/{script_name}')
                    if resp.status_code == 200:
                        restarted = True
                        result_msg += f'；✅ 已自动重启脚本 {script_name}'
                    else:
                        result_msg += f'；⚠️ 自动重启脚本 {script_name} 失败'
    return jsonify({
        'message': result_msg,
        'killed': {'pid': pid, 'name': name, 'rss_mb': rss_mb},
        'restarted': restarted,
        'script_name': script_name
    })

# ========== 重启路由器 ==========
@app.route('/api/restart_router', methods=['POST'])
def restart_router():
    try:
        subprocess.Popen(['reboot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'message': '✅ 路由器正在重启...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

# ========== GitHub 同步 ==========
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
                pass
        if downloaded:
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

# ==================== HTML 模板 ====================
HTML = r'''
<!DOCTYPE html>
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
.stat-card{background:#fff;padding:12px 20px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.06);flex:1;min-width:70px}
.stat-card .num{font-size:24px;font-weight:700;color:#333}
.stat-card .label{font-size:12px;color:#999}
.stat-card .mem-bar-wrap{width:100%;height:4px;background:#e0e0e0;border-radius:2px;margin-top:6px;overflow:hidden}
.stat-card .mem-bar{height:100%;border-radius:2px;transition:width 0.3s}
.actions-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;padding:8px 12px;background:#f8f9fa;border-radius:8px}
.actions-bar .sep{color:#ccc;font-size:20px;font-weight:300;display:flex;align-items:center}
.actions-bar button{padding:6px 14px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500}
.actions-bar .group-label{font-size:11px;color:#999;font-weight:600;display:flex;align-items:center;margin-right:2px}
.btn-new{background:#667eea;color:#fff}.btn-new:hover{background:#5a6fd6}
.btn-upload{background:#4caf50;color:#fff}.btn-upload:hover{background:#43a047}
.btn-sync{background:#ff6b6b;color:#fff}.btn-sync:hover{background:#e55a5a}
.btn-gc{background:#607d8b;color:#fff}.btn-gc:hover{background:#455a64}
.btn-cron{background:#00897b;color:#fff}.btn-cron:hover{background:#00695c}
.btn-luci{background:#1565c0;color:#fff}.btn-luci:hover{background:#0d47a1}
.btn-9090{background:#e65100;color:#fff}.btn-9090:hover{background:#bf360c}
.btn-reboot{background:#c62828;color:#fff}.btn-reboot:hover{background:#b71c1c}
.btn-kill{background:#7b1fa2;color:#fff}.btn-kill:hover{background:#4a148c}
.btn-kill:disabled{opacity:.5;cursor:not-allowed}
.btn-cache{background:#00695c;color:#fff}.btn-cache:hover{background:#004d40}
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
input, textarea, select{width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin:6px 0;font-size:14px;font-family:inherit}
textarea{min-height:180px;font-family:monospace;resize:vertical}
select{appearance:auto;background:#fff}
.modal-box .form-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.modal-box .form-actions button{padding:6px 20px;border:none;border-radius:6px;cursor:pointer;font-weight:500}
.btn-primary{background:#667eea;color:#fff}
.btn-primary:hover{background:#5a6fd6}
.btn-secondary{background:#eceff1;color:#333}
.btn-secondary:hover{background:#d5d9de}
.btn-danger{background:#f44336;color:#fff}
.btn-danger:hover{background:#d32f2f}
.btn-success{background:#4caf50;color:#fff}
.btn-success:hover{background:#388e3c}
.sync-input-group{display:flex;flex-direction:column;gap:4px;margin:8px 0}
.sync-input-group label{font-weight:500;font-size:14px;color:#555}
.sync-input-group input{width:100%;padding:8px 12px;border:1px solid #ddd;border-radius:6px;font-size:14px;font-family:monospace}
.sync-input-group .hint{font-size:12px;color:#999;margin-top:2px}
.cron-item{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid #f0f0f0;flex-wrap:wrap;gap:6px}
.cron-item .cron-sched{font-family:monospace;font-size:13px;color:#333;background:#f5f5f5;padding:2px 10px;border-radius:4px}
.cron-item .cron-cmd{font-size:13px;color:#555;word-break:break-all;flex:1;margin:0 10px}
.cron-item .cron-actions button{padding:2px 12px;border:none;border-radius:4px;cursor:pointer;font-size:12px}
.cron-empty{color:#999;padding:20px;text-align:center}
.cron-grid{max-height:300px;overflow-y:auto;border:1px solid #eee;border-radius:8px}
@media(max-width:600px){.grid{grid-template-columns:1fr}.actions-bar{flex-direction:column;align-items:stretch}}
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
<div class="stat-card" id="memCard">
<div class="num" id="memText">-- MB</div>
<div class="label" id="memLabel">💾 内存使用</div>
<div class="mem-bar-wrap"><div class="mem-bar" id="memBar" style="width:0%;background:#4caf50"></div></div>
</div>
<div class="stat-card" id="cacheCard">
<div class="num" id="cacheSize">-- MB</div>
<div class="label">📦 APK缓存</div>
</div>
<div class="stat-card" style="flex:0"><button class="refresh-btn" id="refreshBtn">🔄 刷新</button></div>
</div>

<!-- 按钮组1: 脚本管理 -->
<div class="actions-bar">
<span class="group-label">📜 脚本</span>
<button class="btn-new" id="btnNew">➕ 新建</button>
<button class="btn-upload" id="btnUpload">📤 上传</button>
<button class="btn-sync" id="btnSync">📥 同步</button>
<button class="btn-gc" id="btnGc">🧹 GC</button>
<button class="btn-cron" id="btnCron">⏰ 定时</button>
<input type="file" id="fileInput" accept=".py" style="display:none">
</div>

<!-- 按钮组2: 路由器工具 -->
<div class="actions-bar">
<span class="group-label">⚙️ 路由</span>
<button class="btn-luci" id="btnLuci">🌐 路由器</button>
<button class="btn-9090" id="btn9090">🔧 后端</button>
<button class="btn-reboot" id="btnReboot">🔄 重启路由</button>
<button class="btn-kill" id="btnKill">💣 清理进程</button>
<button class="btn-cache" id="btnCache">🧹 清理缓存</button>
</div>

<div class="grid" id="grid"></div>
</div>

<!-- 新建脚本弹窗 -->
<div class="modal" id="newModal"><div class="modal-box">
<span class="close" id="closeNew">&times;</span>
<h2>📝 新建脚本</h2>
<div style="margin:12px 0"><label>文件名（.py）</label><input type="text" id="newName" placeholder="例如: monitor.py"></div>
<div><label>代码内容</label><textarea id="newContent" placeholder="# 在此编写 Python 代码"></textarea></div>
<div class="form-actions"><button class="btn-primary" id="saveNew">💾 保存</button><button class="btn-secondary" id="cancelNew">取消</button></div>
</div></div>

<!-- 编辑脚本弹窗 -->
<div class="modal" id="editModal"><div class="modal-box">
<span class="close" id="closeEdit">&times;</span>
<h2>✏️ 编辑脚本</h2>
<div style="margin:12px 0"><label id="editFileName">文件名</label><textarea id="editContent"></textarea></div>
<div class="form-actions"><button class="btn-primary" id="saveEditBtn">💾 保存</button><button class="btn-secondary" id="cancelEdit">取消</button></div>
</div></div>

<!-- 同步脚本弹窗 -->
<div class="modal" id="syncModal"><div class="modal-box">
<span class="close" id="closeSync">&times;</span>
<h2>📥 从 GitHub 同步脚本</h2>
<div class="sync-input-group">
<label>仓库地址（含 Token）</label>
<input type="text" id="syncTongbukuang" placeholder="https://token@github.com/用户名/仓库名">
<div class="hint">💡 格式：https://{token}@github.com/{用户名}/{仓库名}</div>
</div>
<div class="form-actions"><button class="btn-primary" id="doSyncBtn">📥 开始同步</button><button class="btn-secondary" id="cancelSync">取消</button></div>
</div></div>

<!-- Cron 管理弹窗 -->
<div class="modal" id="cronModal"><div class="modal-box">
<span class="close" id="closeCron">&times;</span>
<h2>⏰ 定时任务管理 (Cron)</h2>
<div style="margin:12px 0;background:#f5f7fa;padding:12px;border-radius:8px">
<div style="display:flex;gap:8px;flex-wrap:wrap">
<div style="flex:2;min-width:180px"><label>执行时间</label><input type="text" id="cronSchedule" placeholder="分 时 日 月 周" value="0 */6 * * *"></div>
<div style="flex:3;min-width:200px"><label>执行命令</label>
<select id="cronCommand" style="margin:6px 0">
<option value="">-- 选择脚本 --</option>
</select>
</div>
</div>
<div style="margin-top:6px"><label>自定义命令</label><input type="text" id="cronCustomCmd" placeholder="或直接输入完整命令"></div>
<div class="form-actions"><button class="btn-success" id="addCronBtn">➕ 添加任务</button></div>
<div style="margin-top:8px;font-size:12px;color:#888">💡 示例: <code>0 */6 * * *</code> = 每6小时执行一次</div>
</div>
<div style="margin-top:12px"><label>📋 当前任务列表</label>
<div class="cron-grid" id="cronList"><div class="cron-empty">加载中...</div></div>
</div>
<div class="form-actions"><button class="btn-secondary" id="closeCronBtn">关闭</button></div>
</div></div>

<!-- 日志弹窗 -->
<div class="modal" id="logModal"><div class="modal-box"><span class="close" id="closeLog">&times;</span><h2 id="logTitle">日志</h2><div class="meta" id="logMeta"></div><pre id="logContent">暂无</pre></div></div>

<script>
(function() {
    'use strict';

    var routerIP = '';

    function st(s) {
        var map = {idle:'待执行', running:'运行中', success:'成功', failed:'失败', timeout:'超时', error:'错误', stopped:'已停止'};
        return map[s] || s;
    }

    function badge(s) {
        return '<span class="badge ' + s + '">' + st(s) + '</span>';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;');
    }

    function fetchRouterIP() {
        fetch('/api/router_ip').then(function(r) { return r.json(); }).then(function(data) {
            routerIP = data.ip || window.location.hostname || '192.168.1.1';
        }).catch(function() {
            routerIP = window.location.hostname || '192.168.1.1';
        });
    }

    function loadMem() {
        fetch('/api/meminfo').then(function(r) { return r.json(); }).then(function(data) {
            var total = data.total_kb || 0;
            var used = data.used_kb || 0;
            var totalMB = (total/1024).toFixed(0);
            var usedMB = (used/1024).toFixed(0);
            var percent = data.percent || 0;
            document.getElementById('memText').textContent = usedMB + '/' + totalMB + ' MB';
            document.getElementById('memLabel').textContent = '💾 内存使用 ' + percent + '%';
            var bar = document.getElementById('memBar');
            bar.style.width = Math.min(percent, 100) + '%';
            if (percent > 85) bar.style.background = '#f44336';
            else if (percent > 70) bar.style.background = '#ff9800';
            else bar.style.background = '#4caf50';
        }).catch(function() {});
    }

    function loadApkCache() {
        fetch('/api/apk_cache_size').then(function(r) { return r.json(); }).then(function(data) {
            var size = data.size_mb || 0;
            document.getElementById('cacheSize').textContent = size.toFixed(1) + ' MB';
        }).catch(function() {
            document.getElementById('cacheSize').textContent = '-- MB';
        });
    }

    function loadScripts() {
        fetch('/api/scripts').then(function(r) { return r.json(); }).then(function(data) {
            var g = document.getElementById('grid');
            if (!data || !data.length) {
                g.innerHTML = '<div class="empty">📂 暂无脚本<br><small>点击 "新建"、"上传" 或 "同步" 添加脚本</small></div>';
                updateStats(0, 0, 0, 0);
                return;
            }
            var rn = 0, su = 0, fa = 0;
            var html = '';
            data.forEach(function(s) {
                var status = s.status || 'idle';
                if (status === 'running') rn++;
                if (status === 'success') su++;
                if (['failed','timeout','error'].indexOf(status) !== -1) fa++;
                var remarkHtml = s.remark ? '<div class="remark-line">' + s.remark + '</div>' : '';
                var stopBtn = status === 'running' ? '<button class="btn-stop" data-name="' + s.name + '">⏹ 停止</button>' : '';
                html += '<div class="card ' + status + '">' +
                    '<div class="top"><span class="name">' + s.name + '</span>' + badge(status) + '</div>' +
                    remarkHtml +
                    '<div class="info"><span class="lbl">📏</span> ' + (s.size/1024).toFixed(1) + 'KB &nbsp; <span class="lbl">🕐</span> ' + s.mtime +
                    '<br><span class="lbl">⏱</span> ' + (s.last_run || '从未运行') + ' &nbsp; <span class="lbl">📋</span> ' + (s.history_count || 0) + '次</div>' +
                    '<div class="actions">' +
                    '<button class="btn-run" data-name="' + s.name + '" ' + (status === 'running' ? 'disabled' : '') + '>▶ 运行</button>' +
                    stopBtn +
                    '<button class="btn-edit" data-name="' + s.name + '">✏️ 编辑</button>' +
                    '<button class="btn-del" data-name="' + s.name + '">🗑 删除</button>' +
                    '<button class="btn-log" data-name="' + s.name + '">📄 日志</button>' +
                    '</div></div>';
            });
            g.innerHTML = html;
            updateStats(data.length, rn, su, fa);
            bindCardEvents();
        }).catch(function() {});
    }

    function updateStats(total, rn, su, fa) {
        document.getElementById('total').textContent = total;
        document.getElementById('running').textContent = rn;
        document.getElementById('success').textContent = su;
        document.getElementById('failed').textContent = fa;
    }

    function loadAll() {
        loadScripts();
        loadMem();
        loadApkCache();
    }

    function bindCardEvents() {
        document.querySelectorAll('.btn-run').forEach(function(btn) {
            btn.removeEventListener('click', runHandler);
            btn.addEventListener('click', runHandler);
        });
        document.querySelectorAll('.btn-stop').forEach(function(btn) {
            btn.removeEventListener('click', stopHandler);
            btn.addEventListener('click', stopHandler);
        });
        document.querySelectorAll('.btn-edit').forEach(function(btn) {
            btn.removeEventListener('click', editHandler);
            btn.addEventListener('click', editHandler);
        });
        document.querySelectorAll('.btn-del').forEach(function(btn) {
            btn.removeEventListener('click', delHandler);
            btn.addEventListener('click', delHandler);
        });
        document.querySelectorAll('.btn-log').forEach(function(btn) {
            btn.removeEventListener('click', logHandler);
            btn.addEventListener('click', logHandler);
        });
    }

    function runHandler(e) {
        var name = e.target.getAttribute('data-name');
        if (!confirm('确定执行 "' + name + '" 吗？')) return;
        fetch('/api/run/' + encodeURIComponent(name), {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(d) { alert(d.message || d.error); loadAll(); })
            .catch(function() {});
    }

    function stopHandler(e) {
        var name = e.target.getAttribute('data-name');
        if (!confirm('确定停止 "' + name + '" 吗？')) return;
        fetch('/api/stop/' + encodeURIComponent(name), {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(d) { alert(d.message || d.error); loadAll(); })
            .catch(function() {});
    }

    function editHandler(e) {
        var name = e.target.getAttribute('data-name');
        showEditModal(name);
    }

    function delHandler(e) {
        var name = e.target.getAttribute('data-name');
        if (!confirm('确定删除 "' + name + '" 吗？')) return;
        fetch('/api/delete/' + encodeURIComponent(name), {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(d) { alert(d.message || d.error); loadAll(); })
            .catch(function() {});
    }

    function logHandler(e) {
        var name = e.target.getAttribute('data-name');
        fetch('/api/log/' + encodeURIComponent(name))
            .then(function(r) { return r.json(); })
            .then(function(d) {
                document.getElementById('logTitle').textContent = '📄 ' + name;
                document.getElementById('logMeta').textContent = '状态: ' + st(d.status);
                document.getElementById('logContent').textContent = d.output || '暂无输出';
                document.getElementById('logModal').classList.add('active');
            })
            .catch(function() {});
    }

    function openModal(id) { document.getElementById(id).classList.add('active'); }
    function closeModal(id) { document.getElementById(id).classList.remove('active'); }

    // 新建脚本
    function showNewModal() { openModal('newModal'); }
    function closeNewModal() { closeModal('newModal'); }
    function createScript() {
        var name = document.getElementById('newName').value.trim();
        var content = document.getElementById('newContent').value;
        if (!name) { alert('请输入文件名'); return; }
        if (!content) { alert('代码内容不能为空'); return; }
        fetch('/api/new', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, content: content})
        })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            alert(d.message || d.error);
            if (d.message) {
                closeNewModal();
                document.getElementById('newName').value = '';
                document.getElementById('newContent').value = '';
                loadAll();
            }
        })
        .catch(function() {});
    }

    // 编辑脚本
    var editingName = '';
    function showEditModal(name) {
        editingName = name;
        document.getElementById('editFileName').textContent = '📄 ' + name;
        fetch('/api/get/' + encodeURIComponent(name))
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.error) { alert(d.error); return; }
                document.getElementById('editContent').value = d.content || '';
                openModal('editModal');
            })
            .catch(function() { alert('获取脚本失败'); });
    }
    function closeEditModal() { closeModal('editModal'); editingName = ''; }
    function saveEdit() {
        var content = document.getElementById('editContent').value;
        if (!content) { alert('内容不能为空'); return; }
        fetch('/api/edit/' + encodeURIComponent(editingName), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({content: content})
        })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            alert(d.message || d.error);
            if (d.message) { closeEditModal(); loadAll(); }
        })
        .catch(function() {});
    }

    // 上传
    function uploadFile() {
        var input = document.getElementById('fileInput');
        if (!input.files.length) return;
        var file = input.files[0];
        var formData = new FormData();
        formData.append('file', file);
        fetch('/api/upload', {method: 'POST', body: formData})
            .then(function(r) { return r.json(); })
            .then(function(d) { alert(d.message || d.error); if (d.message) loadAll(); })
            .catch(function() {});
        input.value = '';
    }

    // 同步
    function showSyncModal() {
        openModal('syncModal');
        fetch('/api/sync_config')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                document.getElementById('syncTongbukuang').value = data.tongbukuang || '';
            })
            .catch(function() {});
    }
    function closeSyncModal() { closeModal('syncModal'); }
    function doSync() {
        var val = document.getElementById('syncTongbukuang').value.trim();
        if (!val) { alert('请输入仓库地址'); return; }
        if (!confirm('将从以下地址同步脚本:\n' + val + '\n确定吗？')) return;
        fetch('/api/sync_github', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tongbukuang: val})
        })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            alert(d.message || d.error);
            if (d.message) { closeSyncModal(); loadAll(); }
        })
        .catch(function() {});
    }

    // GC
    function forceGC() {
        if (!confirm('执行垃圾回收，可能会短暂卡顿，确定吗？')) return;
        fetch('/api/gc', {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(d) { alert(d.message); loadAll(); })
            .catch(function() {});
    }

    // Cron
    function showCronModal() {
        openModal('cronModal');
        loadCronList();
        loadScriptsForCronSelect();
    }
    function closeCronModal() { closeModal('cronModal'); }

    function loadScriptsForCronSelect() {
        fetch('/api/scripts')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var sel = document.getElementById('cronCommand');
                sel.innerHTML = '<option value="">-- 选择脚本 --</option>';
                if (data && data.length) {
                    data.forEach(function(s) {
                        var opt = document.createElement('option');
                        opt.value = 'python3 /root/scripts/' + s.name;
                        opt.textContent = s.name;
                        sel.appendChild(opt);
                    });
                }
            })
            .catch(function() {});
    }

    function loadCronList() {
        var container = document.getElementById('cronList');
        container.innerHTML = '<div class="cron-empty">加载中...</div>';
        fetch('/api/cron_jobs')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!data || !data.length) {
                    container.innerHTML = '<div class="cron-empty">📭 暂无定时任务</div>';
                    return;
                }
                var html = '';
                data.forEach(function(job) {
                    var label = job.is_script ? '📜' : '⚙️';
                    html += '<div class="cron-item">' +
                        '<span class="cron-sched">' + job.schedule + '</span>' +
                        '<span class="cron-cmd">' + label + ' ' + escapeHtml(job.command) + '</span>' +
                        '<div class="cron-actions"><button class="btn-danger" data-line="' + escapeHtml(job.full_line) + '">🗑</button></div>' +
                        '</div>';
                });
                container.innerHTML = html;
                container.querySelectorAll('.cron-actions .btn-danger').forEach(function(btn) {
                    btn.removeEventListener('click', deleteCronHandler);
                    btn.addEventListener('click', deleteCronHandler);
                });
            })
            .catch(function() {
                container.innerHTML = '<div class="cron-empty">⚠️ 加载失败</div>';
            });
    }

    function deleteCronHandler(e) {
        var fullLine = e.target.getAttribute('data-line');
        if (!confirm('确定删除该定时任务吗？')) return;
        fetch('/api/cron_delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({full_line: fullLine})
        })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            alert(d.message || d.error);
            if (d.message) loadCronList();
        })
        .catch(function() { alert('删除失败'); });
    }

    function addCronJob() {
        var schedule = document.getElementById('cronSchedule').value.trim();
        var cmdSelect = document.getElementById('cronCommand').value;
        var customCmd = document.getElementById('cronCustomCmd').value.trim();
        var command = cmdSelect || customCmd;
        if (!schedule) { alert('请输入执行时间'); return; }
        if (!command) { alert('请选择脚本或输入自定义命令'); return; }
        var parts = schedule.split(/\s+/);
        if (parts.length !== 5) {
            alert('Cron 格式错误，应为: 分 时 日 月 周\n例如: 0 */6 * * *');
            return;
        }
        fetch('/api/cron_add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({schedule: schedule, command: command})
        })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            alert(d.message || d.error);
            if (d.message) { loadCronList(); document.getElementById('cronCustomCmd').value = ''; }
        })
        .catch(function() { alert('请求失败'); });
    }

    // 清理进程
    function killTopProcess() {
        if (!confirm('🔪 将查找占用内存最高的进程并杀掉\n→ 自动清理系统缓存\n→ 自动触发内存回收\n如果是面板管理的脚本则自动重启\n确定执行吗？')) return;
        var btn = document.getElementById('btnKill');
        btn.disabled = true;
        btn.textContent = '⏳ 执行中...';
        fetch('/api/kill_top_process', {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.error) { alert('❌ ' + d.error); }
                else { alert(d.message || '执行完成'); }
                loadAll();
                btn.disabled = false;
                btn.textContent = '💣 清理进程';
            })
            .catch(function() {
                alert('❌ 执行失败');
                btn.disabled = false;
                btn.textContent = '💣 清理进程';
            });
    }

    // APK缓存清理
    function cleanApkCache() {
        if (!confirm('🧹 将清理 apk 下载缓存（/var/cache/apk/）\n确定执行吗？')) return;
        var btn = document.getElementById('btnCache');
        var origText = btn.textContent;
        btn.disabled = true;
        btn.textContent = '⏳ 清理中...';
        fetch('/api/apk_clean_cache', {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(d) {
                alert(d.message || d.error || '执行完成');
                loadApkCache();
                loadMem();
                btn.disabled = false;
                btn.textContent = origText;
            })
            .catch(function() {
                alert('❌ 清理失败');
                btn.disabled = false;
                btn.textContent = origText;
            });
    }

    // 重启路由器
    function rebootRouter() {
        if (!confirm('⚠️ 确定要重启路由器吗？\n面板将断开连接！')) return;
        if (!confirm('⚠️ 再次确认：重启路由器？')) return;
        alert('🔄 路由器正在重启，请稍后重新访问...');
        fetch('/api/restart_router', {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(d) {});
    }

    // 跳转
    function goLuci() {
        if (routerIP) {
            window.open('http://' + routerIP + '/cgi-bin/luci', '_blank');
        } else {
            window.open('/cgi-bin/luci', '_blank');
        }
    }

    function go9090() {
        if (routerIP) {
            window.open('http://' + routerIP + ':9090/ui', '_blank');
        } else {
            window.open('http://192.168.1.1:9090/ui', '_blank');
        }
    }

    // ========== 绑定按钮事件 ==========
    function bindTopButtons() {
        document.getElementById('refreshBtn').addEventListener('click', loadAll);
        document.getElementById('btnNew').addEventListener('click', showNewModal);
        document.getElementById('btnUpload').addEventListener('click', function() { document.getElementById('fileInput').click(); });
        document.getElementById('btnSync').addEventListener('click', showSyncModal);
        document.getElementById('btnGc').addEventListener('click', forceGC);
        document.getElementById('btnCron').addEventListener('click', showCronModal);
        document.getElementById('btnLuci').addEventListener('click', goLuci);
        document.getElementById('btn9090').addEventListener('click', go9090);
        document.getElementById('btnReboot').addEventListener('click', rebootRouter);
        document.getElementById('btnKill').addEventListener('click', killTopProcess);
        document.getElementById('btnCache').addEventListener('click', cleanApkCache);

        document.getElementById('fileInput').addEventListener('change', uploadFile);

        document.getElementById('saveNew').addEventListener('click', createScript);
        document.getElementById('cancelNew').addEventListener('click', closeNewModal);
        document.getElementById('closeNew').addEventListener('click', closeNewModal);

        document.getElementById('saveEditBtn').addEventListener('click', saveEdit);
        document.getElementById('cancelEdit').addEventListener('click', closeEditModal);
        document.getElementById('closeEdit').addEventListener('click', closeEditModal);

        document.getElementById('doSyncBtn').addEventListener('click', doSync);
        document.getElementById('cancelSync').addEventListener('click', closeSyncModal);
        document.getElementById('closeSync').addEventListener('click', closeSyncModal);

        document.getElementById('addCronBtn').addEventListener('click', addCronJob);
        document.getElementById('closeCronBtn').addEventListener('click', closeCronModal);
        document.getElementById('closeCron').addEventListener('click', closeCronModal);

        document.getElementById('closeLog').addEventListener('click', function() { closeModal('logModal'); });
        document.getElementById('logModal').addEventListener('click', function(e) {
            if (e.target === this) closeModal('logModal');
        });

        ['newModal','editModal','syncModal','cronModal'].forEach(function(id) {
            document.getElementById(id).addEventListener('click', function(e) {
                if (e.target === this) closeModal(id);
            });
        });
    }

    // ========== 启动 ==========
    fetchRouterIP();
    loadAll();
    setInterval(loadAll, 10000);
    bindTopButtons();

})();
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
