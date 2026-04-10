#!/usr/bin/env python3
"""
抖音文案提取 - 完整服务版 v3.3
支持：抖音分享链接解析 + 视频下载 + AI 语音识别
使用：snapany.com 解析服务
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

app = Flask(__name__, static_folder='public')
CORS(app)

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

def download_video_direct(video_url, output_path):
    """直接下载视频"""
    cmd = [
        'curl', '-L', '-o', output_path,
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        '--connect-timeout', '60',
        '--max-time', '600',
        video_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=700)
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 1000:
                return True, None
            return False, f"文件太小"
        return False, "下载失败"
    except Exception as e:
        return False, str(e)

def transcribe_video(video_path, model_size='tiny'):
    """使用 faster-whisper 进行语音识别"""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device='cpu', compute_type='int8')
        segments, info = model.transcribe(video_path, language='zh')
        
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text)
        
        full_transcript = ''.join(transcript_parts)
        return full_transcript.strip(), info.duration
    except Exception as e:
        raise Exception(f"语音识别失败: {e}")

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/extract', methods=['POST'])
def start_extract():
    """提取文案 - 需要前端提供视频直链"""
    temp_dir = None
    try:
        data = request.get_json()
        video_url = data.get('video_url', '')
        
        if not video_url:
            return jsonify({
                'success': False, 
                'message': '请提供视频直链。使用说明：\n1. 访问 https://snapany.com\n2. 粘贴抖音链接获取直链\n3. 复制直链到此处提取文案'
            }), 400
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        
        # 下载视频
        success, error = download_video_direct(video_url, video_path)
        
        if not success:
            return jsonify({'success': False, 'message': f'视频下载失败: {error}'}), 400
        
        file_size = os.path.getsize(video_path)
        
        # 语音识别
        transcript, duration = transcribe_video(video_path)
        
        # 清理
        try:
            os.remove(video_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        return jsonify({
            'success': True,
            'data': {
                'duration': round(duration, 1),
                'transcript': transcript,
                'file_size_mb': round(file_size / 1024 / 1024, 2)
            }
        })
        
    except Exception as e:
        try:
            if temp_dir and os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
        except:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'douyin-transcript',
        'version': '3.3',
        'updated': '2024-04-10'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
