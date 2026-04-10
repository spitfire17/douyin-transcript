# 抖音文案提取工具

一键提取抖音视频完整文案，支持 AI 语音识别精准转录。

## 🎯 功能特点

- ✅ 支持多种链接格式（视频链接、分享口令）
- ✅ AI 语音识别，准确率高
- ✅ 支持长视频（25分钟+）
- ✅ 自动下载视频并转录
- ✅ 提供 Web 界面和 API 接口

## 🚀 快速部署

### 方案一：Railway（推荐，免费试用）

[Railway](https://railway.app) 提供免费试用额度，支持 Docker 部署。

1. **注册 Railway**
   - 访问 https://railway.app
   - 使用 GitHub 账号登录

2. **新建项目**
   ```
   点击 "New Project" → "Deploy from GitHub repo"
   选择你的仓库 → 点击 "Deploy Now"
   ```

3. **等待构建完成**
   - Railway 会自动检测 Dockerfile 并构建
   - 构建完成后会自动分配一个域名

4. **访问你的服务**
   - Railway 会提供类似 `https://xxx.up.railway.app` 的地址
   - 直接打开即可使用

### 方案二：Render（免费层）

[Render](https://render.com) 提供免费的 Web Service。

1. **注册 Render**
   - 访问 https://render.com
   - 使用 GitHub 账号登录

2. **创建 Web Service**
   ```
   New → Web Service
   连接 GitHub 仓库
   选择 "Docker" 作为运行环境
   ```

3. **配置服务**
   - Name: `douyin-transcript`
   - Region: 选择离你最近的
   - Instance Type: Free

4. **部署**
   - 点击 "Create Web Service"
   - 等待构建完成（约 5-10 分钟）

### 方案三：腾讯云/阿里云

适合需要稳定长期运行的用户。

**腾讯云轻量应用服务器**：
- 价格：约 50元/月起
- 配置：2核2G 即可
- 支持 Docker 一键部署

**部署步骤**：
```bash
# 1. 购买服务器后 SSH 登录

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 3. 克隆代码
git clone https://github.com/your-repo/douyin-server.git
cd douyin-server

# 4. 构建并运行
docker build -t douyin-transcript .
docker run -d -p 5000:5000 --name douyin-app douyin-transcript

# 5. 访问服务
# http://你的服务器IP:5000
```

### 方案四：本地运行

适合个人使用或测试。

**系统要求**：
- Python 3.9+
- ffmpeg

**安装步骤**：
```bash
# 1. 安装 ffmpeg
# macOS:
brew install ffmpeg

# Ubuntu/Debian:
sudo apt install ffmpeg

# Windows: 下载 https://ffmpeg.org/download.html

# 2. 克隆代码
git clone https://github.com/your-repo/douyin-server.git
cd douyin-server

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 yt-dlp（视频下载）
pip install yt-dlp

# 5. 运行服务
python app.py

# 6. 访问
# http://localhost:5000
```

## 📱 API 使用

### 提取文案

**请求**：
```http
POST /api/extract
Content-Type: application/json

{
  "url_or_share_text": "https://v.douyin.com/xxx 或分享口令"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "title": "视频标题",
    "author": "作者",
    "duration": 150.5,
    "url": "https://www.douyin.com/video/xxx",
    "transcript": "完整的文案内容..."
  }
}
```

### 健康检查

```http
GET /api/health
```

## 🔧 配置选项

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `PORT` | 服务端口 | 5000 |
| `MODEL_SIZE` | Whisper 模型大小 | tiny |

模型大小选项：
- `tiny`: 最快，准确率较低（适合快速测试）
- `base`: 平衡速度和准确率
- `small`: 较慢，准确率较高
- `medium`: 最慢，准确率最高

## 📂 项目结构

```
douyin-server/
├── app.py              # 主应用
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 配置
├── railway.json        # Railway 配置
└── public/
    └── index.html      # Web 界面
```

## ⚠️ 注意事项

1. **执行时间限制**：免费平台通常有 30 秒 - 5 分钟的执行时间限制，超长视频可能处理失败

2. **视频下载**：部分私密视频或限制视频可能无法下载

3. **版权声明**：本工具仅供学习交流，请勿用于侵犯他人版权

4. **合规使用**：请遵守抖音平台规则，合理使用

## 🛠️ 故障排除

### 问题：视频下载失败
- 检查链接是否有效
- 确认视频不是私密视频
- 尝试更新 yt-dlp：`pip install -U yt-dlp`

### 问题：语音识别效果差
- 尝试使用更大的模型：将 `model_size` 改为 `base` 或 `small`
- 背景音乐或噪音会影响识别准确率

### 问题：处理超时
- 缩短视频长度
- 使用付费服务器（无时间限制）
- 增加平台超时设置

## 📄 License

MIT License - 自由使用，请勿用于商业用途

---

如有问题或建议，欢迎提交 Issue 或 PR！
