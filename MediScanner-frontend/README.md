# DoctorGuardians 프론트엔드

MedRAG 기반 한국어 의료 QA 시스템의 React 프론트엔드

## 기술 스택

- **React 18** - UI 프레임워크
- **Vite** - 빌드 도구
- **Tailwind CSS** - 스타일링
- **Axios** - HTTP 클라이언트
- **Lucide React** - 아이콘

## 설치 및 실행

### 1. 의존성 설치
```bash
npm install
```

### 2. 환경 변수 설정
`.env.example`을 복사하여 `.env` 파일 생성:
```bash
cp .env.example .env
```

`.env` 파일 수정:
```
VITE_API_URL=http://localhost:8000
```

### 3. 개발 서버 실행
```bash
npm run dev
```

브라우저에서 `http://localhost:5173` 접속

### 4. 프로덕션 빌드
```bash
npm run build
```

빌드된 파일은 `dist/` 폴더에 생성됩니다.

## 프로젝트 구조

```
src/
├── components/
│   ├── ChatWindow.jsx          # 메인 채팅 UI
│   ├── MessageBubble.jsx        # 메시지 말풍선
│   ├── SourceBadge.jsx          # 출처 배지
│   ├── AnswerModeToggle.jsx     # 간단/상세 답변 토글
│   └── MedicineSearch.jsx       # 약 검색 탭
├── App.jsx                      # 메인 앱 컴포넌트
├── main.jsx                     # 진입점
└── index.css                    # 글로벌 스타일
```

## 주요 기능

### 1. 의료 상담 탭
- RAG 기반 의료 질문 응답
- 간단/상세 답변 모드 전환
- 출처 표시 (대한의학회, 세브란스병원 등)
- 실시간 채팅 UI

### 2. 약 검색 탭
- e약은요 API 연동
- 약 이름 또는 성분명 검색
- 효능, 용법, 부작용 정보
- DUR 병용금기 정보

## 백엔드 연동

백엔드 API 엔드포인트:

- `POST /api/chat` - 의료 질문
  ```json
  {
    "query": "고혈압 치료법은?",
    "answer_mode": "simple"  // "simple" | "detailed"
  }
  ```

- `POST /api/medicine/search` - 약 검색
  ```json
  {
    "drug_name": "타이레놀"
  }
  ```

- `GET /api/status` - 시스템 상태

## Vercel 배포

1. GitHub 레포지토리 연결
2. Build Command: `npm run build`
3. Output Directory: `dist`
4. 환경 변수 설정:
   - `VITE_API_URL`: Render 백엔드 URL

## 모바일 최적화

- 375×720px 모바일 우선 디자인
- 반응형 레이아웃
- 터치 최적화 UI

## 개발 참고사항

### API 에러 처리
백엔드 서버가 꺼져있을 때:
```
죄송합니다. 현재 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.
```

### CORS 설정
백엔드 `main_rest_api.py`에서 CORS 허용:
- `http://localhost:5173` (Vite 개발 서버)
- `https://*.vercel.app` (Vercel 배포)

## 라이선스

K-Digital 의료AI융합 교육 프로그램 파이널 프로젝트
