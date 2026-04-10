#!/usr/bin/env python3
"""
抖音文案提取 - 完整服务版 v4.0
支持：抖音分享链接直接解析 + 视频下载 + AI 语音识别
使用：api.xingzhige.com API
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import tempfile
import os
import re
import json
import time
import requests

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

def parse_douyin_url(douyin_url):
    """使用 API 解析抖音链接"""
    try:
        api_url = f"https://api.xingzhige.com/API/douyin/?url={douyin_url}"
        resp = requests.get(api_url, timeout=30)
        data = resp.json()
        
        if data.get('code') != 0:
            return None, data.get('msg', '解析失败')
        
        video_data = data.get('data', {})
        item = video_data.get('item', {})
        
        # 获取无水印视频链接
        video_url = item.get('url')
        if not video_url:
            return None, '未找到视频链接'
        
        title = item.get('title', '抖音视频')
        author = video_data.get('author', {}).get('name', '未知')
        
        return {
            'video_url': video_url,
            'title': title,
            'author': author,
            'cover': item.get('cover'),
            'music': item.get('muisic')
        }, None
        
    except Exception as e:
        return None, f'解析出错: {str(e)}'

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
def extract():
    """提取文案 - 支持抖音分享链接"""
    temp_dir = None
    try:
        data = request.get_json()
        input_text = data.get('url', '')
        
        if not input_text:
            return jsonify({'success': False, 'message': '请输入内容'}), 400
        
        # 提取抖音链接
        douyin_url = extract_url_from_share(input_text)
        
        if not douyin_url:
            # 可能是直链，直接使用
            if input_text.startswith('http'):
                video_url = input_text
                title = '视频'
                author = '未知'
            else:
                return jsonify({'success': False, 'message': '未找到有效的抖音链接'}), 400
        else:
            # 解析抖音链接
            result, error = parse_douyin_url(douyin_url)
            if not result:
                return jsonify({'success': False, 'message': error}), 400
            
            video_url = result['video_url']
            title = result['title']
            author = result['author']
        
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
                'title': title,
                'author': author,
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
        'version': '4.0',
        'updated': '2024-04-10'
    })

if __name__ == '__main__':
    print("=" * 50)
    print("抖音文案提取服务 v4.0")
    print("支持：抖音分享链接直接解析")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
