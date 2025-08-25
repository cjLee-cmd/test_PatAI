# Pat.AI - 특허분석 AI

RAG(Retrieval-Augmented Generation) 기반의 특허 검색 및 분석 시스템입니다.

## 주요 기능

- **특허 문서 검색**: AI 기반 자연어 질의응답
- **문서 관리**: PDF 특허 문서 업로드 및 자동 처리
- **사용자 관리**: 로그인/회원가입, 관리자/사용자 권한 분리
- **검색 히스토리**: 개인별 검색 기록 관리
- **실시간 채팅 인터페이스**: ChatGPT 스타일의 사용자 친화적 UI

## 기술 스택

### Backend
- **FastAPI**: 고성능 웹 프레임워크
- **SQLAlchemy**: ORM 및 데이터베이스 관리
- **ChromaDB**: 벡터 데이터베이스
- **Sentence Transformers**: 텍스트 임베딩
- **PyPDF**: PDF 텍스트 추출

### Frontend
- **HTML/CSS/JavaScript**: 순수 웹 기술
- **Tailwind CSS**: 유틸리티 기반 CSS 프레임워크
- **Axios**: HTTP 클라이언트

### AI/ML
- **OpenAI GPT**: 자연어 생성 (설정 시)
- **Sentence-BERT**: 다국어 임베딩 모델

## 설치 및 실행

### 1. 환경 설정

```bash
# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 API 키 등을 설정하세요
```

### 2. 실행

```bash
# 개발 서버 실행
python main.py

# 또는 uv를 사용하여 실행
uv run python main.py
```

서버가 실행되면 http://localhost:8000 에서 애플리케이션에 접근할 수 있습니다.

### 3. 초기 설정

- 기본 관리자 계정: `Admin` / `Admin`
- 관리자로 로그인 후 PDF 문서를 업로드하세요
- 일반 사용자는 회원가입 후 특허 검색이 가능합니다

## 사용 방법

### 1. 관리자 기능
- `/admin` 페이지에서 PDF 문서 업로드/삭제
- 시스템 통계 및 사용자 관리

### 2. 사용자 기능
- 메인 페이지에서 특허 관련 질문 입력
- 검색 기록 확인 및 관리
- 실시간 응답 및 관련 문서 확인

### 3. 검색 예시
- "AI 기술 관련 특허는 어떤 것들이 있나요?"
- "바이오 센서 특허의 최신 동향을 알려주세요"
- "반도체 관련 핵심 기술 특허를 찾아주세요"

## 프로젝트 구조

```
pat-ai/
├── app/
│   ├── api/           # API 엔드포인트
│   ├── models/        # 데이터베이스 모델
│   ├── services/      # 비즈니스 로직
│   ├── static/        # 정적 파일 (CSS, JS)
│   ├── templates/     # HTML 템플릿
│   ├── config.py      # 설정
│   └── main.py        # FastAPI 애플리케이션
├── data/
│   ├── documents/     # 업로드된 PDF 파일
│   └── vectordb/      # ChromaDB 데이터
├── tests/             # 테스트 파일
├── main.py            # 실행 진입점
└── pyproject.toml     # 프로젝트 설정
```

## 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `SECRET_KEY` | JWT 토큰 비밀키 | - |
| `OPENAI_API_KEY` | OpenAI API 키 (선택) | - |
| `DATABASE_URL` | 데이터베이스 URL | sqlite:///./data/patai.db |
| `CHROMA_DB_PATH` | ChromaDB 저장 경로 | ./data/vectordb |
| `EMBEDDING_MODEL` | 임베딩 모델 | paraphrase-multilingual-MiniLM-L12-v2 |