FROM python:3.12-slim

WORKDIR /server

# PostgreSQL 관련 라이브러리 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    zlib1g-dev \
    libpq-dev \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 포트 노출
EXPOSE 21009

# 애플리케이션 실행 (새로운 구조에 맞게 수정)
CMD ["python", "src/main.py"]