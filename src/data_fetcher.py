"""
KIS API를 통한 주식 데이터 수집 모듈
국내 및 해외 주식의 현재가, 재무정보 등을 조회합니다.
"""

import requests
import yaml
import logging
import os
import re
from typing import Dict, List, Optional
from datetime import datetime


class KISDataFetcher:
    """한국투자증권 API를 통해 주식 데이터를 가져오는 클래스"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
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
        self.logger = logging.getLogger(__name__)

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

    def get_domestic_stock_price(self, stock_code: str) -> Dict:
        """
        국내 주식 현재가 조회

        Args:
            stock_code: 종목코드 (6자리)

        Returns:
            주식 현재가 정보 딕셔너리
        """
        if not self.access_token:
            self.get_access_token()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100"
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data['rt_cd'] == '0':
                output = data['output']
                return {
                    'stock_code': stock_code,
                    'stock_name': output.get('prdy_vrss', ''),
                    'current_price': int(output.get('stck_prpr', 0)),
                    'market_cap': int(output.get('hts_avls', 0)),  # 시가총액 (백만원)
                    'per': float(output.get('per', 0)),
                    'pbr': float(output.get('pbr', 0)),
                    'eps': float(output.get('eps', 0)),
                    'bps': float(output.get('bps', 0)),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.error(f"Error fetching stock {stock_code}: {data['msg1']}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to fetch domestic stock {stock_code}: {e}")
            return None

    def get_international_stock_price(self, stock_symbol: str) -> Dict:
        """
        해외 주식 현재가 조회

        Args:
            stock_symbol: 종목 심볼 (예: AAPL, MSFT)

        Returns:
            주식 현재가 정보 딕셔너리
        """
        if not self.access_token:
            self.get_access_token()

        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/price"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "HHDFS00000300"
        }
        params = {
            "AUTH": "",
            "EXCD": "NAS",  # NASDAQ (NYSE의 경우 'NYS')
            "SYMB": stock_symbol
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data['rt_cd'] == '0':
                output = data['output']
                return {
                    'stock_symbol': stock_symbol,
                    'stock_name': output.get('name', ''),
                    'current_price': float(output.get('last', 0)),
                    'market_cap': float(output.get('marketcap', 0)),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.error(f"Error fetching stock {stock_symbol}: {data['msg1']}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to fetch international stock {stock_symbol}: {e}")
            return None

    def get_domestic_financial_info(self, stock_code: str) -> Dict:
        """
        국내 주식 재무정보 조회 (ROE, 부채비율 등)

        Args:
            stock_code: 종목코드

        Returns:
            재무정보 딕셔너리
        """
        if not self.access_token:
            self.get_access_token()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010100"
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0"
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data['rt_cd'] == '0':
                # 재무정보는 별도 API 호출이 필요할 수 있음
                # 여기서는 기본 정보만 반환
                return {
                    'stock_code': stock_code,
                    'roe': 0.0,  # ROE는 별도 계산 필요
                    'debt_ratio': 0.0,  # 부채비율은 별도 조회 필요
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.error(f"Error fetching financial info {stock_code}: {data['msg1']}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to fetch financial info {stock_code}: {e}")
            return None

    def get_all_domestic_stocks(self) -> List[Dict]:
        """
        설정된 모든 국내 주식 데이터 조회

        Returns:
            주식 데이터 리스트
        """
        stocks = []
        domestic_stocks = self.config['stocks']['domestic']

        for stock_code in domestic_stocks:
            self.logger.info(f"Fetching domestic stock: {stock_code}")
            stock_data = self.get_domestic_stock_price(stock_code)
            if stock_data:
                # 재무정보 추가
                financial_info = self.get_domestic_financial_info(stock_code)
                if financial_info:
                    stock_data.update(financial_info)
                stocks.append(stock_data)

        return stocks

    def get_all_international_stocks(self) -> List[Dict]:
        """
        설정된 모든 해외 주식 데이터 조회

        Returns:
            주식 데이터 리스트
        """
        stocks = []
        international_stocks = self.config['stocks']['international']

        for stock_symbol in international_stocks:
            self.logger.info(f"Fetching international stock: {stock_symbol}")
            stock_data = self.get_international_stock_price(stock_symbol)
            if stock_data:
                stocks.append(stock_data)

        return stocks


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)

    fetcher = KISDataFetcher()

    # 국내 주식 조회 테스트
    print("\n=== 국내 주식 조회 ===")
    domestic_stocks = fetcher.get_all_domestic_stocks()
    for stock in domestic_stocks:
        print(stock)

    # 해외 주식 조회 테스트
    print("\n=== 해외 주식 조회 ===")
    international_stocks = fetcher.get_all_international_stocks()
    for stock in international_stocks:
        print(stock)
