# 追番日语

把你在追的动漫变成全方位日语训练的本地学习应用。设计见 `docs/superpowers/specs/`。

## 快速开始

1. `cp .env.example .env` 并填入 fox 网关 key 与 Jimaku token
2. `make setup` 安装后端依赖
3. `make test` 运行测试

**浏览器要求**：语音功能需用 Chrome 或 Edge。

## 启动

1. `cp .env.example .env` 并填入 fox / Jimaku 凭证
2. `make setup && make frontend`
3. `make serve`
4. 用 **Chrome 或 Edge** 打开 `http://localhost:8000`

开发模式（前后端分跑、热更）：
- 终端 A：`make dev`（后端 8000）
- 终端 B：`make frontend-dev`（前端 5173，已配置 `/api` 代理到 8000）
