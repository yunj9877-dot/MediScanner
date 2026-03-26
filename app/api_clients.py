"""
공공데이터 API 클라이언트
========================
e약은요 API: 의약품 기본 정보 (효능, 용법, 부작용)
DUR API: 약물 안전 정보 (병용금기, 연령금기)
"""

import httpx
import re
from typing import Optional
from app.config import DATA_GO_KR_API_KEY, DRUG_API_BASE, DUR_API_BASE


class DrugAPIClient:
    """e약은요 + DUR API 통합 클라이언트"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or DATA_GO_KR_API_KEY
        self.timeout = 10.0

    # ──────────────────────────────────────
    # e약은요 API
    # ──────────────────────────────────────
    async def search_drug(self, drug_name: str, num_rows: int = 5) -> list[dict]:
        """
        e약은요 API로 의약품 검색
        - drug_name: 의약품명 (예: "타이레놀")
        - 반환: 의약품 정보 리스트
        """
        if not self.api_key:
            return []

        params = {
            "serviceKey": self.api_key,
            "type": "json",
            "numOfRows": str(num_rows),
            "itemName": drug_name,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(DRUG_API_BASE, params=params)

                if response.status_code != 200:
                    return []

                data = response.json()
                body = data.get("body", {})
                items = body.get("items", [])

                if not items:
                    return []

                # HTML 태그 제거 + 정리
                cleaned = []
                for item in items:
                    cleaned.append(self._clean_drug_item(item))
                return cleaned

        except Exception as e:
            print(f"[e약은요 API 오류] {e}")
            return []

    async def search_drug_smart(self, drug_name: str, num_rows: int = 5) -> list[dict]:
        """
        정확한 약 이름으로 검색, 없으면 제형 제거 후 1번만 재시도
        최대 2번 검색: 원래 이름 → 제형 제거
        """
        # 1차: 원래 이름으로 검색
        results = await self.search_drug(drug_name, num_rows)
        if results:
            return results

        # 2차: 제형 키워드 제거 후 재시도
        forms = ["정", "캡슐", "시럽", "주사", "안약", "연고", "크림", "패치", "산", "액"]
        base_name = drug_name
        for form in sorted(forms, key=len, reverse=True):
            if drug_name.endswith(form) and len(drug_name) > len(form):
                base_name = drug_name[:-len(form)]
                break

        if base_name != drug_name:
            results = await self.search_drug(base_name, num_rows)
            if results:
                return results

        return []

    def _clean_drug_item(self, item: dict) -> dict:
        """API 응답에서 HTML 태그 제거 및 필드 정리"""
        fields = [
            "itemName", "entpName", "itemSeq",
            "efcyQesitm", "useMethodQesitm",
            "atpnWarnQesitm", "atpnQesitm",
            "intrcQesitm", "seQesitm",
            "depositMethodQesitm",
        ]
        cleaned = {}
        for field in fields:
            value = item.get(field, "") or ""
            # HTML 태그 제거
            value = re.sub(r"<[^>]+>", "", value)
            # 연속 공백/줄바꿈 정리
            value = re.sub(r"\s+", " ", value).strip()
            cleaned[field] = value
        return cleaned

    # ──────────────────────────────────────
    # DUR API (병용금기)
    # ──────────────────────────────────────
    async def check_dur(self, drug_name: str, num_rows: int = 10) -> list[dict]:
        """
        DUR 병용금기 정보 조회
        - drug_name: 의약품명
        - 반환: 병용금기 항목 리스트
        """
        if not self.api_key:
            return []

        params = {
            "serviceKey": self.api_key,
            "type": "json",
            "numOfRows": str(num_rows),
            "typeName": "병용금기",
            "itemName": drug_name,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(DUR_API_BASE, params=params)

                if response.status_code != 200:
                    return []

                data = response.json()
                body = data.get("body", {})
                items = body.get("items", [])

                if not items:
                    return []

                return items

        except Exception as e:
            print(f"[DUR API 오류] {e}")
            return []

    # ──────────────────────────────────────
    # 통합 검색
    # ──────────────────────────────────────
    async def get_full_drug_info(self, drug_name: str) -> dict:
        """
        e약은요 + DUR 통합 조회
        정확한 이름으로 검색, 없으면 제형 제거 후 1번 재시도
        """
        drug_results = await self.search_drug_smart(drug_name, num_rows=3)
        dur_results = await self.check_dur(drug_name, num_rows=10)

        return {
            "drug_name": drug_name,
            "drug_info": drug_results,
            "dur_info": dur_results,
            "has_drug_info": len(drug_results) > 0,
            "has_dur_info": len(dur_results) > 0,
        }


def extract_drug_names(query: str) -> list[str]:
    """
    사용자 질문에서 의약품명 추출 (간단한 규칙 기반)
    """
    common_drugs = [
        "타이레놀", "아스피린", "이부프로펜", "부루펜",
        "게보린", "암피린", "판피린", "베아제",
        "인스린", "글리메피리드", "메글루", "스트렙타",
        "지르텍", "클라리틴", "로라타딘",
        "오메가3", "비타민", "마그네슘", "칼슘",
        "메트포르민", "아토르바스타틴", "암로디핀",
        "로사르탄", "리바스티그민", "텔미정",
        "텔미사르탄", "노바스크", "넥시움", "트라마돌",
        "아모디핀", "리피토", "크레스토", "자누비아",
        "트윈스타", "올메텍", "디오반", "코자",
    ]

    found = []
    for drug in common_drugs:
        if drug in query:
            found.append(drug)

    return found
