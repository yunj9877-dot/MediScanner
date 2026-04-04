import os
from dotenv import load_dotenv
load_dotenv()

"""
MediScanner - FastAPI 메인 앱
=================================
MedRAG 기반 한국어 의료 QA 시스템
FastAPI REST API + React 프론트엔드 (분리 구조)
"""

import json
import base64
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import router as api_router
from app.database import init_db, get_profile, save_profile, save_chat, get_chat_history


# ── 앱 시작/종료 ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 DB + RAG 엔진 미리 로딩"""
    init_db()

    # RAG 엔진 미리 초기화 (BM25 캐시 포함)
    print("▶ RAG 엔진 초기화 중...")
    from app.api.routes import get_usecase
    get_usecase()
    print("✓ RAG 엔진 초기화 완료")

    print("✅ MediScanner 서버 시작 (포트 8001)")
    yield
    print("🛑 MediScanner 종료")


app = FastAPI(
    title="MediScanner",
    description="MedRAG 기반 한국어 의료 QA 시스템",
    lifespan=lifespan,
)


# ── CORS 설정 (React 프론트엔드 허용) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API 라우터 연결 ──
app.include_router(api_router, prefix="/api")


# ═══════════════════════════════════════════════════════════════
# 프로필 API
# ═══════════════════════════════════════════════════════════════
@app.get("/api/profile/{user_id}")
async def get_user_profile(user_id: str):
    """사용자 프로필 조회"""
    profile = get_profile(user_id)
    if profile:
        return JSONResponse({"status": "ok", "profile": profile})
    return JSONResponse({"status": "ok", "profile": None})


@app.post("/api/profile")
async def save_user_profile(request: Request):
    """사용자 프로필 저장"""
    data = await request.json()
    save_profile(
        user_id=data.get("user_id", "default"),
        name=data.get("name", ""),
        age=data.get("age", 0),
        diseases=data.get("diseases", ""),
        medications=data.get("medications", ""),
    )
    return JSONResponse({"status": "ok", "message": "프로필이 저장되었습니다."})


# ═══════════════════════════════════════════════════════════════
# 상담 히스토리 API
# ═══════════════════════════════════════════════════════════════
@app.get("/api/history/{user_id}")
async def get_history(user_id: str, limit: int = 20):
    """상담 히스토리 조회"""
    history = get_chat_history(user_id, limit)
    return JSONResponse({"history": history})


# ═══════════════════════════════════════════════════════════════
# 카메라 OCR API (GPT-4 Vision)
# ═══════════════════════════════════════════════════════════════
@app.post("/api/camera/medications")
async def camera_medications(request: Request):
    """처방전 이미지 촬영 후 복용약 자동 추출"""
    try:
        from openai import OpenAI
        from app.config import OPENAI_API_KEY

        data = await request.json()
        image_base64 = data.get("image_base64", "")

        if not image_base64:
            return JSONResponse({"error": "이미지가 없습니다"}, status_code=400)

        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "이 사진에서 약 이름만 추출해주세요. 쉼표로 구분해서 약 이름만 나열해주세요. 예: 아스피린, 메트포르민, 리피토"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                ],
            }],
            max_tokens=200,
        )
        medications = response.choices[0].message.content.strip()
        return JSONResponse({"medications": medications})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# 약 검색 API (React MedicineSearch용)
# ═══════════════════════════════════════════════════════════════
@app.post("/api/medicine/search")
async def medicine_search(request: Request):
    """3단계 대체 의약품 검색 (e약은요 → 허가정보)"""
    try:
        from app.infra.drug_api import DrugAPIClient

        data = await request.json()
        drug_name = data.get("drug_name", "").strip()

        if not drug_name:
            return JSONResponse({"error": "약 이름을 입력해주세요"}, status_code=400)

        client = DrugAPIClient()
        result = await client.search_unified(drug_name)

        if not result["found"]:
            return JSONResponse({"drug_info": []})

        # 프론트엔드 형식에 맞춰서 변환
        drug_item = {
            "itemName": result["item_name"],
            "entpName": result["entp_name"],
            "efcyQesitm": result["efcy"],
            "useMethodQesitm": result["use_method"],
            "atpnQesitm": result["atpn"],
            "seQesitm": result["se"],
            "intrcQesitm": "",
            "depositMethodQesitm": "",
            "source": result["source"],
        }

        return JSONResponse({"drug_info": [drug_item]})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# 날씨 API (기상청 초단기실황)
# ═══════════════════════════════════════════════════════════════
@app.get("/api/weather")
async def get_weather():
    """기상청 초단기실황 + 에어코리아 미세먼지 → 프론트엔드 날씨 카드"""
    import httpx
    from datetime import datetime, timedelta

    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        return JSONResponse({"weather": None})

    now = datetime.now()
    if now.minute < 40:
        now = now - timedelta(hours=1)
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H00")

    weather = {
        "temp": "--", "humidity": "--", "wind": "--",
        "icon": "🌤️", "description": "날씨 정보",
        "pm10": "--", "pm25": "--", "dust_grade": "",
        "dust_advice": "",
        "tips": [],
    }

    # ── 1) 기상청 날씨 ──
    try:
        params = {
            "serviceKey": api_key,
            "numOfRows": "10", "pageNo": "1",
            "dataType": "JSON",
            "base_date": base_date, "base_time": base_time,
            "nx": "60", "ny": "127",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(
                "https://apis.data.go.kr/1360000/VilageFcstInfoService2/getUltraSrtNcst",
                params=params,
            )
            data = res.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

            for item in items:
                cat = item.get("category", "")
                val = item.get("obsrValue", "")
                if cat == "T1H":
                    weather["temp"] = val
                    temp_f = float(val)
                    if temp_f <= 0:
                        weather["icon"] = "❄️"
                        weather["description"] = "매우 추움"
                        weather["tips"] = ["옷을 따뜻하게 입고 외출하세요", "손 따뜻이 장갑 하세요"]
                    elif temp_f <= 10:
                        weather["icon"] = "🍂"
                        weather["description"] = "쌀쌀함"
                        weather["tips"] = ["긴 겉옷을 챙기세요"]
                    elif temp_f <= 20:
                        weather["icon"] = "🌤️"
                        weather["description"] = "선선함"
                        weather["tips"] = ["좋은 산책하기 좋은 날씨예요"]
                    elif temp_f <= 30:
                        weather["icon"] = "☀️"
                        weather["description"] = "따뜻함"
                        weather["tips"] = ["수분 섭취를 충분히 해주세요"]
                    else:
                        weather["icon"] = "🔥"
                        weather["description"] = "매우 더움"
                        weather["tips"] = ["야외 활동을 자제하세요", "수분 섭취 권장 필수"]
                elif cat == "REH":
                    weather["humidity"] = val
                elif cat == "WSD":
                    weather["wind"] = val
    except Exception as e:
        print(f"[날씨 API 오류] {e}")

    # ── 2) 에어코리아 미세먼지 ──
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(
                "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty",
                params={
                    "serviceKey": api_key,
                    "returnType": "json",
                    "numOfRows": "1",
                    "sidoName": "서울",
                    "ver": "1.0",
                },
            )
            data = res.json()
            items = data.get("response", {}).get("body", {}).get("items", [])

            if items:
                item = items[0]
                pm10 = item.get("pm10Value", "--")
                pm25 = item.get("pm25Value", "--")
                weather["pm10"] = pm10
                weather["pm25"] = pm25

                # 미세먼지 등급 산정 + 어드바이스
                try:
                    pm10_val = int(pm10)
                    pm25_val = int(pm25)
                    worst = max(pm10_val, pm25_val)

                    if worst <= 30:
                        weather["dust_grade"] = "좋음 😊"
                        weather["dust_advice"] = "마스크 없이 외출해도 좋아요"
                    elif worst <= 80:
                        weather["dust_grade"] = "보통 😐"
                        weather["dust_advice"] = "민감한 분은 마스크를 챙기세요"
                    elif worst <= 150:
                        weather["dust_grade"] = "나쁨 😷"
                        weather["dust_advice"] = "외출 시 마스크를 꼭 착용하세요"
                    else:
                        weather["dust_grade"] = "매우나쁨 🚫"
                        weather["dust_advice"] = "외출을 자제하세요. 실내 활동을 권합니다"
                except (ValueError, TypeError):
                    weather["dust_grade"] = "측정중"
                    weather["dust_advice"] = ""
    except Exception as e:
        print(f"[미세먼지 API 오류] {e}")

    return JSONResponse({"weather": weather})


# ═══════════════════════════════════════════════════════════════
# 시스템 상태
# ═══════════════════════════════════════════════════════════════
@app.get("/api/status")
async def system_status():
    """서버 상태 확인"""
    return JSONResponse({"status": "ok", "message": "MediScanner 서버 정상"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=False)
