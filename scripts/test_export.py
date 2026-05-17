import os
import sys
import uuid
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.services.data_export_service import DataExportService


def run_tests():
    print("🎬 [백엔드 통합 테스트] 공간 데이터 추출 서비스 검증을 시작합니다...\n")

    try:
        service = DataExportService()
    except Exception as e:
        print(f"🚨 [DB 연결 실패] 테스트를 중단합니다. 원인: {e}")
        return

    test_scenarios = [
        {
            "name": "테스트 1: [자연데이터+BBox+GEOJSON] - 정상 추출",
            "category": "지하수",
            "target_format": "GEOJSON",
            "bbox": [128.5, 36.5, 129.5, 37.5],  # 경상북도 인근 좌표
            "filters": None
        },
        {
            "name": "테스트 2: [행정데이터+지역명+SHP] - 정상 추출",
            "category": "불투수면 비율",
            "target_format": "SHP",
            "bbox": None,
            "filters": {"region_name": "종로구"}  # 특정 구역만 필터링
        },
        {
            "name": "테스트 3: [포인트데이터+BBox+CSV] - 좌표계 분리 추출",
            "category": "지하수 산출량(양수량)",
            "target_format": "CSV",
            "bbox": [126.5, 35.5, 127.5, 36.5],  # 전라북도 인근 좌표
            "filters": None
        },
        {
            "name": "테스트 4: [대용량폴리곤+BBox+EXCEL] - WKT 텍스트 변환 추출",
            "category": "중분류 토지피복",
            "target_format": "EXCEL",
            "bbox": [126.97, 37.56, 126.98, 37.57],  # 서울 시청 반경 아주 좁은 구역
            "filters": None
        },
        {
            "name": "테스트 5: [예외처리] - 데이터가 없는 엉뚱한 BBox 좌표를 넣었을 때",
            "category": "지하수",
            "target_format": "GEOJSON",
            "bbox": [10.0, 10.0, 11.0, 11.0],  # 아프리카 바다 한가운데
            "filters": None
        }
    ]

    success_count = 0

    for i, scenario in enumerate(test_scenarios, 1):
        task_id = f"test_task_{i}_{uuid.uuid4().hex[:8]}"
        print(f"\n{'=' * 60}")
        print(f"▶️ {scenario['name']}")
        print(
            f"   조건: {scenario['category']} / {scenario['target_format']} / BBox: {scenario['bbox']} / 필터: {scenario['filters']}")
        print(f"{'-' * 60}")

        result_json = service.export_spatial_data(
            task_id=task_id,
            category=scenario["category"],
            target_format=scenario["target_format"],
            bbox=scenario["bbox"],
            filters=scenario["filters"]
        )

        result = json.loads(result_json)

        if result.get("status") == "SUCCESS":
            print(f"🟢 [통과] 파일이 성공적으로 생성되었습니다!")
            print(f"   📂 저장 경로: {result.get('file_path')}")
            success_count += 1
        else:
            # 테스트 5번은 원래 실패해야 정상이므로 통과 처리
            if i == 5 and "데이터가 없습니다" in result.get("error", ""):
                print(f"🟢 [통과] 의도된 에러(데이터 없음)를 시스템이 정확히 잡아냈습니다!")
                success_count += 1
            else:
                print(f"🔴 [실패] 에러 발생: {result.get('error')}")

    print(f"\n{'=' * 60}")
    print(f"🏁 [테스트 결과 요약] 총 {len(test_scenarios)}개 중 {success_count}개 통과!")
    if success_count == len(test_scenarios):
        print("🎉 축하합니다! 프론트엔드와 연결할 백엔드 서비스 로직이 완벽하게 작동합니다!")
    else:
        print("🛠️ 실패한 테스트의 로그를 확인하고 코드를 수정해 보세요.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_tests()