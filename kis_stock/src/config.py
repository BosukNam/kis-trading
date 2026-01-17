"""환경변수 기반 설정 모듈"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class KISConfig:
    """KIS API 설정"""
    app_key: str
    app_secret: str
    account_number: str
    base_url: str = "https://openapi.koreainvestment.com:9443"

    @classmethod
    def from_env(cls) -> "KISConfig":
        return cls(
            app_key=os.getenv("KIS_APP_KEY", ""),
            app_secret=os.getenv("KIS_APP_SECRET", ""),
            account_number=os.getenv("KIS_ACCOUNT_NUMBER", ""),
            base_url=os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443"),
        )


@dataclass
class ServerConfig:
    """서버 설정"""
    port: int
    bearer_token: str
    log_level: str

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            port=int(os.getenv("PORT", "8000")),
            bearer_token=os.getenv("MCP_BEARER_TOKEN", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# 전역 설정 인스턴스
kis_config = KISConfig.from_env()
server_config = ServerConfig.from_env()
