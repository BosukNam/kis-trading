# 수정사항 요약

## 완료된 수정사항

### 1. API 호출 정합성 체크 및 retry 로직 추가 ✓
**파일:** `src/data_fetcher.py`

- **`_api_call_with_retry()` 메서드 추가** (85-116줄)
  - 최대 3회 재시도
  - 재시도 간 0.2초 대기
  - API 오류 코드 및 네트워크 오류 처리

- **`get_domestic_stock_price()` 메서드 개선** (118-212줄)
  - `safe_float()`, `safe_int()` 함수로 None, 빈 문자열, 'None' 문자열 안전하게 파싱
  - ROE 자동 계산 추가: `ROE = (EPS / BPS) × 100`
  - 재무지표 누락 시 0으로 기본값 설정
  - API 호출 제한 고려하여 0.05초 대기 추가

- **PER, PBR, ROE 값이 0으로 나오는 경우**
  - 일부 종목(ETF, 우선주 등)은 KIS API에서 재무지표를 제공하지 않음
  - 이는 API의 한계이며, 정상적으로 값이 있는 종목은 제대로 표시됨
  - 예: `005930` (삼성전자), `098460`, `092200` 등은 정상적으로 PER, PBR, ROE 표시

### 2. 종목명 한글 표시 ✓
**파일:** `src/data_fetcher.py`

- **종목명 조회 로직 개선** (151-167줄)
  - 'None' 문자열 필터링 추가
  - 여러 필드 확인: `hts_kor_isnm`, `prdt_name`, `prdt_abrv_name`
  - 종목명을 못 찾으면 `get_stock_basic_info()` API 호출
  - 최종 fallback은 종목코드

- **`get_top_market_cap_stocks()` 개선** (367-428줄)
  - volume-rank API 응답에서 종목명(`hts_kor_isnm`) 추출
  - 종목코드와 종목명을 함께 반환
  - 'None' 문자열 처리 추가

- **`get_all_domestic_stocks()` 개선** (430-467줄)
  - 종목명 매핑(stock_info_map) 생성
  - 종목명이 코드와 같으면 매핑에서 찾은 한글명으로 대체

**파일:** `src/analyzer.py`

- **리포트 출력 개선** (279줄)
  - "종목명 (종목코드)" 형식으로 표시
  - 예: `삼성전자 (005930)`
  - 종목명이 코드와 같으면 코드만 표시

### 3. 저평가 점수 기준 정렬 ✓
**파일:** `src/analyzer.py`

- **`print_analysis_report()` 메서드 개선** (258-286줄)
  - `df.sort_values('undervalue_score', ascending=False)` 추가
  - **높은 점수 → 낮은 점수 순으로 정렬** (내림차순)
  - 점수가 높을수록 저평가 가능성이 높은 종목이 먼저 표시됨

## 주의사항

### API 제한사항
- 일부 종목(ETF, 우선주, 관리종목 등)은 KIS API에서 PER, PBR, ROE 데이터를 제공하지 않습니다
- 이러한 종목들은 `PER: 0.00 | PBR: 0.00 | ROE: 0.00%`로 표시됩니다
- 이는 정상 동작이며, 값이 있는 종목은 제대로 표시됩니다

### 종목명 조회
- volume-rank API에서 `hts_kor_isnm` 필드로 한글 종목명 조회
- 일부 종목은 API에서 종목명을 'None' 문자열로 반환할 수 있음
- 이 경우 종목코드로 표시됩니다

## 테스트 방법

```bash
# 국내 주식 분석 (시가총액 상위 30개)
python src/main.py analyze --market domestic

# 예상 결과:
# - 종목명이 한글로 표시: "삼성전자 (005930)"
# - 저평가 점수가 높은 순으로 정렬
# - PER, PBR, ROE가 있는 종목은 정상 표시
# - 재무지표가 없는 종목은 0.00으로 표시
```

## 변경된 파일 목록

1. `src/data_fetcher.py` - API 호출, retry 로직, 종목명 조회 개선
2. `src/analyzer.py` - 정렬 순서 변경, 종목명 표시 개선
3. `src/main.py` - 로그 메시지 추가
