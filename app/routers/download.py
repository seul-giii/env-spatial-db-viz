from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import DownloadTask
from app.schemas import DownloadRequest, TaskResponse
from app.services.data_export_service import generate_export_file

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

        # TODO: 2. 여기서 S3 업로드 로직이 들어갈 예정입니다. (다음 스텝)

        # 3. DB 상태를 COMPLETED로 업데이트
        task.status = "COMPLETED"
        task.completed_at = datetime.now()
        db.commit()

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