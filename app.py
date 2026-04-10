#!/usr/bin/env python3
"""
抖音文案提取 - v5.0 异步版
解决超时问题：异步处理 + 快速语音识别
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import tempfile
import os
import re
import json
import time
import uuid
import threading
import requests

app = Flask(__name__, static_folder='public')
CORS(app)

# 任务存储（生产环境应使用 Redis）
tasks = {}

def extract_url_from_share(text):
    """从分享口令中提取抖音链接"""
    pattern = r'https://v\.douyin\.com/[A-Za-z0-9]+'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    pattern2 = r'https://www\.douyin\.com/video/\d+'
    match2 = re.search(pattern2, text)
    if match2:
        return match2.group(0)
    return None

def parse_douyin_url(douyin_url):
    """解析抖音链接"""
    try:
        api_url = f"https://api.xingzhige.com/API/douyin/?url={douyin_url}"
        resp = requests.get(api_url, timeout=30)
        data = resp.json()
        
        if data.get('code') != 0:
            return None, data.get('msg', '解析失败')
        
        video_data = data.get('data', {})
        item = video_data.get('item', {})
        
        video_url = item.get('url')
        if not video_url:
            return None, '未找到视频链接'
        
        return {
            'video_url': video_url,
            'title': item.get('title', '抖音视频'),
            'author': video_data.get('author', {}).get('name', '未知'),
        }, None
    except Exception as e:
        return None, str(e)

def download_video(video_url, output_path):
    """下载视频"""
    cmd = [
        'curl', '-L', '-o', output_path,
        '-H', 'User-Agent: Mozilla/5.0',
        '--connect-timeout', '30',
        '--max-time', '120',
        video_url
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=150)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except:
        return False

def transcribe_fast(video_path):
    """快速语音识别"""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel('tiny', device='cpu', compute_type='int8')
        segments, info = model.transcribe(video_path, language='zh')
        
        text = ''.join([s.text for s in segments])
        return text.strip(), info.duration
    except Exception as e:
        return None, 0

def process_task(task_id, douyin_url):
    """后台处理任务"""
    try:
        tasks[task_id]['status'] = 'parsing'
        tasks[task_id]['progress'] = 10
        
        # 解析链接
        result, error = parse_douyin_url(douyin_url)
        if not result:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = error
            return
        
        tasks[task_id]['progress'] = 30
        tasks[task_id]['status'] = 'downloading'
        tasks[task_id]['title'] = result['title']
        tasks[task_id]['author'] = result['author']
        
        # 下载视频
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        
        if not download_video(result['video_url'], video_path):
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '视频下载失败'
            return
        
        file_size = os.path.getsize(video_path)
        tasks[task_id]['progress'] = 60
        tasks[task_id]['status'] = 'transcribing'
        
        # 语音识别
        transcript, duration = transcribe_fast(video_path)
        
        if not transcript:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '语音识别失败'
            return
        
        # 清理
        try:
            os.remove(video_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        # 完成
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['result'] = {
            'title': result['title'],
            'author': result['author'],
            'duration': round(duration, 1),
            'transcript': transcript,
            'file_size_mb': round(file_size / 1024 / 1024, 2)
        }
        
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/extract', methods=['POST'])
def create_task():
    """创建提取任务"""
    try:
        data = request.get_json()
        input_text = data.get('url', '')
        
        if not input_text:
            return jsonify({'success': False, 'message': '请输入内容'}), 400
        
        # 提取抖音链接
        douyin_url = extract_url_from_share(input_text)
        if not douyin_url:
            return jsonify({'success': False, 'message': '未找到有效的抖音链接'}), 400
        
        # 创建任务
        task_id = str(uuid.uuid4())[:8]
        tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'created_at': time.time()
        }
        
        # 后台处理
        thread = threading.Thread(target=process_task, args=(task_id, douyin_url))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'taskId': task_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/status/<task_id>')
def get_status(task_id):
    """查询任务状态"""
    if task_id not in tasks:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    
    task = tasks[task_id]
    
    response = {
        'success': True,
        'status': task['status'],
        'progress': task['progress']
    }
    
    if task['status'] == 'completed':
        response['data'] = task['result']
    elif task['status'] == 'failed':
        response['message'] = task.get('error', '处理失败')
    
    return jsonify(response)

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'douyin-transcript',
        'version': '5.0',
        'updated': '2024-04-10'
    })

if __name__ == '__main__':
    print("=" * 50)
    print("抖音文案提取服务 v5.0（异步版）")
    print("支持：抖音分享链接直接解析")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
