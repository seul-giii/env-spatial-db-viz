from typing import Dict, Literal, Optional
from pydantic import BaseModel

class DownloadRequest(BaseModel):
    category: str
    target_format: Literal["CSV", "EXCEL", "SHP", "GeoJSON", "GEOJSON"]
    filters: Optional[Dict[str, str]] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str