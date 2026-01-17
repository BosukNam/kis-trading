"""KIS MCP Server - 메인 서버"""

import os
import logging
import sys
from typing import Optional
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import kis_config, server_config
from .kis.client import get_kis_client

# 로깅 설정 (stderr로 출력 - stdout은 MCP 통신용)
logging.basicConfig(
    level=getattr(logging, server_config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# MCP 서버 인스턴스
server = Server("kis-stock-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록 반환"""
    return [
        Tool(
            name="get_domestic_balance",
            description="국내 주식 잔고를 조회합니다. 보유 종목, 평가손익, 수익률 등을 확인할 수 있습니다.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_overseas_balance",
            description="해외 주식 잔고를 조회합니다. 미국 주식 등 해외 보유 종목의 현황을 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_stock_price",
            description="주식의 현재가를 조회합니다. 국내 주식은 종목코드(6자리), 해외 주식은 심볼(AAPL, MSFT 등)을 입력합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "종목코드 (국내: 005930, 해외: AAPL)",
                    },
                    "market": {
                        "type": "string",
                        "enum": ["domestic", "overseas"],
                        "description": "시장 구분 (domestic: 국내, overseas: 해외)",
                        "default": "domestic",
                    },
                    "exchange": {
                        "type": "string",
                        "enum": ["NAS", "NYS", "AMS"],
                        "description": "해외 거래소 (NAS: 나스닥, NYS: 뉴욕, AMS: 아멕스)",
                        "default": "NAS",
                    },
                },
                "required": ["stock_code"],
            },
        ),
        Tool(
            name="get_investor_trend",
            description="종목의 투자자별 매매동향을 조회합니다. 개인, 외국인, 기관의 순매수 현황을 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "종목코드 (6자리, 예: 005930)",
                    },
                },
                "required": ["stock_code"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """도구 호출 처리"""
    client = get_kis_client()

    try:
        if name == "get_domestic_balance":
            result = await handle_domestic_balance(client)
        elif name == "get_overseas_balance":
            result = await handle_overseas_balance(client)
        elif name == "get_stock_price":
            result = await handle_stock_price(client, arguments)
        elif name == "get_investor_trend":
            result = await handle_investor_trend(client, arguments)
        else:
            result = f"알 수 없는 도구: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"오류 발생: {str(e)}")]


async def handle_domestic_balance(client) -> str:
    """국내 주식 잔고 조회 처리"""
    balance = await client.get_domestic_balance()

    if not balance:
        return "잔고 조회에 실패했습니다. API 인증 정보를 확인해주세요."

    lines = [
        "## 국내 주식 잔고",
        "",
        f"**총 자산**: {balance.total_asset:,}원",
        f"**예수금**: {balance.cash:,}원",
        f"**주식 평가액**: {balance.stock_value:,}원",
        f"**평가손익**: {balance.profit_loss:+,}원 ({balance.profit_rate:+.2f}%)",
        "",
    ]

    if balance.holdings:
        lines.append("### 보유 종목")
        lines.append("")
        lines.append("| 종목명 | 종목코드 | 수량 | 평균단가 | 현재가 | 평가금액 | 손익 | 수익률 |")
        lines.append("|--------|----------|------|----------|--------|----------|------|--------|")

        for h in balance.holdings:
            lines.append(
                f"| {h.stock_name} | {h.stock_code} | {h.quantity:,} | "
                f"{h.avg_price:,} | {h.current_price:,} | {h.eval_amount:,} | "
                f"{h.profit_loss:+,} | {h.profit_rate:+.2f}% |"
            )
    else:
        lines.append("*보유 종목이 없습니다.*")

    lines.append("")
    lines.append(f"_조회 시각: {balance.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_")

    return "\n".join(lines)


async def handle_overseas_balance(client) -> str:
    """해외 주식 잔고 조회 처리"""
    balance = await client.get_overseas_balance()

    if not balance:
        return "해외 잔고 조회에 실패했습니다. API 인증 정보를 확인해주세요."

    lines = [
        "## 해외 주식 잔고",
        "",
        f"**총 자산 (USD)**: ${balance.total_asset_usd:,.2f}",
        f"**총 자산 (KRW)**: {balance.total_asset_krw:,}원",
        f"**평가손익**: ${balance.profit_loss_usd:+,.2f} ({balance.profit_rate:+.2f}%)",
        f"**환율**: {balance.exchange_rate:,.2f}원/USD",
        "",
    ]

    if balance.holdings:
        lines.append("### 보유 종목")
        lines.append("")
        lines.append("| 종목명 | 심볼 | 거래소 | 수량 | 평균단가 | 현재가 | 평가금액 | 손익 | 수익률 |")
        lines.append("|--------|------|--------|------|----------|--------|----------|------|--------|")

        for h in balance.holdings:
            lines.append(
                f"| {h.stock_name} | {h.symbol} | {h.exchange} | {h.quantity:,} | "
                f"${h.avg_price:.2f} | ${h.current_price:.2f} | ${h.eval_amount:.2f} | "
                f"${h.profit_loss:+.2f} | {h.profit_rate:+.2f}% |"
            )
    else:
        lines.append("*보유 종목이 없습니다.*")

    lines.append("")
    lines.append(f"_조회 시각: {balance.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_")

    return "\n".join(lines)


async def handle_stock_price(client, arguments: dict) -> str:
    """주식 현재가 조회 처리"""
    stock_code = arguments.get("stock_code", "")
    market = arguments.get("market", "domestic")
    exchange = arguments.get("exchange", "NAS")

    if not stock_code:
        return "종목코드를 입력해주세요."

    if market == "overseas":
        price = await client.get_overseas_stock_price(stock_code.upper(), exchange)
    else:
        price = await client.get_domestic_stock_price(stock_code)

    if not price:
        return f"종목 {stock_code} 정보를 찾을 수 없습니다."

    if market == "overseas":
        # 해외 주식 (USD)
        current = price.current_price / 100  # 센트 -> 달러
        change = price.change_amount / 100
        lines = [
            f"## {price.stock_name} ({price.stock_code})",
            "",
            f"**현재가**: ${current:,.2f}",
            f"**전일대비**: ${change:+,.2f} ({price.change_rate:+.2f}%)",
            f"**거래량**: {price.volume:,}주",
        ]
    else:
        # 국내 주식 (KRW)
        lines = [
            f"## {price.stock_name} ({price.stock_code})",
            "",
            f"**현재가**: {price.current_price:,}원",
            f"**전일대비**: {price.change_amount:+,}원 ({price.change_rate:+.2f}%)",
            f"**거래량**: {price.volume:,}주",
            f"**시가총액**: {price.market_cap:,}백만원",
        ]

        if price.per:
            lines.append(f"**PER**: {price.per:.2f}")
        if price.pbr:
            lines.append(f"**PBR**: {price.pbr:.2f}")
        if price.eps:
            lines.append(f"**EPS**: {price.eps:,.0f}원")
        if price.bps:
            lines.append(f"**BPS**: {price.bps:,.0f}원")

    lines.append("")
    lines.append(f"_조회 시각: {price.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_")

    return "\n".join(lines)


async def handle_investor_trend(client, arguments: dict) -> str:
    """투자자별 매매동향 조회 처리"""
    stock_code = arguments.get("stock_code", "")

    if not stock_code:
        return "종목코드를 입력해주세요."

    trend = await client.get_investor_trend(stock_code)

    if not trend:
        return f"종목 {stock_code} 투자자 동향을 찾을 수 없습니다."

    # 순매수 방향 표시
    def arrow(value: int) -> str:
        if value > 0:
            return "🔴 매수"
        elif value < 0:
            return "🔵 매도"
        else:
            return "⚪ 중립"

    lines = [
        f"## {trend.stock_name} ({trend.stock_code}) 투자자 동향",
        "",
        f"**기준일**: {trend.date[:4]}-{trend.date[4:6]}-{trend.date[6:]}",
        "",
        "### 순매수 현황",
        "",
        f"| 투자자 | 순매수(주) | 순매수(금액) | 방향 |",
        f"|--------|------------|--------------|------|",
        f"| 개인 | {trend.individual:+,} | {trend.individual_amount:+,}원 | {arrow(trend.individual)} |",
        f"| 외국인 | {trend.foreign:+,} | {trend.foreign_amount:+,}원 | {arrow(trend.foreign)} |",
        f"| 기관 | {trend.institution:+,} | {trend.institution_amount:+,}원 | {arrow(trend.institution)} |",
        "",
        f"_조회 시각: {trend.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_",
    ]

    return "\n".join(lines)


async def main():
    """메인 함수 - stdio 서버 실행"""
    logger.info("KIS MCP Server starting...")
    logger.info(f"KIS API configured: {bool(kis_config.app_key)}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
