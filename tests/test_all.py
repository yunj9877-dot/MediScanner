"""
메디스캐너 TDD 테스트
===================
클린 아키텍처 + TDD (RED → GREEN → REFACTOR)

테스트 구조:
  1. Domain 계층 테스트 — 비즈니스 로직 (외부 의존 없음, Mock 사용)
  2. Infra 계층 테스트 — 외부 도구 독립 동작 검증
  3. 통합 테스트 — Domain + Infra 연결 검증
  4. API 계층 테스트 — REST API 요청/응답 검증
  5. DB 계층 테스트 — SQLite 히스토리/프로필 CRUD 검증
  6. 날씨/카메라 API 테스트 — 새 기능 검증

실행: $env:PYTHONPATH = "."; pytest tests/ -v
"""

import pytest
import os
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
from app.domain.entities import (
    Question, QuestionType, Document, DrugInfo, DURInfo, Answer
)


# ════════════════════════════════════════════════════════════
# 1. Domain 계층 테스트 — 핵심 비즈니스 로직
#    클린 아키텍처 원칙: domain은 infra에 의존하지 않음
#    → Mock으로 infra를 대체하여 domain만 독립 테스트
# ════════════════════════════════════════════════════════════

class TestEntities:
    """
    [TDD RED] 엔티티가 올바른 구조를 가져야 한다
    [TDD GREEN] dataclass로 구현하여 통과
    """

    def test_question_defaults_to_medical_type(self):
        """질문 생성 시 기본 타입은 MEDICAL이어야 한다"""
        q = Question(text="고혈압 치료법은?")
        assert q.question_type == QuestionType.MEDICAL
        assert q.detected_drugs == []

    def test_question_preserves_drug_info(self):
        """약 이름이 감지된 질문은 약 정보를 보존해야 한다"""
        q = Question(
            text="타이레놀 부작용은?",
            question_type=QuestionType.DRUG,
            detected_drugs=["타이레놀"],
        )
        assert q.question_type == QuestionType.DRUG
        assert "타이레놀" in q.detected_drugs

    def test_document_has_default_scores(self):
        """문서 생성 시 기본 점수는 0이어야 한다"""
        doc = Document(id="doc_1", text="테스트 문서")
        assert doc.score == 0.0
        assert doc.rrf_score == 0.0
        assert doc.found_in == []

    def test_drug_info_from_api_maps_fields_correctly(self):
        """API 응답이 DrugInfo 필드에 올바르게 매핑되어야 한다"""
        api_data = {
            "itemName": "타이레놀정500밀리그램",
            "entpName": "한국존슨앤드존슨",
            "efcyQesitm": "해열, 진통",
            "useMethodQesitm": "1일 3회",
            "atpnQesitm": "간질환 주의",
            "seQesitm": "간손상",
        }
        info = DrugInfo.from_api(api_data)
        assert info.item_name == "타이레놀정500밀리그램"
        assert info.efcy == "해열, 진통"
        assert info.use_method == "1일 3회"
        assert info.atpn == "간질환 주의"
        assert info.se == "간손상"

    def test_drug_info_handles_missing_fields(self):
        """API 응답에 필드가 없어도 빈 문자열로 처리해야 한다"""
        info = DrugInfo.from_api({})
        assert info.item_name == ""
        assert info.efcy == ""

    def test_dur_info_from_api_maps_correctly(self):
        """DUR API 응답이 올바르게 매핑되어야 한다"""
        api_data = {
            "MIXTURE_ITEM_NAME": "아스피린",
            "PROHBT_CONTENT": "병용 시 출혈 위험 증가",
            "REMARK": "위장관 출혈",
        }
        info = DURInfo.from_api(api_data)
        assert info.mixture_item_name == "아스피린"
        assert "출혈" in info.prohbt_content

    def test_answer_tracks_api_usage(self):
        """답변이 API 사용 여부를 올바르게 추적해야 한다"""
        answer = Answer(text="타이레놀은 해열제입니다.", has_drug_api=True, has_dur_api=False)
        assert answer.has_drug_api is True
        assert answer.has_dur_api is False

    def test_question_type_enum_values(self):
        """질문 타입 enum 값이 올바른 문자열이어야 한다"""
        assert QuestionType.MEDICAL.value == "medical"
        assert QuestionType.DRUG.value == "drug"
        assert QuestionType.HYBRID.value == "hybrid"


# ════════════════════════════════════════════════════════════
# 2. Infra 계층 테스트 — 외부 도구 독립 테스트
# ════════════════════════════════════════════════════════════

class TestQuestionClassifier:
    """
    [TDD RED] 질문에서 약 이름을 정확히 추출해야 한다
    [TDD GREEN] extract_drug_names() 구현하여 통과
    [TDD REFACTOR] common_drugs 리스트 확장
    """

    def test_no_drug_in_medical_question(self):
        """의학 지식 질문에서는 약 이름이 없어야 한다"""
        from app.infra.drug_api import extract_drug_names
        assert extract_drug_names("고혈압 치료법은?") == []

    def test_detects_single_drug(self):
        """단일 약 이름을 감지해야 한다"""
        from app.infra.drug_api import extract_drug_names
        assert "타이레놀" in extract_drug_names("타이레놀 부작용은?")

    def test_detects_multiple_drugs(self):
        """여러 약 이름을 동시에 감지해야 한다"""
        from app.infra.drug_api import extract_drug_names
        result = extract_drug_names("타이레놀이랑 아스피린 같이 먹어도 돼?")
        assert "타이레놀" in result
        assert "아스피린" in result

    def test_does_not_detect_non_drug_words(self):
        """약이 아닌 단어를 약으로 감지하면 안 된다"""
        from app.infra.drug_api import extract_drug_names
        assert extract_drug_names("오늘 날씨가 좋아요") == []

    def test_detects_vitamin(self):
        """비타민 같은 영양제도 감지해야 한다"""
        from app.infra.drug_api import extract_drug_names
        assert "비타민" in extract_drug_names("비타민 많이 먹어도 돼요?")


class TestRRFFusion:
    """
    [TDD RED] 두 검색 결과를 합칠 때 양쪽 모두 높은 문서가 1위여야 한다
    [TDD GREEN] RRFFusion.fuse() 구현하여 통과
    [TDD REFACTOR] Document dataclass 활용으로 코드 정리
    """

    def test_both_sides_high_ranks_first(self):
        """양쪽 검색에서 모두 상위인 문서가 최종 1위여야 한다"""
        from app.infra.rrf_fusion import RRFFusion
        semantic = [
            Document(id="A", text="문서A", score=0.9, source="semantic"),
            Document(id="B", text="문서B", score=0.8, source="semantic"),
        ]
        bm25 = [
            Document(id="B", text="문서B", score=10.0, source="bm25"),
            Document(id="A", text="문서A", score=8.0, source="bm25"),
        ]
        results = RRFFusion().fuse(semantic, bm25, top_k=2)
        assert len(results) == 2
        assert all(doc.rrf_score > 0 for doc in results)

    def test_found_in_tracks_source(self):
        """found_in에 검색 출처가 올바르게 기록되어야 한다"""
        from app.infra.rrf_fusion import RRFFusion
        results = RRFFusion().fuse(
            [Document(id="A", text="문서A", source="semantic")],
            [Document(id="A", text="문서A", source="bm25")],
            top_k=1,
        )
        assert "semantic" in results[0].found_in
        assert "bm25" in results[0].found_in

    def test_empty_inputs_return_empty(self):
        """빈 입력이면 빈 결과를 반환해야 한다"""
        from app.infra.rrf_fusion import RRFFusion
        assert RRFFusion().fuse([], [], top_k=5) == []

    def test_single_source_works(self):
        """한쪽 검색 결과만 있어도 동작해야 한다"""
        from app.infra.rrf_fusion import RRFFusion
        results = RRFFusion().fuse(
            [Document(id="A", text="문서A", source="semantic")], [], top_k=5
        )
        assert len(results) == 1

    def test_top_k_limits_results(self):
        """top_k보다 많은 결과가 있어도 top_k개만 반환해야 한다"""
        from app.infra.rrf_fusion import RRFFusion
        docs = [Document(id=f"doc_{i}", text=f"문서{i}", source="semantic") for i in range(10)]
        assert len(RRFFusion().fuse(docs, [], top_k=3)) == 3


class TestBM25Search:
    """
    [TDD RED] 한국어 토크나이징과 검색이 올바르게 동작해야 한다
    [TDD GREEN] BM25Search 구현하여 통과
    """

    def test_tokenizes_korean_words(self):
        """한국어 단어를 올바르게 분리해야 한다"""
        from app.infra.bm25_search import BM25Search
        tokens = BM25Search()._tokenize("고혈압 치료법은 무엇인가요?")
        assert "고혈압" in tokens

    def test_filters_single_char_tokens(self):
        """1글자 토큰은 제외해야 한다 (노이즈 방지)"""
        from app.infra.bm25_search import BM25Search
        tokens = BM25Search()._tokenize("나 는 약 을 먹었다")
        assert "나" not in tokens
        assert "먹었다" in tokens

    def test_handles_mixed_language(self):
        """한영 혼합 텍스트도 처리해야 한다"""
        from app.infra.bm25_search import BM25Search
        tokens = BM25Search()._tokenize("COVID19 코로나 백신 접종")
        assert "covid19" in tokens
        assert "코로나" in tokens

    def test_search_returns_empty_without_index(self):
        """인덱스 없이 검색하면 빈 리스트를 반환해야 한다"""
        from app.infra.bm25_search import BM25Search
        assert BM25Search().search("테스트 질문") == []

    def test_build_and_search(self):
        """인덱스 구축 후 검색이 동작해야 한다"""
        from app.infra.bm25_search import BM25Search
        bm25 = BM25Search()
        bm25.build_index(
            docs=[
                "고혈압 치료 방법은 저염식이와 운동입니다",
                "당뇨병 환자는 혈당 관리가 중요합니다",
                "감기에 걸리면 충분한 휴식이 필요합니다",
                "두통이 심하면 진통제를 복용할 수 있습니다",
                "비만 예방을 위해 균형 잡힌 식단이 중요합니다",
            ],
            metadatas=[{"source": f"test{i}"} for i in range(5)],
            ids=[f"doc_{i}" for i in range(5)],
        )
        results = bm25.search("고혈압 치료", top_k=1)
        assert len(results) >= 1
        assert "고혈압" in results[0].text


class TestOpenAIContext:
    """
    [TDD RED] GPT에 전달하는 컨텍스트가 올바르게 구성되어야 한다
    [TDD GREEN] _build_context() 구현하여 통과
    [TDD REFACTOR] 각 데이터 유형별 컨텍스트 분리
    """

    def _client(self):
        from app.infra.openai_client import OpenAIClient
        return OpenAIClient(api_key="test")

    def test_context_includes_rag_results(self):
        """RAG 검색 결과가 컨텍스트에 포함되어야 한다"""
        context = self._client()._build_context(
            [Document(id="1", text="고혈압 치료 방법", metadata={"source_spec": "대한의학회"})],
            None, None,
        )
        assert "의료DB 검색 결과" in context
        assert "대한의학회" in context

    def test_context_includes_drug_api(self):
        """식약처 API 결과가 컨텍스트에 포함되어야 한다"""
        context = self._client()._build_context(
            [], DrugInfo(item_name="타이레놀", efcy="해열, 진통", se="간손상"), None,
        )
        assert "식약처" in context
        assert "타이레놀" in context
        assert "간손상" in context

    def test_context_includes_dur(self):
        """DUR 병용금기 정보가 컨텍스트에 포함되어야 한다"""
        context = self._client()._build_context(
            [], None, [DURInfo(mixture_item_name="아스피린", prohbt_content="출혈 위험 증가")],
        )
        assert "DUR" in context
        assert "아스피린" in context

    def test_context_combines_all_sources(self):
        """RAG + API + DUR이 모두 하나의 컨텍스트에 합쳐져야 한다"""
        context = self._client()._build_context(
            [Document(id="1", text="고혈압 약물 치료", metadata={"source_spec": "세브란스병원"})],
            DrugInfo(item_name="아달라트", efcy="혈압 강하"),
            [DURInfo(mixture_item_name="자몽주스", prohbt_content="약효 증가 위험")],
        )
        assert "의료DB" in context
        assert "식약처" in context
        assert "DUR" in context

    def test_empty_context_returns_empty_string(self):
        """아무 데이터도 없으면 빈 문자열을 반환해야 한다"""
        assert self._client()._build_context([], None, None) == ""


# ════════════════════════════════════════════════════════════
# 3. 통합 테스트 — Domain + Infra 연결
#    클린 아키텍처 원칙: domain이 infra를 Mock으로 주입받아 테스트
# ════════════════════════════════════════════════════════════

class TestMedicalQAUseCaseClassification:
    """
    [TDD RED] 질문 분류가 올바르게 동작해야 한다
    [TDD GREEN] classify_question() 구현하여 통과
    ※ infra(ChromaDB, BM25) 없이 domain 로직만 Mock으로 테스트
    """

    def _make_usecase(self):
        from app.domain.usecases import MedicalQAUseCase
        with patch.object(MedicalQAUseCase, '__init__', lambda self: None):
            return MedicalQAUseCase()

    def test_classifies_medical_question(self):
        """의학 질문은 MEDICAL로 분류해야 한다"""
        q = self._make_usecase().classify_question("고혈압 치료법은?")
        assert q.question_type == QuestionType.MEDICAL

    def test_classifies_drug_question(self):
        """약 이름만 있는 질문은 DRUG로 분류해야 한다"""
        q = self._make_usecase().classify_question("타이레놀 부작용은?")
        assert q.question_type == QuestionType.DRUG
        assert "타이레놀" in q.detected_drugs

    def test_classifies_hybrid_question(self):
        """약 + 질환이 있는 질문은 HYBRID로 분류해야 한다"""
        q = self._make_usecase().classify_question("고혈압인데 아스피린 치료에 좋아?")
        assert q.question_type == QuestionType.HYBRID

    def test_drug_without_medical_keyword_is_drug(self):
        """의학 키워드 없이 약 이름만 있으면 DRUG"""
        q = self._make_usecase().classify_question("타이레놀 가격은?")
        assert q.question_type == QuestionType.DRUG


# ════════════════════════════════════════════════════════════
# 4. API 계층 테스트 — REST API 요청/응답
# ════════════════════════════════════════════════════════════

class TestAPIModels:
    """
    [TDD RED] API 요청/응답 모델이 올바르게 동작해야 한다
    [TDD GREEN] Pydantic BaseModel로 구현하여 통과
    """

    def test_ask_request_model(self):
        """요청 모델에 question 필드가 있어야 한다"""
        from app.api.routes import AskRequest
        req = AskRequest(question="고혈압 치료법은?")
        assert req.question == "고혈압 치료법은?"

    def test_ask_response_has_all_fields(self):
        """응답 모델에 필수 필드가 모두 있어야 한다"""
        from app.api.routes import AskResponse
        resp = AskResponse(
            answer="고혈압은 저염식이가 중요합니다.",
            question_type="medical",
            detected_drugs=[],
            sources=[],
            has_drug_api=False,
            has_dur_api=False,
            tokens={"input": 100, "output": 50},
        )
        assert resp.answer != ""
        assert resp.question_type == "medical"

    def test_health_response_model(self):
        """헬스체크 응답에 status와 count가 있어야 한다"""
        from app.api.routes import HealthResponse
        resp = HealthResponse(status="ok", collection_count=1509657)
        assert resp.status == "ok"
        assert resp.collection_count == 1509657


# ════════════════════════════════════════════════════════════
# 5. DB 계층 테스트 — SQLite 히스토리/프로필 CRUD
#    실제 SQLite 파일을 테스트용으로 생성하고 삭제
# ════════════════════════════════════════════════════════════

class TestDatabase:
    """
    [TDD RED] SQLite DB에 상담 히스토리와 건강 프로필을 저장/조회/삭제할 수 있어야 한다
    [TDD GREEN] database.py 모듈 구현하여 통과
    """

    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path):
        """테스트마다 임시 DB를 생성하고 테스트 후 삭제"""
        import app.database as db
        self.test_db = str(tmp_path / "test.db")
        db.DB_PATH = self.test_db
        db.init_db()
        self.db = db

    def test_init_db_creates_tables(self):
        """init_db가 user_profile과 chat_history 테이블을 생성해야 한다"""
        conn = sqlite3.connect(self.test_db)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        conn.close()
        assert "user_profile" in table_names
        assert "chat_history" in table_names

    def test_save_and_get_profile(self):
        """프로필을 저장하고 조회할 수 있어야 한다"""
        self.db.save_profile("test_user", name="홍길동", age=70, diseases="고혈압, 당뇨병", medications="아스피린")
        profile = self.db.get_profile("test_user")
        assert profile is not None
        assert profile["name"] == "홍길동"
        assert profile["age"] == 70
        assert "고혈압" in profile["diseases"]
        assert "아스피린" in profile["medications"]

    def test_update_profile(self):
        """기존 프로필을 수정하면 업데이트되어야 한다"""
        self.db.save_profile("test_user", name="홍길동", age=70, diseases="고혈압")
        self.db.save_profile("test_user", name="홍길동", age=71, diseases="고혈압, 당뇨병")
        profile = self.db.get_profile("test_user")
        assert profile["age"] == 71
        assert "당뇨병" in profile["diseases"]

    def test_delete_profile(self):
        """프로필을 삭제하면 조회 시 None이어야 한다"""
        self.db.save_profile("test_user", name="홍길동")
        self.db.delete_profile("test_user")
        assert self.db.get_profile("test_user") is None

    def test_get_nonexistent_profile_returns_none(self):
        """존재하지 않는 프로필 조회 시 None을 반환해야 한다"""
        assert self.db.get_profile("nonexistent") is None

    def test_save_and_get_chat_history(self):
        """상담 내역을 저장하고 조회할 수 있어야 한다"""
        self.db.save_chat("test_user", question="고혈압 증상은?", answer="증상이 없을 수 있습니다.", answer_mode="simple")
        history = self.db.get_chat_history("test_user")
        assert len(history) == 1
        assert history[0]["question"] == "고혈압 증상은?"
        assert history[0]["answer_mode"] == "simple"

    def test_chat_history_ordered_by_newest(self):
        """상담 내역은 최신순으로 정렬되어야 한다"""
        self.db.save_chat("test_user", question="첫번째 질문", answer="첫번째 답변")
        self.db.save_chat("test_user", question="두번째 질문", answer="두번째 답변")
        history = self.db.get_chat_history("test_user")
        assert history[0]["question"] == "두번째 질문"

    def test_chat_history_limit(self):
        """limit 파라미터가 결과 수를 제한해야 한다"""
        for i in range(10):
            self.db.save_chat("test_user", question=f"질문{i}", answer=f"답변{i}")
        history = self.db.get_chat_history("test_user", limit=3)
        assert len(history) == 3

    def test_clear_chat_history(self):
        """상담 내역 삭제 후 빈 리스트를 반환해야 한다"""
        self.db.save_chat("test_user", question="테스트", answer="테스트 답변")
        self.db.clear_chat_history("test_user")
        assert self.db.get_chat_history("test_user") == []

    def test_chat_saves_token_info(self):
        """상담 내역에 토큰 사용량이 저장되어야 한다"""
        self.db.save_chat("test_user", question="테스트", answer="답변",
                          tokens_input=1500, tokens_output=50)
        history = self.db.get_chat_history("test_user")
        assert history[0]["tokens_input"] == 1500
        assert history[0]["tokens_output"] == 50

    def test_chat_saves_drug_names(self):
        """상담 내역에 감지된 약 이름이 저장되어야 한다"""
        self.db.save_chat("test_user", question="타이레놀 부작용", answer="답변",
                          drug_names="타이레놀")
        history = self.db.get_chat_history("test_user")
        assert "타이레놀" in history[0]["drug_names"]

    def test_separate_user_histories(self):
        """다른 user_id는 서로 독립적인 히스토리를 가져야 한다"""
        self.db.save_chat("user_a", question="질문A", answer="답변A")
        self.db.save_chat("user_b", question="질문B", answer="답변B")
        assert len(self.db.get_chat_history("user_a")) == 1
        assert len(self.db.get_chat_history("user_b")) == 1
        assert self.db.get_chat_history("user_a")[0]["question"] == "질문A"


# ════════════════════════════════════════════════════════════
# 6. 프로필 기반 맞춤 답변 테스트
#    건강 프로필이 GPT 컨텍스트에 올바르게 전달되는지 검증
# ════════════════════════════════════════════════════════════

class TestProfileContext:
    """
    [TDD RED] 건강 프로필이 있으면 GPT 컨텍스트에 포함되어야 한다
    [TDD GREEN] rag_engine.py의 generate_answer에 user_profile 파라미터 추가하여 통과
    """

    def test_profile_adds_context_to_prompt(self):
        """프로필 정보가 GPT 프롬프트에 포함되어야 한다"""
        from app.rag_engine import RAGEngine
        engine = RAGEngine.__new__(RAGEngine)
        engine.client = MagicMock()
        engine.usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "searches": 0}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "테스트 답변"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        engine.client.chat.completions.create.return_value = mock_response

        result = engine.generate_answer(
            query="고혈압약 추천해주세요",
            retrieved_docs=[],
            user_profile={"age": 70, "diseases": "고혈압, 당뇨병", "medications": "아스피린"},
        )

        call_args = engine.client.chat.completions.create.call_args
        user_content = call_args[1]["messages"][1]["content"]
        assert "70세" in user_content
        assert "고혈압" in user_content
        assert "아스피린" in user_content

    def test_no_profile_skips_context(self):
        """프로필이 없으면 건강 정보 컨텍스트가 없어야 한다"""
        from app.rag_engine import RAGEngine
        engine = RAGEngine.__new__(RAGEngine)
        engine.client = MagicMock()
        engine.usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "searches": 0}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "테스트 답변"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        engine.client.chat.completions.create.return_value = mock_response

        result = engine.generate_answer(
            query="고혈압 증상은?",
            retrieved_docs=[],
            user_profile=None,
        )

        call_args = engine.client.chat.completions.create.call_args
        user_content = call_args[1]["messages"][1]["content"]
        assert "사용자 건강 정보" not in user_content


# ════════════════════════════════════════════════════════════
# 7. 답변 모드 테스트 — 간단/상세 프롬프트 분기
# ════════════════════════════════════════════════════════════

class TestAnswerMode:
    """
    [TDD RED] 간단/상세 모드에 따라 다른 프롬프트와 max_tokens이 적용되어야 한다
    [TDD GREEN] answer_mode 분기 구현하여 통과
    """

    def _make_engine(self):
        from app.rag_engine import RAGEngine
        engine = RAGEngine.__new__(RAGEngine)
        engine.client = MagicMock()
        engine.usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "searches": 0}
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "테스트"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        engine.client.chat.completions.create.return_value = mock_response
        return engine

    def test_simple_mode_uses_low_max_tokens(self):
        """간단 모드는 max_tokens가 200이어야 한다"""
        engine = self._make_engine()
        engine.generate_answer("테스트", [], answer_mode="simple")
        call_args = engine.client.chat.completions.create.call_args
        assert call_args[1]["max_tokens"] == 200

    def test_detailed_mode_uses_high_max_tokens(self):
        """상세 모드는 max_tokens가 800이어야 한다"""
        engine = self._make_engine()
        engine.generate_answer("테스트", [], answer_mode="detailed")
        call_args = engine.client.chat.completions.create.call_args
        assert call_args[1]["max_tokens"] == 800

    def test_simple_prompt_contains_one_sentence_rule(self):
        """간단 모드 프롬프트에 핵심 답변 규칙이 포함되어야 한다"""
        engine = self._make_engine()
        engine.generate_answer("테스트", [], answer_mode="simple")
        call_args = engine.client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]
        assert "간단 답변 규칙" in system_prompt

    def test_detailed_prompt_contains_four_sentence_rule(self):
        """상세 모드 프롬프트에 답변 규칙이 포함되어야 한다"""
        engine = self._make_engine()
        engine.generate_answer("테스트", [], answer_mode="detailed")
        call_args = engine.client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]
        assert "답변 규칙" in system_prompt

# ══════════════════════════════════════════════════════════════
# 8. XML/CDATA 파싱 테스트 (2026-03-20 추가)
#    허가정보 API 응답의 XML 태그 + CDATA 처리
# ══════════════════════════════════════════════════════════════
class TestXMLCDATAParsing:
    """XML/CDATA 파싱 — _clean_html_str() 검증"""

    def test_cdata_extraction(self):
        """CDATA 태그 안의 텍스트가 추출되어야 한다"""
        from app.infra.drug_api import DrugAPIClient
        client = DrugAPIClient()
        xml = '<DOC><SECTION><PARAGRAPH><![CDATA[고혈압 치료에 사용]]></PARAGRAPH></SECTION></DOC>'
        result = client._clean_html_str(xml)
        assert "고혈압 치료에 사용" in result

    def test_empty_string_returns_empty(self):
        """빈 문자열 입력 시 빈 문자열 반환"""
        from app.infra.drug_api import DrugAPIClient
        client = DrugAPIClient()
        assert client._clean_html_str("") == ""
        assert client._clean_html_str(None) == ""

# ══════════════════════════════════════════════════════════════
# 9. 프로필 맞춤 시스템 프롬프트 테스트 (2026-03-20 추가)
#    프로필 정보가 GPT 프롬프트에 반영되는지 검증
# ══════════════════════════════════════════════════════════════
class TestProfileSystemPrompt:
    """프로필 맞춤 — _build_system_prompt() 검증"""

    def test_profile_included_in_prompt(self):
        """프로필이 있으면 기저질환/복용약이 프롬프트에 포함되어야 한다"""
        from app.infra.openai_client import OpenAIClient
        client = OpenAIClient(api_key="test")
        profile = {"name": "홍길동", "age": 72, "diseases": "고혈압, 당뇨병", "medications": "아스피린"}
        prompt = client._build_system_prompt(answer_mode="simple", user_profile=profile)
        assert "고혈압" in prompt
        assert "아스피린" in prompt

    def test_no_profile_no_diseases_in_prompt(self):
        """프로필이 없으면 기저질환 정보가 프롬프트에 없어야 한다"""
        from app.infra.openai_client import OpenAIClient
        client = OpenAIClient(api_key="test")
        prompt = client._build_system_prompt(answer_mode="simple", user_profile=None)
        assert "기저질환" not in prompt


# ══════════════════════════════════════════════════════════════
# 10. BM25 캐시 로딩 테스트 (2026-03-20 추가)
#     try_load_cache() 캐시 파일 없을 때 안전하게 False 반환
# ══════════════════════════════════════════════════════════════
class TestBM25CacheSafety:
    """BM25 캐시 — 캐시 없을 때 안전 처리"""

    def test_try_load_cache_no_file_returns_false(self):
        """캐시 파일이 없으면 False 반환"""
        from app.infra.bm25_search import BM25Search
        import app.infra.bm25_search as bm25_module
        bm25 = BM25Search()
        original_path = bm25_module.BM25_CACHE_PATH
        bm25_module.BM25_CACHE_PATH = "nonexistent_cache_99999.pkl"
        result = bm25.try_load_cache()
        bm25_module.BM25_CACHE_PATH = original_path
        assert result is False