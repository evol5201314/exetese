#!/usr/bin/env python3
# -*- coding: utf-8 -*-
beizhu = "📈 面板完整版（所有弹窗动态加载）"

import os, sys, json, subprocess, threading, signal, gc
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, send_from_directory

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
                k, v = line.split(':',
