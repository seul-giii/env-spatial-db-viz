import os
import shutil
from datetime import datetime
from typing import Optional, Dict

import geopandas as gpd
import pandas as pd
from sqlalchemy.orm import Session


def generate_export_file(
    db: Session,
    category: str,
    target_format: str,
    filters: Optional[Dict] = None
) -> str:
    """
    DB에서 공간 데이터를 조회하여 지정된 포맷으로 변환하고, 저장된 파일의 로컬 경로를 반환합니다.
    """
    print(f"[데이터 추출 시작] 카테고리: {category}, 포맷: {target_format}")

    query = "SELECT id, category, properties, geom FROM spatial_data WHERE category = %(category)s"
    params: Dict = {"category": category}

    # properties JSONB 컬럼에 대한 추가 필터 적용
    if filters:
        for i, (key, value) in enumerate(filters.items()):
            query += f" AND properties->>%(fk{i})s = %(fv{i})s"
            params[f"fk{i}"] = key
            params[f"fv{i}"] = str(value)

    engine = db.get_bind()
    gdf = gpd.read_postgis(query, con=engine, params=params, geom_col="geom")

    if gdf.empty:
        raise ValueError(f"'{category}'에 해당하는 데이터가 없습니다.")

    props_df = pd.json_normalize(gdf['properties'])
    gdf = gdf.drop(columns=['properties']).join(props_df)

    base_dir = os.getcwd()
    downloads_dir = os.path.join(base_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_format = target_format.upper()

    try:
        if target_format == "CSV":
            file_name = f"{category}_{timestamp}.csv"
            file_path = os.path.join(downloads_dir, file_name)
            gdf.drop(columns=['geom']).to_csv(file_path, index=False, encoding="utf-8-sig")
            return file_path

        elif target_format == "EXCEL":
            file_name = f"{category}_{timestamp}.xlsx"
            file_path = os.path.join(downloads_dir, file_name)
            gdf.drop(columns=['geom']).to_excel(file_path, index=False)
            return file_path

        elif target_format == "SHP":
            shp_folder_name = f"{category}_{timestamp}"
            shp_dir = os.path.join(downloads_dir, shp_folder_name)
            os.makedirs(shp_dir, exist_ok=True)

            shp_path = os.path.join(shp_dir, f"{category}.shp")
            gdf.to_file(shp_path, encoding="cp949")

            zip_path = os.path.join(downloads_dir, shp_folder_name)
            shutil.make_archive(zip_path, 'zip', shp_dir)
            shutil.rmtree(shp_dir)

            return zip_path + ".zip"

        else:
            raise ValueError(f"지원하지 않는 포맷입니다: {target_format}")

    except (ValueError, RuntimeError):
        raise
    except Exception as e:
        raise RuntimeError(f"파일 변환 중 오류 발생: {str(e)}") from e
