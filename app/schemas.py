from typing import Dict, Literal, Optional
from pydantic import BaseModel, field_validator
import re

class DownloadRequest(BaseModel):
    category: str
    target_format: Literal["CSV", "EXCEL", "SHP", "GeoJSON", "GEOJSON"]
    filters: Optional[Dict[str, str]] = None

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
    download_url: Optional[str] = None