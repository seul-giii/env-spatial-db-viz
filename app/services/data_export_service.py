import os
import json
import logging
from datetime import datetime
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
from shapely import wkt

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(BASE_DIR, '.env')

# 환경 변수 로드
if os.path.exists(env_path):
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=env_path, override=True)

DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL) if DB_URL else None


class DataExportService:
    def __init__(self, db_engine=None):
        self.engine = db_engine or engine
        if not self.engine:
            raise ValueError("❌ DATABASE_URL 환경 변수가 설정되지 않았거나 엔진이 없습니다.")

    def export_spatial_data(self, task_id: str, category: str, target_format: str, bbox: list = None,
                            filters: dict = None) -> str:

        # 1. 사용자 터미널 로그 규격 맞춤 출력
        logger.info(f"[Task ID: {task_id}] 백그라운드 파일 생성 작업을 시작합니다...")
        logger.info(f"[데이터 추출 시작] 카테고리: {category}, 포맷: {target_format.upper()}")

        try:
            # 2. 동적 SQL 쿼리 작성
            query_str = """
                SELECT id, category, properties, region_name, ST_AsText(geom) as geom_wkt
                FROM spatial_data
                WHERE category = :category
            """
            params = {"category": category}

            if bbox and len(bbox) == 4:
                # bbox 순서: [min_x, min_y, max_x, max_y] (경도_min, 위도_min, 경도_max, 위도_max)
                query_str += """
                    AND ST_Intersects(
                        geom, 
                        ST_MakeEnvelope(:min_x, :min_y, :max_x, :max_y, 4326)
                    )
                """
                params.update({
                    "min_x": bbox[0],
                    "min_y": bbox[1],
                    "max_x": bbox[2],
                    "max_y": bbox[3]
                })

            elif filters and filters.get("region_name"):
                query_str += " AND region_name = :region_name"
                params["region_name"] = filters["region_name"]

            # 3. 데이터 로딩
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query_str), conn, params=params)

            # 4. 데이터가 없을 경우 예외 발생
            if df.empty:
                error_msg = f"'{category}'에 해당하는 데이터가 없습니다."
                logger.error(f"❌ [Task ID: {task_id}] 작업 실패: {error_msg}")
                return json.dumps({"status": "FAILED", "error": error_msg}, ensure_ascii=False)

            # 5. DB 속성(JSON) 및 도형(WKT) 데이터 전처리
            df['properties'] = df['properties'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)

            df['geometry'] = df['geom_wkt'].apply(lambda x: wkt.loads(x) if x else None)

            gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")

            props_df = pd.json_normalize(gdf['properties'])
            gdf = pd.concat([gdf.drop(columns=['properties', 'geom_wkt']), props_df], axis=1)
            gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs="EPSG:4326")

            # 6. 포맷별 로컬 파일 저장 경로 설정
            export_dir = os.path.join(BASE_DIR, "exports")
            os.makedirs(export_dir, exist_ok=True)

            file_name = f"export_{category}_{task_id}"
            fmt = target_format.upper()

            # 7. 포맷별 익스포트 연산 분기
            if fmt == "GEOJSON":
                output_path = os.path.join(export_dir, f"{file_name}.geojson")
                gdf.to_file(output_path, driver="GeoJSON", encoding="utf-8")

            elif fmt == "SHP":
                output_path = os.path.join(export_dir, file_name)
                gdf.to_file(output_path, driver="ESRI Shapefile", encoding="utf-8")

            elif fmt == "CSV":
                output_path = os.path.join(export_dir, f"{file_name}.csv")

                if gdf.geometry.iloc[0].geom_type == 'Point':
                    gdf['경도'] = gdf.geometry.x
                    gdf['위도'] = gdf.geometry.y
                else:
                    gdf['wkt_geometry'] = gdf.geometry.apply(lambda g: g.wkt if g else "")

                df_out = pd.DataFrame(gdf.drop(columns=['geometry']))
                df_out.to_csv(output_path, index=False, encoding="utf-8-sig")

            elif fmt == "EXCEL":
                output_path = os.path.join(export_dir, f"{file_name}.xlsx")
                if gdf.geometry.iloc[0].geom_type == 'Point':
                    gdf['경도'] = gdf.geometry.x
                    gdf['위도'] = gdf.geometry.y
                else:
                    gdf['wkt_geometry'] = gdf.geometry.apply(lambda g: g.wkt if g else "")

                df_out = pd.DataFrame(gdf.drop(columns=['geometry']))
                df_out.to_excel(output_path, index=False)

            else:
                raise ValueError(f"❌ 지원하지 않는 포맷입니다: {target_format}")

            logger.info(f"✅ [Task ID: {task_id}] 파일 생성 완료: {output_path}")
            return json.dumps({"status": "SUCCESS", "file_path": output_path}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ [Task ID: {task_id}] 작업 중 내부 시스템 에러 발생: {e}")
            return json.dumps({"status": "FAILED", "error": str(e)}, ensure_ascii=False)