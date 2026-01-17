"""KIS MCP HTTP/SSE 서버 - Railway 배포용 (GitHub OAuth 인증)"""

import os
import logging
import sys
import json
import asyncio
import hashlib
import hmac
import base64
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, StreamingResponse, Response, HTMLResponse, RedirectResponse
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles
import uvicorn

from .config import server_config, kis_config, github_config, dart_config
from .kis.client import get_kis_client
from .kis.dart_client import get_dart_client

# Static 파일 경로
STATIC_DIR = Path(__file__).parent / "static"

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, server_config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# 세션 저장소 (메모리 기반 - 프로덕션에서는 Redis 등 사용 권장)
sessions: dict[str, dict] = {}


def sign_token(data: str, secret: str) -> str:
    """토큰 서명"""
    signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{signature}"


def verify_token(token: str, secret: str) -> str | None:
    """토큰 검증"""
    if "." not in token:
        return None
    data, signature = token.rsplit(".", 1)
    expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(signature, expected):
        return data
    return None


def create_session(username: str) -> str:
    """세션 생성"""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "username": username,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(days=7)).isoformat(),
    }
    return sign_token(session_id, github_config.session_secret)


def get_session(token: str) -> dict | None:
    """세션 조회"""
    session_id = verify_token(token, github_config.session_secret)
    if not session_id:
        return None
    session = sessions.get(session_id)
    if not session:
        return None
    if datetime.fromisoformat(session["expires_at"]) < datetime.now():
        del sessions[session_id]
        return None
    return session


def delete_session(token: str) -> None:
    """세션 삭제"""
    session_id = verify_token(token, github_config.session_secret)
    if session_id and session_id in sessions:
        del sessions[session_id]


class AuthMiddleware(BaseHTTPMiddleware):
    """인증 미들웨어"""

    # 인증 제외 경로
    PUBLIC_PATHS = ["/health", "/auth/login", "/auth/callback", "/auth/logout", "/login", "/sse", "/api"]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # GitHub OAuth가 비활성화된 경우 모든 요청 허용
        if not github_config.enabled:
            return await call_next(request)

        # 공개 경로는 인증 제외
        if path in self.PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        # MCP Bearer Token 인증 (API 호출용)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            if token == server_config.bearer_token:
                return await call_next(request)

        # 세션 쿠키 확인
        session_token = request.cookies.get("session")
        if session_token:
            session = get_session(session_token)
            if session:
                request.state.user = session["username"]
                return await call_next(request)

        # 인증되지 않은 요청 -> 로그인 페이지로 리다이렉트
        if request.headers.get("Accept", "").startswith("text/html"):
            return RedirectResponse("/login", status_code=302)

        return JSONResponse({"error": "Unauthorized"}, status_code=401)


async def health(request: Request) -> JSONResponse:
    """헬스체크 엔드포인트"""
    return JSONResponse({
        "status": "healthy",
        "service": "kis-mcp-server",
        "timestamp": datetime.now().isoformat(),
        "kis_configured": bool(kis_config.app_key),
        "oauth_enabled": github_config.enabled,
    })


async def login_page(request: Request) -> HTMLResponse:
    """로그인 페이지"""
    html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KIS Stock - 로그인</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }
        .login-card {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            max-width: 400px;
            width: 90%;
        }
        .logo {
            font-size: 48px;
            margin-bottom: 16px;
        }
        h1 {
            font-size: 24px;
            margin-bottom: 8px;
        }
        .subtitle {
            color: #888;
            margin-bottom: 32px;
            font-size: 14px;
        }
        .github-btn {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            background: #fff;
            color: #000;
            padding: 14px 28px;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .github-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(255,255,255,0.2);
        }
        .github-btn svg {
            width: 24px;
            height: 24px;
        }
        .footer {
            margin-top: 32px;
            font-size: 12px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo">📈</div>
        <h1>KIS Stock</h1>
        <p class="subtitle">한국투자증권 주식 정보 조회</p>
        <a href="/auth/login" class="github-btn">
            <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            GitHub로 로그인
        </a>
        <p class="footer">허가된 사용자만 접근 가능합니다</p>
    </div>
</body>
</html>
"""
    return HTMLResponse(html)


async def auth_login(request: Request) -> RedirectResponse:
    """GitHub OAuth 로그인 시작"""
    if not github_config.enabled:
        return RedirectResponse("/", status_code=302)

    state = secrets.token_urlsafe(16)
    # state를 세션에 저장 (CSRF 방지)
    sessions[f"state:{state}"] = {"created_at": datetime.now().isoformat()}

    # Railway 프록시 뒤에서 https 강제
    callback_url = str(request.url_for("auth_callback"))
    if callback_url.startswith("http://"):
        callback_url = callback_url.replace("http://", "https://", 1)

    params = {
        "client_id": github_config.client_id,
        "redirect_uri": callback_url,
        "scope": "read:user",
        "state": state,
    }
    url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url, status_code=302)


async def auth_callback(request: Request) -> Response:
    """GitHub OAuth 콜백"""
    if not github_config.enabled:
        return RedirectResponse("/", status_code=302)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(f"<h1>인증 오류</h1><p>{error}</p>", status_code=400)

    # State 검증
    state_key = f"state:{state}"
    if state_key not in sessions:
        return HTMLResponse("<h1>잘못된 요청</h1><p>State mismatch</p>", status_code=400)
    del sessions[state_key]

    # Access token 교환
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": github_config.client_id,
                "client_secret": github_config.client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_response.json()

        if "error" in token_data:
            return HTMLResponse(f"<h1>토큰 오류</h1><p>{token_data.get('error_description', token_data['error'])}</p>", status_code=400)

        access_token = token_data["access_token"]

        # 사용자 정보 조회
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_data = user_response.json()
        username = user_data["login"]

    # 허용된 사용자 확인
    if github_config.allowed_users and username not in github_config.allowed_users:
        logger.warning(f"Unauthorized user attempted login: {username}")
        return HTMLResponse(
            f"<h1>접근 거부</h1><p>사용자 '{username}'은(는) 접근이 허용되지 않았습니다.</p>",
            status_code=403
        )

    # 세션 생성
    session_token = create_session(username)
    logger.info(f"User logged in: {username}")

    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key="session",
        value=session_token,
        max_age=7 * 24 * 60 * 60,  # 7일
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


async def auth_logout(request: Request) -> RedirectResponse:
    """로그아웃"""
    session_token = request.cookies.get("session")
    if session_token:
        delete_session(session_token)

    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session")
    return response


async def root(request: Request) -> Response:
    """루트 - 모바일 웹 UI 제공"""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return JSONResponse({
        "name": "KIS Stock MCP Server",
        "version": "0.1.0",
        "description": "한국투자증권 주식 정보 MCP 서버",
    })


async def app_page(request: Request) -> Response:
    """앱 페이지 (루트와 동일)"""
    return await root(request)


async def api_info(request: Request) -> JSONResponse:
    """API 정보"""
    return JSONResponse({
        "name": "KIS Stock MCP Server",
        "version": "0.1.0",
        "description": "한국투자증권 주식 정보 MCP 서버",
        "endpoints": {
            "health": "/health",
            "sse": "/sse",
            "tools": "/tools",
            "call": "/call",
        },
    })


async def list_tools(request: Request) -> JSONResponse:
    """도구 목록 반환"""
    tools = [
        {
            "name": "get_domestic_balance",
            "description": "국내 주식 잔고를 조회합니다.",
        },
        {
            "name": "get_overseas_balance",
            "description": "해외 주식 잔고를 조회합니다.",
        },
        {
            "name": "get_stock_price",
            "description": "주식의 현재가를 조회합니다.",
            "parameters": ["stock_code", "market", "exchange"],
        },
        {
            "name": "get_investor_trend",
            "description": "투자자별 매매동향을 조회합니다.",
            "parameters": ["stock_code"],
        },
        {
            "name": "get_technical_indicators",
            "description": "기술적 지표를 조회합니다. (52주 고저, RSI, 변동성, 이동평균)",
            "parameters": ["stock_code"],
        },
        {
            "name": "get_financial_ratio",
            "description": "재무비율을 조회합니다. (ROE, 성장률, 부채비율 등)",
            "parameters": ["stock_code", "stock_name"],
        },
        {
            "name": "get_financial_statement",
            "description": "재무제표/현금흐름표를 조회합니다. (DART)",
            "parameters": ["stock_name", "year", "report_type"],
        },
        {
            "name": "get_disclosures",
            "description": "기업 공시 목록을 조회합니다. (DART)",
            "parameters": ["stock_name", "stock_code", "count"],
        },
    ]
    return JSONResponse({"tools": tools})


async def call_tool(request: Request) -> JSONResponse:
    """도구 호출"""
    try:
        body = await request.json()
        tool_name = body.get("name")
        arguments = body.get("arguments", {})

        client = get_kis_client()

        if tool_name == "get_domestic_balance":
            result = await client.get_domestic_balance()
            if result:
                return JSONResponse(result.model_dump(mode="json"))
            else:
                return JSONResponse({"error": "Failed to get balance"}, status_code=500)

        elif tool_name == "get_overseas_balance":
            result = await client.get_overseas_balance()
            if result:
                return JSONResponse(result.model_dump(mode="json"))
            else:
                return JSONResponse({"error": "Failed to get overseas balance"}, status_code=500)

        elif tool_name == "get_stock_price":
            stock_code = arguments.get("stock_code", "")
            market = arguments.get("market", "domestic")
            exchange = arguments.get("exchange", "NAS")

            if market == "overseas":
                result = await client.get_overseas_stock_price(stock_code.upper(), exchange)
            else:
                result = await client.get_domestic_stock_price(stock_code)

            if result:
                return JSONResponse(result.model_dump(mode="json"))
            else:
                return JSONResponse({"error": "Stock not found"}, status_code=404)

        elif tool_name == "get_investor_trend":
            stock_code = arguments.get("stock_code", "")
            result = await client.get_investor_trend(stock_code)
            if result:
                return JSONResponse(result.model_dump(mode="json"))
            else:
                return JSONResponse({"error": "Trend data not found"}, status_code=404)

        elif tool_name == "get_technical_indicators":
            stock_code = arguments.get("stock_code", "")
            result = await client.get_technical_indicators(stock_code)
            if result:
                return JSONResponse(result.model_dump(mode="json"))
            else:
                return JSONResponse({"error": "Technical data not found"}, status_code=404)

        elif tool_name == "get_financial_ratio":
            stock_code = arguments.get("stock_code", "")
            stock_name = arguments.get("stock_name", "")
            result = await client.get_financial_ratio(stock_code)
            if result:
                data = result.model_dump(mode="json")
                # API 결과의 stock_name이 코드와 같거나 비어있으면 전달받은 값 사용
                if stock_name and (not data.get("stock_name") or data.get("stock_name") == stock_code):
                    data["stock_name"] = stock_name
                return JSONResponse(data)
            else:
                return JSONResponse({"error": "Financial ratio not found"}, status_code=404)

        elif tool_name == "get_financial_statement":
            stock_name = arguments.get("stock_name", "")
            year = arguments.get("year", str(datetime.now().year - 1))
            report_type = arguments.get("report_type", "11011")  # 사업보고서

            dart_client = get_dart_client()
            if not dart_config.enabled:
                return JSONResponse({"error": "DART API not configured"}, status_code=500)

            # 회사명으로 공시 검색하여 corp_code 획득
            disclosures = await dart_client.get_disclosures(corp_name=stock_name, page_count=1)
            if not disclosures:
                return JSONResponse({"error": f"Company not found: {stock_name}"}, status_code=404)

            corp_code = disclosures[0].corp_code
            result = await dart_client.get_financial_statements(corp_code, year, report_type)
            if result:
                return JSONResponse(result.model_dump(mode="json"))
            else:
                return JSONResponse({"error": "Financial statement not found"}, status_code=404)

        elif tool_name == "get_disclosures":
            stock_name = arguments.get("stock_name", "")
            stock_code = arguments.get("stock_code", "")
            count = arguments.get("count", 10)

            dart_client = get_dart_client()
            if not dart_config.enabled:
                return JSONResponse({"error": "DART API not configured"}, status_code=500)

            # stock_code가 있으면 corp_code 조회하여 1년치 공시 조회 가능
            if stock_code:
                result = await dart_client.get_disclosures_by_stock(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    page_count=count
                )
            else:
                # stock_code 없을 때: 회사명으로 먼저 corp_code 검색 시도 (정확한 매칭)
                corp_code = await dart_client.get_corp_code_by_name(stock_name)
                if corp_code:
                    # 정확히 매칭되는 회사가 있으면 1년치 조회
                    logger.info(f"Found corp_code {corp_code} for '{stock_name}'")
                    result = await dart_client.get_disclosures(corp_code=corp_code, page_count=count)
                else:
                    # 매칭되지 않으면 부분 검색 (3개월 제한)
                    result = await dart_client.get_disclosures(corp_name=stock_name, page_count=count)
            return JSONResponse({"disclosures": [d.model_dump(mode="json") for d in result]})

        else:
            return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=400)

    except Exception as e:
        logger.error(f"Tool call failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


async def sse_endpoint(request: Request) -> StreamingResponse:
    """SSE 엔드포인트 (MCP 클라이언트용)"""

    async def event_generator():
        """SSE 이벤트 생성기"""
        yield f"data: {json.dumps({'type': 'connected', 'server': 'kis-mcp-server'})}\n\n"

        while True:
            try:
                await asyncio.sleep(30)
                yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# 라우트 정의
routes = [
    Route("/", root),
    Route("/app", app_page),
    Route("/api", api_info),
    Route("/health", health),
    Route("/login", login_page),
    Route("/auth/login", auth_login, name="auth_login"),
    Route("/auth/callback", auth_callback, name="auth_callback"),
    Route("/auth/logout", auth_logout),
    Route("/tools", list_tools),
    Route("/call", call_tool, methods=["POST"]),
    Route("/sse", sse_endpoint),
]

# Static 파일 마운트 (존재하는 경우)
if STATIC_DIR.exists():
    routes.append(Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"))

# Starlette 앱
app = Starlette(
    routes=routes,
    middleware=[Middleware(AuthMiddleware)],
    on_startup=[lambda: logger.info(f"KIS MCP HTTP Server started (OAuth: {github_config.enabled})")],
)


def main():
    """HTTP 서버 실행"""
    port = server_config.port
    logger.info(f"Starting KIS MCP HTTP Server on port {port}")
    uvicorn.run(
        "src.http_server:app",
        host="0.0.0.0",
        port=port,
        log_level=server_config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
