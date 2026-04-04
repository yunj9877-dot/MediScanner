"""
MediScanner - FastAPI REST API
===================================
MedRAG 기반 한국어 의료 QA 시스템 (React 프론트엔드 전용)
FastAPI + ChromaDB + ko-sroberta + GPT-4o-mini
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
import asyncio
import time

from app.rag_engine import RAGEngine
from app.infra.drug_api import DrugAPIClient, extract_drug_names
from app.config import COLLECTION_NAME
from app import database as db


# ── 전역 인스턴스 ──
rag_engine: RAGEngine = None
drug_client: DrugAPIClient = None


async def _auto_expire_loop():
    """1시간마다 오래된 세션 자동 삭제 (개인정보 보호)"""
    while True:
        await asyncio.sleep(3600)  # 1시간 대기
        try:
            cutoff = time.time() - 3600  # 1시간 전
            db.delete_expired_sessions(cutoff)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    global rag_engine, drug_client
    db.init_db()
    rag_engine = RAGEngine()
    drug_client = DrugAPIClient()
    print("✅ MediScanner RAG 엔진 시작")
    print(f"   ChromaDB 컬렉션 상태: {rag_engine.get_collection_stats()}")
    # 자동 만료 스케줄러 시작
    task = asyncio.create_task(_auto_expire_loop())
    yield
    task.cancel()
    print("🛑 MediScanner 종료")


app = FastAPI(
    title="MediScanner API",
    description="MedRAG 기반 한국어 의료 QA REST API",
    version="1.0.0",
    lifespan=lifespan,
)


# ──────────────────────────────────────
# CORS 설정 (수동 핸들러)
# ──────────────────────────────────────
# FastAPI CORSMiddleware 대신 수동 핸들러 사용
# 이유: Windows 환경에서 CORSMiddleware + credentials 옵션 충돌 문제 해결
@app.middleware("http")
async def cors_handler(request, call_next):
    """모든 요청에 CORS 헤더 추가, OPTIONS preflight 처리"""
    if request.method == "OPTIONS":
        response = JSONResponse(content="OK")
    else:
        response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# ──────────────────────────────────────
# Request/Response 모델
# ──────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    answer_mode: str = "simple"
    user_id: str = "default"
    save_history: bool = True
    model: str = "e5-large"  # 임베딩 모델 선택: e5-large / ko-sroberta / e5-small


class DrugSearchRequest(BaseModel):
    drug_name: str


class APIKeysRequest(BaseModel):
    openai_key: Optional[str] = ""
    data_go_kr_key: Optional[str] = ""


class ProfileRequest(BaseModel):
    user_id: str = "default"
    name: str = ""
    age: int = 0
    diseases: str = ""
    medications: str = ""


class CameraRequest(BaseModel):
    image_base64: str
    user_id: str = "default"


# ──────────────────────────────────────
# Health Check
# ──────────────────────────────────────
@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "service": "MediScanner API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/api/chat",
            "drug_search": "/api/medicine/search",
            "system_status": "/api/status",
        },
    }


# ──────────────────────────────────────
# API 키 설정
# ──────────────────────────────────────
@app.post("/api/set-keys")
async def set_api_keys(request: APIKeysRequest):
    """API 키 설정 (OpenAI, 공공데이터포털)"""
    global rag_engine, drug_client

    if request.openai_key:
        rag_engine = RAGEngine(openai_api_key=request.openai_key)
    if request.data_go_kr_key:
        drug_client = DrugAPIClient(api_key=request.data_go_kr_key)

    return {
        "status": "ok",
        "message": "API 키가 설정되었습니다.",
        "openai_set": bool(request.openai_key),
        "data_api_set": bool(request.data_go_kr_key),
        "collections": rag_engine.get_collection_stats(),
    }


# ──────────────────────────────────────
# 의료 QA (메인 RAG)
# ──────────────────────────────────────
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    메인 RAG 파이프라인:
    1) ChromaDB 벡터 검색 (ko-sroberta 임베딩)
    2) 질문에서 의약품명 추출 → e약은요 + DUR 실시간 API
    3) 전체 컨텍스트를 GPT-4o-mini에 전달 → Self-RAG 답변 생성
    4) answer_mode에 따라 "간단" / "상세" 답변 선택
    """
    if not rag_engine or not rag_engine.client:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API 키를 먼저 설정해주세요. /api/set-keys 엔드포인트를 사용하세요.",
        )

    # 1) ChromaDB 벡터 검색 (선택된 임베딩 모델 사용)
    retrieved_docs = rag_engine.search(request.query, model=request.model)

    # 2) 의약품명 추출 → API 호출
    drug_api_data = None
    dur_api_data = None
    drug_names = extract_drug_names(request.query)

    if drug_names and drug_client and drug_client.api_key:
        full_info = await drug_client.search_unified(drug_names[0])
        if full_info.get("found"):
            drug_api_data = full_info
        dur_api_data = None  # DUR은 별도 check_dur 사용

    # 3) 건강 프로필 조회 (있으면 맞춤 답변)
    user_profile = db.get_profile(request.user_id)

    # 3-1) 프로필 복용약 → 식약처 API 병렬 조회 (방법 A)
    profile_drug_api_data = []
    if user_profile and user_profile.get("medications") and drug_client and drug_client.api_key:
        import asyncio
        med_names = [m.strip() for m in user_profile["medications"].split(",") if m.strip()]
        print(f"[복용약 API 조회 시작] {med_names}")
        async def safe_search(name):
            try:
                result = await drug_client.search_unified(name)
                if result.get("found"):
                    print(f"[복용약 API 성공] {name} → {result.get('item_name')} / {result.get('efcy','')[:50]}")
                    return result
                else:
                    print(f"[복용약 API 미발견] {name}")
            except Exception as e:
                print(f"[복용약 API 오류] {name}: {e}")
            return None
        results = await asyncio.gather(*[safe_search(name) for name in med_names])
        profile_drug_api_data = [r for r in results if r]
        print(f"[복용약 API 완료] {len(profile_drug_api_data)}개 조회 성공")
    else:
        print(f"[복용약 API 건너뜀] medications={user_profile.get('medications') if user_profile else None}, api_key={bool(drug_client and drug_client.api_key)}")

    # 4) GPT-4o-mini 답변 생성 (유료)
    result = rag_engine.generate_answer(
        query=request.query,
        retrieved_docs=retrieved_docs,
        drug_api_data=drug_api_data,
        dur_api_data=dur_api_data,
        answer_mode=request.answer_mode,
        user_profile=user_profile,
        profile_drug_api_data=profile_drug_api_data,
    )

    # 5) 상담 히스토리 저장 (save_history=False면 건너뜀)
    if request.save_history:
        sources_str = ", ".join([s.get("source", "") for s in result.get("sources", [])])
        db.save_chat(
            user_id=request.user_id,
            question=request.query,
            answer=result["answer"],
            answer_mode=request.answer_mode,
            sources=sources_str,
            drug_names=", ".join(drug_names) if drug_names else "",
            tokens_input=result.get("tokens", {}).get("input", 0),
            tokens_output=result.get("tokens", {}).get("output", 0),
        )

    # 6) 비용 정보 추가
    result["cost"] = rag_engine.get_cost()
    result["drug_names_detected"] = drug_names
    result["answer_mode"] = request.answer_mode

    return result


# ──────────────────────────────────────
# 날씨 정보 (기상청 초단기실황 + 초단기예보)
# ──────────────────────────────────────
@app.get("/api/weather")
async def get_weather(nx: int = 98, ny: int = 76):
    """
    기상청 초단기실황 + 초단기예보 조회
    기본값: 부산 (nx=98, ny=76)
    서울: nx=60, ny=127
    """
    import httpx
    from datetime import datetime, timedelta

    now = datetime.now()
    # 실황: 매시 40분 이후 발표
    obs_time = now - timedelta(hours=1) if now.minute < 40 else now
    base_date = obs_time.strftime("%Y%m%d")
    base_time = obs_time.strftime("%H00")

    # 예보: 매시 45분 발표, 30분 단위
    fcst_time = now - timedelta(hours=1) if now.minute < 45 else now
    fcst_base_time = fcst_time.strftime("%H30")

    api_key = drug_client.api_key if drug_client else ""
    if not api_key:
        return {"status": "error", "message": "공공데이터 API 키가 없습니다."}

    base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
    common_params = {
        "serviceKey": api_key,
        "pageNo": 1,
        "numOfRows": 60,
        "dataType": "JSON",
        "base_date": base_date,
        "nx": nx,
        "ny": ny,
    }
    
    try:
        weather = {}
        temp_min_val = None
        temp_max_val = None

        async with httpx.AsyncClient() as client:
            # 1) 초단기실황 (기온, 습도, 바람, 강수량, 강수형태)
            obs_res = await client.get(
                f"{base_url}/getUltraSrtNcst",
                params={**common_params, "base_time": base_time},
                timeout=10,
            )
            # 2) 초단기예보 (하늘상태 SKY)
            fcst_res = await client.get(
                f"{base_url}/getUltraSrtFcst",
                params={**common_params, "base_time": fcst_base_time},
                timeout=10,
            )
            # 3) 단기예보 (최저기온 TMN: 0200 발표, 최고기온 TMX: 1100 발표)
            try:
                tmn_res = await client.get(
                    f"{base_url}/getVilageFcst",
                    params={**common_params, "base_time": "0200", "numOfRows": 300},
                    timeout=10,
                )
                for item in tmn_res.json().get("response", {}).get("body", {}).get("items", {}).get("item", []):
                    if item.get("category") == "TMN":
                        temp_min_val = float(item.get("fcstValue"))
                        break

                tmx_res = await client.get(
                    f"{base_url}/getVilageFcst",
                    params={**common_params, "base_time": "1100", "numOfRows": 300},
                    timeout=10,
                )
                for item in tmx_res.json().get("response", {}).get("body", {}).get("items", {}).get("item", []):
                    if item.get("category") == "TMX":
                        temp_max_val = float(item.get("fcstValue"))
                        break
            except:
                pass

        # 실황 데이터 파싱
        obs_data = obs_res.json()
        obs_items = obs_data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

        for item in obs_items:
            cat = item.get("category")
            val = item.get("obsrValue")
            if cat == "T1H":
                weather["temp"] = float(val)
            elif cat == "RN1":
                rain_val = float(val) if val != "강수없음" else 0
                weather["rain_mm"] = rain_val
            elif cat == "REH":
                weather["humidity"] = int(float(val))
            elif cat == "WSD":
                weather["wind"] = float(val)
            elif cat == "PTY":
                pty_map = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림"}
                weather["precipitation"] = pty_map.get(val, "없음")

        # 최저/최고 기온 추가
        if temp_min_val is not None:
            weather["temp_min"] = temp_min_val
        if temp_max_val is not None:
            weather["temp_max"] = temp_max_val

        # 예보 데이터에서 하늘상태(SKY) 파싱
        fcst_data = fcst_res.json()
        fcst_items = fcst_data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        sky_val = "1"
        for item in fcst_items:
            if item.get("category") == "SKY":
                sky_val = item.get("fcstValue", "1")
                break

        sky_map = {"1": "맑음", "3": "구름많음", "4": "흐림"}
        weather["sky"] = sky_map.get(sky_val, "맑음")

        # 종합 날씨 설명 생성
        precip = weather.get("precipitation", "없음")
        sky = weather.get("sky", "맑음")
        temp = weather.get("temp", 15)

        if precip == "비":
            weather["description"] = "비가 내리고 있어요"
            weather["icon"] = "🌧️"
        elif precip == "눈":
            weather["description"] = "눈이 내리고 있어요"
            weather["icon"] = "🌨️"
        elif precip == "비/눈":
            weather["description"] = "비와 눈이 내리고 있어요"
            weather["icon"] = "🌨️"
        elif precip in ["빗방울", "빗방울/눈날림", "눈날림"]:
            weather["description"] = f"{precip}이 날리고 있어요"
            weather["icon"] = "🌦️"
        elif sky == "맑음":
            weather["description"] = "맑은 하늘이에요"
            weather["icon"] = "☀️" if temp > 15 else "🌤️"
        elif sky == "구름많음":
            weather["description"] = "구름이 많아요"
            weather["icon"] = "⛅"
        elif sky == "흐림":
            weather["description"] = "흐린 날씨에요"
            weather["icon"] = "☁️"
        else:
            weather["description"] = "날씨 정보"
            weather["icon"] = "🌤️"

        # 건강 팁 생성
        tips = []
        if temp <= 0:
            tips.append("영하 날씨입니다! 보온에 신경 쓰시고, 빙판길 넘어짐에 주의하세요.")
        elif temp <= 5:
            tips.append("추운 날씨입니다. 따뜻한 옷을 챙기시고, 혈압 변동에 주의하세요.")
        elif temp <= 10:
            tips.append("쌀쌀합니다. 외출 시 겉옷을 꼭 챙기세요.")
        elif temp <= 20:
            tips.append("활동하기 좋은 날씨입니다. 가벼운 산책을 추천해요.")
        elif temp <= 28:
            tips.append("따뜻합니다. 수분 섭취를 충분히 해주세요.")
        elif temp <= 33:
            tips.append("더운 날씨입니다! 직사광선을 피하시고, 물을 자주 드세요.")
        else:
            tips.append("폭염 주의! 외출을 삼가시고, 시원한 실내에 계세요.")

        if precip == "비":
            tips.append("비가 옵니다. 우산을 챙기시고, 미끄러운 길 조심하세요.")
        elif precip == "눈":
            tips.append("눈이 옵니다. 빙판길 낙상에 각별히 주의하세요.")
        elif precip in ["비/눈", "빗방울", "빗방울/눈날림", "눈날림"]:
            tips.append("비 또는 눈이 예상됩니다. 우산을 준비하세요.")

        humidity = weather.get("humidity", 50)
        if humidity < 30:
            tips.append("공기가 매우 건조합니다. 물을 자주 드시고 보습에 신경 쓰세요.")
        elif humidity > 80:
            tips.append("습도가 높습니다. 관절 통증이 있으신 분은 주의하세요.")

        wind = weather.get("wind", 0)
        if wind > 10:
            tips.append("강풍입니다. 외출 시 주의하시고, 모자가 날리지 않게 조심하세요.")
        elif wind > 5:
            tips.append("바람이 불고 있어요. 체감온도가 낮을 수 있으니 겉옷을 챙기세요.")

        weather["tips"] = tips
        weather["base_date"] = base_date
        weather["base_time"] = base_time

        # ── 미세먼지 (에어코리아, 환경부 기준) ──
        try:
            async with httpx.AsyncClient(timeout=5.0) as dust_client:
                dust_res = await dust_client.get(
                    "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty",
                    params={
                        "serviceKey": api_key,
                        "returnType": "json",
                        "numOfRows": "1",
                        "sidoName": "서울",
                        "ver": "1.0",
                    },
                )
                dust_data = dust_res.json()
                dust_items = dust_data.get("response", {}).get("body", {}).get("items", [])
                if dust_items:
                    d = dust_items[0]
                    pm10 = d.get("pm10Value", "--")
                    pm25 = d.get("pm25Value", "--")
                    weather["pm10"] = pm10
                    weather["pm25"] = pm25
                    try:
                        pm10_v = int(pm10)
                        pm25_v = int(pm25)
                        if pm10_v <= 30:
                            g10 = 1
                        elif pm10_v <= 80:
                            g10 = 2
                        elif pm10_v <= 150:
                            g10 = 3
                        else:
                            g10 = 4
                        if pm25_v <= 15:
                            g25 = 1
                        elif pm25_v <= 35:
                            g25 = 2
                        elif pm25_v <= 75:
                            g25 = 3
                        else:
                            g25 = 4
                        grade = max(g10, g25)
                        if grade == 1:
                            weather["dust_grade"] = "좋음"
                            weather["dust_advice"] = "마스크 없이 외출해도 좋아요"
                        elif grade == 2:
                            weather["dust_grade"] = "보통"
                            weather["dust_advice"] = "민감한 분은 마스크를 챙기세요"
                        elif grade == 3:
                            weather["dust_grade"] = "나쁨"
                            weather["dust_advice"] = "외출 시 마스크를 꼭 착용하세요"
                        else:
                            weather["dust_grade"] = "매우나쁨"
                            weather["dust_advice"] = "외출을 자제하세요! 실내 활동을 권합니다"
                    except (ValueError, TypeError):
                        weather["dust_grade"] = "측정중"
                        weather["dust_advice"] = ""
                    if weather.get("dust_advice"):
                        weather["tips"].append(weather["dust_advice"])
        except Exception as e:
            print(f"[미세먼지 API 오류] {e}")

        return {"status": "ok", "weather": weather}

    except Exception as e:
        return {"status": "error", "message": f"날씨 조회 실패: {str(e)}"}


# ──────────────────────────────────────
# 복용약 OCR (처방전/약봉투 → 약 이름 추출)
# ──────────────────────────────────────
@app.post("/api/camera/ocr-meds")
async def ocr_medications(request: CameraRequest):
    """처방전/약봉투 이미지에서 약 이름만 추출"""
    if not rag_engine or not rag_engine.client:
        raise HTTPException(status_code=400, detail="OpenAI API 키를 먼저 설정해주세요.")

    try:
        response = rag_engine.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "상품명(브랜드명)만 추출하세요. 쉼표로 구분하여 나열하세요. 다른 설명은 하지 마세요. 약통/처방전에 표시된 상품명만 추출하고, 성분명(피타바스타틴, 로수바스타틴, 에제티미브, 암로디핀 등 화학/일반명)은 절대 포함하지 마세요. 예: 페바로젯정, 텔미지, 고덱스"},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{request.image_base64}"}},
                    {"type": "text", "text": "이 처방전/약봉투에 있는 약 이름만 추출해주세요."},
                ]},
            ],
            temperature=0.1,
            max_tokens=200,
        )

        meds = response.choices[0].message.content.strip()
        usage = response.usage
        rag_engine.usage["input_tokens"] += usage.prompt_tokens
        rag_engine.usage["output_tokens"] += usage.completion_tokens
        rag_engine.usage["api_calls"] += 1

        return {"medications": meds, "tokens": {"input": usage.prompt_tokens, "output": usage.completion_tokens}}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"약 이름 인식 실패: {str(e)}")


# ──────────────────────────────────────
# 복용약 OCR (처방전/약봉투 → 약 이름 추출)
# ──────────────────────────────────────
@app.post("/api/camera/medications")
async def camera_medications(request: CameraRequest):
    """처방전/약봉투 이미지에서 약 이름만 추출"""
    if not rag_engine or not rag_engine.client:
        raise HTTPException(status_code=400, detail="OpenAI API 키를 먼저 설정해주세요.")

    try:
        response = rag_engine.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "이미지에서 약 이름만 추출하세요. 쉼표로 구분하여 약 이름만 나열하세요. 다른 설명은 하지 마세요.\n반드시 처방된 약품명(상품명)만 추출하고, 성분명(예: 피타바스타틴, 로수바스타틴, 암로디핀 등)은 절대 포함하지 마세요.\n예: 페바로젯정, 텔미지, 아스피린프로텍트"},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{request.image_base64}"}},
                    {"type": "text", "text": "이 이미지에서 약 이름만 추출해주세요."},
                ]},
            ],
            temperature=0.1,
            max_tokens=200,
        )

        usage = response.usage
        rag_engine.usage["input_tokens"] += usage.prompt_tokens
        rag_engine.usage["output_tokens"] += usage.completion_tokens
        rag_engine.usage["api_calls"] += 1

        medications = response.choices[0].message.content.strip()
        return {"medications": medications}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"약 이름 추출 실패: {str(e)}")


# ──────────────────────────────────────
# 카메라 OCR (약 성분표/처방전 분석)
# ──────────────────────────────────────
@app.post("/api/camera/analyze")
async def camera_analyze(request: CameraRequest):
    """
    약 스캔 3단계 파이프라인:
    1) GPT Vision → 약 이름만 추출
    2) 식약처 API → 정확한 약효/주의사항 조회
    3) GPT → API 데이터 기반 설명 생성
    """
    if not rag_engine or not rag_engine.client:
        raise HTTPException(status_code=400, detail="OpenAI API 키를 먼저 설정해주세요.")

    # 건강 프로필 조회
    user_profile = db.get_profile(request.user_id)

    # ── 1단계: GPT Vision → 약 이름만 추출 ──
    import re, asyncio
    try:
        name_resp = rag_engine.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "약통/약봉투 이미지에서 상품명(브랜드명)만 추출하세요. 성분명(피타바스타틴, 에제티미브, 암로디핀 등 화학명/일반명)은 절대 포함하지 마세요. 한국어 상품명만 쉼표로 구분하여 반환하세요. 예: 페바로젯정, 고덱스캡슐"},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{request.image_base64}"}},
                    {"type": "text", "text": "이 약의 상품명만 한국어로 추출해주세요. 성분명은 제외하세요."},
                ]},
            ],
            temperature=0.1,
            max_tokens=100,
        )
        rag_engine.usage["input_tokens"] += name_resp.usage.prompt_tokens
        rag_engine.usage["output_tokens"] += name_resp.usage.completion_tokens
        rag_engine.usage["api_calls"] += 1
        raw_names = name_resp.choices[0].message.content.strip()
        drug_names = [n.strip() for n in raw_names.split(',') if n.strip()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"약 이름 추출 실패: {str(e)}")

    # 영어→한국어 사전 변환
    ENG_TO_KOR = {
        "momet nasal spray": "모메트 나잘 스프레이", "mometasone": "모메타손",
        "godex": "고덱스", "nasonex": "나조넥스", "flonase": "플로나제",
        "tylenol": "타이레놀", "advil": "애드빌", "aspirin": "아스피린",
        "ibuprofen": "이부프로펜", "amoxicillin": "아목시실린", "metformin": "메트포르민",
    }
    def translate_drug_name(name):
        lower = name.lower().strip()
        for eng, kor in ENG_TO_KOR.items():
            if eng in lower:
                return kor
        return name
    drug_names = [translate_drug_name(n) for n in drug_names]
    print(f"[약스캔] 추출된 약 이름: {drug_names}")

    # ── 2단계: 식약처 API → 정확한 약효 조회 ──
    api_results = []
    if drug_client and drug_client.api_key:
        async def safe_search(name):
            try:
                result = await drug_client.search_unified(name)
                if result.get("found"):
                    print(f"[약스캔 API 성공] {name} → {result.get('efcy','')[:60]}")
                    return result
                print(f"[약스캔 API 미발견] {name}")
            except Exception as e:
                print(f"[약스캔 API 오류] {name}: {e}")
            return None
        results = await asyncio.gather(*[safe_search(name) for name in drug_names])
        api_results = [r for r in results if r]

    # ── 3단계: GPT → API 데이터 기반 설명 생성 ──
    # 컨텍스트 구성
    context_parts = []
    if api_results:
        context_parts.append("【식약처 확인 약품 정보】")
        for drug in api_results:
            context_parts.append(f"▶ {drug.get('item_name','')} ({drug.get('entp_name','')})")
            if drug.get('ingredient') and drug.get('ingredient') != '관련 정보 없음':
                context_parts.append(f"  성분: {drug.get('ingredient','')[:100]}")
            if drug.get('efcy') and drug.get('efcy') != '관련 정보 없음':
                context_parts.append(f"  효능: {drug.get('efcy','')[:300]}")
            if drug.get('use_method') and drug.get('use_method') != '관련 정보 없음':
                context_parts.append(f"  용법: {drug.get('use_method','')[:200]}")
            if drug.get('atpn') and drug.get('atpn') != '관련 정보 없음':
                context_parts.append(f"  주의사항: {drug.get('atpn','')[:200]}")
            if drug.get('se') and drug.get('se') != '관련 정보 없음':
                context_parts.append(f"  부작용: {drug.get('se','')[:150]}")

    profile_context = ""
    if user_profile:
        parts = []
        if user_profile.get("age"):
            parts.append(f"나이: {user_profile['age']}세")
        if user_profile.get("diseases"):
            parts.append(f"기저질환: {user_profile['diseases']}")
        if user_profile.get("medications"):
            parts.append(f"복용 중인 약: {user_profile['medications']}")
        if parts:
            profile_context = "\n".join(parts)

    system_prompt = """당신은 고령자를 위한 의료 AI 메디스캐너입니다.
아래 【식약처 확인 약품 정보】를 바탕으로 어르신이 이해하기 쉽게 설명하세요.

규칙:
1. 반드시 식약처 정보에 있는 내용만 사용하세요. 없는 내용은 절대 추가하지 마세요.
2. 어려운 의학 용어는 쉬운 말로 바꾸세요. 예: "경구투여" → "입으로 드세요"
3. 핵심만 3~4문장으로 간결하게 설명하세요.
4. 주의사항은 ⚠️로 표시하고 꼭 포함하세요.
5. 사용자 건강 정보가 있으면 기저질환/복용약과의 관련성을 ⚠️로 추가하세요.
6. 마지막에 "※ 참고용 정보이며, 정확한 진단은 의료 전문가와 상담하세요." 추가"""

    user_text = f"{chr(10).join(context_parts)}"
    if profile_context:
        user_text += f"\n\n【사용자 건강 정보】\n{profile_context}"
    user_text += "\n\n위 약에 대해 어르신이 이해하기 쉽게 설명해주세요."

    # API 결과 없으면 이미지 직접 분석으로 fallback
    if not api_results:
        user_text = f"이미지에서 찾은 약: {', '.join(drug_names)}\n식약처 API 조회 실패. 이미지를 직접 분석하여 설명해주세요."

    try:
        resp = rag_engine.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
            max_tokens=700,
        )
        answer = resp.choices[0].message.content
        rag_engine.usage["input_tokens"] += resp.usage.prompt_tokens
        rag_engine.usage["output_tokens"] += resp.usage.completion_tokens
        rag_engine.usage["api_calls"] += 1

        profile_warning = None
        if "⚠️" in answer:
            warning_parts = [l.strip() for l in answer.split('\n') if '⚠️' in l]
            if warning_parts:
                profile_warning = '\n'.join(warning_parts)

        return {
            "analysis": answer,
            "drug_names": drug_names,
            "profile_warning": profile_warning,
            "drug_source": api_results[0].get("source", "") if api_results else "",
            "tokens": {"input": resp.usage.prompt_tokens, "output": resp.usage.completion_tokens},
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 분석 실패: {str(e)}")


# ──────────────────────────────────────
# 의약품 검색 (e약은요 직접 검색)
# ──────────────────────────────────────
@app.post("/api/medicine/search")
async def medicine_search(request: DrugSearchRequest):
    """e약은요 + DUR 통합 검색"""
    if not drug_client or not drug_client.api_key:
        raise HTTPException(
            status_code=400,
            detail="공공데이터 API 키를 먼저 설정해주세요.",
        )

    return await drug_client.search_unified(request.drug_name)


# ──────────────────────────────────────
# 음성 입력 교정 (GPT로 의료 문맥 자동 교정)
# ──────────────────────────────────────
class VoiceCorrectRequest(BaseModel):
    text: str

@app.post("/api/voice-correct")
async def voice_correct(request: VoiceCorrectRequest):
    """음성 인식 오류를 의료 문맥에 맞게 GPT로 교정"""
    if not rag_engine or not rag_engine.client:
        return {"corrected": request.text}
    try:
        response = rag_engine.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """음성 인식 오류가 있는 텍스트를 자연스러운 의료 상담 질문으로 교정하세요.

교정 규칙:
1. 발음이 비슷한 잘못된 단어를 올바른 의료/약품 용어로 교정하세요
   예: '열화' → '열 알', '달미정/텔미종/댈미정' → '텔미정', '고덱스' → '고덱스'
2. 문법이 어색하거나 끊긴 문장을 자연스럽게 다듬으세요
3. 원래 없던 말("괜찮을까요?" 등)을 추가하지 마세요. 있는 내용만 교정하세요
4. 의료 상담에 적합한 완전한 질문 형태로 만드세요
5. 원래 의도한 내용을 최대한 보존하세요
6. 교정된 질문만 출력하고 설명은 절대 하지 마세요

예시:
입력: "디티랑 어제 술도 많이 먹고 지금 실수로 달미정을 열화를 먹었어"
출력: "어제 술도 많이 마셨고 지금 실수로 텔미정을 열 알을 먹었어"

입력: "고혈압이랑 당뇨 있는데 홍삼 먹어도 됄까"
출력: "고혈압과 당뇨가 있는데 홍삼을 먹어도 될까요?"
"""},
                {"role": "user", "content": request.text},
            ],
            temperature=0.0,
            max_tokens=150,
        )
        corrected = response.choices[0].message.content.strip()
        return {"corrected": corrected}
    except Exception:
        return {"corrected": request.text}


# ──────────────────────────────────────
# AI 건강 분석 리포트 (RAG 없이 GPT 직접 호출 — 빠름)
# ──────────────────────────────────────
class AnalyzeProfileRequest(BaseModel):
    age: int
    diseases: str = ""
    medications: str = ""

@app.post("/api/analyze-profile")
async def analyze_profile(request: AnalyzeProfileRequest):
    """나이·기저질환·복용약 분석 — 식약처 API + GPT"""
    if not rag_engine or not rag_engine.client:
        raise HTTPException(status_code=400, detail="OpenAI API 키를 먼저 설정해주세요.")

    import asyncio

    # 식약처 API로 복용약 조회
    med_api_info = []
    if request.medications and drug_client and drug_client.api_key:
        med_names = [m.strip() for m in request.medications.split(',') if m.strip()]
        async def safe_search(name):
            try:
                result = await drug_client.search_unified(name)
                if result.get("found"):
                    return name, result
            except Exception:
                pass
            return name, None
        results = await asyncio.gather(*[safe_search(name) for name in med_names])
        med_api_info = [(name, r) for name, r in results]

    # medications_str 구성 — API 결과 있으면 정확한 정보 사용, 없으면 이름만
    KNOWN_MEDS = {
        "고덱스": "간장약 (전문의약품) — 간세포 손상으로 인한 트랜스아미나제(SGPT/ALT) 수치 상승 시 수치를 낮추고 간세포를 보호합니다.",
        "텔미지": "고혈압 치료제 (ARB 계열, 혈압 강하)",
        "텔미사르탄": "고혈압 치료제 (ARB 계열, 혈압 강하)",
        "페바로젯": "고지혈증 치료제 (스타틴 계열, 콜레스테롤 감소)",
        "페바로젯정": "고지혈증 치료제 (스타틴 계열, 콜레스테롤 감소)",
        "아스피린": "혈전 예방 및 항혈소판제",
        "메트포르민": "당뇨병 치료제 (혈당 조절)",
        "글리메피리드": "당뇨병 치료제 (인슐린 분비 촉진)",
        "암로디핀": "고혈압·협심증 치료제 (칼슘채널차단제)",
        "로수바스타틴": "고지혈증 치료제 (스타틴 계열)",
        "아토르바스타틴": "고지혈증 치료제 (스타틴 계열)",
    }

    med_context_parts = []
    if med_api_info:
        med_context_parts.append("【복용약 식약처 확인 정보】")
        for name, result in med_api_info:
            if result:
                efcy = result.get('efcy', '')
                use_method = result.get('use_method', '')
                info = efcy if efcy and efcy != '관련 정보 없음' else use_method
                if info and info != '관련 정보 없음':
                    med_context_parts.append(f"- {result.get('item_name', name)}: {info[:150]}")
                else:
                    # API 정보 없으면 KNOWN_MEDS 사전 사용
                    matched = next((desc for key, desc in KNOWN_MEDS.items() if key in name), None)
                    med_context_parts.append(f"- {name}: {matched if matched else '복용 목적은 처방의에게 확인하세요.'}")
            else:
                matched = next((desc for key, desc in KNOWN_MEDS.items() if key in name), None)
                med_context_parts.append(f"- {name}: {matched if matched else '복용 목적은 처방의에게 확인하세요.'}")

    system_prompt = """의료 정보 분석 AI입니다. 간결하게 답변하세요.
각 항목은 1줄 이내로, ①②③ 기호를 사용하세요.
복용약 분석 시 반드시 【복용약 식약처 확인 정보】에 나온 내용만 사용하세요. 없는 내용은 만들지 마세요."""

    age_str = f"{request.age}세" if request.age and request.age > 0 else "정보 없음"
    diseases_str = request.diseases if request.diseases else "정보 없음"
    medications_str = request.medications if request.medications else "정보 없음"

    med_context = "\n".join(med_context_parts) if med_context_parts else ""

    user_prompt = f"""{med_context}

나이: {age_str} / 기저질환: {diseases_str} / 복용약: {medications_str}

반드시 아래 4개 항목 타이틀을 그대로 쓰고, 각 내용을 작성하세요.
단, "정보 없음"인 항목은 "입력된 정보가 없습니다."로 간단히 표시하세요:

1. 기저질환 요약:
(각 질환 1줄씩)

2. 복용약 분석:
(각 약 1줄씩 — 반드시 위 식약처 정보 기반으로)

3. 건강 주의사항:
①②③ 각 1줄

4. 종합 한마디:
(1줄)"""

    try:
        response = rag_engine.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=350,
        )
        answer = response.choices[0].message.content.strip()
        answer += "\n\n(출처: 대한의학회 기준)\n※ 이 분석은 AI 참고 정보이며, 정확한 진단은 의료 전문가와 상담하세요."
        usage = response.usage
        rag_engine.usage["input_tokens"] += usage.prompt_tokens
        rag_engine.usage["output_tokens"] += usage.completion_tokens
        rag_engine.usage["api_calls"] += 1

        return {"answer": answer, "tokens": {"input": usage.prompt_tokens, "output": usage.completion_tokens}}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")


# ──────────────────────────────────────
# 시스템 정보
# ──────────────────────────────────────
@app.get("/api/status")
async def system_status():
    """시스템 상태 확인"""
    stats = rag_engine.get_collection_stats() if rag_engine else {}
    cost = rag_engine.get_cost() if rag_engine else {}

    return {
        "collections": stats,
        "cost": cost,
        "openai_connected": bool(rag_engine and rag_engine.client),
        "data_api_connected": bool(drug_client and drug_client.api_key),
    }


@app.post("/api/reset-usage")
async def reset_usage():
    """비용 추적 초기화"""
    if rag_engine:
        rag_engine.reset_usage()
    return {"status": "ok", "message": "사용량이 초기화되었습니다."}


# ──────────────────────────────────────
# 상담 히스토리
# ──────────────────────────────────────
@app.get("/api/history/{user_id}")
async def get_history(user_id: str = "default", limit: int = 50):
    """상담 히스토리 조회"""
    history = db.get_chat_history(user_id, limit)
    return {"user_id": user_id, "count": len(history), "history": history}


@app.delete("/api/history/{user_id}")
async def clear_history(user_id: str = "default"):
    """상담 히스토리 삭제"""
    db.clear_chat_history(user_id)
    return {"status": "ok", "message": f"{user_id}의 상담 히스토리가 삭제되었습니다."}


# ──────────────────────────────────────
# 건강 프로필
# ──────────────────────────────────────
@app.post("/api/profile")
async def save_profile(request: ProfileRequest):
    """건강 프로필 저장/수정"""
    db.save_profile(
        user_id=request.user_id,
        name=request.name,
        age=request.age,
        diseases=request.diseases,
        medications=request.medications,
    )
    return {"status": "ok", "message": "건강 프로필이 저장되었습니다.", "profile": db.get_profile(request.user_id)}


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str = "default"):
    """건강 프로필 조회"""
    profile = db.get_profile(user_id)
    if not profile:
        return {"status": "not_found", "message": "등록된 프로필이 없습니다."}
    return {"status": "ok", "profile": profile}


@app.delete("/api/profile/{user_id}")
async def delete_profile(user_id: str = "default"):
    """건강 프로필 삭제"""
    db.delete_profile(user_id)
    return {"status": "ok", "message": f"{user_id}의 프로필이 삭제되었습니다."}


@app.post("/api/cleanup/{user_id}")
async def cleanup_session(user_id: str):
    """세션 종료 시 개인정보 일괄 삭제 (sendBeacon 호출용)"""
    db.delete_profile(user_id)
    db.delete_history(user_id)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_rest_api:app", host="0.0.0.0", port=8001)
