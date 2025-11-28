"""
KIS API를 통한 주식 데이터 수집 모듈
국내 및 해외 주식의 현재가, 재무정보 등을 조회합니다.
"""

import requests
import yaml
import logging
import os
import re
import time
from typing import Dict, List, Optional
from datetime import datetime
from stock_names import get_stock_name


class KISDataFetcher:
    """한국투자증권 API를 통해 주식 데이터를 가져오는 클래스"""

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

    def _api_call_with_retry(self, url: str, headers: Dict, params: Dict, max_retries: int = 3, delay: float = 0.2) -> Optional[Dict]:
        """
        API 호출 재시도 로직

        Args:
            url: API URL
            headers: 요청 헤더
            params: 요청 파라미터
            max_retries: 최대 재시도 횟수
            delay: 재시도 간 대기 시간(초)

        Returns:
            응답 데이터 또는 None
        """
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get('rt_cd') == '0':
                    return data
                else:
                    self.logger.warning(f"API returned error code: {data.get('msg1', 'Unknown error')} (Attempt {attempt + 1}/{max_retries})")

            except Exception as e:
                self.logger.warning(f"API call failed: {e} (Attempt {attempt + 1}/{max_retries})")

            if attempt < max_retries - 1:
                time.sleep(delay)

        return None

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
            data = self._api_call_with_retry(url, headers, params)

            if data:
                output = data['output']

                # 종목명 조회 (여러 필드 확인, 'None' 문자열도 제외)
                def get_valid_name(value):
                    if value and value != 'None' and value.strip():
                        return value
                    return None

                stock_name = (get_valid_name(output.get('hts_kor_isnm')) or
                             get_valid_name(output.get('prdt_name')) or
                             get_valid_name(output.get('prdt_abrv_name')))

                # 종목명을 못 찾았으면 매핑 테이블에서 조회
                if not stock_name:
                    stock_name = get_stock_name(stock_code)

                # 재무지표 파싱 (빈 문자열과 None 처리)
                def safe_float(value, default=0.0):
                    if value is None or value == '':
                        return default
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default

                def safe_int(value, default=0):
                    if value is None or value == '':
                        return default
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return default

                per = safe_float(output.get('per'))
                pbr = safe_float(output.get('pbr'))
                eps = safe_float(output.get('eps'))
                bps = safe_float(output.get('bps'))

                # ROE 계산 (EPS / BPS * 100)
                roe = 0.0
                if bps > 0 and eps != 0:
                    roe = (eps / bps) * 100

                # 디버그 로깅
                self.logger.debug(f"Stock {stock_code} name fields: hts_kor_isnm='{output.get('hts_kor_isnm')}', "
                                f"prdt_name='{output.get('prdt_name')}', prdt_abrv_name='{output.get('prdt_abrv_name')}'")
                self.logger.debug(f"Stock {stock_code} ({stock_name}): PER={per}, PBR={pbr}, EPS={eps}, BPS={bps}, ROE={roe:.2f}")

                stock_data = {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'current_price': safe_int(output.get('stck_prpr')),
                    'market_cap': safe_int(output.get('hts_avls')),  # 시가총액 (백만원)
                    'per': per,
                    'pbr': pbr,
                    'eps': eps,
                    'bps': bps,
                    'roe': roe,
                    'timestamp': datetime.now().isoformat()
                }

                self.logger.info(f"✓ {stock_name} ({stock_code}): 가격={stock_data['current_price']:,}원, "
                               f"PER={per:.2f}, PBR={pbr:.2f}, ROE={roe:.2f}%")

                return stock_data
            else:
                self.logger.error(f"Failed to fetch stock {stock_code} after retries")
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

    def get_stock_basic_info(self, stock_code: str) -> Optional[Dict]:
        """
        국내 주식 기본정보 조회 (종목명 포함)

        Args:
            stock_code: 종목코드

        Returns:
            기본정보 딕셔너리
        """
        if not self.access_token:
            self.get_access_token()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/search-stock-info"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "CTPF1002R"
        }
        params = {
            "PRDT_TYPE_CD": "300",
            "PDNO": stock_code
        }

        try:
            data = self._api_call_with_retry(url, headers, params)

            if data and 'output' in data:
                output = data['output']
                return {
                    'stock_name': output.get('prdt_name', stock_code),
                    'stock_abbr_name': output.get('prdt_abrv_name', ''),
                }
            else:
                return None

        except Exception as e:
            self.logger.debug(f"Failed to fetch stock basic info {stock_code}: {e}")
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

    def get_top_market_cap_stocks(self, top_n: int = 30) -> List[Dict]:
        """
        시가총액 상위 종목 코드 및 종목명 조회

        Args:
            top_n: 조회할 상위 종목 수

        Returns:
            종목 정보 리스트 (딕셔너리: stock_code, stock_name)
        """
        if not self.access_token:
            self.get_access_token()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/volume-rank"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHPST01710000"
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",  # 시가총액 상위
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "0",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_INPUT_DATE_1": ""
        }

        try:
            data = self._api_call_with_retry(url, headers, params)

            if data and 'output' in data:
                stock_list = []

                # 첫 번째 항목으로 사용 가능한 필드 확인 (디버깅)
                if len(data['output']) > 0:
                    first_item = data['output'][0]
                    self.logger.debug(f"Available fields in volume-rank response: {list(first_item.keys())}")

                for item in data['output'][:top_n]:
                    # 여러 가능한 종목코드 필드 시도
                    stock_code = (item.get('stck_shrn_iscd') or
                                 item.get('mksc_shrn_iscd') or
                                 item.get('stck_iscd') or
                                 item.get('iscd'))

                    if not stock_code:
                        self.logger.warning(f"Could not find stock code in item: {item}")
                        continue

                    # volume-rank API의 모든 가능한 종목명 필드 확인
                    stock_name = (item.get('hts_kor_isnm') or
                                 item.get('prdt_name') or
                                 item.get('prdt_abrv_name') or
                                 item.get('itm_name'))

                    # 'None' 문자열 처리 및 빈 값 처리
                    if not stock_name or stock_name == 'None' or not stock_name.strip():
                        # 매핑 테이블에서 조회
                        stock_name = get_stock_name(stock_code)

                    stock_list.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name
                    })

                self.logger.info(f"Found {len(stock_list)} top stocks by market cap")
                return stock_list
            else:
                self.logger.error("Failed to fetch top market cap stocks")
                return []

        except Exception as e:
            self.logger.error(f"Failed to fetch top market cap stocks: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []

    def get_all_domestic_stocks(self, use_top_market_cap: bool = True, top_n: int = 30) -> List[Dict]:
        """
        설정된 모든 국내 주식 데이터 조회

        Args:
            use_top_market_cap: True면 시가총액 상위 종목 조회, False면 설정 파일 종목 조회
            top_n: 시가총액 상위 조회 시 종목 수

        Returns:
            주식 데이터 리스트
        """
        stocks = []
        stock_info_map = {}  # 종목코드 -> 종목명 매핑

        if use_top_market_cap:
            # 시가총액 상위 종목 조회 (종목명 포함)
            stock_list = self.get_top_market_cap_stocks(top_n)
            # 종목명 매핑 생성
            for item in stock_list:
                stock_info_map[item['stock_code']] = item['stock_name']
            stock_codes = [item['stock_code'] for item in stock_list]
        else:
            # 설정 파일의 종목 조회
            stock_codes = self.config['stocks']['domestic']

        for idx, stock_code in enumerate(stock_codes, 1):
            self.logger.info(f"[{idx}/{len(stock_codes)}] Fetching domestic stock: {stock_code}")
            stock_data = self.get_domestic_stock_price(stock_code)
            if stock_data:
                # 종목명이 코드와 같으면 매핑에서 찾은 종목명으로 대체
                if stock_data['stock_name'] == stock_code and stock_code in stock_info_map:
                    stock_data['stock_name'] = stock_info_map[stock_code]
                stocks.append(stock_data)

            # API 호출 제한 고려 (초당 20건)
            time.sleep(0.05)

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
