"""Pydantic 데이터 모델 정의"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class StockPrice(BaseModel):
    """주식 현재가 정보"""
    stock_code: str = Field(description="종목코드")
    stock_name: str = Field(description="종목명")
    current_price: int = Field(description="현재가")
    change_rate: float = Field(default=0.0, description="등락률 (%)")
    change_amount: int = Field(default=0, description="전일대비 금액")
    market_cap: int = Field(default=0, description="시가총액 (백만원)")
    per: Optional[float] = Field(default=None, description="PER")
    pbr: Optional[float] = Field(default=None, description="PBR")
    eps: Optional[float] = Field(default=None, description="EPS")
    bps: Optional[float] = Field(default=None, description="BPS")
    volume: int = Field(default=0, description="거래량")
    timestamp: datetime = Field(default_factory=datetime.now)


class BalanceItem(BaseModel):
    """보유 종목 정보"""
    stock_code: str = Field(description="종목코드")
    stock_name: str = Field(description="종목명")
    quantity: int = Field(description="보유수량")
    avg_price: int = Field(description="평균매입가")
    current_price: int = Field(description="현재가")
    eval_amount: int = Field(description="평가금액")
    profit_loss: int = Field(description="평가손익")
    profit_rate: float = Field(description="수익률 (%)")


class BalanceInfo(BaseModel):
    """계좌 잔고 정보"""
    total_asset: int = Field(description="총 자산")
    cash: int = Field(description="예수금")
    stock_value: int = Field(description="주식 평가액")
    profit_loss: int = Field(description="총 평가손익")
    profit_rate: float = Field(description="총 수익률 (%)")
    holdings: List[BalanceItem] = Field(default_factory=list, description="보유 종목 리스트")
    timestamp: datetime = Field(default_factory=datetime.now)


class OverseasBalanceItem(BaseModel):
    """해외 보유 종목 정보"""
    symbol: str = Field(description="종목 심볼")
    stock_name: str = Field(description="종목명")
    exchange: str = Field(description="거래소 (NAS, NYS 등)")
    quantity: int = Field(description="보유수량")
    avg_price: float = Field(description="평균매입가 (USD)")
    current_price: float = Field(description="현재가 (USD)")
    eval_amount: float = Field(description="평가금액 (USD)")
    profit_loss: float = Field(description="평가손익 (USD)")
    profit_rate: float = Field(description="수익률 (%)")


class OverseasBalanceInfo(BaseModel):
    """해외 계좌 잔고 정보"""
    total_asset_usd: float = Field(description="총 자산 (USD)")
    total_asset_krw: int = Field(description="총 자산 (KRW)")
    profit_loss_usd: float = Field(description="총 평가손익 (USD)")
    profit_rate: float = Field(description="총 수익률 (%)")
    holdings: List[OverseasBalanceItem] = Field(default_factory=list)
    exchange_rate: float = Field(description="환율")
    timestamp: datetime = Field(default_factory=datetime.now)


class InvestorTrend(BaseModel):
    """투자자별 매매동향"""
    stock_code: str = Field(description="종목코드")
    stock_name: str = Field(description="종목명")
    date: str = Field(description="기준일")
    individual: int = Field(description="개인 순매수 (주)")
    foreign: int = Field(description="외국인 순매수 (주)")
    institution: int = Field(description="기관 순매수 (주)")
    individual_amount: int = Field(default=0, description="개인 순매수 금액")
    foreign_amount: int = Field(default=0, description="외국인 순매수 금액")
    institution_amount: int = Field(default=0, description="기관 순매수 금액")
    timestamp: datetime = Field(default_factory=datetime.now)


class DailyPrice(BaseModel):
    """일별 시세"""
    date: str = Field(description="날짜 (YYYYMMDD)")
    open_price: int = Field(description="시가")
    high_price: int = Field(description="고가")
    low_price: int = Field(description="저가")
    close_price: int = Field(description="종가")
    volume: int = Field(description="거래량")
    change_rate: float = Field(default=0.0, description="등락률 (%)")


class TechnicalIndicators(BaseModel):
    """기술적 지표"""
    stock_code: str = Field(description="종목코드")
    stock_name: str = Field(description="종목명")
    current_price: int = Field(description="현재가")
    # 52주 고저
    high_52w: int = Field(description="52주 최고가")
    low_52w: int = Field(description="52주 최저가")
    high_52w_date: str = Field(default="", description="52주 최고가 일자")
    low_52w_date: str = Field(default="", description="52주 최저가 일자")
    from_high_52w: float = Field(description="52주 최고 대비 (%)")
    from_low_52w: float = Field(description="52주 최저 대비 (%)")
    # RSI
    rsi_14: Optional[float] = Field(default=None, description="RSI (14일)")
    # 변동성
    volatility_20: Optional[float] = Field(default=None, description="20일 변동성 (%)")
    # 이동평균
    ma_5: Optional[int] = Field(default=None, description="5일 이동평균")
    ma_20: Optional[int] = Field(default=None, description="20일 이동평균")
    ma_60: Optional[int] = Field(default=None, description="60일 이동평균")
    timestamp: datetime = Field(default_factory=datetime.now)


class FinancialRatio(BaseModel):
    """재무비율"""
    stock_code: str = Field(description="종목코드")
    stock_name: str = Field(description="종목명")
    fiscal_year: str = Field(description="결산년월")
    # 수익성
    roe: Optional[float] = Field(default=None, description="ROE (%)")
    roa: Optional[float] = Field(default=None, description="ROA (%)")
    # 성장성
    revenue_growth: Optional[float] = Field(default=None, description="매출액증가율 (%)")
    operating_profit_growth: Optional[float] = Field(default=None, description="영업이익증가율 (%)")
    net_income_growth: Optional[float] = Field(default=None, description="순이익증가율 (%)")
    # 안정성
    debt_ratio: Optional[float] = Field(default=None, description="부채비율 (%)")
    current_ratio: Optional[float] = Field(default=None, description="유동비율 (%)")
    # 밸류에이션
    per: Optional[float] = Field(default=None, description="PER")
    pbr: Optional[float] = Field(default=None, description="PBR")
    eps: Optional[float] = Field(default=None, description="EPS")
    bps: Optional[float] = Field(default=None, description="BPS")
    dividend_yield: Optional[float] = Field(default=None, description="배당수익률 (%)")
    timestamp: datetime = Field(default_factory=datetime.now)


class CashFlowItem(BaseModel):
    """현금흐름 항목"""
    account_name: str = Field(description="계정명")
    current_amount: Optional[int] = Field(default=None, description="당기 금액")
    previous_amount: Optional[int] = Field(default=None, description="전기 금액")


class FinancialStatement(BaseModel):
    """재무제표 (DART)"""
    stock_code: str = Field(description="종목코드")
    stock_name: str = Field(description="종목명")
    fiscal_year: str = Field(description="사업연도")
    report_type: str = Field(description="보고서 유형 (1분기/반기/3분기/사업)")
    # 현금흐름
    operating_cashflow: Optional[int] = Field(default=None, description="영업활동 현금흐름")
    investing_cashflow: Optional[int] = Field(default=None, description="투자활동 현금흐름")
    financing_cashflow: Optional[int] = Field(default=None, description="재무활동 현금흐름")
    free_cashflow: Optional[int] = Field(default=None, description="잉여현금흐름 (FCF)")
    # 손익
    revenue: Optional[int] = Field(default=None, description="매출액")
    operating_profit: Optional[int] = Field(default=None, description="영업이익")
    net_income: Optional[int] = Field(default=None, description="당기순이익")
    # 재무상태
    total_assets: Optional[int] = Field(default=None, description="총자산")
    total_liabilities: Optional[int] = Field(default=None, description="총부채")
    total_equity: Optional[int] = Field(default=None, description="자본총계")
    timestamp: datetime = Field(default_factory=datetime.now)


class Disclosure(BaseModel):
    """공시 정보 (DART)"""
    corp_code: str = Field(description="기업코드")
    corp_name: str = Field(description="기업명")
    report_name: str = Field(description="보고서명")
    rcept_no: str = Field(description="접수번호")
    flr_nm: str = Field(description="공시 제출인")
    rcept_dt: str = Field(description="접수일자")
    rm: str = Field(default="", description="비고")


class NewsItem(BaseModel):
    """뉴스 항목"""
    title: str = Field(description="뉴스 제목")
    date: str = Field(description="날짜")
    time: str = Field(default="", description="시간")
    source: str = Field(default="", description="출처")
