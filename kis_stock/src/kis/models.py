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
