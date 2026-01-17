FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 의존성 설치
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# 소스 복사
COPY src/ ./src/

# 포트 노출
EXPOSE 8000

# 환경변수 기본값
ENV PORT=8000
ENV LOG_LEVEL=INFO

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# 서버 실행
CMD ["python", "-m", "src.http_server"]
