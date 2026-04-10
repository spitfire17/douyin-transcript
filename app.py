#!/usr/bin/env python3
"""
抖音文案提取工具 - 完整独立版
支持部署到：Railway、Render、腾讯云、阿里云、本地服务器
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import tempfile
import os
import re
import json
import requests
import time
from pathlib import Path

app = Flask(__name__, static_folder='public')
CORS(app)

class DouyinTranscriptExtractor:
    """抖音视频文案提取器"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.douyin.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
    
    def extract_url(self, text):
        """从分享口令中提取URL"""
        patterns = [
            r'https://v\.douyin\.com/[A-Za-z0-9]+',
            r'https://www\.douyin\.com/video/\d+',
            r'https://www\.iesdouyin\.com/share/video/\d+',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return text.strip()
    
    def get_video_info(self, url):
        """获取视频信息（通过重定向解析）"""
        try:
            # 先获取重定向后的真实URL
            resp = requests.get(url, headers=self.headers, allow_redirects=True, timeout=10)
            final_url = resp.url
            
            # 从URL提取视频ID
            video_id_match = re.search(r'/video/(\d+)', final_url)
            if video_id_match:
                video_id = video_id_match.group(1)
            else:
                video_id = 'unknown'
            
            return {
                'video_id': video_id,
                'url': final_url,
                'title': f'抖音视频_{video_id}',
                'author': '未知作者'
            }
        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")
    
    def download_video(self, url, output_path):
        """下载抖音视频"""
        try:
            # 方法1: 使用 yt-dlp（推荐）
            result = subprocess.run(
                ['yt-dlp', '-f', 'best', '-o', output_path, '--no-playlist', url],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            
            # 方法2: 使用 curl 直接下载
            # 需要先获取视频直链
            result = subprocess.run(
                ['curl', '-L', '-o', output_path,
                 '-H', f'User-Agent: {self.headers["User-Agent"]}',
                 '-H', f'Referer: {self.headers["Referer"]}',
                 url],
                capture_output=True, text=True, timeout=60
            )
            return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
            
        except subprocess.TimeoutExpired:
            raise Exception("下载超时")
        except FileNotFoundError:
            raise Exception("缺少下载工具，请安装 yt-dlp 或 curl")
        except Exception as e:
            raise Exception(f"下载失败: {str(e)}")
    
    def transcribe(self, video_path, model_size='tiny'):
        """使用 faster-whisper 进行语音识别"""
        try:
            from faster_whisper import WhisperModel
            
            # 初始化模型
            model = WhisperModel(model_size, device='cpu', compute_type='int8')
            
            # 转录
            segments, info = model.transcribe(video_path, language='zh')
            
            # 收集结果
            transcript_parts = []
            for segment in segments:
                transcript_parts.append(segment.text)
            
            full_transcript = ''.join(transcript_parts)
            return full_transcript.strip(), info.duration
            
        except ImportError:
            # 回退到 openai-whisper
            try:
                import whisper
                model = whisper.load_model(model_size)
                result = model.transcribe(video_path, language='zh')
                return result['text'].strip(), result.get('duration', 0)
            except ImportError:
                raise Exception("请安装语音识别库: pip install faster-whisper 或 pip install openai-whisper")
        except Exception as e:
            raise Exception(f"语音识别失败: {str(e)}")

# 全局提取器实例
extractor = DouyinTranscriptExtractor()

# 任务存储（生产环境应使用 Redis 或数据库）
tasks = {}

@app.route('/')
def index():
    """主页"""
    return send_from_directory('public', 'index.html')

@app.route('/api/extract', methods=['POST'])
def start_extract():
    """开始提取文案"""
    try:
        data = request.get_json()
        url_or_share = data.get('url_or_share_text', '')
        
        if not url_or_share:
            return jsonify({'success': False, 'message': '请提供视频链接'}), 400
        
        # 提取URL
        url = extractor.extract_url(url_or_share)
        
        # 获取视频信息
        video_info = extractor.get_video_info(url)
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        
        # 下载视频
        download_success = extractor.download_video(url, video_path)
        
        if not download_success:
            return jsonify({
                'success': False, 
                'message': '视频下载失败，可能是私密视频或链接已失效'
            }), 400
        
        # 语音识别
        model_size = data.get('model', 'tiny')  # tiny/fast/small/medium
        transcript, duration = extractor.transcribe(video_path, model_size)
        
        # 清理临时文件
        try:
            os.remove(video_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        return jsonify({
            'success': True,
            'data': {
                'title': video_info['title'],
                'author': video_info['author'],
                'duration': round(duration, 1),
                'url': video_info['url'],
                'transcript': transcript
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'douyin-transcript-extractor',
        'version': '1.0.0'
    })

if __name__ == '__main__':
    # 本地开发模式
    print("=" * 50)
    print("抖音文案提取服务启动中...")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
