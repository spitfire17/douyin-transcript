#!/usr/bin/env python3
"""
抖音文案提取 - 完整服务版
集成浏览器自动化获取视频直链
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

# 任务存储
tasks = {}

def run_browser_script(url):
    """运行浏览器脚本获取视频直链"""
    script = f'''
const puppeteer = require('puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security']
    }});
    
    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    
    try {{
        // 访问页面
        await page.goto('{url}', {{ waitUntil: 'networkidle2', timeout: 30000 }});
        
        // 等待视频加载
        await page.waitForSelector('video', {{ timeout: 10000 }});
        
        // 获取视频信息
        const result = await page.evaluate(() => {{
            const video = document.querySelector('video');
            const titleEl = document.querySelector('[data-e2e="video-desc"]') || 
                           document.querySelector('.video-info-detail') ||
                           document.querySelector('h1');
            const authorEl = document.querySelector('[data-e2e="video-author-nickname"]') ||
                            document.querySelector('.author-nickname') ||
                            document.querySelector('.nickname');
            
            return {{
                videoUrl: video ? video.src : null,
                title: titleEl ? titleEl.textContent.trim() : '抖音视频',
                author: authorEl ? authorEl.textContent.trim() : '未知'
            }};
        }});
        
        console.log(JSON.stringify(result));
    }} catch (e) {{
        console.log(JSON.stringify({{ error: e.message }}));
    }} finally {{
        await browser.close();
    }}
}})();
'''
    return script

def extract_video_url_with_curl(url):
    """使用 curl 获取重定向后的视频页面"""
    # 抖音短链接会重定向
    cmd = [
        'curl', '-s', '-L', '-I',
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    # 从响应中提取最终 URL
    lines = result.stdout.split('\n')
    final_url = url
    for line in lines:
        if line.startswith('HTTP/') and '200' in line:
            continue
        if line.startswith('location:') or line.startswith('Location:'):
            final_url = line.split(':', 1)[1].strip()
    
    return final_url

def extract_from_api(url):
    """尝试从抖音 API 提取视频信息"""
    # 从 URL 提取视频 ID
    video_id_match = re.search(r'/video/(\d+)', url)
    if not video_id_match:
        # 尝试从短链接获取
        redirect_url = extract_video_url_with_curl(url)
        video_id_match = re.search(r'/video/(\d+)', redirect_url)
        if video_id_match:
            url = redirect_url
    
    if not video_id_match:
        return None
    
    video_id = video_id_match.group(1)
    
    # 抖音 API (注意：这个 API 可能需要更新)
    api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
    
    cmd = [
        'curl', '-s', '-L',
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        '-H', 'Referer: https://www.douyin.com/',
        api_url
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    try:
        data = json.loads(result.stdout)
        if data.get('status_code') == 0 and data.get('item_list'):
            item = data['item_list'][0]
            video_url = item.get('video', {}).get('play_addr', {}).get('url_list', [None])[0]
            
            if video_url:
                # 替换为无水印版本
                video_url = video_url.replace('playwm', 'play')
                
                return {
                    'video_url': video_url,
                    'title': item.get('desc', '抖音视频'),
                    'author': item.get('author', {}).get('nickname', '未知'),
                    'duration': item.get('video', {}).get('duration', 0) / 1000
                }
    except:
        pass
    
    return None

def download_video_direct(video_url, output_path):
    """直接下载视频"""
    cmd = [
        'curl', '-L', '-o', output_path,
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '-H', 'Referer: https://www.douyin.com/',
        '-H', 'Accept: */*',
        video_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"下载失败: {e}")
        return False

def transcribe_video(video_path, model_size='tiny'):
    """语音识别"""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device='cpu', compute_type='int8')
        segments, info = model.transcribe(video_path, language='zh')
        
        transcript = ''.join([s.text for s in segments])
        return transcript.strip(), info.duration
    except Exception as e:
        raise Exception(f"语音识别失败: {e}")

def process_task(task_id, url_or_share):
    """后台处理任务"""
    try:
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['progress'] = 10
        
        # 提取 URL
        url_match = re.search(r'https://v\.douyin\.com/[A-Za-z0-9]+', url_or_share)
        if not url_match:
            url_match = re.search(r'https://www\.douyin\.com/video/\d+', url_or_share)
        
        if not url_match:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '无效的抖音链接'
            return
        
        url = url_match.group(0)
        tasks[task_id]['progress'] = 20
        
        # 获取视频信息
        video_info = extract_from_api(url)
        
        if not video_info or not video_info.get('video_url'):
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '无法获取视频下载链接，请确认链接有效'
            return
        
        tasks[task_id]['progress'] = 40
        tasks[task_id]['title'] = video_info.get('title', '抖音视频')
        tasks[task_id]['author'] = video_info.get('author', '未知')
        
        # 下载视频
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        
        if not download_video_direct(video_info['video_url'], video_path):
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '视频下载失败'
            return
        
        tasks[task_id]['progress'] = 60
        
        # 语音识别
        transcript, duration = transcribe_video(video_path)
        
        # 清理
        try:
            os.remove(video_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['result'] = {
            'title': video_info.get('title', '抖音视频'),
            'author': video_info.get('author', '未知'),
            'duration': round(duration, 1),
            'url': url,
            'transcript': transcript
        }
        
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/extract', methods=['POST'])
def start_extract():
    """开始提取（异步）"""
    try:
        data = request.get_json()
        url_or_share = data.get('url_or_share_text', '')
        
        if not url_or_share:
            return jsonify({'success': False, 'message': '请提供视频链接'}), 400
        
        # 创建任务
        task_id = str(uuid.uuid4())[:8]
        tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'created_at': time.time()
        }
        
        # 后台处理
        thread = threading.Thread(target=process_task, args=(task_id, url_or_share))
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
        'progress': task['progress']
    }
    
    if task['status'] == 'completed':
        response['data'] = task['result']
    elif task['status'] == 'failed':
        response['message'] = task.get('error', '处理失败')
    
    return jsonify(response)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'douyin-transcript'})

if __name__ == '__main__':
    print("启动抖音文案提取服务...")
    print("访问地址: http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
