# UK House Invest

英国区域房价监控系统：捕捉新房源 → 每日对比新增/调价/已下架 → 前端按区域组织、浏览与追踪。

## 核心能力

- **捕捉新房源**：每日 0 点自动重抓（OnTheMarket 挂牌数据），对比出 **本次新增 / 本次已下架（含下架时间）/ 本次调价 / 状态变化**
- **诚实语义**：房源从列表消失标注为"已下架"并记录检测时间（OTM 无法区分售出与撤牌，不编造"已售"）
- **首同步友好**：首次同步不报假"新增 N 套"，显示"首次同步，共发现 N 套挂牌"（判定统一：该区域仅有一次成功同步记录）
- **即时信号**：直接采集中介自带的 `Reduced 降价 / Added 上架时长 / New Home` 标记，当天即可用
- **价格 K 线**：房源详情把每日价格历史聚合为开盘/最高/最低/收盘（OHLC）K 线
- **区域工作台**：房源列表为主内容，新增在前、已下架紧随；自适应价格分档、类型分类、降价榜、中位数、详情抽屉（价格历史曲线）
- **全局切换**：顶栏区域切换器 + 跨区域搜索 + 我的收藏（watchlist）
- **数据库可复用**：启动时自动迁移（旧库无损加列），全量 JSON 导出 + 每区域 Excel 导出
- **防误判**：搜索不完整时不判定"已下架"；空页/重复页也会标记为不完整；房源需**连续缺席 N 次同步**（默认 2，`UKH_MISS_THRESHOLD`）才标为下架，网络抖动不会误删数据
- **身份稳健**：门牌号提取不会把邮编数字（如 SE16 的 16）当门牌；OTM 无门牌/邮编时关闭自动重挂合并，避免误并

## 核心设计

- **房子身份**：主键 = 数据源挂牌 ID；物理身份指纹 = `规范化地址 + 卧室数 + 物业类型`（**排除描述**）。下架后重新挂牌是否自动合并由数据源能力决定：指纹可靠的数据源（Rightmove/mock）启用（`relist_merge=True`）；**OnTheMarket 不暴露门牌号/完整邮编，指纹弱，默认关闭**（`onthemarket.py` 中 `relist_merge = False`）。
- **区域 = 配置 + 物化成员关系**：一个房子只存一份，区域持有 `region_properties` 成员表、每日快照与每区域 SyncRun 日志。区域交错时房源自动共享。探索新地方 = 前端加一条区域。
- **增量更新**：价格/状态变化才写事件；描述等字段变化仅刷新。
- **有意义的变化 = 价格变化**；新增、状态变化、已下架也记录为事件。SyncRun 分别统计 `price_changed_count`（调价）与 `status_changed_count`（状态变化），不再混算进"调价"。
- **数据源可插拔**（`backend/app/scraper/base.py` 定义契约）：默认 **OnTheMarket** + Rightmove 适配器（待可访问环境）+ 离线演示 mock 源。换数据源只加一个适配器，业务层零改动。

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite + APScheduler（每日 0 点定时同步）
- 前端：Vue 3 + Vite + Pinia + Leaflet（地图）+ ECharts（趋势图）
- 采集：requests + BeautifulSoup，浏览器模式用 Playwright

## 快速开始

```bash
# 一键启动（构建前端 + 启动服务）→ http://localhost:8000
./start.sh

# 后台运行（关终端不退出）
./start.sh --daemon
./start.sh --stop

# 安装 macOS 开机自启 + 崩溃自动重启 + 每日 0 点自动同步
./scripts/install_service.sh
```

> 注意：`start.sh` 前台运行时若关闭终端，服务与每日 0 点定时都会停止。需要 7×24 自动监控，建议使用 `install_service.sh`（launchd 常驻、崩溃重启）；服务启动后会自动检查并补跑错过的最近一次同步。

手动方式：

```bash
# 后端
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd backend && .venv/bin/uvicorn app.main:app --port 8000

# 前端（另一终端，开发热更新）
cd frontend && npm install && npm run dev   # http://localhost:5173
```

> 提示：修改 `backend/.env`（参考 `.env.example`）切换数据源、定时时间、采集参数与通知。

## 通知（有变化时推送）

配置 `backend/.env` 后，每次同步完成会自动推送摘要（新增/已下架/调价）：

```
UKH_NOTIFY_WEBHOOK_URL=https://...          # 通用 webhook，POST {"text": "..."}
UKH_NOTIFY_TELEGRAM_TOKEN=...                # 或 Telegram bot
UKH_NOTIFY_TELEGRAM_CHAT_ID=...
```

未配置则静默跳过，不影响同步。

## 时区说明

- 数据统一存 UTC；每日定时默认在 `Europe/London` 的 0 点（`UKH_SCHEDULER_TIMEZONE` / `UKH_SYNC_HOUR` 可改）。
- 非英国时区请按需调整 `UKH_SCHEDULER_TIMEZONE` 与 `UKH_SYNC_HOUR`。

## 离线演示（不需要联网）

```bash
cd backend && UKH_DATA_SOURCE=mock .venv/bin/uvicorn app.main:app --port 8000
```

mock 源生成确定性的假房源（价格按日期漂移），地理编码也走离线确定性坐标——**创建区域、同步、浏览全流程不产生任何真实网络请求**。

## 关于 Rightmove

Rightmove 反爬较强（F5 系），本网络实测被软封（房源接口返回空结果）。适配器已实现待用，但当前默认数据源是 **OnTheMarket**。

## 数据源

| 数据源 | 状态 | 说明 |
|---|---|---|
| **OnTheMarket**（默认） | ✅ 可用 | 真实挂牌房源（价格/卧室/类型/描述），邮编+半径搜索，每日增量检测新增/调价/下架 |
| Rightmove | ⚠️ 本网络被软封 | 适配器已就绪，可在能访问的网络使用 |
| mock | ✅ 离线演示 | 确定性假数据，价格按日漂移，可演示变化检测 |

> OnTheMarket 不暴露房源坐标与完整邮编，地图只显示区域中心圈（标注点无坐标时自动跳过）。采集间隔 `UKH_OTHEM_DELAY_SECONDS`、分页上限 `UKH_OTHEM_MAX_PAGES` 可在 `.env` 配置；请遵守其服务条款。

## 项目结构

```
backend/
  app/
    api/            # 薄层路由：区域/房源/变化/统计
    services/       # 业务：同步/区域/变化查询/导出/收藏/地理编码
    scraper/        # 数据源：base(契约)/onthemarket/rightmove/mock
    identity/       # 房子身份指纹
    models/         # SQLAlchemy ORM
    core/           # 配置/数据库/迁移
    scheduler.py    # 每日 0 点定时同步
  tests/            # 单元测试 + API 层测试
frontend/
  src/pages/        # 总览/区域详情+列表/变化记录/区域管理/我的收藏
  src/components/   # PropertyDrawer(浮层) / MapView(Leaflet) / PriceTrend(ECharts) 等
  src/stores/       # Pinia：app(区域/收藏/toast) / regionFilters(筛选持久化)
```

## 测试

```bash
# 后端（单元 + API 层）
cd backend && .venv/bin/python -m pytest tests/ -q

# 前端（store + 组件）
cd frontend && npm run test
```

## GitHub Actions 自动同步

完整部署教程见 [docs/github-actions-tutorial.md](docs/github-actions-tutorial.md)。

`.github/workflows/daily-sync.yml` 每天通过 GitHub Actions 执行三次 OTM 同步，结果写回 `data/ukhouse.db` 并自动提交。报告筛选配置在隐藏目录 `.automation/targets.json`，默认以 Surrey Quays 为首，筛选伦敦中心附近、**£300,000 以下且按性价比排序**（低于所在区域均价越多、带降价/新房标记越靠前）的房源。

首次启用前需要把数据库纳入仓库：

```bash
git add data/ukhouse.db .github/workflows/daily-sync.yml
git commit -m "chore: enable daily property sync"
git push
```

仓库 Settings → Actions → General 的 Workflow permissions 需要允许 `Read and write permissions`。邮件需要在仓库 Secrets 中配置 `UKH_SMTP_HOST`、`UKH_SMTP_USERNAME`、`UKH_SMTP_PASSWORD`，Gmail 建议使用应用专用密码。每次同步会把最新 K 线 SVG 作为附件发送到 `haha030324@gmail.com`；SMTP 无法直接控制 Gmail 的隐藏文件夹，请在 Gmail 中按邮件主题建立过滤器和标签。也可以在 Actions 页面手动运行 `Daily House Sync`。GitHub runner 的出口 IP 可能被 OTM 限流；代码会在结果不完整时跳过下架判断，不会批量误删。
