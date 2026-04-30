from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from app.database import Base


class SpatialData(Base):
    __tablename__ = "spatial_data"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False)
    properties = Column(JSON)
    geom = Column(Geometry('GEOMETRY', srid=4326))
    created_at = Column(DateTime, server_default=func.now())


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger)
    format = Column(String(50))
    s3_path = Column(String)
    file_type = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())


class DownloadTask(Base):
    __tablename__ = "download_tasks"

    id = Column(Integer, primary_key=True, index=True)
    result_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    user_id = Column(Integer, nullable=True)
    target_format = Column(String(50), nullable=False)
    status = Column(String(50), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())