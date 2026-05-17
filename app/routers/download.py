import os
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import DownloadTask, File
from app.schemas import DownloadRequest, TaskResponse, TaskStatusResponse

from app.services.data_export_service import DataExportService
from app.services.s3_uploader import generate_presigned_url, upload_to_s3

router = APIRouter()

def process_export_task(task_id: UUID, category: str, target_format: str, region_name: Optional[str],
                        filters: Optional[dict], bbox: Optional[list]):
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

        export_service = DataExportService()

        if region_name:
            if not filters:
                filters = {}
            filters["region_name"] = region_name

        result_json = export_service.export_spatial_data(
            task_id=str(task_id),
            category=category,
            target_format=target_format,
            bbox=bbox,
            filters=filters
        )

        result = json.loads(result_json)

        # 에러 발생 시 처리
        if result.get("status") == "FAILED":
            raise Exception(result.get("error"))

        # 정상적으로 생성된 로컬 파일 경로 확보
        generated_file_path = result.get("file_path")
        print(f"✅ [Task ID: {task_id}] 로컬 파일 생성 완료! 위치: {generated_file_path}")

        # S3 업로드
        file_name = os.path.basename(generated_file_path)
        s3_key = upload_to_s3(generated_file_path, file_name)
        print(f"✅ [Task ID: {task_id}] S3 업로드 완료!")

        #  FILES 테이블에 S3 키 기록
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

        # DOWNLOAD_TASKS 상태 업데이트
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
                task.progress = 0
                db.commit()
        except Exception:
            pass

    finally:
        # 성공/실패 무관하게 서버 용량 관리를 위해 임시 파일 삭제
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
        status="PENDING",
        request_params={
            "category": request.category,
            "target_format": request.target_format,
            "region_name": request.region_name,
            "filters": request.filters,
            "bbox": request.bbox
        }
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    background_tasks.add_task(
        process_export_task,
        task_id=new_task.id,
        category=request.category,
        target_format=request.target_format,
        region_name=request.region_name,
        filters=request.filters,
        bbox=request.bbox
    )

    return TaskResponse(
        task_id=str(new_task.id),
        status=new_task.status,
        message="다운로드 작업이 서버 백그라운드에서 시작되었습니다."
    )


@router.get("/spatial/task/{task_id}", response_model=TaskStatusResponse)
def check_task_status(task_id: UUID, db: Session = Depends(get_db)):
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다.")

    response_data = {
        "task_id": str(task.id),
        "status": task.status,
        "target_format": task.target_format,
        "progress": task.progress,
        "download_url": None
    }

    # COMPLETED 상태일 때 Presigned URL을 동적으로 생성 (만료 1시간)
    if task.status == "COMPLETED" and task.result_file_id:
        result_file = db.query(File).filter(File.id == task.result_file_id).first()
        if result_file and result_file.s3_path:
            response_data["download_url"] = generate_presigned_url(result_file.s3_path)

    return response_data


@router.get("/spatial/tasks")
def list_tasks(
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        db: Session = Depends(get_db)
):
    query = db.query(DownloadTask).order_by(DownloadTask.created_at.desc())
    if status:
        query = query.filter(DownloadTask.status == status)
    tasks = query.offset(offset).limit(limit).all()

    return [{"task_id": str(t.id), "status": t.status, "target_format": t.target_format, "progress": t.progress} for t
            in tasks]