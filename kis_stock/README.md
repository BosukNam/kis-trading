# KIS MCP Server

한국투자증권 API를 활용한 MCP (Model Context Protocol) 원격 서버입니다.
Claude.ai, Claude Desktop, Claude Code에서 자연어로 주식 정보를 조회할 수 있습니다.

## 기능

- **국내 주식 잔고 조회**: 보유 종목, 평가손익, 수익률 확인
- **해외 주식 잔고 조회**: 미국 주식 등 해외 보유 종목 현황
- **종목 현재가 조회**: 국내/해외 주식 실시간 시세
- **투자자 동향 조회**: 개인/외국인/기관 순매수 현황

## 설치

### 로컬 실행

```bash
# 의존성 설치
pip install -e .

# 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 KIS API 키 입력

# stdio 서버 실행 (Claude Desktop용)
python -m src.server

# HTTP 서버 실행 (원격 접속용)
python -m src.http_server
```

### Railway 배포

1. GitHub에 푸시
2. Railway에서 새 프로젝트 생성
3. GitHub 레포 연결
4. 환경변수 설정:
   - `KIS_APP_KEY`
   - `KIS_APP_SECRET`
   - `KIS_ACCOUNT_NUMBER`
   - `MCP_BEARER_TOKEN` (선택, 인증용)

## 환경변수

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `KIS_APP_KEY` | KIS API 앱 키 | O |
| `KIS_APP_SECRET` | KIS API 앱 시크릿 | O |
| `KIS_ACCOUNT_NUMBER` | 계좌번호 (8자리-2자리) | O |
| `KIS_BASE_URL` | KIS API URL | X (기본값 제공) |
| `MCP_BEARER_TOKEN` | MCP 인증 토큰 | X |
| `PORT` | 서버 포트 | X (기본값: 8000) |
| `LOG_LEVEL` | 로그 레벨 | X (기본값: INFO) |

## Claude 연결

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kis-stock": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/kis-mcp-server"
    }
  }
}
```

### Claude Code (원격 서버)

```bash
claude mcp add --transport http kis-stock https://your-app.railway.app \
  --header "Authorization: Bearer your_token"
```

## 사용 예시

Claude에서 자연어로 질문하세요:

- "내 주식 잔고 보여줘"
- "삼성전자 현재가 알려줘"
- "AAPL 주가 확인해줘"
- "삼성전자 외국인 매매 동향 알려줘"

## API 엔드포인트 (HTTP 서버)

| 경로 | 메서드 | 설명 |
|------|--------|------|
| `/` | GET | 서버 정보 |
| `/health` | GET | 헬스체크 |
| `/tools` | GET | 도구 목록 |
| `/call` | POST | 도구 호출 |
| `/sse` | GET | SSE 연결 |

## 라이선스

MIT License
