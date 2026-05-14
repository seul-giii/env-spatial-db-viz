import os
import re
import tempfile
import uuid as uuid_lib
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import File as FileModel
from app.schemas import UploadResponse, FileResponse
from app.services.file_parser import SUPPORTED_EXTENSIONS, parse_upload_file
from app.services.s3_uploader import upload_to_s3

router = APIRouter()

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
_CATEGORY_RE = re.compile(r'^[a-zA-Z0-9가-힣_-]{1,50}$')


@router.post("/spatial/upload", response_model=UploadResponse)
async def upload_spatial_file(
    file: UploadFile = File(..., description="SHP(ZIP), GeoJSON, CSV 파일"),
    category: str = Form(..., description="레이어 분류명 (예: 지하수, 수질)"),
    region_name: Optional[str] = Form(None, description="지역명 (예: 서울)"),
    db: Session = Depends(get_db),
):

    if not _CATEGORY_RE.match(category):
        raise HTTPException(
            status_code=422,
            detail="category는 1~50자의 영문, 한글, 숫자, _, - 만 허용됩니다.",
        )

    original_name = file.filename or "upload"
    file_ext = os.path.splitext(original_name)[1].lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 허용: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="파일 크기는 100MB를 초과할 수 없습니다.")

    tmp_path: Optional[str] = None
    file_record: Optional[FileModel] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        # 1. S3에 원본 파일 저장 (uploads/ prefix)
        unique_name = f"{uuid_lib.uuid4().hex}_{original_name}"
        s3_key = upload_to_s3(tmp_path, unique_name, prefix="uploads")

        # 2. FILES 테이블에 ORIGINAL 기록
        file_record = FileModel(
            file_name=original_name,
            file_size=len(contents),
            format=file_ext.lstrip(".").upper(),
            s3_path=s3_key,
            file_type="ORIGINAL",
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        # 3. 파싱 → SPATIAL_DATA 저장
        record_count = parse_upload_file(
            file_path=tmp_path,
            file_ext=file_ext,
            category=category,
            region_name=region_name,
            file_id=file_record.id,
            db=db,
        )

        return UploadResponse(
            file_id=file_record.id,
            file_name=original_name,
            record_count=record_count,
            message=f"업로드 완료. {record_count}개의 공간 데이터가 저장되었습니다.",
        )

    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        if file_record:
            db.delete(file_record)
            db.commit()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        if file_record:
            try:
                db.delete(file_record)
                db.commit()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"업로드 처리 중 오류: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.get("/spatial/files", response_model=list[FileResponse])
def list_files(file_type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(FileModel).order_by(FileModel.created_at.desc())
    if file_type:
        query = query.filter(FileModel.file_type == file_type)
    return query.limit(50).all()