"""
닥터가디언 REST API (api 계층)
===============================
FastAPI 라우터 — 프론트엔드(React)와 통신하는 엔드포인트
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.domain.usecases import MedicalQAUseCase

router = APIRouter()

# 유스케이스 초기화 (서버 시작 시 1회)
qa_usecase: MedicalQAUseCase | None = None


def get_usecase() -> MedicalQAUseCase:
    global qa_usecase
    if qa_usecase is None:
        qa_usecase = MedicalQAUseCase()
    return qa_usecase


# ════════════════════════════════════════
# 요청/응답 모델
# ════════════════════════════════════════
class AskRequest(BaseModel):
    question: str


class ChatRequest(BaseModel):
    """프론트엔드 ChatWindow.jsx가 보내는 형식"""
    query: str
    answer_mode: str = "simple"      # "simple" | "detailed"
    user_id: str = "default"


class AskResponse(BaseModel):
    answer: str
    question_type: str
    detected_drugs: list[str]
    sources: list[dict]
    has_drug_api: bool
    has_dur_api: bool
    tokens: dict


class ChatResponse(BaseModel):
    """프론트엔드 ChatWindow.jsx가 받는 형식"""
    answer: str
    question_type: str
    detected_drugs: list[str]
    sources: list[dict]
    has_drug_api: bool
    has_dur_api: bool
    drug_names_detected: list[str]
    tokens: dict


class HealthResponse(BaseModel):
    status: str
    collection_count: int


# ════════════════════════════════════════
# 엔드포인트
# ════════════════════════════════════════

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    닥터가디언 핵심 API — 프로필 맞춤 답변

    ChatWindow.jsx → /api/chat
    1) user_id로 프로필(기저질환, 복용약) 조회
    2) answer_mode(간단/상세)에 따라 답변 길이 조절
    3) 프로필 정보를 GPT 프롬프트에 포함 → 맞춤 답변
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문을 입력해주세요")

    usecase = get_usecase()

    # ── 1) 프로필 조회 ──
    profile = None
    try:
        from app.database import get_profile
        profile = get_profile(request.user_id)
    except Exception:
        pass  # 프로필 없으면 None으로 진행

    # ── 2) 프로필 기반 맞춤 답변 ──
    answer = await usecase.ask(
        query=request.query,
        answer_mode=request.answer_mode,
        user_profile=profile,
    )

    return ChatResponse(
        answer=answer.text,
        question_type=answer.question_type.value,
        detected_drugs=answer.detected_drugs,
        sources=answer.sources,
        has_drug_api=answer.has_drug_api,
        has_dur_api=answer.has_dur_api,
        drug_names_detected=answer.detected_drugs,
        tokens={
            "input": answer.input_tokens,
            "output": answer.output_tokens,
        },
    )


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    기존 API (하위 호환) — 프로필 없이 답변
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력해주세요")

    usecase = get_usecase()
    answer = await usecase.ask(request.question)

    return AskResponse(
        answer=answer.text,
        question_type=answer.question_type.value,
        detected_drugs=answer.detected_drugs,
        sources=answer.sources,
        has_drug_api=answer.has_drug_api,
        has_dur_api=answer.has_dur_api,
        tokens={
            "input": answer.input_tokens,
            "output": answer.output_tokens,
        },
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """서버 상태 + 데이터 건수 확인"""
    usecase = get_usecase()
    count = usecase.chromadb.get_count()
    return HealthResponse(
        status="ok",
        collection_count=count,
    )
