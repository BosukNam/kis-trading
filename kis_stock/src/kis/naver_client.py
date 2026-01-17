"""네이버 검색 API 클라이언트 - 뉴스 검색"""

import logging
import re
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

import httpx

from ..config import naver_config

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """뉴스 아이템"""
    title: str
    link: str
    description: str
    pub_date: str
    pub_date_formatted: str


class NaverClient:
    """네이버 검색 API 클라이언트"""

    def __init__(self):
        self.client_id = naver_config.client_id
        self.client_secret = naver_config.client_secret
        self.base_url = naver_config.base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 반환"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _clean_html(self, text: str) -> str:
        """HTML 태그 제거"""
        # <b>, </b> 등 HTML 태그 제거
        clean = re.sub(r'<[^>]+>', '', text)
        # HTML 엔티티 변환
        clean = clean.replace('&quot;', '"')
        clean = clean.replace('&amp;', '&')
        clean = clean.replace('&lt;', '<')
        clean = clean.replace('&gt;', '>')
        clean = clean.replace('&apos;', "'")
        return clean

    def _format_date(self, date_str: str) -> str:
        """날짜 포맷 변환 (RFC 2822 -> YYYY.MM.DD)"""
        try:
            # "Fri, 17 Jan 2026 10:30:00 +0900" 형식
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt.strftime("%Y.%m.%d")
        except Exception:
            return date_str[:10] if len(date_str) >= 10 else date_str

    async def search_news(
        self,
        query: str,
        display: int = 10,
        start: int = 1,
        sort: str = "date"
    ) -> List[NewsItem]:
        """뉴스 검색

        Args:
            query: 검색어 (종목명 + 주식 등)
            display: 결과 개수 (최대 100)
            start: 시작 위치
            sort: 정렬 (sim: 정확도, date: 날짜순)
        """
        if not self.client_id or not self.client_secret:
            logger.warning("Naver API credentials not configured")
            return []

        client = await self._get_client()

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

        params = {
            "query": query,
            "display": min(display, 100),
            "start": start,
            "sort": sort,
        }

        try:
            logger.info(f"Naver news search: query='{query}', display={display}")
            response = await client.get(
                f"{self.base_url}/news.json",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            items = []
            for item in data.get("items", []):
                items.append(
                    NewsItem(
                        title=self._clean_html(item.get("title", "")),
                        link=item.get("originallink") or item.get("link", ""),
                        description=self._clean_html(item.get("description", "")),
                        pub_date=item.get("pubDate", ""),
                        pub_date_formatted=self._format_date(item.get("pubDate", "")),
                    )
                )

            logger.info(f"Naver news search result: {len(items)} items")
            return items

        except Exception as e:
            logger.error(f"Naver news search failed: {e}")
            return []

    async def search_stock_news(
        self,
        stock_name: str,
        count: int = 10
    ) -> List[NewsItem]:
        """주식 종목 뉴스 검색

        Args:
            stock_name: 종목명
            count: 결과 개수
        """
        # 종목명 + "주식" 또는 "주가"로 검색하여 관련성 높은 뉴스 조회
        query = f"{stock_name} 주식"
        return await self.search_news(query, display=count, sort="date")


# 전역 클라이언트 인스턴스 (싱글톤)
_naver_client: Optional[NaverClient] = None


def get_naver_client() -> NaverClient:
    """네이버 클라이언트 싱글톤 반환"""
    global _naver_client
    if _naver_client is None:
        _naver_client = NaverClient()
    return _naver_client
