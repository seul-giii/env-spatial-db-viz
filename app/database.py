from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# DB 주소
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:0617@localhost:5432/capstone_gis"

# DB 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# DB 세션 생성기
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 모델의 기본 클래스
Base = declarative_base()

# DB 세션 의존성 주입 함수 (API 호출 시 사용)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()