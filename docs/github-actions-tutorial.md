# 部署指南：GitHub Actions 每日自动抓房

本仓库已经内置了 `.github/workflows/daily-sync.yml`，用 GitHub Actions 每天自动执行三次房源同步、把最新数据提交回仓库，并把高性价比房源的 K 线图发到指定邮箱。下面是从零到跑通的完整步骤。

## 1. 前置条件

- 一个 GitHub 账号，并已把代码推送到 `XLBen/house`（已完成）。
- 仓库设置里 Actions 被允许运行（默认允许公开/私有仓库，私有仓库可能需要手动开启）。
- 需要一个可以发信的 Gmail 账号（发送方），收件箱是 `haha030324@gmail.com`。

## 2. 开启 Workflow 的写权限（关键）

工作流要把抓取后的 `data/ukhouse.db` 提交回仓库，所以必须允许 Actions 写代码：

1. 打开仓库页面，进入 **Settings → Actions → General**。
2. 找到 **Workflow permissions**。
3. 选择 **Read and write permissions**。
4. 点 **Save**。

> 如果不开启写权限，同步虽然会跑，但最后的 `git push` 步骤会失败。

## 3. 配置 SMTP 邮箱密钥

工作流里的邮件发送依赖仓库 Secrets。把下面这些 Secrets 加到 **Settings → Secrets and variables → Actions**：

| Secret 名 | 说明 | 示例值 |
|---|---|---|
| `UKH_SMTP_HOST` | SMTP 服务器 | `smtp.gmail.com` |
| `UKH_SMTP_PORT` | 端口（默认 465 SSL） | `465` |
| `UKH_SMTP_USERNAME` | 发件 Gmail 账号 | `your@gmail.com` |
| `UKH_SMTP_PASSWORD` | **Gmail 应用专用密码**（不是登录密码） | `abcd efgh ijkl mnop` |
| `UKH_EMAIL_FROM` | 发件人显示（可填发件邮箱） | `your@gmail.com` |

如何生成 Gmail 应用专用密码：
1. 打开 https://myaccount.google.com/security
2. 开启 **两步验证**。
3. 进入「应用专用密码」，生成一个新密码。
4. 把生成的 16 位密码填入 `UKH_SMTP_PASSWORD`。

> 收件人默认是 `haha030324@gmail.com`，已在工作流里写死，不需要配置。

## 4. 手动运行一次

1. 打开仓库 **Actions** 页面。
2. 左侧选择 **Daily House Sync**。
3. 点 **Run workflow** → 选 `main` 分支 → **Run workflow**。

等待几分钟，看到绿色对勾说明成功。此时：
- `data/ukhouse.db` 会被更新并自动提交一个新 commit；
- `haha030324@gmail.com` 会收到一封带 K 线 SVG 附件的邮件。

## 5. 自动调度

工作流已配置每天运行三次：

```yaml
schedule:
  - cron: "15 0,8,16 * * *"
```

这是 UTC 时间，分别对应英国本地时间的 `00:15 / 08:15 / 16:15`（夏令时 +1 小时）。想改时间，编辑 `.github/workflows/daily-sync.yml` 里的 `cron` 表达式即可。

> GitHub 免费账号的定时任务有可能被推迟运行，这是平台行为，不影响最终执行。

## 6. 如何验证结果

### 检查同步是否成功
- Actions 页面查看最近一次运行日志；
- 打开仓库的 **Commits** 页面，应看到 `chore: daily property sync` 的自动提交。

### 检查邮件
- 打开 `haha030324@gmail.com`，搜索主题 `UK高性价比房源 K线`。

### 本地查看同一份数据
代码里默认数据库就是仓库中的 `data/ukhouse.db`，拉取最新代码后本地启动即可看到最新房源：
```bash
git pull
./start.sh
# 打开 http://localhost:8000
```

## 7. 调整筛选范围

筛选配置在隐藏目录 `.automation/targets.json`，可修改：

- `price_max`：只看 **£300,000** 以下（目前设置）；
- `price_min`：价格下限（默认 £200,000，过滤地皮/拍卖噪声）；
- `max_properties`：邮件里最多展示几套（默认 8）；
- `postcodes`：监控的区域邮编列表（Surrey Quays 在最前）。

改完提交并推送，下次 Actions 运行就会按新配置发邮件。

## 8. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 邮件没收到 | 检查 Secrets 是否齐全；Gmail 是否用「应用专用密码」；查看 Actions 日志里的 `邮件 K 线报告` 输出 |
| `git push` 步骤失败 | 没开 **Read and write permissions**，按第 2 步设置 |
| 同步提示「结果不完整」 | OTM 限流或页面结构变化，属正常保护；不会误删房源，稍后会补齐 |
| 想停掉自动同步 | 把工作流文件删除，或在 Actions 页面 Disable workflow |

## 9. 部署时序图

```text
每天 00:15/08:15/16:15 (英国时间)
        │
        ▼
 GitHub Actions runner
        │ 1. checkout 仓库（含 data/ukhouse.db）
        │ 2. 安装 Python 依赖
        │ 3. 读取 Secrets（SMTP 凭据）
        ▼
 抓取 OTM 房源（Surrey Quays 等区域, ≤£300k）
        │
        ▼
 更新 SQLite → 提交 + 推送回仓库
        │
        ▼
 生成高性价比 K 线 SVG
        │
        ▼
 SMTP 发送 → haha030324@gmail.com
```
