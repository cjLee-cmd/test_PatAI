# Pat.AI / 특허분석 RAG 시스템 고도화 사양서 (v2)

본 문서는 기존 `SPECIFICATION.md`를 기반으로 실제 운영/확장/평가/보안까지 고려한 구체 사양을 추가한 개정판이다.

## 0. 변경 요약
- 배포 구조: GitHub Pages + 별도 API/Worker 인프라 분리 명시
- 모델 전략: 7B 양자화 기본, 13B/20B 확장 옵션 및 선택 기준
- 특허 도메인 전처리 & 섹션 구조 세분화
- 데이터/스키마 확장 (chunks, ingestion_jobs, eval_runs 등)
- 검색 파이프라인: Dense → (옵션 BM25) → Re-rank → Answer Synth + Citation
- 평가 지표/목표 및 자동 평가 파이프라인 정의
- 보안·프롬프트 공격·법적 고지 정책 명문화
- 운영 절차(재인덱싱, 키 회전, 롤백) 및 관측성 추가
- 성능 목표(P95, 처리량) 및 하드웨어 요구 정의

## 1. 프로젝트 개요
### 1.1 목적
학교/기관 내 축적된 특허 PDF를 로컬 또는 프라이빗 환경에서 안전하게 처리·검색·질의응답(RAG) 제공.
### 1.2 범위 (MVP vs 확장)
- MVP: 사용자 인증, 문서 업로드 → 청킹/임베딩/검색 → 인용 근거 포함 답변
- 확장: 재랭킹, 평가 지표 자동화, Admin 운영 패널, Guardrails, 관측성, 모델 A/B
### 1.3 비법률 자문 고지
"본 시스템은 제공된 특허 문서 기반 정보 요약 도구이며 법률 자문이 아닙니다."

## 2. 아키텍처
### 2.1 논리 다이어그램
```
[Static Frontend] --HTTPS--> [API Gateway(FastAPI)] --(RPC/Queue)--> [Worker]
         |                                  |                     |
         |                                  |-->[Vector Store(HNSW/FAISS/Chroma)]
         |                                  |-->[Relational DB(PostgreSQL)]
         |                                  |-->[Object/File Storage (PDF, Logs)]
         |                                  |-->[Model Runtime (LLM + Embedding)]
         |                                  |-->[Monitoring/Tracing]
```
### 2.2 컴포넌트
- Frontend: 정적(HTML/CSS/JS, GitHub Pages). API Base URL 환경변수로 주입.
- API: FastAPI (Auth, Query, Admin, Status, Eval)
- Worker: 비동기 Ingestion/Embedding/Re-index (RQ 또는 Celery). 초기 단순 BackgroundTasks → 확장 시 Redis 기반 큐.
- Vector Store: 기본 Chroma(로컬). 확장 시 FAISS(HNSW) 또는 Pinecone(클라우드) 추상화 인터페이스.
- Relational DB: PostgreSQL (개발 SQLite 허용). SQLAlchemy ORM.
- Model Runtime: LLM (7B 양자화 ggml/gguf; 옵션 13B/20B), Embedding(bge-m3 or KoSimCSE).
- Observability: 구조적 로그(JSON) + OpenTelemetry(추적) + 메트릭(Prometheus 포맷).

### 2.3 배포
- 프론트: GitHub Pages (CI: build & push).
- API/Worker: Container 이미지 → (선택) Fly.io / Render / EC2 / 온프레.
- 환경변수: `MODEL_PATH`, `EMBED_MODEL_NAME`, `DB_URL`, `VECTOR_DB_DIR`, `JWT_SECRET`, `RATE_LIMIT_*`.

## 3. 모델 및 임베딩 선정
### 3.1 LLM 후보
| 목적 | 모델 | 조건 | 비고 |
|------|------|------|------|
| 기본 | 7B 양자화(Q4_K_M) (e.g. Llama2 7B, Mistral 7B) | VRAM ≥ 8~12GB | 저지연
| 중간 | 13B 양자화 | VRAM ≥ 16GB | 정확도 향상
| 고성능 | 20B+ (GPT-OSS-20B) | VRAM ≥ 40GB / 서버 | 선택적

선택 기준: (a) 도메인 사실성(Faithfulness) (b) 한국어 Claims 처리 정확도 (c) 속도(P95) (d) 라이선스.

### 3.2 임베딩 모델 후보
| 우선순위 | 모델 | 장점 | 주의 |
|----------|------|------|------|
| 1 | bge-m3 | 멀티태스킹, 고품질 | 메모리 ↑ |
| 2 | KoSimCSE | 한국어 최적 | 다국어 한계 |
| 3 | sentence-transformers multilingual MiniLM | 경량 | 품질 중간 |
| 4 | OpenAI ada-002 (fallback) | 안정 | 비용/외부의존 |

평가: nDCG@10, Recall@5, embedding throughput(chunk/s).

## 4. 문서 처리 & RAG 파이프라인
### 4.1 단계
1. 업로드 수신 (파일 메타 검증, SHA256, MIME)
2. 작업 레코드 생성 (ingestion_jobs: status=pending)
3. 텍스트 추출 (PDFMiner / PyPDF2; 이미지 페이지 OCR(Tesseract) 옵션)
4. 섹션 태깅 (Title, Abstract, Claims, Description, IPC, CPC, Citations) 정규/패턴
5. 정규화 (whitespace, Unicode NFKC, 페이지 break 마커)
6. 청킹(섹션별 규칙)
7. 임베딩 배치 처리 (retry/backoff)
8. Vector upsert (idempotent: chunk hash 비교)
9. Job 완료/실패 기록 + 에러 로그
10. (옵션) 평가 샘플 업데이트

### 4.2 청킹 규칙
| 섹션 | 단위 | 목표 토큰 | 오버랩 | 비고 |
|------|------|----------|--------|------|
| Title/Abstract | 전체 | 단일 | 0 | 그대로
| Claims | Claim 단위 | 150~350 | 0 | 독립성 유지
| Description | 문단 슬라이딩 | 800~1200 | 10~15% | 의미 경계 우선
| IPC/CPC | 코드 라인 | <100 | 0 | 메타

토큰화: tiktoken 또는 sentencepiece (모델에 맞춤). 길이 초과 분할 시 문장 경계 우선.

### 4.3 저장 메타데이터
- chunk_id, doc_id, section_type, ordinal, token_count, start_char, end_char, hash, source_page_range

### 4.4 검색 파이프라인
1. Query Normalize (lower, 공백정리, 선택적 IPC 코드 추출)
2. 임베딩 생성
3. Dense Vector Top-K (기본 k=50)
4. (옵션) BM25 필터 pre-cut (k=200 → dense 교집합)
5. Re-rank (Cross-Encoder top_50 → top_m=8)
6. Answer Synthesis (프롬프트 + citation tags)
7. Citation Format ([S1]...[Sn]) + 출처 매핑 테이블
8. Logging (latency, used_chunks, model_version)

### 4.5 프롬프트 가드레일
System 지시: "출처 제공된 청크 외 추론 금지. 정보 없으면 '관련 근거 없음' 명시." 공격 패턴(“ignore previous”, 외부 URL 삽입) 사전 필터.

## 5. API (초안)
| 메서드 | 경로 | 목적 | 인증 |
|--------|------|------|------|
| POST | /auth/login | 로그인 | - |
| POST | /auth/refresh | 토큰 갱신 | Refresh |
| POST | /users | 가입 | Admin(Optional) or Open |
| GET | /me | 내 정보 | Access |
| POST | /documents | PDF 업로드 | Admin |
| GET | /documents/{id}/status | 처리 상태 | Auth |
| DELETE | /documents/{id} | 삭제(soft) | Admin |
| POST | /query | RAG 질의 | Access |
| GET | /history | 내 질의 | Access |
| GET | /admin/jobs | Ingestion 목록 | Admin |
| POST | /admin/reindex/{doc_id} | 재인덱스 | Admin |
| GET | /metrics | 메트릭 | Internal |
| GET | /health | 헬스 체크 | - |

## 6. 데이터베이스 스키마 (요약)
```sql
-- users
users(id PK, username UNIQUE, password_hash, name, profile_image, role, created_at, updated_at)
-- roles (선택적 분리)
-- search_history
search_history(id PK, user_id FK, query, response, sources_json, latency_ms, created_at)
-- documents
documents(id PK, filename, file_path, sha256, size_bytes, mime_type, language, status, version, license, processed_at, created_at, updated_at, deleted_at)
-- document_chunks
document_chunks(id PK, doc_id FK, section_type, ordinal, start_char, end_char, text, token_count, hash, page_start, page_end, created_at)
-- ingestion_jobs
ingestion_jobs(id PK, doc_id FK, phase, status, error_log, started_at, finished_at)
-- eval_runs
eval_runs(id PK, dataset_id, model_version, retrieval_metrics_json, answer_metrics_json, created_at)
-- answers (옵션: answer 별 citation 세분화)
answers(id PK, query, answer_text, model_version, created_at)
-- citations
citations(id PK, answer_id FK, chunk_id FK, rank, relevance_score)
```

인덱스: `document_chunks(doc_id)`, `document_chunks(section_type)`, `search_history(user_id, created_at DESC)`.

## 7. 보안 / 컴플라이언스
### 7.1 인증/인가
- JWT Access(15m) + Refresh(7d), 키 회전: kid 헤더 + 키 테이블.
- RBAC: role(admin,user) & 세분 route decorator.
### 7.2 패스워드 정책
- bcrypt cost 12, 최소 10자 (영문/숫자/특문 2종 이상), HaveIBeenPwned API (옵션)
### 7.3 파일 업로드
- 확장자 whitelist(pdf) + MIME 검사 + size ≤ 25MB
- SHA256 중복 차단
- 악성 패턴(임베디드 JS) 검사
### 7.4 Rate Limiting
- /query 사용자별 60 req/min, /auth/login 5 req/min (IP + 사용자 식별자)
### 7.5 Prompt Injection 방어
- 컨텍스트 내 외부 URL/명령어(“ignore”, “override system”) 매칭 시 마스킹 라벨
### 7.6 데이터 보호
- 삭제: soft delete 후 30일 배치 영구 제거
- 로그 PII 최소화( user_id → 내부 numeric, username 미노출 )
### 7.7 법적 고지 & 라이선스
- UI footer: 비법률 자문 고지
- 모델/임베딩 라이선스 문서화 (3rd_party_licenses.md)

## 8. 성능 및 목표 지표
| 항목 | 목표 | 메모 |
|------|------|------|
| Ingestion 처리율 | ≥30 PDF/시간 (20p 평균) | 병렬 Worker 2 | 
| Query P95 | <3.5s | 임베딩<150ms, 검색<300ms, 재랭크<700ms, 생성<2s |
| Retrieval Hit@5 | ≥85% | 평가셋 기준 |
| Faithfulness | ≥90% | 수동/자동 하이브리드 |
| 메모리 Footprint(7B) | <10GB VRAM | gguf 양자화 |

## 9. 평가 (Evaluation)
### 9.1 데이터셋 생성
- 표본: 문서 50개, 질의 30~50 (Claims/기술요약/비교/번호식 질의 구분 태그)
### 9.2 자동 메트릭
- Retrieval: Recall@k, nDCG@10, MRR
- Answer: Faithfulness(출처 문장 포함율), Context Precision(사용된 청크 적중 비율), Length Ratio
### 9.3 파이프라인
- 주 1회 eval_runs 생성 → 메트릭 추세 저장 → 회귀 검사(Threshold 하락 알림)

## 10. 운영 절차
| 절차 | 설명 |
|------|------|
| 재인덱싱 | 문서 상태 force → ingestion_jobs 새 row (reason=manual) |
| 롤백 | 모델 버전 태그별 캐시된 임베딩 유지, 이전 버전 재선택 |
| 키 회전 | 새 secret 추가(kid2) → 발급 전환 → 기존 키 만료 스케줄 |
| 인덱스 검증 | 주간 checksum + size 비교, 불일치 시 재빌드 |

## 11. 관측성 & 로깅
- 구조 로그 필드: timestamp, trace_id, span_id, user_id, route, latency_ms, status, error_code
- 메트릭: `rag_query_latency_seconds`, `embedding_queue_depth`, `ingestion_fail_total`, `retrieval_hit_ratio` 등
- 추적: ingestion 단계별 span (extract, chunk, embed, upsert)

## 12. 캐싱 전략
| 레벨 | 키 | TTL | 비고 |
|------|----|-----|------|
| Query Result | hash(query+top_k+model_version) | 10m | 사용자별 분리(X) → 개인정보 없는 답변 | 
| Embedding | hash(text+embed_model) | 영구 | 중복 청크 절감 |
| Chunk Text | chunk_id | 영구 | 메모리 LRU |

## 13. 에러 처리
- 사용자 응답: 표준 에러 구조 `{code, message, trace_id}`
- 재시도 정책: 임베딩 실패(지수 backoff 최대 3회), 벡터 upsert 실패시 dead-letter 큐
- 경고 배지: 답변 중 미인용 문장 감지 시 "⚠ 출처 미확인 문장 포함" 표시

## 14. 하드웨어 요구 (기준)
| 구성 | 최소 | 권장 |
|------|------|------|
| CPU | 4 vCPU | 8 vCPU |
| RAM | 8GB | 16GB |
| GPU | (옵션) 8GB VRAM | 16GB VRAM |
| 디스크 | 20GB | 100GB (문서+벡터) |

## 15. 개발 일정 (재조정)
| 주 | 범위 |
|----|------|
| 1 | Auth/RBAC, 업로드, 단순 청킹/임베딩, Vector 검색 (No generation) |
| 2 | LLM 답변 + Citation, Observability 기본 |
| 3 | Re-rank, Guardrails 1차, Admin 문서/잡 뷰 |
| 4 | 평가셋/자동 메트릭, 재인덱싱, 캐싱 |
| 5 | 최적화(양자화, 프롬프트), 보안 강화를 반복 |
| 6 | 부하/회귀 테스트, 문서화, 스테이징→프로덕션 |

## 16. 테스트 전략
| 레벨 | 항목 | 예 |
|------|------|----|
| 유닛 | 청킹·토큰계수 | 긴 문단 경계 유지 |
| 유닛 | 임베딩 캐시 | 동일 입력 해시 재사용 |
| 통합 | Ingestion end-to-end | PDF→chunks 수 검증 |
| 통합 | Query RAG | Top-K>0 & Citation 링크 |
| 회귀 | Retrieval 성능 | nDCG 저하 알림 |
| 부하 | 동시 질의 30 | P95<목표 |

## 17. 오픈 이슈 & 리스크
| 이슈 | 영향 | 대응 |
|------|------|------|
| 한국어 Claims 난해 구문 | 답변 왜곡 | 문장 분리 규칙 개선 + 예제 학습 프롬프트 |
| LLM 할루시네이션 | 신뢰 저하 | Faithfulness 검출 + 경고 배지 |
| 대용량 PDF (500p+) | 지연 | 스트리밍 추출 + 부분 커밋 |
| OCR 품질 저하 | 누락 | 사후 품질 스코어/재시도 |
| 모델 라이선스 | 법적 | 3rd_party_licenses.md 관리 |

## 18. 채택/비채택 결정 기록 (ADR 요약)
| 결정 | 선택 | 근거 |
|-------|------|------|
| 벡터DB | Chroma(초기) | 빠른 PoC, 로컬 용이 |
| 재랭크 | Cross-Encoder (bge reranker) | 품질 향상 > 추가 지연 허용 |
| Queue | 초기 Background → Redis RQ | 단순→확장 경로 명확 |
| Embedding | bge-m3 | 한국어/다국어 균형 |
| LLM 크기 | 7B 기본 | 자원/지연 최적화 |

## 19. 확장 로드맵 (Post-MVP)
- A/B 모델 라우팅 (Traffic Split)
- Structured Output (JSON schema) → Downstream BI
- 온디바이스 간단 요약(Edge Worker)
- IPC 코드 기반 필터 UI
- 다중 코퍼스 라우팅 (특허 vs 논문)

## 20. 용어 정의
- Chunk: 검색 단위로 분리된 텍스트 블록
- Citation: 답변이 참조한 Chunk 매핑
- Faithfulness: 답변 문장 중 출처 청크에서 근거 가능한 비율
- Re-rank: 1차 후보를 문맥모델로 재정렬

---
본 사양서는 변경 관리 대상. 수정 시 버전/날짜/작성자 기록.

(끝)
