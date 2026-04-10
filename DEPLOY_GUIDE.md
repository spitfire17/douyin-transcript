# 🚀 抖音文案提取工具 - 部署指南

## 方案一：Railway 部署（最简单）

### 步骤

1. **注册 Railway**
   - 访问：https://railway.app
   - 点击 "Start a Free Trial"
   - 用 Google 账号登录（无需 GitHub）

2. **创建新项目**
   - 点击 "New Project"
   - 选择 "Empty Project"

3. **上传代码**
   - 在项目中点击 "+ New"
   - 选择 "Volume" 创建存储
   - 点击 "+ New" → "Service" → "Empty Service"

4. **配置服务**
   - 在服务设置中添加以下环境变量：
     ```
     PORT=5000
     ```
   - 在 "Settings" → "Build" 中选择 Dockerfile

5. **上传文件**
   - 将以下文件打包上传：
     - app.py (后端代码)
     - Dockerfile
     - requirements.txt
     - public/ 文件夹

---

## 方案二：Render 部署（免费）

### 步骤

1. **注册 Render**
   - 访问：https://render.com
   - 用 Google 账号登录

2. **创建 Web Service**
   - 点击 "New" → "Web Service"
   - 选择 "Deploy an existing image from a registry"

3. **使用 Docker Hub**
   - 先将 Docker 镜像推送到 Docker Hub
   - 然后在 Render 中选择该镜像

---

## 方案三：本地永久运行（无需云平台）

如果你有一台电脑可以一直开机：

### Windows

```batch
# 1. 安装 Python 3.11
# 2. 下载项目文件
# 3. 双击运行 start.bat
```

### Mac/Linux

```bash
# 1. 安装依赖
pip install flask flask-cors requests faster-whisper yt-dlp gunicorn

# 2. 安装 ffmpeg
brew install ffmpeg  # Mac
apt install ffmpeg   # Linux

# 3. 运行服务
python app_v2.py
```

---

## 📦 部署包位置

所有文件已准备好：

```
/workspace/douyin-server/
├── app_v2.py          # 后端服务
├── app_async.py       # 异步版本
├── Dockerfile         # Docker 配置
├── requirements.txt   # Python 依赖
├── railway.json       # Railway 配置
├── public/
│   └── index.html     # 网页界面
└── README.md          # 详细文档
```

---

## 💡 推荐方案

| 方案 | 难度 | 费用 | 适合人群 |
|-----|------|------|---------|
| **Railway** | ⭐ 简单 | 免费额度 | 想快速上线 |
| **Render** | ⭐⭐ 中等 | 免费 | 想长期免费 |
| **本地运行** | ⭐⭐⭐ 复杂 | 免费 | 有闲置电脑 |

---

## ❓ 需要帮助？

告诉我你选择哪个方案，我可以提供更详细的指导！
