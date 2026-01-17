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


@dataclass
class DARTConfig:
    """DART OpenAPI 설정"""
    api_key: str
    base_url: str = "https://opendart.fss.or.kr/api"

    @classmethod
    def from_env(cls) -> "DARTConfig":
        return cls(
            api_key=os.getenv("DART_API_KEY", ""),
            base_url=os.getenv("DART_BASE_URL", "https://opendart.fss.or.kr/api"),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


@dataclass
class GitHubOAuthConfig:
    """GitHub OAuth 설정"""
    client_id: str
    client_secret: str
    allowed_users: list[str]
    session_secret: str

    @classmethod
    def from_env(cls) -> "GitHubOAuthConfig":
        allowed = os.getenv("ALLOWED_GITHUB_USERS", "")
        return cls(
            client_id=os.getenv("GITHUB_CLIENT_ID", ""),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
            allowed_users=[u.strip() for u in allowed.split(",") if u.strip()],
            session_secret=os.getenv("SESSION_SECRET", os.getenv("MCP_BEARER_TOKEN", "default-secret")),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)


# 전역 설정 인스턴스
kis_config = KISConfig.from_env()
server_config = ServerConfig.from_env()
dart_config = DARTConfig.from_env()
github_config = GitHubOAuthConfig.from_env()
