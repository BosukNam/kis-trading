"""
저평가 주식 스크리닝 모듈
설정된 기준에 따라 저평가된 주식을 선별합니다.
"""

import yaml
import logging
from typing import List, Dict
import pandas as pd


class StockScreener:
    """저평가 주식 스크리닝 클래스"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.criteria = self.config['screening']
        self.logger = logging.getLogger(__name__)

    def apply_screening_criteria(self, stock: Dict) -> bool:
        """
        개별 주식에 스크리닝 기준 적용

        Args:
            stock: 주식 분석 데이터

        Returns:
            기준 통과 여부
        """
        # PER 체크
        per = stock.get('per', 0)
        if per <= 0 or per < self.criteria['per_min'] or per > self.criteria['per_max']:
            self.logger.debug(f"{stock.get('stock_code')}: PER 기준 미달 (PER: {per})")
            return False

        # ROE 체크
        roe = stock.get('roe', 0)
        if roe < self.criteria['roe_min']:
            self.logger.debug(f"{stock.get('stock_code')}: ROE 기준 미달 (ROE: {roe})")
            return False

        # PBR 체크
        pbr = stock.get('pbr', 0)
        if pbr <= 0 or pbr < self.criteria['pbr_min'] or pbr > self.criteria['pbr_max']:
            self.logger.debug(f"{stock.get('stock_code')}: PBR 기준 미달 (PBR: {pbr})")
            return False

        # 시가총액 체크 (백만원 단위를 억원으로 변환)
        market_cap_billion = stock.get('market_cap', 0) / 100  # 백만원 -> 억원
        if market_cap_billion < self.criteria['market_cap_min'] or \
           market_cap_billion > self.criteria['market_cap_max']:
            self.logger.debug(f"{stock.get('stock_code')}: 시가총액 기준 미달 (시가총액: {market_cap_billion:.0f}억원)")
            return False

        # 부채비율 체크
        debt_ratio = stock.get('debt_ratio', 0)
        if debt_ratio > self.criteria['debt_ratio_max']:
            self.logger.debug(f"{stock.get('stock_code')}: 부채비율 기준 미달 (부채비율: {debt_ratio}%)")
            return False

        self.logger.info(f"{stock.get('stock_code')}: 모든 스크리닝 기준 통과")
        return True

    def screen_stocks(self, analyzed_stocks: pd.DataFrame) -> pd.DataFrame:
        """
        분석된 주식들을 스크리닝

        Args:
            analyzed_stocks: 분석된 주식 DataFrame

        Returns:
            스크리닝 통과 주식 DataFrame
        """
        if analyzed_stocks.empty:
            self.logger.warning("No stocks to screen")
            return pd.DataFrame()

        screened_stocks = []

        for idx, stock in analyzed_stocks.iterrows():
            stock_dict = stock.to_dict()
            if self.apply_screening_criteria(stock_dict):
                screened_stocks.append(stock_dict)

        result_df = pd.DataFrame(screened_stocks)

        # 저평가 점수로 정렬
        if not result_df.empty and 'undervalue_score' in result_df.columns:
            result_df = result_df.sort_values('undervalue_score')

        self.logger.info(f"Screened {len(result_df)} stocks out of {len(analyzed_stocks)}")

        return result_df

    def get_top_picks(self, screened_stocks: pd.DataFrame, top_n: int = None) -> pd.DataFrame:
        """
        스크리닝된 주식 중 상위 N개 선택

        Args:
            screened_stocks: 스크리닝된 주식 DataFrame
            top_n: 선택할 종목 수 (None이면 설정값 사용)

        Returns:
            상위 N개 주식 DataFrame
        """
        if top_n is None:
            top_n = self.config['trading']['max_stocks_to_buy']

        if screened_stocks.empty:
            self.logger.warning("No stocks to pick from")
            return pd.DataFrame()

        top_picks = screened_stocks.head(top_n)

        self.logger.info(f"Selected top {len(top_picks)} stocks for buying")

        return top_picks

    def print_screening_report(self, original_df: pd.DataFrame, screened_df: pd.DataFrame):
        """
        스크리닝 결과 리포트 출력

        Args:
            original_df: 원본 주식 데이터
            screened_df: 스크리닝 통과 주식 데이터
        """
        print("\n" + "="*100)
        print("스크리닝 결과 리포트")
        print("="*100)

        print(f"\n총 분석 종목 수: {len(original_df)}")
        print(f"스크리닝 통과 종목 수: {len(screened_df)}")
        print(f"통과율: {len(screened_df)/len(original_df)*100:.1f}%")

        print("\n현재 스크리닝 기준:")
        print(f"  - PER: {self.criteria['per_min']} ~ {self.criteria['per_max']}")
        print(f"  - ROE: {self.criteria['roe_min']}% 이상")
        print(f"  - PBR: {self.criteria['pbr_min']} ~ {self.criteria['pbr_max']}")
        print(f"  - 시가총액: {self.criteria['market_cap_min']}억 ~ {self.criteria['market_cap_max']}억")
        print(f"  - 부채비율: {self.criteria['debt_ratio_max']}% 이하")

        if screened_df.empty:
            print("\n스크리닝 통과 종목이 없습니다.")
            return

        print("\n스크리닝 통과 종목:")
        print("-" * 100)

        for idx, stock in screened_df.iterrows():
            print(f"\n{idx+1}. {stock['stock_name']} ({stock['stock_code']})")
            print(f"   현재가: {stock['current_price']:,.0f}원")
            print(f"   PER: {stock['per']:.2f} | PBR: {stock['pbr']:.2f} | ROE: {stock['roe']:.2f}%")
            print(f"   시가총액: {stock['market_cap']/100:,.0f}억원 | 부채비율: {stock['debt_ratio']:.2f}%")
            print(f"   저평가 점수: {stock['undervalue_score']:.2f}")

        print("\n" + "="*100)

    def export_to_csv(self, df: pd.DataFrame, filename: str = "screened_stocks.csv"):
        """
        스크리닝 결과를 CSV 파일로 저장

        Args:
            df: 저장할 DataFrame
            filename: 파일명
        """
        try:
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"Screening results saved to {filename}")
            print(f"\n스크리닝 결과가 {filename}에 저장되었습니다.")
        except Exception as e:
            self.logger.error(f"Failed to save CSV: {e}")


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)

    screener = StockScreener()

    # 샘플 데이터
    sample_analyzed_stocks = pd.DataFrame([
        {
            'stock_code': '005930',
            'stock_name': '삼성전자',
            'current_price': 70000,
            'market_cap': 4000000000,  # 4조원 = 40,000억원
            'per': 12.5,
            'pbr': 1.2,
            'roe': 15.5,
            'debt_ratio': 45.0,
            'undervalue_score': 35.2
        },
        {
            'stock_code': '000660',
            'stock_name': 'SK하이닉스',
            'current_price': 120000,
            'market_cap': 900000000,  # 9000억원
            'per': 8.5,
            'pbr': 0.9,
            'roe': 20.3,
            'debt_ratio': 32.5,
            'undervalue_score': 22.8
        },
        {
            'stock_code': '035720',
            'stock_name': '카카오',
            'current_price': 50000,
            'market_cap': 200000000,  # 2000억원
            'per': 25.0,  # 기준 초과
            'pbr': 2.5,   # 기준 초과
            'roe': 8.0,   # 기준 미달
            'debt_ratio': 15.0,
            'undervalue_score': 65.5
        }
    ])

    # 스크리닝 실행
    screened = screener.screen_stocks(sample_analyzed_stocks)
    screener.print_screening_report(sample_analyzed_stocks, screened)

    # 상위 종목 선택
    top_picks = screener.get_top_picks(screened, top_n=2)
    print(f"\n매수 추천 종목 ({len(top_picks)}개):")
    for idx, stock in top_picks.iterrows():
        print(f"  - {stock['stock_name']} ({stock['stock_code']})")
