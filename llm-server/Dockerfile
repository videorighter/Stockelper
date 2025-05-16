FROM python:3.12-slim

WORKDIR /server

# PostgreSQL 관련 라이브러리 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 21009

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "21009"]