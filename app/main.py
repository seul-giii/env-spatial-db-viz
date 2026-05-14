from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import download, upload

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EnvData Spatial API",
    description="공간 데이터 다운로드 및 변환 서비스",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(download.router, tags=["Download"])
app.include_router(upload.router, tags=["Upload"])

@app.get("/")
def read_root():
    return {"message": "EnvData API 서버가 정상적으로 실행 중입니다."}