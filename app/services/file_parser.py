import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from geoalchemy2 import WKTElement
from shapely import wkt as shapely_wkt
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.models import SpatialData

SUPPORTED_EXTENSIONS = {".zip", ".geojson", ".json", ".csv"}


def parse_upload_file(
    file_path: str,
    file_ext: str,
    category: str,
    region_name: Optional[str],
    file_id: int,
    db: Session,
) -> int:
    gdf = _read_to_gdf(file_path, file_ext)

    # CRS가 없으면 WGS84 기본 설정, 다른 CRS면 변환
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    records = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        props = {}
        for col in gdf.columns:
            if col == "geometry":
                continue
            val = row[col]
            # null 값 제외
            try:
                if pd.isna(val):
                    continue
            except (TypeError, ValueError):
                pass
            # numpy 스칼라 → Python 기본 타입 변환
            props[col] = val.item() if hasattr(val, "item") else val

        records.append(SpatialData(
            original_file_id=file_id,
            category=category,
            region_name=region_name,
            geom=WKTElement(geom.wkt, srid=4326),
            properties=props,
        ))

    if not records:
        raise ValueError("파일 내 유효한 공간 데이터가 없습니다.")

    db.add_all(records)
    db.commit()
    return len(records)


def _read_to_gdf(file_path: str, file_ext: str) -> gpd.GeoDataFrame:
    if file_ext == ".zip":
        # SHP ZIP: 압축 해제 후 .shp 파일 탐색 (중첩 폴더 포함)
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(file_path, "r") as z:
                z.extractall(tmpdir)
            shp_files = list(Path(tmpdir).rglob("*.shp"))
            if not shp_files:
                raise ValueError("ZIP 파일 내에 .shp 파일이 없습니다.")
            return gpd.read_file(str(shp_files[0]))

    if file_ext in (".geojson", ".json"):
        return gpd.read_file(file_path)

    if file_ext == ".csv":
        df = pd.read_csv(file_path)

        # WKT 컬럼 자동 감지 (wkt / geom / geometry / the_geom)
        wkt_col = next(
            (c for c in df.columns if c.lower() in ("wkt", "geom", "geometry", "the_geom")),
            None,
        )
        if wkt_col:
            df["geometry"] = df[wkt_col].apply(shapely_wkt.loads)
            return gpd.GeoDataFrame(df.drop(columns=[wkt_col]), geometry="geometry", crs="EPSG:4326")

        # 위경도 컬럼 자동 감지
        lat_col = next(
            (c for c in df.columns if c.lower() in ("lat", "latitude", "위도", "y")), None
        )
        lon_col = next(
            (c for c in df.columns if c.lower() in ("lon", "lng", "longitude", "경도", "x")), None
        )
        if lat_col and lon_col:
            geometry = [Point(lon, lat) for lon, lat in zip(df[lon_col], df[lat_col])]
            return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

        raise ValueError(
            "CSV 파일에 공간 컬럼이 없습니다.\n"
            "WKT 컬럼(wkt/geom/geometry) 또는 위경도 컬럼(lat/lon, 위도/경도)이 필요합니다."
        )

    raise ValueError(f"지원하지 않는 파일 형식입니다: {file_ext}")