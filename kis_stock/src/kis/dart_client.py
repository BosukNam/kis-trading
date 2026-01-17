"""DART OpenAPI 클라이언트"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx

from ..config import dart_config
from .models import FinancialStatement, Disclosure

logger = logging.getLogger(__name__)


class DARTClient:
    """DART OpenAPI 클라이언트"""

    # 주요 기업 종목코드 -> DART 고유번호 매핑 (자주 사용되는 종목)
    CORP_CODE_MAP: Dict[str, str] = {}

    def __init__(self):
        self.api_key = dart_config.api_key
        self.base_url = dart_config.base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._corp_codes: Dict[str, str] = {}  # 종목코드 -> DART 고유번호

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 반환"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _api_call(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """DART API 호출"""
        if not self.api_key:
            logger.warning("DART API key not configured")
            return None

        url = f"{self.base_url}{endpoint}"
        params["crtfc_key"] = self.api_key

        client = await self._get_client()

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "000":
                return data
            else:
                logger.warning(f"DART API error: {data.get('message', 'Unknown')}")
                return None

        except Exception as e:
            logger.error(f"DART API call failed: {e}")
            return None

    async def get_corp_code(self, stock_code: str) -> Optional[str]:
        """종목코드로 DART 고유번호 조회"""
        # 캐시 확인
        if stock_code in self._corp_codes:
            return self._corp_codes[stock_code]

        # corpCode.xml 다운로드는 무거우므로 직접 매핑 사용
        # 실제 구현 시 corpCode.xml을 다운로드하여 매핑 테이블 구축 필요
        # 여기서는 공시 검색 API로 우회

        return None

    async def search_company(self, corp_name: str) -> Optional[str]:
        """회사명으로 DART 고유번호 검색"""
        # 공시검색 API로 회사 정보 조회
        data = await self._api_call(
            "/list.json",
            {
                "corp_name": corp_name,
                "page_count": 1,
            },
        )

        if data and data.get("list"):
            corp_code = data["list"][0].get("corp_code")
            if corp_code:
                return corp_code

        return None

    async def get_financial_statements(
        self,
        corp_code: str,
        year: str,
        report_code: str = "11011",  # 사업보고서
    ) -> Optional[FinancialStatement]:
        """재무제표 조회

        Args:
            corp_code: DART 고유번호
            year: 사업연도 (YYYY)
            report_code: 보고서 코드
                - 11011: 사업보고서
                - 11012: 반기보고서
                - 11013: 1분기보고서
                - 11014: 3분기보고서
        """
        # 단일회사 주요계정 조회
        data = await self._api_call(
            "/fnlttSinglAcnt.json",
            {
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": report_code,
            },
        )

        if not data or not data.get("list"):
            return None

        items = data["list"]

        # 계정과목별 데이터 추출
        def find_amount(account_nm: str, sj_div: str = None) -> Optional[int]:
            for item in items:
                if account_nm in item.get("account_nm", ""):
                    if sj_div and item.get("sj_div") != sj_div:
                        continue
                    amt = item.get("thstrm_amount", "").replace(",", "")
                    if amt and amt != "-":
                        try:
                            return int(amt)
                        except ValueError:
                            pass
            return None

        # 현금흐름표 항목 (sj_div: CF)
        operating_cf = find_amount("영업활동", "CF")
        investing_cf = find_amount("투자활동", "CF")
        financing_cf = find_amount("재무활동", "CF")

        # 손익계산서 항목 (sj_div: IS)
        revenue = find_amount("매출액", "IS") or find_amount("영업수익", "IS")
        operating_profit = find_amount("영업이익", "IS")
        net_income = find_amount("당기순이익", "IS")

        # 재무상태표 항목 (sj_div: BS)
        total_assets = find_amount("자산총계", "BS")
        total_liabilities = find_amount("부채총계", "BS")
        total_equity = find_amount("자본총계", "BS")

        # FCF 계산 (영업CF - 자본적지출)
        # 단순화: 영업CF - |투자CF|의 일부로 근사
        fcf = None
        if operating_cf is not None and investing_cf is not None:
            fcf = operating_cf + investing_cf  # 투자CF는 보통 음수

        report_type_map = {
            "11011": "사업보고서",
            "11012": "반기보고서",
            "11013": "1분기보고서",
            "11014": "3분기보고서",
        }

        # 회사명 조회
        corp_name = items[0].get("corp_name", "") if items else ""

        return FinancialStatement(
            stock_code=items[0].get("stock_code", "") if items else "",
            stock_name=corp_name,
            fiscal_year=year,
            report_type=report_type_map.get(report_code, report_code),
            operating_cashflow=operating_cf,
            investing_cashflow=investing_cf,
            financing_cashflow=financing_cf,
            free_cashflow=fcf,
            revenue=revenue,
            operating_profit=operating_profit,
            net_income=net_income,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        )

    async def get_disclosures(
        self,
        corp_code: str = None,
        corp_name: str = None,
        start_date: str = None,
        end_date: str = None,
        page_count: int = 10,
    ) -> List[Disclosure]:
        """공시 목록 조회

        Args:
            corp_code: DART 고유번호
            corp_name: 회사명 (부분 일치)
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            page_count: 조회 건수
        """
        if not start_date:
            # 기본: 최근 3개월 (90일)
            from datetime import timedelta
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=90)
            start_date = start_dt.strftime("%Y%m%d")
            end_date = end_dt.strftime("%Y%m%d")

        params = {
            "bgn_de": start_date,
            "end_de": end_date,
            "page_count": page_count,
        }

        if corp_code:
            params["corp_code"] = corp_code
        if corp_name:
            params["corp_name"] = corp_name

        data = await self._api_call("/list.json", params)

        if not data or not data.get("list"):
            return []

        disclosures = []
        for item in data["list"]:
            disclosures.append(
                Disclosure(
                    corp_code=item.get("corp_code", ""),
                    corp_name=item.get("corp_name", ""),
                    report_name=item.get("report_nm", ""),
                    rcept_no=item.get("rcept_no", ""),
                    flr_nm=item.get("flr_nm", ""),
                    rcept_dt=item.get("rcept_dt", ""),
                    rm=item.get("rm", ""),
                )
            )

        return disclosures

    async def get_disclosures_by_stock(
        self,
        stock_code: str,
        stock_name: str,
        page_count: int = 10,
    ) -> List[Disclosure]:
        """종목코드/종목명으로 공시 조회"""
        # 종목명으로 검색 (종목코드로 직접 검색 불가)
        return await self.get_disclosures(
            corp_name=stock_name,
            page_count=page_count,
        )


# 전역 클라이언트 인스턴스 (싱글톤)
_dart_client: Optional[DARTClient] = None


def get_dart_client() -> DARTClient:
    """DART 클라이언트 싱글톤 반환"""
    global _dart_client
    if _dart_client is None:
        _dart_client = DARTClient()
    return _dart_client
