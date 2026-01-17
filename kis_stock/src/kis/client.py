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
    DailyPrice,
    TechnicalIndicators,
    FinancialRatio,
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

    async def get_daily_prices(
        self, stock_code: str, period: str = "D", count: int = 100
    ) -> List[DailyPrice]:
        """일별/주별/월별 시세 조회

        Args:
            stock_code: 종목코드
            period: D(일), W(주), M(월)
            count: 조회 개수 (최대 100)
        """
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=count * 2)).strftime("%Y%m%d")

        data = await self._api_call(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            "FHKST03010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": period,
                "FID_ORG_ADJ_PRC": "0",  # 수정주가
            },
        )

        if not data:
            return []

        prices = []
        for item in data.get("output2", [])[:count]:
            if not item.get("stck_bsop_date"):
                continue
            prices.append(
                DailyPrice(
                    date=item.get("stck_bsop_date", ""),
                    open_price=self._safe_int(item.get("stck_oprc")),
                    high_price=self._safe_int(item.get("stck_hgpr")),
                    low_price=self._safe_int(item.get("stck_lwpr")),
                    close_price=self._safe_int(item.get("stck_clpr")),
                    volume=self._safe_int(item.get("acml_vol")),
                    change_rate=self._safe_float(item.get("prdy_ctrt")),
                )
            )

        return prices

    def _calculate_rsi(self, prices: List[DailyPrice], period: int = 14) -> Optional[float]:
        """RSI 계산"""
        if len(prices) < period + 1:
            return None

        # 종가 기준 변화량 계산
        changes = []
        for i in range(1, len(prices)):
            changes.append(prices[i - 1].close_price - prices[i].close_price)

        if len(changes) < period:
            return None

        # 최근 period일간의 변화량
        recent_changes = changes[:period]

        gains = [c for c in recent_changes if c > 0]
        losses = [-c for c in recent_changes if c < 0]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def _calculate_volatility(self, prices: List[DailyPrice], period: int = 20) -> Optional[float]:
        """변동성 계산 (일간 수익률의 표준편차 * sqrt(252))"""
        if len(prices) < period + 1:
            return None

        # 일간 수익률 계산
        returns = []
        for i in range(1, min(period + 1, len(prices))):
            if prices[i].close_price > 0:
                daily_return = (prices[i - 1].close_price - prices[i].close_price) / prices[i].close_price
                returns.append(daily_return)

        if len(returns) < period:
            return None

        # 표준편차 계산
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        # 연율화 (252 거래일)
        annualized_vol = std_dev * (252 ** 0.5) * 100
        return round(annualized_vol, 2)

    def _calculate_ma(self, prices: List[DailyPrice], period: int) -> Optional[int]:
        """이동평균 계산"""
        if len(prices) < period:
            return None

        total = sum(p.close_price for p in prices[:period])
        return int(total / period)

    async def get_technical_indicators(self, stock_code: str) -> Optional[TechnicalIndicators]:
        """기술적 지표 조회 (52주 고저, RSI, 변동성, 이동평균)"""
        # 현재가 조회
        price_data = await self.get_domestic_stock_price(stock_code)
        if not price_data:
            return None

        # 일별 시세 조회 (최대 100일)
        daily_prices = await self.get_daily_prices(stock_code, count=100)

        # 52주 고저 계산 (약 250 거래일이지만 100일만 조회하므로 근사치)
        # 더 정확한 52주 고저는 별도 API 필요
        if daily_prices:
            high_52w = max(p.high_price for p in daily_prices)
            low_52w = min(p.low_price for p in daily_prices)
            high_52w_date = next(
                (p.date for p in daily_prices if p.high_price == high_52w), ""
            )
            low_52w_date = next(
                (p.date for p in daily_prices if p.low_price == low_52w), ""
            )
        else:
            high_52w = price_data.current_price
            low_52w = price_data.current_price
            high_52w_date = ""
            low_52w_date = ""

        current = price_data.current_price
        from_high = ((current - high_52w) / high_52w * 100) if high_52w > 0 else 0
        from_low = ((current - low_52w) / low_52w * 100) if low_52w > 0 else 0

        # RSI 계산
        rsi_14 = self._calculate_rsi(daily_prices, 14)

        # 변동성 계산
        volatility_20 = self._calculate_volatility(daily_prices, 20)

        # 이동평균 계산
        ma_5 = self._calculate_ma(daily_prices, 5)
        ma_20 = self._calculate_ma(daily_prices, 20)
        ma_60 = self._calculate_ma(daily_prices, 60)

        return TechnicalIndicators(
            stock_code=stock_code,
            stock_name=price_data.stock_name,
            current_price=current,
            high_52w=high_52w,
            low_52w=low_52w,
            high_52w_date=high_52w_date,
            low_52w_date=low_52w_date,
            from_high_52w=round(from_high, 2),
            from_low_52w=round(from_low, 2),
            rsi_14=rsi_14,
            volatility_20=volatility_20,
            ma_5=ma_5,
            ma_20=ma_20,
            ma_60=ma_60,
        )

    async def get_financial_ratio(self, stock_code: str) -> Optional[FinancialRatio]:
        """재무비율 조회"""
        # 현재가 API에서 기본 정보 가져오기
        price_data = await self.get_domestic_stock_price(stock_code)
        if not price_data:
            return None

        # 재무비율 API 호출 (FHKST66430300 - 국내주식 재무비율)
        data = await self._api_call(
            "GET",
            "/uapi/domestic-stock/v1/finance/financial-ratio",
            "FHKST66430300",
            params={
                "FID_DIV_CLS_CODE": "0",
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": stock_code,
            },
        )

        # 기본값 설정
        fiscal_year = datetime.now().strftime("%Y")
        roe = None
        revenue_growth = None
        op_profit_growth = None
        net_income_growth = None
        debt_ratio = None

        if data and data.get("output"):
            output = data["output"][0] if isinstance(data["output"], list) else data["output"]
            fiscal_year = output.get("stac_yymm", fiscal_year)
            roe = self._safe_float(output.get("roe_val")) or None
            revenue_growth = self._safe_float(output.get("grs")) or None
            op_profit_growth = self._safe_float(output.get("bsop_prfi_inrt")) or None
            net_income_growth = self._safe_float(output.get("ntin_inrt")) or None
            debt_ratio = self._safe_float(output.get("lblt_rate")) or None

        return FinancialRatio(
            stock_code=stock_code,
            stock_name=price_data.stock_name,
            fiscal_year=fiscal_year,
            roe=roe,
            revenue_growth=revenue_growth,
            operating_profit_growth=op_profit_growth,
            net_income_growth=net_income_growth,
            debt_ratio=debt_ratio,
            per=price_data.per,
            pbr=price_data.pbr,
            eps=price_data.eps,
            bps=price_data.bps,
        )

    async def get_overseas_daily_prices(
        self, symbol: str, exchange: str = "NAS", count: int = 100
    ) -> List[DailyPrice]:
        """해외주식 일별 시세 조회

        Args:
            symbol: 종목 심볼 (예: AAPL, TSLA)
            exchange: 거래소 코드 (NAS: 나스닥, NYS: 뉴욕, AMS: 아멕스)
            count: 조회 개수 (최대 100)
        """
        end_date = datetime.now().strftime("%Y%m%d")

        # 해외주식 기간별시세 API (FHKST03030100)
        data = await self._api_call(
            "GET",
            "/uapi/overseas-price/v1/quotations/dailyprice",
            "FHKST03030100",
            params={
                "AUTH": "",
                "EXCD": exchange,
                "SYMB": symbol.upper(),
                "GUBN": "0",  # 0: 일봉
                "BYMD": end_date,
                "MODP": "1",  # 수정주가 반영
            },
        )

        if not data:
            return []

        prices = []
        for item in data.get("output2", [])[:count]:
            if not item.get("xymd"):
                continue
            prices.append(
                DailyPrice(
                    date=item.get("xymd", ""),
                    open_price=int(self._safe_float(item.get("open", 0)) * 100),
                    high_price=int(self._safe_float(item.get("high", 0)) * 100),
                    low_price=int(self._safe_float(item.get("low", 0)) * 100),
                    close_price=int(self._safe_float(item.get("clos", 0)) * 100),
                    volume=self._safe_int(item.get("tvol")),
                    change_rate=self._safe_float(item.get("rate")),
                )
            )

        return prices

    async def get_overseas_technical_indicators(
        self, symbol: str, exchange: str = "NAS"
    ) -> Optional[TechnicalIndicators]:
        """해외주식 기술적 지표 조회 (52주 고저, RSI, 변동성, 이동평균)"""
        # 현재가 조회
        price_data = await self.get_overseas_stock_price(symbol, exchange)
        if not price_data:
            return None

        # 일별 시세 조회 (최대 100일)
        daily_prices = await self.get_overseas_daily_prices(symbol, exchange, count=100)

        if not daily_prices:
            # 일별 시세 조회 실패 시 현재가 기반으로 기본 지표만 반환
            return TechnicalIndicators(
                stock_code=symbol,
                stock_name=price_data.stock_name,
                current_price=price_data.current_price,
                high_52w=price_data.current_price,
                low_52w=price_data.current_price,
                high_52w_date="",
                low_52w_date="",
                from_high_52w=0.0,
                from_low_52w=0.0,
                rsi_14=None,
                volatility_20=None,
                ma_5=None,
                ma_20=None,
                ma_60=None,
            )

        # 52주 고저 계산
        high_52w = max(p.high_price for p in daily_prices)
        low_52w = min(p.low_price for p in daily_prices)
        high_52w_date = next(
            (p.date for p in daily_prices if p.high_price == high_52w), ""
        )
        low_52w_date = next(
            (p.date for p in daily_prices if p.low_price == low_52w), ""
        )

        current = price_data.current_price
        from_high = ((current - high_52w) / high_52w * 100) if high_52w > 0 else 0
        from_low = ((current - low_52w) / low_52w * 100) if low_52w > 0 else 0

        # RSI 계산
        rsi_14 = self._calculate_rsi(daily_prices, 14)

        # 변동성 계산
        volatility_20 = self._calculate_volatility(daily_prices, 20)

        # 이동평균 계산
        ma_5 = self._calculate_ma(daily_prices, 5)
        ma_20 = self._calculate_ma(daily_prices, 20)
        ma_60 = self._calculate_ma(daily_prices, 60)

        return TechnicalIndicators(
            stock_code=symbol,
            stock_name=price_data.stock_name,
            current_price=current,
            high_52w=high_52w,
            low_52w=low_52w,
            high_52w_date=high_52w_date,
            low_52w_date=low_52w_date,
            from_high_52w=round(from_high, 2),
            from_low_52w=round(from_low, 2),
            rsi_14=rsi_14,
            volatility_20=volatility_20,
            ma_5=ma_5,
            ma_20=ma_20,
            ma_60=ma_60,
        )


# 전역 클라이언트 인스턴스 (싱글톤)
_client: Optional[KISClient] = None


def get_kis_client() -> KISClient:
    """KIS 클라이언트 싱글톤 반환"""
    global _client
    if _client is None:
        _client = KISClient()
    return _client
