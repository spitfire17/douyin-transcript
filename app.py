#!/usr/bin/env python3
"""
抖音文案提取 - 完整服务版 v2.1
支持视频直链下载 + AI 语音识别
修复：添加视频转码和更好的错误处理
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

def download_video_direct(video_url, output_path):
    """直接下载视频，使用更好的兼容性处理"""
    cmd = [
        'curl', '-L', '-o', output_path,
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '-H', 'Referer: https://www.douyin.com/',
        '-H', 'Accept: */*',
        '--connect-timeout', '60',
        '--max-time', '600',
        '--retry', '3',
        video_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=700)
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 1000:
                return True, None
            return False, f"文件太小 ({file_size} bytes)"
        return False, "文件未创建"
    except subprocess.TimeoutExpired:
        return False, "下载超时"
    except Exception as e:
        return False, str(e)

def convert_video(input_path, output_path):
    """使用 ffmpeg 转码视频为兼容格式"""
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-ar', '16000',
        '-ac', '1',
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True, None
        return False, result.stderr if result.stderr else "转码失败"
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

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/extract', methods=['POST'])
def start_extract():
    """提取文案API"""
    temp_dir = None
    try:
        data = request.get_json()
        video_url = data.get('video_url', '')
        
        if not video_url:
            return jsonify({'success': False, 'message': '请提供视频链接'}), 400
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        raw_path = os.path.join(temp_dir, 'video_raw.mp4')
        converted_path = os.path.join(temp_dir, 'video.mp4')
        
        print(f"下载视频: {video_url}")
        
        # 下载视频
        success, error = download_video_direct(video_url, raw_path)
        
        if not success:
            return jsonify({'success': False, 'message': f'视频下载失败: {error}'}), 400
        
        file_size = os.path.getsize(raw_path)
        print(f"视频下载完成: {file_size} bytes")
        
        # 转码视频以确保兼容性
        print("转码视频...")
        success, error = convert_video(raw_path, converted_path)
        
        if not success:
            print(f"转码失败: {error}")
            # 尝试直接使用原文件
            converted_path = raw_path
        
        # 语音识别
        print("开始语音识别...")
        transcript, duration = transcribe_video(converted_path)
        
        # 清理临时文件
        try:
            for f in [raw_path, converted_path]:
                if os.path.exists(f):
                    os.remove(f)
            os.rmdir(temp_dir)
        except:
            pass
        
        return jsonify({
            'success': True,
            'data': {
                'title': '视频文案',
                'author': '未知',
                'duration': round(duration, 1),
                'url': video_url,
                'transcript': transcript,
                'file_size_mb': round(file_size / 1024 / 1024, 2)
            }
        })
        
    except Exception as e:
        # 清理临时文件
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
        'version': '2.2',
        'updated': '2024-04-10'
    })

if __name__ == '__main__':
    print("=" * 50)
    print("抖音文案提取服务 v2.1")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
