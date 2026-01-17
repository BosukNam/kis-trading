"""KIS MCP HTTP/SSE 서버 - Railway 배포용"""

import os
import logging
import sys
import json
import asyncio
from typing import Optional
from datetime import datetime

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse, Response
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from .config import server_config, kis_config
from .kis.client import get_kis_client

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, server_config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Bearer Token 인증 미들웨어"""

    async def dispatch(self, request: Request, call_next):
        # 헬스체크 및 루트는 인증 제외
        if request.url.path in ["/health", "/", "/sse"]:
            return await call_next(request)

        # Bearer Token 검증
        auth_header = request.headers.get("Authorization", "")
        expected_token = server_config.bearer_token

        if expected_token:  # 토큰이 설정된 경우에만 검증
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Missing or invalid Authorization header"},
                    status_code=401,
                )

            token = auth_header.split(" ", 1)[1]
            if token != expected_token:
                return JSONResponse({"error": "Invalid token"}, status_code=403)

        return await call_next(request)


async def health(request: Request) -> JSONResponse:
    """헬스체크 엔드포인트"""
    return JSONResponse({
        "status": "healthy",
        "service": "kis-mcp-server",
        "timestamp": datetime.now().isoformat(),
        "kis_configured": bool(kis_config.app_key),
    })


async def root(request: Request) -> JSONResponse:
    """루트 엔드포인트"""
    return JSONResponse({
        "name": "KIS Stock MCP Server",
        "version": "0.1.0",
        "description": "한국투자증권 주식 정보 MCP 서버",
        "endpoints": {
            "health": "/health",
            "sse": "/sse",
            "tools": "/tools",
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

        else:
            return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=400)

    except Exception as e:
        logger.error(f"Tool call failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


async def sse_endpoint(request: Request) -> StreamingResponse:
    """SSE 엔드포인트 (MCP 클라이언트용)"""

    async def event_generator():
        """SSE 이벤트 생성기"""
        # 연결 확인 이벤트
        yield f"data: {json.dumps({'type': 'connected', 'server': 'kis-mcp-server'})}\n\n"

        # 클라이언트 연결 유지
        while True:
            try:
                # 30초마다 heartbeat
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
    Route("/health", health),
    Route("/tools", list_tools),
    Route("/call", call_tool, methods=["POST"]),
    Route("/sse", sse_endpoint),
]

# Starlette 앱
app = Starlette(
    routes=routes,
    middleware=[Middleware(BearerAuthMiddleware)],
    on_startup=[lambda: logger.info("KIS MCP HTTP Server started")],
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
