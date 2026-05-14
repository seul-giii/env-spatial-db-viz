import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import DownloadTask, File
from app.schemas import DownloadRequest, TaskResponse, TaskStatusResponse
from app.services.data_export_service import generate_export_file
from app.services.s3_uploader import generate_presigned_url, upload_to_s3



router = APIRouter()


def process_export_task(task_id: int, category: str, target_format: str, filters: Optional[dict]):
    db: Session = SessionLocal()
    generated_file_path: Optional[str] = None

    try:
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        if not task:
            print(f"❌ [Task ID: {task_id}] 작업을 찾을 수 없습니다.")
            return

        task.status = "PROCESSING"
        task.progress = 50
        db.commit()

        print(f"[Task ID: {task_id}] 백그라운드 파일 생성 작업을 시작합니다...")

        # 1. 파일 생성
        generated_file_path = generate_export_file(db, category, target_format, filters)
        print(f"✅ [Task ID: {task_id}] 파일 생성 완료! 위치: {generated_file_path}")

        # 2. S3 업로드 → S3 키 저장 (URL은 조회 시점에 동적 생성)
        file_name = os.path.basename(generated_file_path)
        s3_key = upload_to_s3(generated_file_path, file_name)
        print(f"✅ [Task ID: {task_id}] S3 업로드 완료!")

        # 3. FILES 테이블에 S3 키 기록
        new_file_record = File(
            file_name=file_name,
            file_size=os.path.getsize(generated_file_path),
            format=target_format.upper(),
            s3_path=s3_key,
            file_type="EXPORT"
        )
        db.add(new_file_record)
        db.commit()
        db.refresh(new_file_record)

        # 4. DOWNLOAD_TASKS 상태 업데이트
        task.result_file_id = new_file_record.id
        task.progress = 100
        task.status = "COMPLETED"
        db.commit()

    except Exception as e:
        print(f"❌ [Task ID: {task_id}] 작업 실패: {str(e)}")
        try:
            task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
            if task:
                task.status = "FAILED"
                db.commit()
        except Exception:
            pass

    finally:
        # 성공/실패 무관하게 임시 파일 삭제
        if generated_file_path and os.path.exists(generated_file_path):
            os.remove(generated_file_path)
        db.close()


@router.post("/spatial/query", response_model=TaskResponse)
def request_download(
        request: DownloadRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    new_task = DownloadTask(
        target_format=request.target_format.upper(),
        status="PENDING"
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    background_tasks.add_task(
        process_export_task,
        task_id=new_task.id,
        category=request.category,
        target_format=request.target_format,
        filters=request.filters,
    )

    return TaskResponse(
        task_id=str(new_task.id),
        status=new_task.status,
        message="다운로드 작업이 서버 백그라운드에서 시작되었습니다."
    )


@router.get("/spatial/task/{task_id}", response_model=TaskStatusResponse)
def check_task_status(task_id: UUID, db: Session = Depends(get_db)):
    """
    프론트엔드가 task_id로 작업 진행 상황과 S3 다운로드 링크를 확인하는 API
    """
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다.")

    response_data = {
        "task_id": task.id,
        "status": task.status,
        "target_format": task.target_format,
        "download_url": None
    }

    # COMPLETED 상태일 때 Presigned URL을 동적으로 생성 (만료 1시간)
    if task.status == "COMPLETED" and task.result_file_id:
        result_file = db.query(File).filter(File.id == task.result_file_id).first()
        if result_file and result_file.s3_path:
            response_data["download_url"] = generate_presigned_url(result_file.s3_path)

    return response_data

