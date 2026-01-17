"""DART OpenAPI 클라이언트"""

import io
import logging
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import httpx

from ..config import dart_config
from .models import FinancialStatement, Disclosure

logger = logging.getLogger(__name__)


class DARTClient:
    """DART OpenAPI 클라이언트"""

    # 종목코드 -> DART 고유번호 매핑 캐시 (클래스 레벨)
    _corp_code_cache: Dict[str, str] = {}
    # 회사명 -> DART 고유번호 매핑 캐시 (정확한 매칭용)
    _corp_name_cache: Dict[str, str] = {}
    _corp_code_loaded: bool = False

    def __init__(self):
        self.api_key = dart_config.api_key
        self.base_url = dart_config.base_url
        self._client: Optional[httpx.AsyncClient] = None

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

            status = data.get("status")
            if status == "000":
                return data
            elif status == "013":
                # 조회된 데이터가 없음
                logger.info(f"DART API: No data found - {data.get('message', '')}")
                return {"list": []}  # 빈 리스트 반환
            else:
                logger.warning(f"DART API error [{status}]: {data.get('message', 'Unknown')}")
                return None

        except Exception as e:
            logger.error(f"DART API call failed: {e}")
            return None

    async def _load_corp_codes(self) -> bool:
        """DART에서 기업코드 목록 다운로드 및 캐싱"""
        if DARTClient._corp_code_loaded:
            return True

        if not self.api_key:
            logger.warning("DART API key not configured")
            return False

        url = f"{self.base_url}/corpCode.xml"
        params = {"crtfc_key": self.api_key}

        client = await self._get_client()

        try:
            logger.info("Loading DART corp codes...")
            response = await client.get(url, params=params, timeout=60.0)
            response.raise_for_status()

            # ZIP 파일 압축 해제
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                xml_content = zf.read("CORPCODE.xml")

            # XML 파싱
            root = ET.fromstring(xml_content)
            count = 0
            name_count = 0
            for item in root.findall("list"):
                stock_code = item.findtext("stock_code", "").strip()
                corp_code = item.findtext("corp_code", "").strip()
                corp_name = item.findtext("corp_name", "").strip()

                if stock_code and corp_code:
                    DARTClient._corp_code_cache[stock_code] = corp_code
                    count += 1

                # 회사명 -> corp_code 매핑 (상장사만, 중복 시 첫 번째 유지)
                if corp_name and corp_code and stock_code:
                    if corp_name not in DARTClient._corp_name_cache:
                        DARTClient._corp_name_cache[corp_name] = corp_code
                        name_count += 1

            DARTClient._corp_code_loaded = True
            logger.info(f"Loaded {count} corp codes, {name_count} corp names from DART")
            return True

        except Exception as e:
            logger.error(f"Failed to load corp codes: {e}")
            return False

    async def get_corp_code(self, stock_code: str) -> Optional[str]:
        """종목코드로 DART 고유번호 조회"""
        # 캐시 확인
        if stock_code in DARTClient._corp_code_cache:
            return DARTClient._corp_code_cache[stock_code]

        # 캐시에 없으면 로드 시도
        if not DARTClient._corp_code_loaded:
            await self._load_corp_codes()

        return DARTClient._corp_code_cache.get(stock_code)

    async def get_corp_code_by_name(self, corp_name: str) -> Optional[str]:
        """회사명으로 DART 고유번호 조회 (정확한 매칭)"""
        # 캐시에 없으면 로드 시도
        if not DARTClient._corp_code_loaded:
            await self._load_corp_codes()

        # 정확히 일치하는 경우
        if corp_name in DARTClient._corp_name_cache:
            return DARTClient._corp_name_cache[corp_name]

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
            corp_name: 회사명 (부분 일치, corp_code 없을 때만 사용)
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            page_count: 조회 건수
        """
        end_dt = datetime.now()

        if not start_date:
            # corp_code가 있으면 1년, 없으면 3개월 (DART API 제한)
            if corp_code:
                start_dt = end_dt - timedelta(days=365)
            else:
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
        elif corp_name:
            # corp_code 없이 corp_name으로 검색 시 3개월 제한 적용
            params["corp_name"] = corp_name

        logger.info(f"DART get_disclosures params: {params}")
        data = await self._api_call("/list.json", params)
        logger.info(f"DART get_disclosures result: {len(data.get('list', [])) if data else 0} items")

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
        # 종목코드로 corp_code 조회 시도
        corp_code = await self.get_corp_code(stock_code)

        if corp_code:
            # corp_code가 있으면 1년치 조회 가능
            return await self.get_disclosures(
                corp_code=corp_code,
                page_count=page_count,
            )
        else:
            # corp_code가 없으면 종목명으로 3개월 조회
            logger.warning(f"Corp code not found for {stock_code}, falling back to name search")
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
