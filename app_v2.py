#!/usr/bin/env python3
"""
抖音文案提取 - 完整服务版
支持多种输入方式：
1. 抖音链接（需要解析）
2. 视频直链（直接下载）
3. 本地视频文件（直接识别）
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import tempfile
import os
import re
import json
import threading
import time
import uuid

app = Flask(__name__, static_folder='public')
CORS(app)

tasks = {}

def is_direct_video_url(url):
    """判断是否为视频直链"""
    video_extensions = ['.mp4', '.m3u8', '.mov', '.avi', '.mkv', '.webm']
    video_domains = ['douyinvod.com', 'v.douyin.com', 'bytedance.com', 'bytecdn.cn']
    
    url_lower = url.lower()
    
    # 检查域名
    for domain in video_domains:
        if domain in url_lower:
            return True
    
    # 检查扩展名
    for ext in video_extensions:
        if ext in url_lower:
            return True
    
    return False

def download_video_direct(video_url, output_path):
    """直接下载视频"""
    cmd = [
        'curl', '-L', '-o', output_path,
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '-H', 'Referer: https://www.douyin.com/',
        '--connect-timeout', '30',
        '--max-time', '300',
        video_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=360)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True, None
        return False, "下载的文件太小或不存在"
    except subprocess.TimeoutExpired:
        return False, "下载超时"
    except Exception as e:
        return False, str(e)

def transcribe_video(video_path, model_size='tiny'):
    """使用 faster-whisper 进行语音识别"""
    try:
        from faster_whisper import WhisperModel
        
        print(f"加载 Whisper 模型: {model_size}")
        model = WhisperModel(model_size, device='cpu', compute_type='int8')
        
        print("开始语音识别...")
        segments, info = model.transcribe(video_path, language='zh')
        
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text)
        
        full_transcript = ''.join(transcript_parts)
        print(f"识别完成，时长: {info.duration:.1f}秒")
        
        return full_transcript.strip(), info.duration
        
    except ImportError:
        raise Exception("请安装 faster-whisper: pip install faster-whisper")
    except Exception as e:
        raise Exception(f"语音识别失败: {e}")

def process_task(task_id, input_data):
    """后台处理任务"""
    try:
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['progress'] = 10
        tasks[task_id]['message'] = '准备处理...'
        
        # 获取输入
        video_url = input_data.get('video_url', '')
        is_direct = input_data.get('is_direct_link', False)
        model_size = input_data.get('model', 'tiny')
        
        if not video_url:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '请提供视频链接'
            return
        
        tasks[task_id]['progress'] = 20
        tasks[task_id]['message'] = '正在下载视频...'
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        
        # 下载视频
        success, error = download_video_direct(video_url, video_path)
        
        if not success:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = f'视频下载失败: {error}'
            try:
                os.rmdir(temp_dir)
            except:
                pass
            return
        
        tasks[task_id]['progress'] = 50
        tasks[task_id]['message'] = 'AI 语音识别中...'
        
        # 获取文件大小
        file_size = os.path.getsize(video_path)
        tasks[task_id]['file_size'] = file_size
        
        # 语音识别
        transcript, duration = transcribe_video(video_path, model_size)
        
        # 清理临时文件
        try:
            os.remove(video_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['result'] = {
            'title': '视频文案',
            'author': '未知',
            'duration': round(duration, 1),
            'url': video_url,
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
def start_extract():
    """开始提取文案"""
    try:
        data = request.get_json()
        
        # 支持两种输入方式
        # 1. video_url: 视频直链
        # 2. url_or_share_text: 抖音链接（需要解析）
        
        video_url = data.get('video_url', '')
        input_text = data.get('url_or_share_text', '')
        
        # 如果提供了抖音链接，提示用户需要解析
        if input_text and not video_url:
            url_match = re.search(r'https://v\.douyin\.com/[A-Za-z0-9]+', input_text)
            if not url_match:
                url_match = re.search(r'https://www\.douyin\.com/video/\d+', input_text)
            
            if url_match:
                return jsonify({
                    'success': False,
                    'need_parse': True,
                    'message': '抖音链接需要解析后才能下载。请使用解析工具获取视频直链，或直接提供视频下载地址。',
                    'help': '可以使用手机端抖音的"复制链接"功能，或者第三方解析工具获取视频直链。'
                })
        
        if not video_url and not input_text:
            return jsonify({'success': False, 'message': '请提供视频链接'}), 400
        
        # 使用视频直链
        final_url = video_url if video_url else input_text
        
        # 创建任务
        task_id = str(uuid.uuid4())[:8]
        tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'created_at': time.time()
        }
        
        # 后台处理
        thread = threading.Thread(target=process_task, args=(task_id, {
            'video_url': final_url,
            'is_direct_link': bool(video_url),
            'model': data.get('model', 'tiny')
        }))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'taskId': task_id,
            'message': '任务已创建'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """查询任务状态"""
    if task_id not in tasks:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    
    task = tasks[task_id]
    
    response = {
        'success': True,
        'status': task['status'],
        'progress': task['progress'],
        'message': task.get('message', '')
    }
    
    if task['status'] == 'completed':
        response['data'] = task['result']
    elif task['status'] == 'failed':
        response['message'] = task.get('error', '处理失败')
    
    return jsonify(response)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'douyin-transcript',
        'version': '2.0'
    })

if __name__ == '__main__':
    print("=" * 50)
    print("抖音文案提取服务 v2.0")
    print("支持：视频直链下载 + AI 语音识别")
    print("访问地址: http://localhost:8000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
