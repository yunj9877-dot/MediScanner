"""
GPT 답변 생성 (infra 계층)
==========================
Self-RAG 프롬프트 + 프로필 맞춤 답변 + 간단/상세 모드
"""

from openai import OpenAI
from app.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL
from app.domain.entities import Document, DrugInfo, DURInfo, Answer, QuestionType


class OpenAIClient:
    """GPT-4o-mini 답변 생성 — Self-RAG 환각 방지 + 프로필 맞춤"""

    BASE_SYSTEM_PROMPT = """당신은 고령자를 위한 의료 상담 AI 메디스캐너입니다.

답변 규칙:
1. 어르신이 이해하기 쉬운 말로 설명하세요 (전문 용어는 풀어서)
2. 각 문장 끝에 출처를 표시하세요 — (출처: 대한의학회)
3. 참고자료에서 관련 정보를 찾지 못하면 "관련 정보를 찾지 못했습니다"라고 솔직히 말하세요
4. API 데이터(의약품 정보)가 있으면 정확히 인용하되 과장하지 마세요
5. 주의사항이 있으면 ⚠️로 강조하세요
6. 마지막에 "※ 정보는 참고용이며, 정확한 진단은 의료 전문가와 상담하세요." 안내"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _build_system_prompt(
        self,
        answer_mode: str = "simple",
        user_profile: dict | None = None,
    ) -> str:
        """
        시스템 프롬프트 구성:
        - 기본 규칙 + 프로필 맞춤 지시 + 답변 길이 조절
        """
        prompt_parts = [self.BASE_SYSTEM_PROMPT]

        # ── 프로필 맞춤 지시 ──
        if user_profile:
            age = user_profile.get("age", 0)
            diseases = user_profile.get("diseases", "")
            medications = user_profile.get("medications", "")

            has_profile = age or diseases or medications

            if has_profile:
                disease_list = [d.strip() for d in diseases.split(',') if d.strip()] if diseases else []

                profile_lines = ["\n【⚠️ 최우선 지시 — 반드시 따르세요】"]
                profile_lines.append("이 사용자의 건강 정보:")

                if age:
                    profile_lines.append(f"▶ 나이: {age}세")
                if diseases:
                    profile_lines.append(f"▶ 기저질환: {diseases}")
                if medications:
                    profile_lines.append(f"▶ 현재 복용약: {medications}")

                profile_lines.append("\n【답변 형식 — 반드시 이 형식으로 작성하세요】")

                if disease_list:
                    circles = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']
                    if len(disease_list) == 1:
                        # 기저질환 1개: 항목 형식 강요 안 함
                        profile_lines.append(f"기저질환 '{disease_list[0]}'에 미치는 영향을 중심으로 답변하세요.")
                        profile_lines.append(f"⚠️ 절대로 {disease_list[0]} 외의 다른 질환(당뇨병, 고지혈증 등)을 임의로 추가하지 마세요.")
                    else:
                        profile_lines.append("답변은 반드시 아래 형식으로 기저질환별로 나누어 작성하세요:")
                        for i, disease in enumerate(disease_list):
                            c = circles[i] if i < len(circles) else f"({i+1})"
                            profile_lines.append(f"{c} {disease}: [질문 내용이 {disease}에 미치는 영향을 1~2문장으로]")
                        profile_lines.append(f"⚠️ 위 {len(disease_list)}개 기저질환 외에 다른 질환을 임의로 추가하지 마세요.")
                    if medications:
                        profile_lines.append(f"💊 복용약 주의: [복용 중인 {medications}와의 상호작용]")
                    profile_lines.append("※ 참고용 정보입니다. 정확한 진단은 의료 전문가와 상담하세요.")

                profile_lines.append("\n【추가 규칙】")
                if len(disease_list) > 1:
                    profile_lines.append(f"- 기저질환 {len(disease_list)}개를 반드시 모두 개별 항목으로 작성하세요. 하나라도 빠지면 안 됩니다.")
                profile_lines.append(f"- 등록된 기저질환: {', '.join(disease_list)} — 이 외의 질환은 절대 언급하지 마세요.")
                profile_lines.append("- '일반적으로는...' 표현 절대 금지.")
                profile_lines.append("- 위험한 내용은 ⚠️로 강조하세요.")

                prompt_parts.append("\n".join(profile_lines))

        # ── 답변 길이 조절 ──
        if answer_mode == "simple":
            prompt_parts.append(
                "\n답변 길이는 간단 모드: 핵심만 2~3문장으로 답변하세요."
            )
        else:
            prompt_parts.append(
                "\n답변 길이는 상세 모드: 원인, 증상, 치료법, 주의사항을 포함하여 자세히 답변하세요."
            )

        return "\n".join(prompt_parts)

    def generate(
        self,
        query: str,
        docs: list[Document],
        drug_info: DrugInfo | None = None,
        dur_info: list[DURInfo] | None = None,
        answer_mode: str = "simple",
        user_profile: dict | None = None,
    ) -> tuple[str, int, int]:
        """
        GPT 답변 생성 — 프로필 맞춤 + 간단/상세 모드

        Args:
            query: 사용자 질문
            docs: RAG 검색 결과
            drug_info: e약은요 API 결과
            dur_info: DUR 병용금기 결과
            answer_mode: "simple" / "detailed"
            user_profile: {"name", "age", "diseases", "medications"}

        Returns: (답변 텍스트, input_tokens, output_tokens)
        """
        if not self.client:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다")

        # 시스템 프롬프트 (프로필 + 모드 포함)
        system_prompt = self._build_system_prompt(answer_mode, user_profile)

        # 컨텍스트 구성
        context = self._build_context(docs, drug_info, dur_info)

        # max_tokens 조절 — 기저질환 수에 따라 늘림
        disease_list = []
        if user_profile and user_profile.get("diseases"):
            disease_list = [d.strip() for d in user_profile["diseases"].split(',') if d.strip()]
        base_tokens = 120 if answer_mode == "simple" else 500
        max_tokens = base_tokens + len(disease_list) * 60  # 질환당 60토큰 추가

        # 기저질환별 형식 템플릿 생성
        format_instruction = ""
        if disease_list:
            circles = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']
            lines = [f"【등록된 기저질환: {', '.join(disease_list)} — 이 외 질환 언급 금지】"]
            if len(disease_list) == 1:
                lines.append(f"기저질환 '{disease_list[0]}'에 집중하여 답변하세요.")
            else:
                lines.append("【반드시 아래 형식으로 답변하세요】")
                for i, disease in enumerate(disease_list):
                    c = circles[i] if i < len(circles) else f"({i+1})"
                    lines.append(f"{c} {disease}: (이 질환에 미치는 영향 1~2문장)")
            if user_profile.get("medications"):
                lines.append(f"💊 복용약 주의: (복용 중인 {user_profile['medications']}와의 관계)")
            format_instruction = "\n" + "\n".join(lines) + "\n"

        user_prompt = f"""【참고자료】
{context}

【사용자 질문】{query}
{format_instruction}
위 형식을 반드시 지켜서, 참고자료를 근거로 답변해주세요. 기저질환 항목을 하나라도 빠뜨리지 마세요."""

        response = self.client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
        )

        usage = response.usage
        self.total_input_tokens += usage.prompt_tokens
        self.total_output_tokens += usage.completion_tokens

        return (
            response.choices[0].message.content,
            usage.prompt_tokens,
            usage.completion_tokens,
        )

    def _build_context(
        self,
        docs: list[Document],
        drug_info: DrugInfo | None,
        dur_info: list[DURInfo] | None,
    ) -> str:
        """검색 결과 + API 데이터를 컨텍스트 문자열로 조합"""
        parts = []

        # 1) RAG 검색 결과
        if docs:
            parts.append("【의료DB 검색 결과】")
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("source_spec", "출처 없음")
                parts.append(f"[문서 {i}] (출처: {source})\n{doc.text}")

        # 2) e약은요 API
        if drug_info:
            parts.append("\n【식약처 e약은요 API - 의약품 정보】")
            parts.append(f"제품명: {drug_info.item_name}")
            parts.append(f"업체명: {drug_info.entp_name}")
            parts.append(f"효능: {drug_info.efcy}")
            parts.append(f"사용법: {drug_info.use_method}")
            parts.append(f"주의사항: {drug_info.atpn}")
            parts.append(f"상호작용: {drug_info.intrc}")
            parts.append(f"부작용: {drug_info.se}")

        # 3) DUR 병용금기
        if dur_info:
            parts.append("\n【DUR - 병용금기 정보】")
            for item in dur_info:
                parts.append(
                    f"- {item.mixture_item_name}: "
                    f"{item.prohbt_content} (사유: {item.remark})"
                )

        return "\n".join(parts)
