# KIS 주식 자동매매 시스템

한국투자증권 API를 활용한 국내 및 해외 주식 자동 분석 및 매매 시스템입니다.

## 주요 기능

- 국내 주식 (KOSPI/KOSDAQ) 실시간 시세 조회
- 해외 주식 (미국 시장) 실시간 시세 조회
- 재무지표 분석 (PER, PBR, ROE, 시가총액, 부채비율 등)
- 저평가 주식 스크리닝
- 자동 매수 주문 실행
- 계좌 잔고 조회

## 프로젝트 구조

```
kis/
├── src/
│   ├── data_fetcher.py    # KIS API를 통한 데이터 수집
│   ├── analyzer.py        # 재무지표 분석 및 계산
│   ├── screener.py        # 저평가 주식 스크리닝
│   ├── trader.py          # 매수/매도 주문 실행
│   └── main.py            # 메인 애플리케이션
├── config/
│   └── config.yaml        # 설정 파일
├── requirements.txt       # Python 패키지 의존성
└── README.md
```

## 설치 방법

### 1. 저장소 클론 (또는 다운로드)

```bash
cd /Users/nam/Documents/kis
```

### 2. Python 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

**중요: API 키 등 민감한 정보는 환경변수로 관리합니다.**

#### 3-1. .env 파일 생성

```bash
cp .env.example .env
```

#### 3-2. .env 파일 편집

`.env` 파일을 열어 실제 값을 입력하세요:

```bash
# KIS API 인증 정보
KIS_APP_KEY=your_actual_app_key_here
KIS_APP_SECRET=your_actual_app_secret_here
KIS_ACCT_STOCK=your_account_number_here
KIS_HTS_ID=your_hts_id_here
```

#### 3-3. 환경변수 로드

프로그램 실행 전에 환경변수를 설정하세요:

**방법 1: .env 파일 사용 (권장)**
```bash
# .env 파일에서 환경변수 자동 로드
export $(cat .env | xargs)
```

**방법 2: 직접 export**
```bash
export KIS_APP_KEY="your_app_key"
export KIS_APP_SECRET="your_app_secret"
export KIS_ACCT_STOCK="7207556001"
export KIS_HTS_ID="your_hts_id"
```

**방법 3: 쉘 설정 파일에 추가 (영구 설정)**
```bash
# ~/.bashrc 또는 ~/.zshrc에 추가
echo 'export KIS_APP_KEY="your_app_key"' >> ~/.bashrc
echo 'export KIS_APP_SECRET="your_app_secret"' >> ~/.bashrc
echo 'export KIS_ACCT_STOCK="your_account"' >> ~/.bashrc
echo 'export KIS_HTS_ID="your_hts_id"' >> ~/.bashrc

# 적용
source ~/.bashrc
```

**KIS API 키 발급 방법:**
1. [한국투자증권 오픈API](https://apiportal.koreainvestment.com/) 접속
2. 회원가입 및 로그인
3. APP 생성하여 APP KEY와 APP SECRET 발급
4. 실전투자 계좌 연결
5. HTS ID 확인

## 사용 방법

### 기본 명령어 구조

```bash
python src/main.py <mode> [options]
```

### 실행 모드

#### 1. 주식 분석 모드 (analyze)

주식의 재무지표를 분석하고 리포트를 출력합니다.

```bash
# 국내 + 해외 주식 분석
python src/main.py analyze

# 국내 주식만 분석
python src/main.py analyze --market domestic

# 해외 주식만 분석
python src/main.py analyze --market international
```

#### 2. 스크리닝 모드 (screen)

저평가 주식을 선별하고 CSV 파일로 저장합니다.

```bash
# 스크리닝 실행 및 CSV 저장
python src/main.py screen

# 국내 주식만 스크리닝
python src/main.py screen --market domestic
```

#### 3. 자동매매 모드 (trade)

분석 → 스크리닝 → 매수 주문을 자동으로 실행합니다.

```bash
# 시뮬레이션 모드 (실제 주문 없음)
python src/main.py trade

# 실제 주문 실행 (주의!)
python src/main.py trade --live
```

#### 4. 계좌 조회 모드 (account)

계좌 잔고 및 보유 주식을 조회합니다.

```bash
python src/main.py account
```

### 옵션

- `--market <domestic|international|both>`: 대상 시장 선택 (기본값: both)
- `--live`: 실제 주문 실행 (기본값은 시뮬레이션)
- `--log-level <DEBUG|INFO|WARNING|ERROR>`: 로그 레벨 설정 (기본값: INFO)
- `--config <path>`: 설정 파일 경로 (기본값: config/config.yaml)

## 설정 파일 상세

### 스크리닝 기준

`config/config.yaml`에서 저평가 주식 선별 기준을 조정할 수 있습니다:

```yaml
screening:
  per_max: 15.0          # PER 최대값 (낮을수록 저평가)
  per_min: 0.0           # PER 최소값
  roe_min: 10.0          # ROE 최소값 (높을수록 좋음)
  pbr_max: 1.5           # PBR 최대값 (낮을수록 저평가)
  pbr_min: 0.0           # PBR 최소값
  market_cap_min: 1000   # 최소 시가총액 (억원)
  market_cap_max: 100000 # 최대 시가총액 (억원)
  debt_ratio_max: 200.0  # 최대 부채비율 (%)
```

### 매매 설정

```yaml
trading:
  order_type: "limit"         # 주문 유형 (limit: 지정가, market: 시장가)
  max_stocks_to_buy: 5        # 한 번에 매수할 최대 종목 수
  amount_per_stock: 1000000   # 종목당 매수 금액 (원)
```

### 모니터링 종목 설정

```yaml
stocks:
  domestic:    # 국내 주식 (종목코드 6자리)
    - "005930"  # 삼성전자
    - "000660"  # SK하이닉스

  international:  # 해외 주식 (티커 심볼)
    - "AAPL"    # Apple
    - "MSFT"    # Microsoft
```

## 출력 파일

### 로그 파일
- `stock_analyzer.log`: 실행 로그 기록

### CSV 파일
- `screened_stocks_YYYYMMDD_HHMMSS.csv`: 스크리닝 결과 저장

## 재무지표 설명

### PER (Price to Earnings Ratio)
- 주가수익비율
- 계산: 주가 / 주당순이익(EPS)
- 낮을수록 저평가

### PBR (Price to Book Ratio)
- 주가순자산비율
- 계산: 주가 / 주당순자산(BPS)
- 낮을수록 저평가

### ROE (Return on Equity)
- 자기자본이익률
- 계산: 순이익 / 자기자본 × 100
- 높을수록 우수

### 부채비율
- 계산: 총부채 / 자기자본 × 100
- 낮을수록 재무구조 안정적

### 저평가 점수
시스템이 자체적으로 계산하는 점수 (0-100)
- 낮을수록 저평가
- 가중치: PER 30%, PBR 30%, ROE 20%, 부채비율 20%

## 사용 예시

### 1. 매일 아침 저평가 주식 찾기

```bash
# 스크리닝 실행
python src/main.py screen

# 결과 CSV 파일 확인
# screened_stocks_20250128_090000.csv
```

### 2. 자동매매 (시뮬레이션)

```bash
# 분석부터 매수까지 전체 프로세스 시뮬레이션
python src/main.py trade
```

### 3. 실제 자동매매 실행

```bash
# 실제 주문 실행 (신중하게!)
python src/main.py trade --live
```

### 4. 국내 주식만 집중 분석

```bash
python src/main.py analyze --market domestic --log-level DEBUG
```

## 주의사항

1. **실전 투자 전 충분한 테스트 필수**
   - 먼저 시뮬레이션 모드로 충분히 테스트하세요
   - 모의투자 계좌로 먼저 연습하세요

2. **API 키 보안**
   - `.env` 파일에 민감한 정보를 저장하세요 (절대 Git에 커밋하지 마세요)
   - `.gitignore`에 `.env` 파일이 포함되어 있는지 확인하세요
   - 환경변수를 사용하여 민감한 정보가 소스코드에 노출되지 않도록 하세요

3. **투자 책임**
   - 모든 투자 결정과 손실은 사용자 본인의 책임입니다
   - 이 시스템은 참고용 도구일 뿐입니다

4. **API 사용 제한**
   - KIS API에는 호출 횟수 제한이 있을 수 있습니다
   - 과도한 호출을 피하세요

5. **시장 시간**
   - 국내 주식: 평일 09:00 - 15:30
   - 미국 주식: 한국 시간 23:30 - 06:00 (썸머타임 22:30 - 05:00)

## 문제 해결

### API 인증 오류
```
Failed to get access token
```
→ `config/config.yaml`의 APP KEY, APP SECRET 확인

### 주문 실패
```
Order failed: 잔고 부족
```
→ 계좌 잔고 확인 또는 `amount_per_stock` 값 조정

### 모듈 import 오류
```
ModuleNotFoundError: No module named 'yaml'
```
→ `pip install -r requirements.txt` 실행

## 개발 및 커스터마이징

### 스크리닝 로직 수정
`src/screener.py`의 `apply_screening_criteria()` 함수 수정

### 저평가 점수 계산 수정
`src/analyzer.py`의 `calculate_undervalue_score()` 함수 수정

### 새로운 재무지표 추가
1. `src/data_fetcher.py`에서 데이터 수집 로직 추가
2. `src/analyzer.py`에서 계산 로직 추가
3. `src/screener.py`에서 스크리닝 기준 추가

## 라이선스

이 프로젝트는 교육 및 개인 사용 목적으로 제작되었습니다.

## 문의

프로젝트 관련 문의나 버그 리포트는 이슈를 등록해주세요.

---

**면책조항**: 이 소프트웨어는 "있는 그대로" 제공되며, 어떠한 종류의 명시적 또는 묵시적 보증도 하지 않습니다. 투자에 대한 모든 책임은 사용자에게 있습니다.
