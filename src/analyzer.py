"""
주식 재무지표 분석 모듈
ROE, PER, PBR, 시가총액 등의 지표를 계산하고 분석합니다.
"""

import logging
from typing import Dict, List
import pandas as pd


class StockAnalyzer:
    """주식 재무지표 분석 클래스"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_roe(self, net_income: float, shareholders_equity: float) -> float:
        """
        ROE (Return on Equity) 계산
        ROE = 순이익 / 자기자본 × 100

        Args:
            net_income: 순이익
            shareholders_equity: 자기자본

        Returns:
            ROE (%)
        """
        if shareholders_equity == 0:
            return 0.0
        return (net_income / shareholders_equity) * 100

    def calculate_per(self, stock_price: float, eps: float) -> float:
        """
        PER (Price to Earnings Ratio) 계산
        PER = 주가 / 주당순이익(EPS)

        Args:
            stock_price: 현재 주가
            eps: 주당순이익

        Returns:
            PER
        """
        if eps == 0:
            return 0.0
        return stock_price / eps

    def calculate_pbr(self, stock_price: float, bps: float) -> float:
        """
        PBR (Price to Book Ratio) 계산
        PBR = 주가 / 주당순자산(BPS)

        Args:
            stock_price: 현재 주가
            bps: 주당순자산

        Returns:
            PBR
        """
        if bps == 0:
            return 0.0
        return stock_price / bps

    def calculate_eps(self, net_income: float, total_shares: float) -> float:
        """
        EPS (Earnings Per Share) 계산
        EPS = 순이익 / 총 발행주식수

        Args:
            net_income: 순이익
            total_shares: 총 발행주식수

        Returns:
            EPS
        """
        if total_shares == 0:
            return 0.0
        return net_income / total_shares

    def calculate_bps(self, shareholders_equity: float, total_shares: float) -> float:
        """
        BPS (Book value Per Share) 계산
        BPS = 자기자본 / 총 발행주식수

        Args:
            shareholders_equity: 자기자본
            total_shares: 총 발행주식수

        Returns:
            BPS
        """
        if total_shares == 0:
            return 0.0
        return shareholders_equity / total_shares

    def calculate_debt_ratio(self, total_debt: float, total_equity: float) -> float:
        """
        부채비율 계산
        부채비율 = 총부채 / 자기자본 × 100

        Args:
            total_debt: 총부채
            total_equity: 자기자본

        Returns:
            부채비율 (%)
        """
        if total_equity == 0:
            return 0.0
        return (total_debt / total_equity) * 100

    def analyze_stock(self, stock_data: Dict) -> Dict:
        """
        개별 주식 분석

        Args:
            stock_data: 주식 데이터

        Returns:
            분석 결과 딕셔너리
        """
        try:
            analysis = {
                'stock_code': stock_data.get('stock_code') or stock_data.get('stock_symbol'),
                'stock_name': stock_data.get('stock_name', ''),
                'current_price': stock_data.get('current_price', 0),
                'market_cap': stock_data.get('market_cap', 0),
                'per': stock_data.get('per', 0),
                'pbr': stock_data.get('pbr', 0),
                'eps': stock_data.get('eps', 0),
                'bps': stock_data.get('bps', 0),
                'roe': stock_data.get('roe', 0),
                'debt_ratio': stock_data.get('debt_ratio', 0),
            }

            # PER이 없는 경우 계산
            if analysis['per'] == 0 and analysis['eps'] != 0:
                analysis['per'] = self.calculate_per(
                    analysis['current_price'],
                    analysis['eps']
                )

            # PBR이 없는 경우 계산
            if analysis['pbr'] == 0 and analysis['bps'] != 0:
                analysis['pbr'] = self.calculate_pbr(
                    analysis['current_price'],
                    analysis['bps']
                )

            # 저평가 점수 계산 (낮을수록 저평가)
            analysis['undervalue_score'] = self.calculate_undervalue_score(analysis)

            self.logger.info(f"Analyzed stock: {analysis['stock_code']} - Score: {analysis['undervalue_score']:.2f}")

            return analysis

        except Exception as e:
            self.logger.error(f"Error analyzing stock: {e}")
            return None

    def calculate_undervalue_score(self, analysis: Dict) -> float:
        """
        저평가 점수 계산
        낮을수록 저평가된 주식

        가중치:
        - PER: 30% (낮을수록 좋음)
        - PBR: 30% (낮을수록 좋음)
        - ROE: 20% (높을수록 좋음)
        - 부채비율: 20% (낮을수록 좋음)

        Args:
            analysis: 분석 데이터

        Returns:
            저평가 점수 (0-100, 낮을수록 저평가)
        """
        score = 0.0

        # PER 점수 (0-15를 기준으로 정규화)
        per = analysis.get('per', 0)
        if per > 0:
            per_score = min(per / 15.0 * 30, 30)
        else:
            per_score = 30  # PER이 음수이거나 0이면 불리하게

        # PBR 점수 (0-1.5를 기준으로 정규화)
        pbr = analysis.get('pbr', 0)
        if pbr > 0:
            pbr_score = min(pbr / 1.5 * 30, 30)
        else:
            pbr_score = 30

        # ROE 점수 (높을수록 좋음, 0-30%를 기준으로 정규화, 역수 사용)
        roe = analysis.get('roe', 0)
        if roe > 0:
            roe_score = 20 - min(roe / 30.0 * 20, 20)
        else:
            roe_score = 20

        # 부채비율 점수 (0-200%를 기준으로 정규화)
        debt_ratio = analysis.get('debt_ratio', 0)
        debt_score = min(debt_ratio / 200.0 * 20, 20)

        score = per_score + pbr_score + roe_score + debt_score

        return score

    def analyze_multiple_stocks(self, stocks_data: List[Dict]) -> pd.DataFrame:
        """
        여러 주식 일괄 분석

        Args:
            stocks_data: 주식 데이터 리스트

        Returns:
            분석 결과 DataFrame
        """
        analyzed_stocks = []

        for stock_data in stocks_data:
            analysis = self.analyze_stock(stock_data)
            if analysis:
                analyzed_stocks.append(analysis)

        df = pd.DataFrame(analyzed_stocks)

        # 저평가 점수로 정렬 (높을수록 먼저)
        if not df.empty and 'undervalue_score' in df.columns:
            df = df.sort_values('undervalue_score', ascending=False)

        return df

    def get_stock_rating(self, analysis: Dict) -> str:
        """
        주식 등급 부여

        Args:
            analysis: 분석 데이터

        Returns:
            등급 (A+, A, B, C, D)
        """
        score = analysis.get('undervalue_score', 100)

        if score < 20:
            return 'A+'
        elif score < 35:
            return 'A'
        elif score < 50:
            return 'B'
        elif score < 70:
            return 'C'
        else:
            return 'D'

    def print_analysis_report(self, df: pd.DataFrame):
        """
        분석 결과 리포트 출력 (저평가 점수 높은 순으로 정렬)

        Args:
            df: 분석 결과 DataFrame
        """
        if df.empty:
            self.logger.warning("No stocks to analyze")
            return

        # 저평가 점수 기준 내림차순 정렬 (높은 점수가 먼저)
        df_sorted = df.sort_values('undervalue_score', ascending=False)

        print("\n" + "="*100)
        print("주식 분석 리포트")
        print("="*100)

        for idx, row in df_sorted.iterrows():
            rating = self.get_stock_rating(row.to_dict())
            # 종목명 한글 표시: "종목명 (종목코드)" 형식
            stock_display = f"{row['stock_name']} ({row['stock_code']})" if row['stock_name'] != row['stock_code'] else row['stock_code']
            print(f"\n종목: {stock_display}")
            print(f"  등급: {rating}")
            print(f"  현재가: {row['current_price']:,.0f}원")
            print(f"  시가총액: {row['market_cap']:,.0f}백만원")
            print(f"  PER: {row['per']:.2f} | PBR: {row['pbr']:.2f} | ROE: {row['roe']:.2f}%")
            print(f"  저평가 점수: {row['undervalue_score']:.2f}")
            print("-" * 100)


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)

    analyzer = StockAnalyzer()

    # 샘플 데이터로 테스트
    sample_stocks = [
        {
            'stock_code': '005930',
            'stock_name': '삼성전자',
            'current_price': 70000,
            'market_cap': 4000000000,
            'per': 12.5,
            'pbr': 1.2,
            'eps': 5600,
            'bps': 58333,
            'roe': 15.5,
            'debt_ratio': 45.0
        },
        {
            'stock_code': '000660',
            'stock_name': 'SK하이닉스',
            'current_price': 120000,
            'market_cap': 900000000,
            'per': 8.5,
            'pbr': 0.9,
            'eps': 14118,
            'bps': 133333,
            'roe': 20.3,
            'debt_ratio': 32.5
        }
    ]

    # 분석 실행
    result_df = analyzer.analyze_multiple_stocks(sample_stocks)
    analyzer.print_analysis_report(result_df)
