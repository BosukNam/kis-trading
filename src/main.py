"""
KIS 주식 자동매매 시스템 메인 프로그램
국내 및 해외 주식의 저평가 종목을 분석하고 자동으로 매수합니다.
"""

import logging
import argparse
import sys
from datetime import datetime

from data_fetcher import KISDataFetcher
from analyzer import StockAnalyzer
from screener import StockScreener
from trader import StockTrader


class StockTradingSystem:
    """주식 자동매매 시스템 메인 클래스"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path
        self.data_fetcher = KISDataFetcher(config_path)
        self.analyzer = StockAnalyzer()
        self.screener = StockScreener(config_path)
        self.trader = StockTrader(config_path)
        self.logger = logging.getLogger(__name__)

        # 토큰 발급 및 공유
        try:
            self.trader.get_access_token()
            self.data_fetcher.access_token = self.trader.access_token
            self.logger.info("Shared access token between trader and data_fetcher")
        except Exception as e:
            self.logger.warning(f"Failed to initialize access token: {e}")

    def run_analysis_only(self, market: str = "both"):
        """
        주식 분석만 실행 (매수 없음)

        Args:
            market: 시장 선택 ('domestic', 'international', 'both')
        """
        print("\n" + "="*100)
        print(f"주식 분석 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*100)

        all_stocks = []

        # 국내 주식 조회
        if market in ['domestic', 'both']:
            print("\n국내 주식 데이터 수집 중...")
            domestic_stocks = self.data_fetcher.get_all_domestic_stocks()
            all_stocks.extend(domestic_stocks)
            print(f"✓ {len(domestic_stocks)}개 국내 종목 수집 완료")

        # 해외 주식 조회
        if market in ['international', 'both']:
            print("\n해외 주식 데이터 수집 중...")
            international_stocks = self.data_fetcher.get_all_international_stocks()
            all_stocks.extend(international_stocks)
            print(f"✓ {len(international_stocks)}개 해외 종목 수집 완료")

        if not all_stocks:
            print("\n조회된 주식이 없습니다.")
            return None

        # 주식 분석
        print("\n주식 분석 중...")
        analyzed_df = self.analyzer.analyze_multiple_stocks(all_stocks)
        print(f"✓ {len(analyzed_df)}개 종목 분석 완료")

        # 분석 리포트 출력
        self.analyzer.print_analysis_report(analyzed_df)

        return analyzed_df

    def run_screening(self, market: str = "both", save_csv: bool = True):
        """
        주식 분석 및 스크리닝 실행

        Args:
            market: 시장 선택 ('domestic', 'international', 'both')
            save_csv: CSV 파일로 저장 여부

        Returns:
            스크리닝된 주식 DataFrame
        """
        # 분석 실행
        analyzed_df = self.run_analysis_only(market)

        if analyzed_df is None or analyzed_df.empty:
            return None

        # 스크리닝
        print("\n저평가 주식 스크리닝 중...")
        screened_df = self.screener.screen_stocks(analyzed_df)

        # 스크리닝 리포트 출력
        self.screener.print_screening_report(analyzed_df, screened_df)

        # CSV 저장
        if save_csv and not screened_df.empty:
            filename = f"screened_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.screener.export_to_csv(screened_df, filename)

        return screened_df

    def run_auto_trading(self, market: str = "both", dry_run: bool = True):
        """
        자동매매 실행 (분석 -> 스크리닝 -> 매수)

        Args:
            market: 시장 선택 ('domestic', 'international', 'both')
            dry_run: True면 실제 주문 없이 시뮬레이션만
        """
        print("\n" + "="*100)
        print(f"{'[DRY RUN] ' if dry_run else ''}자동매매 시스템 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*100)

        # 계좌 잔고 확인
        print("\n계좌 잔고 확인 중...")
        balance = self.trader.get_account_balance()

        if balance['success']:
            print(f"✓ 총 자산: {balance['total_asset']:,}원")
            print(f"  예수금: {balance['cash']:,}원")
            print(f"  주식 평가액: {balance['stock_value']:,}원")
            print(f"  평가 손익: {balance['profit_loss']:,}원 ({balance['profit_rate']:.2f}%)")
        else:
            print(f"✗ 계좌 잔고 조회 실패: {balance.get('message', 'Unknown error')}")
            if not dry_run:
                print("실제 주문 모드에서는 계좌 조회가 필수입니다. 프로그램을 종료합니다.")
                return

        # 스크리닝 실행
        screened_df = self.run_screening(market, save_csv=True)

        if screened_df is None or screened_df.empty:
            print("\n매수할 종목이 없습니다.")
            return

        # 상위 종목 선택
        top_picks_df = self.screener.get_top_picks(screened_df)

        if top_picks_df.empty:
            print("\n매수 추천 종목이 없습니다.")
            return

        # 매수 주문 실행
        stocks_to_buy = top_picks_df.to_dict('records')
        results = self.trader.execute_buy_orders(stocks_to_buy, dry_run=dry_run)

        # 결과 요약
        successful_orders = [r for r in results if r.get('success', False)]
        failed_orders = [r for r in results if not r.get('success', False)]

        print("\n" + "="*100)
        print("매매 결과 요약")
        print("="*100)
        print(f"총 주문 수: {len(results)}")
        print(f"성공: {len(successful_orders)}건")
        print(f"실패: {len(failed_orders)}건")

        if successful_orders:
            print("\n성공한 주문:")
            for order in successful_orders:
                print(f"  ✓ {order.get('stock_name', order.get('stock_code'))} - "
                      f"{order.get('quantity')}주 @ {order.get('price', 0):,.0f}원")

        if failed_orders:
            print("\n실패한 주문:")
            for order in failed_orders:
                print(f"  ✗ {order.get('stock_code')} - {order.get('message', 'Unknown error')}")

        print("\n" + "="*100)

    def show_account_info(self):
        """계좌 정보 조회 및 출력"""
        print("\n" + "="*100)
        print("계좌 정보 조회")
        print("="*100)

        balance = self.trader.get_account_balance()

        if balance['success']:
            print(f"\n총 자산: {balance['total_asset']:,}원")
            print(f"예수금: {balance['cash']:,}원")
            print(f"주식 평가액: {balance['stock_value']:,}원")
            print(f"평가 손익: {balance['profit_loss']:,}원 ({balance['profit_rate']:.2f}%)")
        else:
            print(f"\n계좌 조회 실패: {balance.get('message', 'Unknown error')}")

        print("\n" + "="*100)


def setup_logging(level: str = "INFO"):
    """
    로깅 설정

    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler('stock_analyzer.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='KIS 주식 자동매매 시스템')

    parser.add_argument(
        'mode',
        choices=['analyze', 'screen', 'trade', 'account'],
        help='실행 모드 (analyze: 분석만, screen: 스크리닝, trade: 자동매매, account: 계좌조회)'
    )

    parser.add_argument(
        '--market',
        choices=['domestic', 'international', 'both'],
        default='both',
        help='대상 시장 (default: both)'
    )

    parser.add_argument(
        '--live',
        action='store_true',
        help='실제 주문 실행 (기본값은 시뮬레이션)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='로그 레벨 (default: INFO)'
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='설정 파일 경로 (default: config/config.yaml)'
    )

    args = parser.parse_args()

    # 로깅 설정
    setup_logging(args.log_level)

    # 시스템 초기화
    system = StockTradingSystem(args.config)

    # 모드별 실행
    try:
        if args.mode == 'analyze':
            system.run_analysis_only(args.market)

        elif args.mode == 'screen':
            system.run_screening(args.market, save_csv=True)

        elif args.mode == 'trade':
            dry_run = not args.live
            if args.live:
                confirm = input("\n실제 주문을 실행합니다. 계속하시겠습니까? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("주문이 취소되었습니다.")
                    return

            system.run_auto_trading(args.market, dry_run=dry_run)

        elif args.mode == 'account':
            system.show_account_info()

    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logging.error(f"오류 발생: {e}", exc_info=True)
        print(f"\n오류가 발생했습니다: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
