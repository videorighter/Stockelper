FROM python:3.12-slim

WORKDIR /server

# PostgreSQL 관련 라이브러리 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    zlib1g-dev \
    libpq-dev \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# uv 설치 및 설정
# 참고: https://docs.astral.sh/uv/getting-started/installation/#standalone-installer
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.profile
ENV PATH="/root/.local/bin:${PATH}"

# 가상환경 생성 및 활성화 경로 추가
RUN uv venv /server/.venv
ENV VIRTUAL_ENV=/server/.venv
ENV PATH="/server/.venv/bin:${PATH}"

# 의존성 파일 복사 및 uv로 설치
COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt

# 소스 코드 복사
COPY . .

# 포트 노출
EXPOSE 21009

# 애플리케이션 실행 (새로운 구조에 맞게 수정)
CMD ["python", "src/main.py"]