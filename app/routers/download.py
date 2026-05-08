from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import DownloadTask
from app.schemas import DownloadRequest, TaskResponse
from app.services.data_export_service import generate_export_file
from app.services.s3_uploader import upload_to_s3_and_get_url
import os
from app.models import File
from fastapi import HTTPException

router = APIRouter()

def process_export_task(task_id: int, category: str, target_format: str, db: Session):

    print(f"[Task ID: {task_id}] 백그라운드 파일 생성 작업을 시작합니다...")

    # DB에서 상태를 PROCESSING으로 변경
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    if task:
        task.status = "PROCESSING"
        db.commit()

    try:
        # 1. 파일 생성 모듈 호출
        generated_file_path = generate_export_file(db, category, target_format)
        print(f"✅ [Task ID: {task_id}] 파일 생성 완료! 위치: {generated_file_path}")

        # 2. S3 업로드 및 Presigned URL 획득
        file_name = os.path.basename(generated_file_path)
        download_url = upload_to_s3_and_get_url(generated_file_path, file_name)
        print(f"✅ [Task ID: {task_id}] S3 업로드 완료! 다운로드 링크 발급 완료")

        # 3. DB FILES 테이블에 기록 (ERD 반영)
        new_file_record = File(
            file_name=file_name,
            file_size=os.path.getsize(generated_file_path),
            format=target_format.upper(),
            s3_path=download_url,
            file_type="EXPORT"
        )
        db.add(new_file_record)
        db.commit()
        db.refresh(new_file_record)

        # 4. DB DOWNLOAD_TASKS 테이블 상태 및 연결 업데이트
        task.result_file_id = new_file_record.id
        task.status = "COMPLETED"
        task.completed_at = datetime.now()
        db.commit()

        # 5. 서버 용량 확보를 위해 로컬에 남은 임시 파일 삭제
        if os.path.exists(generated_file_path):
            os.remove(generated_file_path)

    except Exception as e:
        print(f"❌ [Task ID: {task_id}] 작업 실패: {str(e)}")
        if task:
            task.status = "FAILED"
            db.commit()


@router.post("/spatial/query", response_model=TaskResponse)
def request_download(
        request: DownloadRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    # 1. DB에 PENDING 상태로 작업 등록
    new_task = DownloadTask(
        target_format=request.target_format.upper(),
        status="PENDING"
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    # 2. 백그라운드 작업 예약
    background_tasks.add_task(
        process_export_task,
        task_id=new_task.id,
        category=request.category,
        target_format=request.target_format,
        db=db
    )

    # 3. 사용자에게 즉시 응답 반환
    return TaskResponse(
        task_id=new_task.id,
        status=new_task.status,
        message="다운로드 작업이 서버 백그라운드에서 시작되었습니다."
    )


@router.get("/spatial/task/{task_id}")
def check_task_status(task_id: int, db: Session = Depends(get_db)):
    """
    프론트엔드가 task_id를 가지고 작업 진행 상황과 최종 S3 다운로드 링크를 확인하는 API
    """
    # 1. 작업(Task) 조회
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다.")

    # 2. 결과 응답 구성
    response_data = {
        "task_id": task.id,
        "status": task.status,  # PENDING, PROCESSING, COMPLETED, FAILED
        "target_format": task.target_format,
        "download_url": None
    }

    # 3. 작업이 완료되었다면 FILES 테이블을 조회하여 S3 링크를 꺼내옴.
    if task.status == "COMPLETED" and task.result_file_id:
        result_file = db.query(File).filter(File.id == task.result_file_id).first()
        if result_file:
            response_data["download_url"] = result_file.s3_path

    return response_data