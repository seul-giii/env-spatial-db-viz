import os
import psycopg2
import sys
import pandas as pd
import json
import geopandas as gpd
import rasterio
from sqlalchemy import create_engine, text
from geoalchemy2.shape import from_shape
from datetime import datetime

from sqlalchemy.engine import row

# DB 연결 설정 (PostgreSQL + PostGIS)
DB_URL = "postgresql://postgres:0617@localhost:5432/capstone_gis"
engine = create_engine(DB_URL)

class SpatialDataLoader:
    def __init__(self, engine):
        self.engine = engine

    def load_vector_data(self, file_path, category_name, encoding='utf-8', source_crs=None):
        try:
            print(f"[{category_name}] 벡터 데이터 로딩 시작: {file_path}")

            # 1. 데이터 읽기
            gdf = gpd.read_file(file_path, encoding=encoding)

            # 2. 좌표계 설정 및 변환
            if gdf.crs is None and source_crs:
                gdf.set_crs(source_crs, inplace=True)

            if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                print(f"[{category_name}] 좌표계 변환 수행 -> EPSG:4326")
                gdf = gdf.to_crs(epsg=4326)

            # 3. DB 적재
            with self.engine.begin() as conn:
                for _, row in gdf.iterrows():
                    # 속성 데이터 추출 (geometry 제외)
                    props = row.drop('geometry').to_dict()

                    # NaN(결측치) 값을 JSON 표준인 null(None)로 안전하게 변환
                    clean_props = {}
                    for k, v in props.items():
                        if pd.isna(v):  # 값이 비어있다면 (NaN, NaT 등)
                            clean_props[k] = None
                        else:
                            clean_props[k] = v

                    # 정화된 딕셔너리로 JSON 생성
                    props_json = json.dumps(clean_props, ensure_ascii=False, default=str)

                    # PostGIS geometry 생성 (WKT 텍스트 방식)
                    geom_wkt = row['geometry'].wkt if row['geometry'] else None

                    sql = text("""
                        INSERT INTO SPATIAL_DATA (category, geom, properties, created_at)
                        VALUES (:category, ST_GeomFromText(:geom, 4326), :properties, :created_at)
                    """)

                    conn.execute(sql, {
                        "category": category_name,
                        "geom": geom_wkt,
                        "properties": props_json,
                        "created_at": datetime.now()
                    })

            print(f"[{category_name}] 적재 완료! ({len(gdf)}건)")

        except Exception as e:
            print(f"❌ [{category_name}] 적재 중 에러 발생: {e}")

    def load_raster_metadata(self, file_path, category_name):
        try:
            print(f"[{category_name}] 래스터 데이터 분석 시작: {file_path}")
            with rasterio.open(file_path) as src:
                metadata = {
                    "width": src.width,
                    "height": src.height,
                    "bounds": list(src.bounds),
                    "crs": str(src.crs),
                    "pixel_size": [src.transform[0], abs(src.transform[4])]
                }

                with self.engine.begin() as conn:
                    sql = text("""
                        INSERT INTO SPATIAL_DATA (category, properties, created_at)
                        VALUES (:category, :properties, :created_at)
                    """)
                    conn.execute(sql, {
                        "category": category_name,
                        "properties": json.dumps(metadata, ensure_ascii=False),
                        "created_at": datetime.now()
                    })
            print(f"[{category_name}] 메타데이터 적재 완료!")
        except Exception as e:
            print(f"❌ [{category_name}] 에러: {e}")


if __name__ == "__main__":
    loader = SpatialDataLoader(engine)

    print("🚀 [ETL 파이프라인 시작] 데이터 적재를 시작합니다...\n")

    # [그룹 B]
    # 1. 수문지질도
    loader.load_vector_data("G:/.shortcut-targets-by-id/1SM2FGxQUujBXwlyhAaxbOfanlHVrwLgQ/3. 수문지질도/한국수문지질도.shp", "수문지질도", encoding="cp949", source_crs="EPSG:4326")

    # 9. 지하수 등수위선
    loader.load_vector_data("G:/.shortcut-targets-by-id/1awuSjLLy9UJd96DiCXTC8RDPWsM0FqmA/W_HG_POTENTIONMETRIC_WGS_L/W_HG_POTENTIONMETRIC_WGS_L.shp", "지하수 등수위선",
                            encoding="utf-8", source_crs="EPSG:4326")

    # [그룹 A]
    # 2. 불투수면 비율
    loader.load_vector_data("G:/.shortcut-targets-by-id/1JUPia2jlTQYOjSRgYBrVvvG1hIhFczlQ/불투수면 비율/시군구_불투수면_비율.shp", "불투수면 비율", encoding="cp949")

    # 4. 지하수 산출량 (양수량)
    loader.load_vector_data("G:/.shortcut-targets-by-id/1bDyLYoIQtlSE82br4l-dvaW2GyVLl6qk/지하수_산출량도_(양수량)/지하수산출량도_양수량.shp", "지하수 산출량(양수량)", encoding="cp949")

    # 5. 지하수 산출량 (투수량계수)
    loader.load_vector_data(
        "G:/.shortcut-targets-by-id/1YSjF2wQIA52raGzuCyW3Ykj_Rt9SzAfn/지하수_산출량도_(투수량계수)/지하수산출량도_투수량계수.shp",
        "지하수 산출량(투수량계수)", encoding="cp949")

    # 6. K31UJB100 (하천구역)
    loader.load_vector_data("G:/.shortcut-targets-by-id/16aO4uHzDMPBQblM6SkCTMvnBxiwUzAcm/K31UJB100/하천구역.shp", "하천구역", encoding="cp949")

    # 8. 수질 악화 위험 (2024 중분류 토지피복)
    loader.load_vector_data("G:/.shortcut-targets-by-id/1q9L9MjQbBm6E9JGAjzm8u2XVRQ_tPpXW/Q_수질악화위험/2024_중분류토지피복_simplify.shp", "중분류 토지피복", encoding="cp949")


    # [그룹 C] 래스터 데이터 대상 (분석 엔진용 TIF 메타데이터 추출)
    # 3. 연간 지하수 재충전
    loader.load_raster_metadata("G:/.shortcut-targets-by-id/1ApxkQL-oUVnPJmz_66MbJX7__OKiHMwZ/연간_지하수_재충전(annual_Recharge)/annual_recharge.tif", "연간 지하수 재충전")

    # 7. 수질 기준 적합성
    loader.load_raster_metadata("G:/.shortcut-targets-by-id/1QaNjtxZFutNmYpwUZbyyy35GSa5Lpq8p/Q_수질기준적합성/IDW_Q_지표수 유기오염물질.tif", "지표수 유기오염")
    loader.load_raster_metadata("G:/.shortcut-targets-by-id/1QaNjtxZFutNmYpwUZbyyy35GSa5Lpq8p/Q_수질기준적합성/IDW_Q_지하수질산염.tif", "지하수 질산성질소")
    loader.load_raster_metadata("G:/.shortcut-targets-by-id/1QaNjtxZFutNmYpwUZbyyy35GSa5Lpq8p/Q_수질기준적합성/Idw_Q_해수침투1.tif", "해수침투 지수")

    print("\n🎉 [ETL 파이프라인 종료] 모든 작업이 완료되었습니다!")