from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UKH_",
        env_file=str(ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "UK House Invest"
    database_url: str = f"sqlite:///{DATA_DIR / 'ukhouse.db'}"

    # data_source: onthemarket | rightmove | mock
    data_source: str = "onthemarket"

    scraper_timeout: int = 25
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # OnTheMarket 采集参数
    othem_delay_seconds: float = 0.6
    othem_max_pages: int = 15
    othem_fetch_detail: bool = True
    # 每次同步最多抓取多少条详情（控制首次同步耗时；剩余后续同步补齐）
    othem_detail_per_sync: int = 50
    rightmove_max_pages: int = 15

    # 通知（留空则不发）：通用 webhook 或 Telegram 二选一
    notify_webhook_url: str | None = None
    notify_telegram_token: str | None = None
    notify_telegram_chat_id: str | None = None

    rightmove_headless: bool = True
    rightmove_use_browser: bool = True
    # 浏览器渠道：chrome（用真实 Chrome，反爬表现更好）| 留空用内置 Chromium
    rightmove_channel: str | None = None

    # 消失宽限期：连续缺席多少次同步才判定为消失（防瞬时抓取问题误删）
    miss_threshold: int = 2

    scheduler_timezone: str = "Europe/London"
    # 逗号分隔的本地时间，例如 00:15,08:15,16:15
    sync_times: str = "00:15,08:15,16:15"
    sync_hour: int = 0
    sync_minute: int = 0

    # 邮件报告。密码只能通过环境变量或 GitHub Secrets 注入。
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_to: str = "haha030324@gmail.com"
    email_from: str | None = None


settings = Settings()
