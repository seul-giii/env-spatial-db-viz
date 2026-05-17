import re
from datetime import datetime
from typing import Dict, Literal, Optional, List

from pydantic import BaseModel, field_validator


class DownloadRequest(BaseModel):
    category: str
    target_format: Literal["CSV", "EXCEL", "SHP", "GEOJSON"]
    region_name: Optional[str] = None
    filters: Optional[Dict[str, str]] = None
    bbox: Optional[List[float]] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9가-힣_-]{1,50}$', v):
            raise ValueError("category는 1~50자의 영문, 한글, 숫자, _, - 만 허용됩니다.")
        return v


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    target_format: str
    progress: int = 0
    download_url: Optional[str] = None


class UploadResponse(BaseModel):
    file_id: int
    file_name: str
    record_count: int
    message: str

class FileResponse(BaseModel):
    id: int
    file_name: str
    format: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True