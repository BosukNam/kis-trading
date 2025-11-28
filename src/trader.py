"""
주식 매매 주문 실행 모듈
KIS API를 통해 실제 매수/매도 주문을 실행합니다.
"""

import requests
import yaml
import logging
import os
import re
from typing import Dict, List
from datetime import datetime


class StockTrader:
    """주식 매매 주문 실행 클래스"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        # logger 먼저 초기화
        self.logger = logging.getLogger(__name__)

        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()
            # 환경변수 치환
            config_content = self._replace_env_variables(config_content)
            self.config = yaml.safe_load(config_content)

        self.app_key = self.config['kis_api']['app_key']
        self.app_secret = self.config['kis_api']['app_secret']
        self.base_url = self.config['kis_api']['base_url']
        self.account_number = self.config['kis_api']['account_number']
        self.hts_id = self.config['kis_api'].get('hts_id', '')

        self.access_token = None

    def _replace_env_variables(self, content: str) -> str:
        """
        문자열에서 ${ENV_VAR} 형식의 환경변수를 실제 값으로 치환

        Args:
            content: 원본 문자열

        Returns:
            환경변수가 치환된 문자열
        """
        pattern = re.compile(r'\$\{([^}]+)\}')

        def replacer(match):
            env_var = match.group(1)
            value = os.getenv(env_var)
            if value is None:
                self.logger.warning(f"Environment variable {env_var} not found")
                return match.group(0)
            return value

        return pattern.sub(replacer, content)

    def get_access_token(self) -> str:
        """
        KIS API 접근 토큰 발급

        Returns:
            접근 토큰
        """
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            self.access_token = response.json()['access_token']
            self.logger.info("Access token obtained successfully")
            return self.access_token
        except Exception as e:
            self.logger.error(f"Failed to get access token: {e}")
            raise

    def place_domestic_buy_order(self, stock_code: str, quantity: int, price: int = 0) -> Dict:
        """
        국내 주식 매수 주문

        Args:
            stock_code: 종목코드
            quantity: 수량
            price: 가격 (0이면 시장가)

        Returns:
            주문 결과 딕셔너리
        """
        if not self.access_token:
            self.get_access_token()

        # 계좌번호 파싱 (앞 8자리-뒤 2자리)
        if '-' in self.account_number:
            account_no, account_prod_cd = self.account_number.split('-')
        else:
            account_no = self.account_number[:8]
            account_prod_cd = self.account_number[8:] if len(self.account_number) > 8 else '01'

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"

        order_type = self.config['trading']['order_type']
        order_div = "01" if order_type == "market" else "00"  # 00: 지정가, 01: 시장가

        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "TTTC0802U"  # 매수 주문
        }

        body = {
            "CANO": account_no,
            "ACNT_PRDT_CD": account_prod_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_div,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if price > 0 else "0"
        }

        try:
            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

            if data['rt_cd'] == '0':
                result = {
                    'success': True,
                    'order_no': data['output'].get('ODNO', ''),
                    'stock_code': stock_code,
                    'quantity': quantity,
                    'price': price,
                    'order_type': order_type,
                    'timestamp': datetime.now().isoformat(),
                    'message': data.get('msg1', 'Order placed successfully')
                }
                self.logger.info(f"Buy order placed: {stock_code} x {quantity} @ {price}")
                return result
            else:
                self.logger.error(f"Buy order failed: {data['msg1']}")
                return {
                    'success': False,
                    'stock_code': stock_code,
                    'message': data['msg1']
                }

        except Exception as e:
            self.logger.error(f"Failed to place buy order for {stock_code}: {e}")
            return {
                'success': False,
                'stock_code': stock_code,
                'message': str(e)
            }

    def place_domestic_sell_order(self, stock_code: str, quantity: int, price: int = 0) -> Dict:
        """
        국내 주식 매도 주문

        Args:
            stock_code: 종목코드
            quantity: 수량
            price: 가격 (0이면 시장가)

        Returns:
            주문 결과 딕셔너리
        """
        if not self.access_token:
            self.get_access_token()

        # 계좌번호 파싱 (앞 8자리-뒤 2자리)
        if '-' in self.account_number:
            account_no, account_prod_cd = self.account_number.split('-')
        else:
            account_no = self.account_number[:8]
            account_prod_cd = self.account_number[8:] if len(self.account_number) > 8 else '01'

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"

        order_type = self.config['trading']['order_type']
        order_div = "01" if order_type == "market" else "00"

        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "TTTC0801U"  # 매도 주문
        }

        body = {
            "CANO": account_no,
            "ACNT_PRDT_CD": account_prod_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_div,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if price > 0 else "0"
        }

        try:
            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

            if data['rt_cd'] == '0':
                result = {
                    'success': True,
                    'order_no': data['output'].get('ODNO', ''),
                    'stock_code': stock_code,
                    'quantity': quantity,
                    'price': price,
                    'order_type': order_type,
                    'timestamp': datetime.now().isoformat(),
                    'message': data.get('msg1', 'Order placed successfully')
                }
                self.logger.info(f"Sell order placed: {stock_code} x {quantity} @ {price}")
                return result
            else:
                self.logger.error(f"Sell order failed: {data['msg1']}")
                return {
                    'success': False,
                    'stock_code': stock_code,
                    'message': data['msg1']
                }

        except Exception as e:
            self.logger.error(f"Failed to place sell order for {stock_code}: {e}")
            return {
                'success': False,
                'stock_code': stock_code,
                'message': str(e)
            }

    def calculate_order_quantity(self, stock_price: float, amount: int = None) -> int:
        """
        매수 수량 계산

        Args:
            stock_price: 주식 가격
            amount: 매수 금액 (None이면 설정값 사용)

        Returns:
            매수 수량
        """
        if amount is None:
            amount = self.config['trading']['amount_per_stock']

        if stock_price <= 0:
            return 0

        quantity = int(amount / stock_price)
        return quantity

    def execute_buy_orders(self, stocks_to_buy: List[Dict], dry_run: bool = True) -> List[Dict]:
        """
        여러 주식에 대해 매수 주문 실행

        Args:
            stocks_to_buy: 매수할 주식 리스트 (stock_code, current_price 포함)
            dry_run: True면 실제 주문 없이 시뮬레이션만

        Returns:
            주문 결과 리스트
        """
        results = []
        max_stocks = self.config['trading']['max_stocks_to_buy']

        # 최대 종목 수만큼만 처리
        stocks_to_process = stocks_to_buy[:max_stocks]

        print("\n" + "="*100)
        print(f"{'[DRY RUN] ' if dry_run else ''}매수 주문 실행")
        print("="*100)

        for stock in stocks_to_process:
            stock_code = stock.get('stock_code')
            stock_name = stock.get('stock_name', '')
            current_price = stock.get('current_price', 0)

            # 매수 수량 계산
            quantity = self.calculate_order_quantity(current_price)

            if quantity <= 0:
                self.logger.warning(f"Skipping {stock_code}: quantity is 0")
                continue

            print(f"\n종목: {stock_name} ({stock_code})")
            print(f"  현재가: {current_price:,.0f}원")
            print(f"  매수수량: {quantity}주")
            print(f"  예상금액: {current_price * quantity:,.0f}원")

            if not dry_run:
                # 실제 주문 실행
                result = self.place_domestic_buy_order(stock_code, quantity, current_price)
                results.append(result)

                if result['success']:
                    print(f"  ✓ 주문 성공 (주문번호: {result['order_no']})")
                else:
                    print(f"  ✗ 주문 실패: {result['message']}")
            else:
                # 시뮬레이션
                print(f"  [DRY RUN] 주문 시뮬레이션 완료")
                results.append({
                    'success': True,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'quantity': quantity,
                    'price': current_price,
                    'order_type': 'simulated',
                    'timestamp': datetime.now().isoformat()
                })

        print("\n" + "="*100)
        print(f"총 {len(results)}건의 주문 {'시뮬레이션' if dry_run else '실행'} 완료")
        print("="*100)

        return results

    def get_account_balance(self) -> Dict:
        """
        계좌 잔고 조회

        Returns:
            계좌 잔고 정보
        """
        if not self.access_token:
            self.get_access_token()

        # 계좌번호 파싱 (앞 8자리-뒤 2자리)
        if '-' in self.account_number:
            account_no, account_prod_cd = self.account_number.split('-')
        else:
            account_no = self.account_number[:8]
            account_prod_cd = self.account_number[8:] if len(self.account_number) > 8 else '01'

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"

        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "TTTC8434R"
        }

        params = {
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
            "CTX_AREA_NK100": ""
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data['rt_cd'] == '0':
                output = data['output2'][0] if data.get('output2') else {}
                return {
                    'success': True,
                    'total_asset': int(output.get('tot_evlu_amt', 0)),
                    'cash': int(output.get('nxdy_excc_amt', 0)),
                    'stock_value': int(output.get('scts_evlu_amt', 0)),
                    'profit_loss': int(output.get('evlu_pfls_smtl_amt', 0)),
                    'profit_rate': float(output.get('evlu_pfls_rt', 0))
                }
            else:
                self.logger.error(f"Failed to get balance: {data['msg1']}")
                return {'success': False, 'message': data['msg1']}

        except Exception as e:
            self.logger.error(f"Failed to get account balance: {e}")
            return {'success': False, 'message': str(e)}


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)

    trader = StockTrader()

    # 계좌 잔고 조회 테스트
    print("\n=== 계좌 잔고 조회 ===")
    balance = trader.get_account_balance()
    if balance['success']:
        print(f"총 자산: {balance['total_asset']:,}원")
        print(f"예수금: {balance['cash']:,}원")
        print(f"주식 평가액: {balance['stock_value']:,}원")
        print(f"평가 손익: {balance['profit_loss']:,}원 ({balance['profit_rate']:.2f}%)")

    # 매수 주문 시뮬레이션
    sample_stocks = [
        {
            'stock_code': '005930',
            'stock_name': '삼성전자',
            'current_price': 70000
        },
        {
            'stock_code': '000660',
            'stock_name': 'SK하이닉스',
            'current_price': 120000
        }
    ]

    print("\n=== 매수 주문 시뮬레이션 ===")
    results = trader.execute_buy_orders(sample_stocks, dry_run=True)
