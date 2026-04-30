import geopandas as gpd
import json

# GeoJSON 데이터 (테스트용)
geojson_data = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [127, 37.5]},
            "properties": {"name": "지하수 관측소 A", "depth": 120, "category": "지하수", "region_name": "서울", "id": 1}
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [127.1, 37.6]},
            "properties": {"name": "수질 측정소 B", "ph": 7.2, "category": "수질", "region_name": "서울", "id": 2}
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [129, 35.1]},
            "properties": {"name": "지하수 관측소 C", "depth": 98, "category": "지하수", "region_name": "부산", "id": 3}
        }
    ]
}

# 1. GeoJSON 데이터를 GeoPandas 데이터프레임으로 변환
gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

# 2. 터미널 출력 확인
print("[데이터 구조 확인]")
print(gdf)
print("-" * 50)

# 3. 실제 파일로 변환 (현재 실행 중인 폴더 위치에 저장됨)
try:
    # CSV 변환 (한글 깨짐 방지 utf-8-sig)
    gdf.drop(columns='geometry').to_csv("test_result.csv", index=False, encoding="utf-8-sig")
    print("✅ CSV 파일 생성 성공!")

    # SHP 변환 (한글 깨짐 방지 cp949)
    gdf.to_file("test_result.shp", encoding="cp949")
    print("✅ SHP 파일 생성 성공!")

except Exception as e:
    print(f"❌ 변환 실패: {e}")