from fastapi import FastAPI
from app.routers import download
from app.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware

# DB 테이블 자동 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EnvData Spatial API",
    description="공간 데이터 다운로드 및 변환 서비스",
    version="1.0.0"
)

# 다운로드 API 라우터 등록
app.include_router(download.router, tags=["Download"])

@app.get("/")
def read_root():
    return {"message": "EnvData API 서버가 정상적으로 실행 중입니다."}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)