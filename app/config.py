from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    host: str = "127.0.0.1"
    port: int = Field(default=8200, ge=1, le=65535)

    dry_run: bool = True
    live_execution_enabled: bool = False

    database_path: str = "./data/bridge.db"

    mt5_terminal_path: str = ""
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""

    magic_number: int = Field(default=881100, ge=0)

    max_risk_percent: float = Field(default=1.0, gt=0, le=100, allow_inf_nan=False)
    max_daily_loss_percent: float = Field(default=3.0, gt=0, le=100, allow_inf_nan=False)
    max_open_positions: int = Field(default=3, ge=1)
    max_trades_per_day: int = Field(default=5, ge=1)
    max_spread_points: int = Field(default=30, ge=1)

    require_stop_loss: bool = True
    allow_market_buy: bool = True
    allow_market_sell: bool = True

    max_signal_age_seconds: int = Field(default=60, ge=1)

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

    @model_validator(mode="after")
    def _validate_live_execution_config(self) -> Settings:
        if self.dry_run or not self.live_execution_enabled:
            return self
        # A password is intentionally not required here: an already
        # authenticated terminal session is a supported way to run live.
        if not self.mt5_server.strip():
            raise ValueError(
                "MT5_SERVER is required when DRY_RUN=false and LIVE_EXECUTION_ENABLED=true "
                "(it is also used to namespace daily risk state per broker/account)."
            )
        if not self.mt5_login.strip():
            raise ValueError("MT5_LOGIN is required when DRY_RUN=false and LIVE_EXECUTION_ENABLED=true.")
        if not self.mt5_login.strip().isdigit():
            raise ValueError("MT5_LOGIN must be numeric.")
        return self

    @property
    def database_dir(self) -> Path:
        return Path(self.database_path).resolve().parent


def get_settings() -> Settings:
    return Settings()
