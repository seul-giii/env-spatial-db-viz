import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from app.database import Base
from datetime import datetime, timezone


class File(Base):
    __tablename__ = "files"
    id = Column(BigInteger, primary_key=True, index=True)
    file_type = Column(String)
    format = Column(String)
    s3_path = Column(String)
    file_name = Column(String)
    file_size = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SpatialData(Base):
    __tablename__ = "spatial_data"
    id = Column(BigInteger, primary_key=True, index=True)

    original_file_id = Column(BigInteger, ForeignKey("files.id"), nullable=True)
    region_name = Column(String, nullable=True)

    category = Column(String, index=True)
    geom = Column(Geometry('GEOMETRY', srid=4326))
    properties = Column(JSONB)


class DownloadTask(Base):
    __tablename__ = "download_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    request_params = Column(JSONB)
    target_format = Column(String)
    status = Column(String, default="PENDING")
    progress = Column(Integer, default=0)
    result_file_id = Column(BigInteger, ForeignKey("files.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))