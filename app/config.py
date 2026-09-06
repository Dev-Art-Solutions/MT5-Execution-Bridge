from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    host: str = "127.0.0.1"
    port: int = 8200

    dry_run: bool = True
    live_execution_enabled: bool = False

    database_path: str = "./data/bridge.db"

    mt5_terminal_path: str = ""
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""

    magic_number: int = 881100

    max_risk_percent: float = 1.0
    max_daily_loss_percent: float = 3.0
    max_open_positions: int = 3
    max_trades_per_day: int = 5
    max_spread_points: int = 30

    require_stop_loss: bool = True
    allow_market_buy: bool = True
    allow_market_sell: bool = True

    max_signal_age_seconds: int = 60

    symbol_map_path: str = "./examples/symbol-map.example.json"

    allow_remote_binding: bool = False

    @property
    def live_execution_allowed(self) -> bool:
        """Both flags must independently agree before a live order can ever be sent."""
        return (not self.dry_run) and self.live_execution_enabled

    @model_validator(mode="after")
    def _enforce_local_binding(self) -> Settings:
        loopback_hosts = {"127.0.0.1", "localhost", "::1"}
        if self.host not in loopback_hosts and not self.allow_remote_binding:
            raise ValueError(
                f"HOST={self.host!r} is not a loopback address. "
                "Refusing to start on a non-local interface unless ALLOW_REMOTE_BINDING=true."
            )
        return self

    @property
    def database_dir(self) -> Path:
        return Path(self.database_path).resolve().parent


def get_settings() -> Settings:
    return Settings()
