from pydantic import BaseModel
from typing import Optional, Dict

# 사용자가 API로 보내는 요청 데이터 구조
class DownloadRequest(BaseModel):
    category: str
    target_format: str
    filters: Optional[Dict] = None  # 추가 필터링 조건

# 서버가 응답하는 데이터 구조
class TaskResponse(BaseModel):
    task_id: int
    status: str
    message: str