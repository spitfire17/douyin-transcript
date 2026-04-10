#!/usr/bin/env python3
"""
抖音文案提取 - 完整服务版 v3.0
支持：抖音分享链接直接解析 + 视频下载 + AI 语音识别
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
    # 匹配 https://v.douyin.com/xxx 格式
    pattern = r'https://v\.douyin\.com/[A-Za-z0-9]+'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    # 匹配 https://www.douyin.com/video/xxx 格式
    pattern2 = r'https://www\.douyin\.com/video/\d+'
    match2 = re.search(pattern2, text)
    if match2:
        return match2.group(0)
    return None

def get_video_url_from_douyin(share_url):
    """使用浏览器自动化获取抖音视频直链"""
    try:
        # 构建 JavaScript 代码来获取视频
        js_code = '''
const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security']
    });
    
    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    
    try {
        await page.goto('SHARE_URL', { waitUntil: 'networkidle2', timeout: 30000 });
        
        // 等待页面加载
        await page.waitForTimeout(3000);
        
        // 获取视频元素
        const videoInfo = await page.evaluate(() => {
            const video = document.querySelector('video');
            if (video && video.src) {
                return {
                    videoUrl: video.src,
                    title: document.title || '抖音视频'
                };
            }
            
            // 尝试从页面源码中找视频链接
            const html = document.documentElement.innerHTML;
            const match = html.match(/(https:\\/\\/[^"]*douyinvod[^"]*\\.mp4[^"]*)"/);
            if (match) {
                return {
                    videoUrl: match[1].replace(/\\/g, '/'),
                    title: document.title || '抖音视频'
                };
            }
            
            return null;
        });
        
        console.log(JSON.stringify(videoInfo || {error: '未找到视频'}));
    } catch (e) {
        console.log(JSON.stringify({error: e.message}));
    } finally {
        await browser.close();
    }
})();
'''
        js_code = js_code.replace('SHARE_URL', share_url)
        
        # 写入临时文件执行
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(js_code)
            js_file = f.name
        
        # 执行 puppeteer 脚本
        result = subprocess.run(
            ['node', js_file],
            capture_output=True,
            text=True,
            timeout=60000
        )
        
        os.remove(js_file)
        
        # 解析结果
        lines = result.stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and line.startswith('{'):
                try:
                    data = json.loads(line)
                    if 'videoUrl' in data:
                        return data['videoUrl'], data.get('title', '抖音视频')
                    elif 'error' in data:
                        return None, data['error']
                except:
                    continue
        
        return None, '未找到视频链接'
        
    except Exception as e:
        return None, str(e)

def download_video_direct(video_url, output_path):
    """直接下载视频"""
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

@app.route('/api/parse', methods=['POST'])
def parse_douyin_link():
    """解析抖音分享链接获取视频直链"""
    try:
        data = request.get_json()
        share_text = data.get('share_text', '')
        
        if not share_text:
            return jsonify({'success': False, 'message': '请输入分享内容'}), 400
        
        # 提取抖音链接
        douyin_url = extract_url_from_share(share_text)
        
        if not douyin_url:
            return jsonify({
                'success': False,
                'message': '未找到有效的抖音链接，请检查分享内容'
            }), 400
        
        # 获取视频直链（使用浏览器自动化）
        video_url, title = get_video_url_from_douyin(douyin_url)
        
        if not video_url:
            return jsonify({
                'success': False,
                'message': f'无法获取视频直链: {title}'
            }), 400
        
        return jsonify({
            'success': True,
            'data': {
                'video_url': video_url,
                'title': title,
                'douyin_url': douyin_url
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/extract', methods=['POST'])
def start_extract():
    """提取文案API"""
    temp_dir = None
    try:
        data = request.get_json()
        video_url = data.get('video_url', '')
        share_text = data.get('share_text', '')
        
        # 如果提供了分享链接，先解析
        if share_text and not video_url:
            douyin_url = extract_url_from_share(share_text)
            if douyin_url:
                video_url, _ = get_video_url_from_douyin(douyin_url)
        
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
        'version': '3.0',
        'updated': '2024-04-10'
    })

if __name__ == '__main__':
    print("=" * 50)
    print("抖音文案提取服务 v3.0")
    print("支持：抖音分享链接直接解析")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
