# NetCatch 自动化测试平台

---

## 📖 项目简介

NetCatch 专为个人开发者设计，帮助快速构建自动化测试体系，降低重复劳动。

- **AI 生成用例**：输入接口描述或需求，DeepSeek 大模型自动生成结构化测试用例（含正常/异常/边界），一键导入。
- **接口测试**：类似 Postman 的 HTTP 请求体验，支持环境变量、多种断言、批量运行。
- **Web 脚本管理**：基于 Playwright 的可视化编排，支持 12+ 种操作（点击、输入、断言标题/文本、截图），失败自动截图回传。
- **数据工厂**：内置 `$random.email`、`$uuid`、`$timestamp` 等动态函数，实时生成唯一测试数据，解决数据依赖。
- **异步批量执行**：基于 Celery + Redis，任务提交后不阻塞前端，支持同步回退。

---

## 🏗️ 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行环境 |
| Flask | 3.0 | Web 框架 |
| SQLAlchemy | 2.0 | ORM |
| Celery | 5.3+ | 异步任务队列 |
| Redis | 5.0+ | 消息代理 / 任务结果存储 |
| Playwright | 1.48+ | Web 自动化引擎 |
| PyMySQL | 1.1+ | MySQL 驱动 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | 3.4 | UI 框架 |
| Element Plus | 2.4 | UI 组件库 |
| Axios | 1.6 | HTTP 客户端 |
| Vue Router | 4.2 | 路由管理 |

### 数据库与中间件

- **MySQL 8.0**：主数据库
- **Redis**：Celery broker 与 backend

---

## 🚀 快速开始

### 前置要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建（生产不需要） |
| MySQL | 8.0 | 数据库 |
| Redis | 5.0+ | 异步任务队列 |

### 一键启动（开发环境）

```bash
# 克隆项目
git clone https://github.com/kaholeeho/NetCatch.git
cd NetCatch

# 创建虚拟环境并安装后端依赖
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 配置数据库（创建 NetCatch 库，修改 .env）
cp .env.example .env
# 编辑 .env 填写 MySQL/Redis/DeepSeek API Key

# 执行数据库迁移
flask db upgrade

# 启动后端（开发模式）
python run.py

访问 http://127.0.0.1:5000 即可使用前端界面。

启动 Celery Worker（可选，用于批量异步执行）
bash
# 开一个终端 , 先启动redis
redis-server
# 另开一个终端
cd NetCatch
celery -A app.tasks.test_runner worker --pool=solo --loglevel=info

```

## 📂 项目结构
text
NetCatch/
├── app/
│   ├── api/               # 接口路由（project, case, suite, web_script, ai_generate...）
│   ├── tasks/             # Celery 异步任务（test_runner）
│   ├── utils/             # 核心引擎（http_client, web_runner, ai_client, data_factory）
│   ├── models.py          # SQLAlchemy 数据模型
│   ├── auth.py            # JWT 认证
│   └── __init__.py        # Flask 应用工厂
├── frontend/              # Vue 3 单页面应用（index.html, 静态资源）
├── migrations/            # Alembic 数据库迁移
├── config.py              # 配置管理（从 .env 读取）
├── run.py                 # 后端启动入口
├── requirements.txt
├── .env.example
└── README.md


## 🔥 核心功能
### 接口测试
功能	描述
HTTP 方法	支持 GET、POST、PUT、DELETE、PATCH 等
环境变量	动态参数替换，{{variable}} 语法
多种断言	状态码、JSONPath、包含文本、正则表达式
用例管理	用例的增删改查、复制、导入/导出
批量运行	将多个用例组成集合，一键执行并生成报告
数据工厂	$random.email、$uuid 等函数，实时生成唯一数据
### Web 自动化脚本管理
功能	描述
脚本编排	可视化步骤编辑，支持 goto、click、fill、assert 等 12 种动作
调试执行	实时运行并展示步骤结果，失败自动截图回传
批量运行	多个脚本组合成集合，异步执行并记录任务
报告落库	执行结果与截图持久化，便于检索与追溯
### AI 生成用例
功能	描述
自然语言描述	输入接口路径、方法、参数及需求，AI 自动生成用例
结构化输出	强制 JSON 格式，包含名称、方法、URL、断言等字段
一键导入	生成后可在前端表格中勾选，直接存入用例库
生成记录	每次生成均保存历史，方便查看与重试


## ⚙️ 环境变量配置 (.env)
ini
# MySQL
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_HOST=127.0.0.1
MYSQL_DB=NetCatch

# Redis (Celery)
REDIS_URL=redis://localhost:6379/0

# Flask
SECRET_KEY=your-secret-key

# DeepSeek API
ANTHROPIC_AUTH_TOKEN=sk-xxxxx
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic


## 🧪 测试报告示例
批量执行后，前端展示：

总用例数、通过数、失败数、通过率

每个用例的状态码、响应时间、断言结果

失败用例的具体错误信息（如“用户名已存在”）


## ❓ 常见问题
启动失败
Q: Redis 连接失败？
A: 确保 Redis 已启动：redis-cli ping 应返回 PONG。

Q: Celery 任务不执行？
A: 检查 Celery Worker 是否运行：celery -A app.tasks.test_runner worker --pool=solo --loglevel=info。

Q: 前端页面空白？
A: 打开浏览器开发者工具 Console，检查是否有 JS 报错。常见原因是后端未启动或 CORS 问题（Flask 已配置 CORS，但需确保前端访问地址正确）。

Q: Web 测试 goto 步骤超时？
A: 可尝试修改 web_runner.py 中 wait_until 默认值为 'domcontentloaded'，或在步骤中增加 timeout 字段（如 60000 毫秒）。

数据库
Q: 如何重置数据库？
A: 删除 migrations/versions/ 下的文件及数据库表，重新执行：

bash
flask db stamp base
flask db migrate -m "reset"
flask db upgrade


## 📝 更新日志
2026-06-02
✅ 完成全部核心功能：接口测试、Web 测试、AI 生成、批量运行、报告展示

✅ 集成数据工厂（$random.email、$uuid 等）

✅ 前端全面改用 Vue 3 + Element Plus，实现类似 Postman 的交互

✅ 支持 Celery 异步任务


## 历史版本
基础脚手架搭建（Flask + SQLAlchemy + MySQL）

JWT 认证与项目管理

接口测试执行引擎封装（requests + 断言）

Web 测试 Playwright 集成与步骤编辑器

AI 生成用例（DeepSeek API 调用与 JSON 解析）


## 🤝 贡献
欢迎提交 Issue 和 Pull Request！


## 📄 许可证
MIT License