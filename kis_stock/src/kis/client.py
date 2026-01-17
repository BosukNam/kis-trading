"""KIS API 클라이언트 - 비동기 버전"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import httpx

from ..config import kis_config
from .models import (
    StockPrice,
    BalanceInfo,
    BalanceItem,
    OverseasBalanceInfo,
    OverseasBalanceItem,
    InvestorTrend,
)

logger = logging.getLogger(__name__)


class KISClient:
    """한국투자증권 API 비동기 클라이언트"""

    def __init__(self):
        self.app_key = kis_config.app_key
        self.app_secret = kis_config.app_secret
        self.account_number = kis_config.account_number
        self.base_url = kis_config.base_url

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 반환 (재사용)"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_access_token(self) -> str:
        """KIS API 접근 토큰 발급 (캐싱 포함)"""
        # 토큰이 유효하면 재사용
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        client = await self._get_client()
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()

        data = response.json()
        self._access_token = data["access_token"]
        # 토큰 유효기간: 24시간
        self._token_expires_at = datetime.now() + timedelta(hours=23)
        logger.info("KIS access token obtained successfully")
        return self._access_token

    def _parse_account_number(self) -> tuple[str, str]:
        """계좌번호 파싱 (앞 8자리, 뒤 2자리)"""
        if "-" in self.account_number:
            account_no, account_prod_cd = self.account_number.split("-")
        else:
            account_no = self.account_number[:8]
            account_prod_cd = (
                self.account_number[8:] if len(self.account_number) > 8 else "01"
            )
        return account_no, account_prod_cd

    async def _api_call(
        self,
        method: str,
        endpoint: str,
        tr_id: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """API 호출 (재시도 로직 포함)"""
        token = await self.get_access_token()

        url = f"{self.base_url}{endpoint}"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

        client = await self._get_client()

        for attempt in range(max_retries):
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                else:
                    response = await client.post(url, headers=headers, json=body)

                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") == "0":
                    return data
                else:
                    logger.warning(
                        f"API error: {data.get('msg1', 'Unknown')} (attempt {attempt + 1}/{max_retries})"
                    )

            except Exception as e:
                logger.warning(f"API call failed: {e} (attempt {attempt + 1}/{max_retries})")

            if attempt < max_retries - 1:
                await asyncio.sleep(0.2)

        return None

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """안전한 float 변환"""
        if value is None or value == "" or value == "None":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """안전한 int 변환"""
        if value is None or value == "" or value == "None":
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    async def get_domestic_stock_price(self, stock_code: str) -> Optional[StockPrice]:
        """국내 주식 현재가 조회"""
        data = await self._api_call(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code},
        )

        if not data:
            return None

        output = data["output"]
        stock_name = (
            output.get("hts_kor_isnm")
            or output.get("prdt_name")
            or output.get("prdt_abrv_name")
            or stock_code
        )
        if stock_name == "None":
            stock_name = stock_code

        return StockPrice(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=self._safe_int(output.get("stck_prpr")),
            change_rate=self._safe_float(output.get("prdy_ctrt")),
            change_amount=self._safe_int(output.get("prdy_vrss")),
            market_cap=self._safe_int(output.get("hts_avls")),
            per=self._safe_float(output.get("per")) or None,
            pbr=self._safe_float(output.get("pbr")) or None,
            eps=self._safe_float(output.get("eps")) or None,
            bps=self._safe_float(output.get("bps")) or None,
            volume=self._safe_int(output.get("acml_vol")),
        )

    async def get_overseas_stock_price(
        self, symbol: str, exchange: str = "NAS"
    ) -> Optional[StockPrice]:
        """해외 주식 현재가 조회"""
        data = await self._api_call(
            "GET",
            "/uapi/overseas-price/v1/quotations/price",
            "HHDFS00000300",
            params={"AUTH": "", "EXCD": exchange, "SYMB": symbol},
        )

        if not data:
            return None

        output = data["output"]
        return StockPrice(
            stock_code=symbol,
            stock_name=output.get("name", symbol),
            current_price=int(self._safe_float(output.get("last", 0)) * 100),  # 센트 단위
            change_rate=self._safe_float(output.get("rate")),
            change_amount=int(self._safe_float(output.get("diff", 0)) * 100),
            market_cap=0,
            volume=self._safe_int(output.get("tvol")),
        )

    async def get_domestic_balance(self) -> Optional[BalanceInfo]:
        """국내 주식 잔고 조회"""
        account_no, account_prod_cd = self._parse_account_number()

        data = await self._api_call(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            "TTTC8434R",
            params={
                "CANO": account_no,
                "ACNT_PRDT_CD": account_prod_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "N",
                "INQR_DVSN": "01",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )

        if not data:
            return None

        # 보유 종목 파싱
        holdings = []
        for item in data.get("output1", []):
            if self._safe_int(item.get("hldg_qty")) > 0:
                holdings.append(
                    BalanceItem(
                        stock_code=item.get("pdno", ""),
                        stock_name=item.get("prdt_name", ""),
                        quantity=self._safe_int(item.get("hldg_qty")),
                        avg_price=self._safe_int(item.get("pchs_avg_pric")),
                        current_price=self._safe_int(item.get("prpr")),
                        eval_amount=self._safe_int(item.get("evlu_amt")),
                        profit_loss=self._safe_int(item.get("evlu_pfls_amt")),
                        profit_rate=self._safe_float(item.get("evlu_pfls_rt")),
                    )
                )

        # 총계 정보
        output2 = data.get("output2", [{}])[0] if data.get("output2") else {}
        return BalanceInfo(
            total_asset=self._safe_int(output2.get("tot_evlu_amt")),
            cash=self._safe_int(output2.get("nxdy_excc_amt")),
            stock_value=self._safe_int(output2.get("scts_evlu_amt")),
            profit_loss=self._safe_int(output2.get("evlu_pfls_smtl_amt")),
            profit_rate=self._safe_float(output2.get("evlu_pfls_rt")),
            holdings=holdings,
        )

    async def get_overseas_balance(self) -> Optional[OverseasBalanceInfo]:
        """해외 주식 잔고 조회"""
        account_no, account_prod_cd = self._parse_account_number()

        data = await self._api_call(
            "GET",
            "/uapi/overseas-stock/v1/trading/inquire-balance",
            "TTTS3012R",
            params={
                "CANO": account_no,
                "ACNT_PRDT_CD": account_prod_cd,
                "OVRS_EXCG_CD": "NASD",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            },
        )

        if not data:
            return None

        # 보유 종목 파싱
        holdings = []
        for item in data.get("output1", []):
            qty = self._safe_int(item.get("ovrs_cblc_qty"))
            if qty > 0:
                holdings.append(
                    OverseasBalanceItem(
                        symbol=item.get("ovrs_pdno", ""),
                        stock_name=item.get("ovrs_item_name", ""),
                        exchange=item.get("ovrs_excg_cd", ""),
                        quantity=qty,
                        avg_price=self._safe_float(item.get("pchs_avg_pric")),
                        current_price=self._safe_float(item.get("now_pric2")),
                        eval_amount=self._safe_float(item.get("ovrs_stck_evlu_amt")),
                        profit_loss=self._safe_float(item.get("frcr_evlu_pfls_amt")),
                        profit_rate=self._safe_float(item.get("evlu_pfls_rt")),
                    )
                )

        output2 = data.get("output2", {}) or {}
        return OverseasBalanceInfo(
            total_asset_usd=self._safe_float(output2.get("tot_evlu_pfls_amt")),
            total_asset_krw=self._safe_int(output2.get("tot_evlu_pfls_amt_krw")),
            profit_loss_usd=self._safe_float(output2.get("ovrs_rlzt_pfls_amt")),
            profit_rate=self._safe_float(output2.get("tot_evlu_pfls_rt")),
            holdings=holdings,
            exchange_rate=self._safe_float(output2.get("exrt", 1300)),
        )

    async def get_investor_trend(self, stock_code: str) -> Optional[InvestorTrend]:
        """투자자별 매매동향 조회"""
        data = await self._api_call(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-investor",
            "FHKST01010900",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code},
        )

        if not data or not data.get("output"):
            return None

        # 최근 데이터 (첫 번째 항목)
        output = data["output"][0] if data["output"] else {}

        # 종목명 조회를 위해 현재가 API 호출
        price_data = await self.get_domestic_stock_price(stock_code)
        stock_name = price_data.stock_name if price_data else stock_code

        return InvestorTrend(
            stock_code=stock_code,
            stock_name=stock_name,
            date=output.get("stck_bsop_date", datetime.now().strftime("%Y%m%d")),
            individual=self._safe_int(output.get("prsn_ntby_qty")),
            foreign=self._safe_int(output.get("frgn_ntby_qty")),
            institution=self._safe_int(output.get("orgn_ntby_qty")),
            individual_amount=self._safe_int(output.get("prsn_ntby_tr_pbmn")),
            foreign_amount=self._safe_int(output.get("frgn_ntby_tr_pbmn")),
            institution_amount=self._safe_int(output.get("orgn_ntby_tr_pbmn")),
        )


# 전역 클라이언트 인스턴스 (싱글톤)
_client: Optional[KISClient] = None


def get_kis_client() -> KISClient:
    """KIS 클라이언트 싱글톤 반환"""
    global _client
    if _client is None:
        _client = KISClient()
    return _client
