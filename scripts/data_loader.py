import os
import json
from datetime import datetime
import pandas as pd
import geopandas as gpd
import rasterio
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from psycopg2.extras import execute_values

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env_path, override=True)

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("❌ DATABASE_URL 환경 변수가 설정되지 않았습니다.")
engine = create_engine(DB_URL)


class SpatialDataLoader:
    def __init__(self, engine):
        self.engine = engine

    def load_vector_data(self, file_path, category_name, encoding='utf-8', source_crs=None, region_column=None):
        try:
            print(f"[{category_name}] 벡터 데이터 로딩 시작: {file_path}")
            gdf = gpd.read_file(file_path, encoding=encoding, engine="pyogrio")

            if gdf.crs is None and source_crs:
                gdf.set_crs(source_crs, inplace=True)
            if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                print(f"[{category_name}] 좌표계 변환 수행 -> EPSG:4326")
                gdf = gdf.to_crs(epsg=4326)

            # 파일 이름과 용량 추출
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            with self.engine.begin() as conn:
                file_insert_sql = text("""
                                    INSERT INTO files (file_type, format, file_name, file_size, s3_path, created_at)
                                    VALUES ('ORIGINAL', 'SHP', :file_name, :file_size, :s3_path, CURRENT_TIMESTAMP)
                                    RETURNING id
                                """)
                result = conn.execute(file_insert_sql, {
                    "file_name": file_name,
                    "file_size": file_size,
                    "s3_path": "LOCAL_ORIGINAL"
                })
                new_file_id = result.scalar()

                print(f"[{category_name}] 원본 파일 등록 완료 (FILES ID: {new_file_id})")

                insert_sql = text("""
                    INSERT INTO spatial_data (category, geom, properties, original_file_id, region_name)
                    VALUES (:category, ST_GeomFromText(:geom, 4326), :properties, :original_file_id, :region_name)
                """)

                print(f"[{category_name}] 데이터 변환 및 Bulk Insert 준비 중...")

                # 1. 속성 데이터를 한 번에 딕셔너리로 변환
                df_props = gdf.drop(columns=['geometry'])
                df_props = df_props.astype(object).where(pd.notnull(df_props), None)
                props_records = df_props.to_dict(orient='records')

                bulk_data = []

                for i, geom in enumerate(gdf['geometry']):
                    props = props_records[i]
                    props_json = json.dumps(props, ensure_ascii=False, default=str, allow_nan=False)
                    geom_wkt = geom.wkt if geom else None
                    extracted_region = props.get(region_column) if region_column else None

                    bulk_data.append((
                        category_name,
                        geom_wkt,
                        props_json,
                        new_file_id,
                        extracted_region,
                    ))

                raw_conn = conn.connection
                with raw_conn.cursor() as cur:
                    execute_values(
                        cur,
                        """
                        INSERT INTO spatial_data (category, geom, properties, original_file_id, region_name)
                        VALUES %s
                        """,
                        bulk_data,
                        template="(%s, ST_GeomFromText(%s, 4326), %s, %s, %s)",
                        page_size=10000,
                    )
                print(f"[{category_name}] {len(bulk_data)}건 적재 완료")

        except Exception as e:
            print(f"❌ [{category_name}] 적재 중 에러 발생: {e}")

    def load_raster_metadata(self, file_path, category_name):
        try:
            print(f"[{category_name}] 래스터 데이터 분석 시작: {file_path}")

            # 파일 이름과 용량 추출
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            with rasterio.open(file_path) as src:
                metadata = {
                    "width": src.width,
                    "height": src.height,
                    "bounds": list(src.bounds),
                    "crs": str(src.crs),
                    "pixel_size": [src.transform[0], abs(src.transform[4])]
                }

                with self.engine.begin() as conn:
                    #래스터 원본 파일 정보 등록
                    file_insert_sql = text("""
                                            INSERT INTO files (file_type, format, file_name, file_size, s3_path, created_at)
                                            VALUES ('ORIGINAL', 'TIF', :file_name, :file_size, :s3_path, CURRENT_TIMESTAMP)
                                            RETURNING id
                                        """)
                    result = conn.execute(file_insert_sql, {
                        "file_name": file_name,
                        "file_size": file_size,
                        "s3_path": "LOCAL_ORIGINAL"
                    })
                    new_file_id = result.scalar()

                    #발급된 ID로 공간 메타데이터 적재
                    insert_sql = text("""
                        INSERT INTO spatial_data (category, properties, original_file_id, region_name)
                        VALUES (:category, :properties, :original_file_id, :region_name)
                    """)
                    conn.execute(insert_sql, {
                        "category": category_name,
                        "properties": json.dumps(metadata, ensure_ascii=False),
                        "original_file_id": new_file_id,
                        "region_name": None
                    })
            print(f"[{category_name}] 메타데이터 적재 완료! (FILES ID: {new_file_id})")
        except Exception as e:
            print(f"❌ [{category_name}] 에러: {e}")


if __name__ == "__main__":
    loader = SpatialDataLoader(engine)

    print("🚀 [ETL 파이프라인 시작] 데이터 적재를 시작합니다...\n")

    # ==========================================
    # [그룹 B] 자연 데이터
    # ==========================================
    # 1. 수문지질도
    loader.load_vector_data(
        "G:/.shortcut-targets-by-id/1SM2FGxQUujBXwlyhAaxbOfanlHVrwLgQ/3. 수문지질도/한국수문지질도.shp",
        "지하수",
        encoding="cp949",
        region_column=None
    )

    # 9. 지하수 등수위선
    loader.load_vector_data(
        "G:/.shortcut-targets-by-id/1awuSjLLy9UJd96DiCXTC8RDPWsM0FqmA/W_HG_POTENTIONMETRIC_WGS_L/W_HG_POTENTIONMETRIC_WGS_L.shp",
        "지하수 등수위선",
        encoding="utf-8",
        region_column=None
    )

    # 6. K31UJB100 (하천구역)
    loader.load_vector_data(
        "G:/.shortcut-targets-by-id/16aO4uHzDMPBQblM6SkCTMvnBxiwUzAcm/K31UJB100/하천구역.shp",
        "하천구역",
        encoding="cp949",
        region_column=None
    )

    # 8. 수질 악화 위험 (2024 중분류 토지피복)
    #loader.load_vector_data(
    #    "G:/.shortcut-targets-by-id/1q9L9MjQbBm6E9JGAjzm8u2XVRQ_tPpXW/Q_수질악화위험/2024_중분류토지피복_simplify.shp",
    #    "중분류 토지피복",
    #    encoding="cp949",
    #    region_column=None
    #)

    # ==========================================
    # [그룹 A] 행정구역 데이터
    # ==========================================
    # 2. 불투수면 비율
    loader.load_vector_data(
        "G:/.shortcut-targets-by-id/1JUPia2jlTQYOjSRgYBrVvvG1hIhFczlQ/불투수면 비율/시군구_불투수면_비율.shp",
        "불투수면 비율",
        encoding="cp949",
        region_column="ADM_NM"
    )

    # 4. 지하수 산출량 (양수량)
    loader.load_vector_data(
        "G:/.shortcut-targets-by-id/1bDyLYoIQtlSE82br4l-dvaW2GyVLl6qk/지하수_산출량도_(양수량)/지하수산출량도_양수량.shp",
        "지하수 산출량(양수량)",
        encoding="cp949",
        region_column="SGG"
    )

    # 5. 지하수 산출량 (투수량계수)
    loader.load_vector_data(
        "G:/.shortcut-targets-by-id/1YSjF2wQIA52raGzuCyW3Ykj_Rt9SzAfn/지하수_산출량도_(투수량계수)/지하수산출량도_투수량계수.shp",
        "지하수 산출량(투수량계수)",
        encoding="cp949",
        region_column="SGG"
    )

    # ==========================================
    # [그룹 C] 래스터 데이터 대상 (TIF 메타데이터)
    # ==========================================
    loader.load_raster_metadata(
        "G:/.shortcut-targets-by-id/1ApxkQL-oUVnPJmz_66MbJX7__OKiHMwZ/연간_지하수_재충전(annual_Recharge)/annual_recharge.tif",
        "연간 지하수 재충전")
    loader.load_raster_metadata(
        "G:/.shortcut-targets-by-id/1QaNjtxZFutNmYpwUZbyyy35GSa5Lpq8p/Q_수질기준적합성/IDW_Q_지표수 유기오염물질.tif", "지표수 유기오염")
    loader.load_raster_metadata(
        "G:/.shortcut-targets-by-id/1QaNjtxZFutNmYpwUZbyyy35GSa5Lpq8p/Q_수질기준적합성/IDW_Q_지하수질산염.tif", "지하수 질산성질소")
    loader.load_raster_metadata(
        "G:/.shortcut-targets-by-id/1QaNjtxZFutNmYpwUZbyyy35GSa5Lpq8p/Q_수질기준적합성/Idw_Q_해수침투1.tif", "해수침투 지수")

    print("\n🎉 [ETL 파이프라인 종료] 모든 작업이 완료되었습니다!")