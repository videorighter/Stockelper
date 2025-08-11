import logging
import sys
import os
import dotenv

# 환경 변수 로딩을 최우선으로 처리
dotenv.load_dotenv(override=True)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.stock import router as stock_router
from routers.base import router as base_router


DEBUG = False
HOST = "0.0.0.0"
PORT = 21009

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# FastAPI 애플리케이션 생성
app = FastAPI(debug=DEBUG)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(base_router)
app.include_router(stock_router)

if __name__ == "__main__":
    try:
        print(f"🚀 Starting Stockelper LLM Server...")
        print(f"📍 Server will run on http://{HOST}:{PORT}")
        print(f"🔧 Debug mode: {DEBUG}")
        
        uvicorn.run(
            app, 
            host=HOST, 
            port=PORT, 
            reload=DEBUG,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1) 