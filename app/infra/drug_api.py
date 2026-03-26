"""
식약처 API 연동 (infra 계층)
============================
2단계 폴백 의약품 검색 (정확한 이름 매칭만)
  1순위: 허가정보 API — 162만 건 전체 허가 의약품 (일반+전문)
  2순위: e약은요 API — 일반의약품 상세 (효능, 부작용, 주의사항)
  + DUR API — 병용금기, 인신주의, 연령금기 등 안전정보

모든 API 결과는 통일 항목 7개로 정규화:
  제품명, 업체명, 성분/함량, 효능, 사용법, 주의사항, 부작용
"""

import re
import httpx
from app.config import (
    DATA_GO_KR_API_KEY, DRUG_API_BASE, DUR_API_BASE, PERMIT_API_BASE,
)
from app.domain.entities import DrugInfo, DURInfo


class DrugAPIClient:
    """식약처 2단계 폴백 의약품 검색 클라이언트"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or DATA_GO_KR_API_KEY
        self.timeout = 10.0

    # ══════════════════════════════════════
    # 통합 검색 (2단계 폴백, 정확한 이름 매칭)
    # ══════════════════════════════════════
    async def search_unified(self, drug_name: str) -> dict:
        """
        2단계 폴백 검색 — 정확한 이름 매칭만, 추측 검색 없음

        1순위: 허가정보 API (162만 건, 일반+전문)
        2순위: e약은요 API (일반의약품 상세)
        없으면: "관련 정보 없음"

        Returns:
            {
                "found": True/False,
                "source": "허가정보" / "e약은요" / "없음",
                "item_name": "텔미정40mg",
                "entp_name": "한미약품(주)",
                "ingredient": "텔미사르탄 40mg",
                "efcy": "효능...",
                "use_method": "사용법...",
                "atpn": "주의사항...",
                "se": "부작용...",
            }
        """
        empty_result = {
            "found": False,
            "source": "없음",
            "item_name": drug_name,
            "entp_name": "관련 정보 없음",
            "ingredient": "관련 정보 없음",
            "efcy": "관련 정보 없음",
            "use_method": "관련 정보 없음",
            "atpn": "관련 정보 없음",
            "se": "관련 정보 없음",
        }

        # 1순위: 허가정보 API (162만 건 — 전문+일반 모두)
        result = await self._search_permit(drug_name)
        if result:
            return result

        # 2순위: e약은요 API (일반의약품 상세)
        result = await self._search_easy_drug(drug_name)
        if result:
            return result

        # 못 찾음
        return empty_result

    # ══════════════════════════════════════
    # 1순위: 허가정보 API (162만 건)
    # ══════════════════════════════════════
    async def _search_permit(self, drug_name: str) -> dict | None:
        """허가정보 API — 전체 허가 의약품 (162만 건, 정확한 이름 매칭)"""
        if not self.api_key:
            return None

        params = {
            "serviceKey": self.api_key,
            "type": "json",
            "numOfRows": "3",
            "item_name": drug_name,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(PERMIT_API_BASE, params=params)
                if response.status_code != 200:
                    return None

                data = response.json()
                items = data.get("body", {}).get("items", [])
                if not items:
                    return None

                item = items[0]

                # 허가정보에서 효능효과, 용법용량, 주의사항 파싱
                ee_doc = self._clean_html_str(item.get("EE_DOC_DATA", ""))
                ud_doc = self._clean_html_str(item.get("UD_DOC_DATA", ""))
                nb_doc = self._clean_html_str(item.get("NB_DOC_DATA", ""))

                # 성분 정보
                main_ingr = item.get("MAIN_ITEM_INGR", "") or ""
                ingr_name = item.get("INGR_NAME", "") or main_ingr

                return {
                    "found": True,
                    "source": "허가정보",
                    "item_name": item.get("ITEM_NAME", drug_name),
                    "entp_name": item.get("ENTP_NAME", "관련 정보 없음"),
                    "ingredient": ingr_name or "관련 정보 없음",
                    "efcy": ee_doc or "관련 정보 없음",
                    "use_method": ud_doc or "관련 정보 없음",
                    "atpn": nb_doc or "관련 정보 없음",
                    "se": "관련 정보 없음",
                }

        except Exception as e:
            print(f"[허가정보 API 오류] {e}")
            return None

    # ══════════════════════════════════════
    # 2순위: e약은요 API
    # ══════════════════════════════════════
    async def _search_easy_drug(self, drug_name: str) -> dict | None:
        """e약은요 API — 일반의약품 상세 정보 (정확한 이름 매칭)"""
        if not self.api_key:
            return None

        params = {
            "serviceKey": self.api_key,
            "type": "json",
            "numOfRows": "3",
            "itemName": drug_name,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(DRUG_API_BASE, params=params)
                if response.status_code != 200:
                    return None

                data = response.json()
                items = data.get("body", {}).get("items", [])
                if not items:
                    return None

                item = self._clean_html(items[0])
                return {
                    "found": True,
                    "source": "e약은요",
                    "item_name": item.get("itemName", drug_name),
                    "entp_name": item.get("entpName", "관련 정보 없음"),
                    "ingredient": item.get("itemName", "관련 정보 없음"),
                    "efcy": item.get("efcyQesitm", "관련 정보 없음"),
                    "use_method": item.get("useMethodQesitm", "관련 정보 없음"),
                    "atpn": item.get("atpnQesitm", "") or item.get("atpnWarnQesitm", "") or "관련 정보 없음",
                    "se": item.get("seQesitm", "관련 정보 없음"),
                }

        except Exception as e:
            print(f"[e약은요 API 오류] {e}")
            return None

    # ══════════════════════════════════════
    # DUR API (병용금기)
    # ══════════════════════════════════════
    async def check_dur(self, drug_name: str, num_rows: int = 10) -> list[DURInfo]:
        """DUR 병용금기 정보 조회"""
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
                items = data.get("body", {}).get("items", [])
                if not items:
                    return []

                return [DURInfo.from_api(item) for item in items]

        except Exception as e:
            print(f"[DUR API 오류] {e}")
            return []

    # ══════════════════════════════════════
    # 기존 호환 메서드 (usecases.py에서 사용)
    # ══════════════════════════════════════
    async def search_drug(self, drug_name: str, num_rows: int = 5) -> list[DrugInfo]:
        """기존 e약은요 검색 (하위 호환)"""
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
                items = data.get("body", {}).get("items", [])
                if not items:
                    return []

                return [DrugInfo.from_api(self._clean_html(item)) for item in items]

        except Exception as e:
            print(f"[e약은요 API 오류] {e}")
            return []

    async def get_full_info(self, drug_name: str) -> tuple[list[DrugInfo], list[DURInfo]]:
        """e약은요 + DUR 통합 조회 (기존 호환)"""
        drug_results = await self.search_drug(drug_name, num_rows=3)
        dur_results = await self.check_dur(drug_name, num_rows=10)
        return drug_results, dur_results

    # ══════════════════════════════════════
    # 유틸리티
    # ══════════════════════════════════════
    def _clean_html(self, item: dict) -> dict:
        """API 응답에서 HTML 태그 제거"""
        fields = [
            "itemName", "entpName", "efcyQesitm", "useMethodQesitm",
            "atpnWarnQesitm", "atpnQesitm", "intrcQesitm", "seQesitm",
            "depositMethodQesitm",
        ]
        cleaned = {}
        for field in fields:
            value = item.get(field, "") or ""
            value = re.sub(r"<[^>]+>", "", value)
            value = re.sub(r"\s+", " ", value).strip()
            cleaned[field] = value
        return cleaned

    def _clean_html_str(self, text: str) -> str:
        """XML/HTML 태그 제거 + CDATA 추출 + 정리"""
        if not text:
            return ""
        text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;?", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 500:
            text = text[:500] + "..."
        return text


def extract_drug_names(query: str) -> list[str]:
    """질문에서 약 이름 추출"""
    common_drugs = [
        "타이레놀", "아스피린", "이부프로펜", "부루펜",
        "게보린", "암피실린", "판피린", "베아제",
        "리피토", "글리메피리드", "자이리텍", "스트렙타",
        "지르텍", "클라리틴", "로사르탄",
        "오메가3", "비타민", "마그네슘", "칼슘",
        "메트포르민", "아토르바스타틴", "아모디핀",
        "로사르탄", "텔미사르탄", "텔미정",
        "아모디핀", "노바스크", "넥시움", "트라마돌",
        "크레스토", "리바로", "자누비아", "바이엘",
        "트윈스타", "올메텍", "디오반", "코자",
    ]

    return [drug for drug in common_drugs if drug in query]
