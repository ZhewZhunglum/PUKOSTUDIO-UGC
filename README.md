# UGC Outreach

UGC Outreach 是一个内部 UGC / influencer outreach 建联工具，目标是先打通可用 MVP，再逐步补齐自动跟进和更完整的智能化闭环。

- `frontend`: Next.js 16 + React 19 + TypeScript
- `backend`: FastAPI + SQLAlchemy + Alembic
- `workers`: Celery + Redis
- `database`: PostgreSQL

当前版本支持达人管理、CSV 导入、邮件模板、单步外联活动、邮箱账号验证、邮件打开追踪、基础数据看板，以及带 AI 降级策略的收件箱工作流。

## Project Layout

```text
.
├── backend
│   ├── app
│   ├── alembic
│   └── pyproject.toml
├── frontend
│   ├── src
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## Quick Start

推荐第一次本地体验先用 Docker Compose 拉起依赖和服务：

```bash
cp .env.example .env
docker compose up --build
```

首次启动后，在另一个终端执行数据库迁移：

```bash
docker compose exec backend alembic upgrade head
```

默认访问地址：

- Frontend: `http://localhost:4317`
- Backend API: `http://localhost:8917`
- API Docs: `http://localhost:8917/docs`
- Health Check: `http://localhost:8917/health`

如果只想启动数据库和 Redis，再本地分别跑前后端：

```bash
docker compose up postgres redis
```

## Environment Variables

复制 `.env.example` 到 `.env` 后，按需修改：

```bash
cp .env.example .env
```

关键变量分组：

- Database: `DATABASE_URL`, `DATABASE_URL_SYNC`
- Redis: `REDIS_URL`
- Auth: `SECRET_KEY`
- Frontend/API: `FRONTEND_URL`, `NEXT_PUBLIC_API_URL`
- AI: `AI_PROVIDER`, `CLAUDE_API_KEY`, `OPENAI_API_KEY`
- SES: `SES_ACCESS_KEY_ID`, `SES_SECRET_ACCESS_KEY`, `SES_REGION`
- SendGrid: `SENDGRID_API_KEY`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`

AI key 不是强依赖。未配置 AI provider 时，收件箱仍可人工处理，页面不会因为缺少 key 而不可用。

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8917
```

常用后端命令：

```bash
cd backend
python3 -m pytest -q
python3 -m compileall app
ruff check .
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Celery Worker

发信、AI 分类、AI 草稿等后台任务依赖 Celery worker。开发时请单独开一个终端：

```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
```

### Celery Beat

周期任务依赖 Celery beat。当前 MVP 的核心单步外联不强依赖复杂调度，但建议开发时保持运行：

```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

常用前端命令：

```bash
cd frontend
npm run lint
npm run build
```

## Product Usage

登录后可以按下面顺序完成第一条完整建联链路：

1. 注册或登录账号。
2. 进入 `设置`，新增邮箱账号，选择 `SES`、`SendGrid` 或 `SMTP`，保存后点击验证。
3. 进入 `邮件模板`，创建首封建联模板。模板正文可使用 `{{name}}`、`{{first_name}}`、`{{email}}`、`{{niche}}` 等变量。
4. 进入 `达人管理`，手动新增达人，或上传 CSV 批量导入达人。
5. 进入 `建联活动`，创建活动，选择首封模板，并把达人加入活动。
6. 在活动详情页启动活动，系统会为入组达人发送首封外联邮件。
7. 进入 `收件箱` 查看入站回复、AI 意图、AI 建议回复，并人工确认发送。
8. 回到 `数据看板` 查看达人数、活动数、发送数、打开率、回复率、退信率等真实统计。

当前 P1 MVP 只支持单封首发外联邮件。多步骤自动 follow-up 是后续 P3 范围，前端和接口不会把当前能力包装成自动序列。

## CSV Import

达人导入当前只支持 CSV，不支持 `.xlsx`。推荐表头：

```csv
name,email,niche,country,platform,username,followers
Jane Creator,jane@example.com,beauty,US,tiktok,janeugc,12000
```

字段说明：

- `name`: 必填，达人名称。
- `email`: 可选，但没有邮箱的达人无法进入真实发信链路。
- `niche`: 可选，达人垂类。
- `country`: 可选，国家或地区。
- `platform`: 可选，例如 `tiktok`、`instagram`、`youtube`。
- `username`: 可选，平台用户名。
- `followers`: 可选，粉丝数。

## Email Account Setup

支持三类发信账号：

- `SES`: 需要 `region`、`access_key_id`、`secret_access_key`。
- `SendGrid`: 需要 `api_key`。
- `SMTP`: 需要 `host`、`port`、`username`、`password`、`use_tls`。

敏感字段保存后不会完整回传给前端。修改账号时请重新填写需要更新的密钥字段。

## Docker Compose

完整本地栈：

```bash
docker compose up --build
```

包含服务：

- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Backend: `http://localhost:8917`
- Frontend: `http://localhost:4317`
- Celery worker
- Celery beat

常用排查命令：

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f celery-worker
docker compose exec backend alembic upgrade head
```

## Health Checks

后端提供：

- `GET /health`

响应会拆分展示：

- `app`: FastAPI 应用状态。
- `db`: 数据库连接状态。
- `redis`: Redis 连接状态。
- `worker`: 后台 worker 心跳状态。

如果 `worker` 异常，前端仍可浏览数据，但发信、AI 草稿、AI 分类等后台任务可能不会执行。

## Troubleshooting

- 前端请求失败：确认 `NEXT_PUBLIC_API_URL` 指向 `http://localhost:8917`，并确认后端已启动。
- 登录后空白或跳回登录：确认后端 token 接口正常，浏览器 local storage 中没有旧环境残留 token。
- 数据库表不存在：执行 `alembic upgrade head`。
- 邮件没有发送：确认邮箱账号已验证、Celery worker 正在运行、达人有邮箱、活动已启动。
- 收件箱没有 AI 草稿：确认已配置 `AI_PROVIDER` 和对应 key；未配置时系统会降级为人工处理。
- CSV 导入失败：确认上传的是 `.csv`，并且至少包含 `name` 列。
- `python` 命令不可用：本项目文档统一使用 `python3`。

## CI

仓库包含最小 CI：

- `frontend`: `npm run lint`, `npm run build`
- `backend`: `python3 -m pytest -q`, `ruff check .`

提交前建议本地至少跑：

```bash
cd frontend && npm run lint && npm run build
cd ../backend && python3 -m pytest -q && ruff check .
```
