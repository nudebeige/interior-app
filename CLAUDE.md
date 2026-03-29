# CLAUDE.md — 인테리어 견적 매니저 프로젝트 규칙

> 이 파일은 Claude(AI)와 개발자가 이 프로젝트에서 반드시 따라야 할 규칙을 정의합니다.
> 모든 코드 작성·수정 전에 이 파일을 먼저 읽고 준수 여부를 확인하세요.

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | 인테리어 견적 매니저 |
| 대상 사용자 | 소규모 인테리어 업체 (비전공자 운영) |
| 배포 환경 | Streamlit Community Cloud (무료) |
| 접근 기기 | 갤럭시탭, iPad, 갤럭시S, iPhone, PC |
| 개발 환경 | GitHub Codespaces (브라우저 기반, 로컬 설치 불필요) |
| 주요 언어 | Python 3.11+ |
| 프레임워크 | Streamlit 1.35+ |

---

## 2. 기술 스택 (비전공자 기준 선정 이유 포함)

```
streamlit>=1.35.0      # 핵심 UI 프레임워크 — Python만으로 웹앱 구현
streamlit-authenticator # bcrypt 기반 비밀번호 해시 인증
pandas>=2.0.0          # 데이터 처리 (견적 항목 계산)
pillow>=10.0.0         # 이미지 리사이즈·최적화
fpdf2>=2.7.0           # PDF 견적서 생성
python-dotenv          # 로컬 개발용 환경변수 관리
```

**선택하지 않은 것과 이유:**
- ❌ React / Next.js — 빌드 환경 설치 필요, 비전공자에게 불필요한 복잡성
- ❌ Django / Flask — 라우팅·템플릿 학습 비용이 높음
- ❌ MySQL / PostgreSQL — 서버 설치 필요, JSON 파일로 충분한 규모
- ❌ Docker — 배포 복잡도 증가, Streamlit Cloud가 대신 처리함

---

## 3. 보안 규칙 (MUST — 반드시 준수)

### 3-1. 인증 구조

```
[공개 영역]          [보호 영역]
고객 카탈로그  ──→  어드민 로그인 벽  ──→  자재 등록/관리
견적서 작성          (bcrypt 해시)          전/후 사진 등록
시공 사례 열람                              도매가 열람
```

### 3-2. 비밀번호 저장 규칙

```python
# ✅ 반드시 이렇게 — bcrypt 해시 저장 (평문 절대 금지)
# secrets.toml 또는 Streamlit Cloud Secrets에 저장
[admin]
hashed_password = "$2b$12$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# ❌ 절대 금지 — 소스코드에 평문 비밀번호 직접 기재
ADMIN_PASSWORD = "admin1234"  # 이 방식은 사용하지 않음
```

### 3-3. Secrets 관리 규칙

- **로컬 개발:** `.streamlit/secrets.toml` 파일 사용
- **배포 후:** Streamlit Cloud 대시보드 → App Settings → Secrets에 입력
- **GitHub에 절대 올리면 안 되는 파일:** `secrets.toml`, `*.env`, 개인 이미지
- `.gitignore`에 반드시 포함:
  ```
  .streamlit/secrets.toml
  data/images/
  data/before_after/
  __pycache__/
  *.pyc
  ```

### 3-4. 세션 보안

- 어드민 로그인 상태는 `st.session_state`에만 저장 (브라우저 탭 닫으면 자동 해제)
- 고객에게 앱을 보여줄 때는 반드시 어드민 로그아웃 후 진행
- 도매가·원가 정보는 `is_admin=True` 조건 블록 안에서만 렌더링

### 3-5. 데이터 노출 방지

```python
# ✅ 올바른 패턴 — 모드에 따라 조건부 렌더링
if st.session_state.get("is_admin"):
    st.write(f"도매가: {item['wholesale_price']:,}원")
    st.write(f"수익: {margin:,}원")
# 고객 화면에는 판매가만 표시됨

# ❌ 금지 패턴 — 모든 데이터를 렌더링 후 CSS로 숨기기
# (브라우저 개발자도구로 볼 수 있어 보안 무효)
```

---

## 4. 코딩 규칙 (효율성 · 유지보수성)

### 4-1. 파일 구조 (변경 금지)

```
interior_app/
├── app.py                    # 메인 진입점 — 페이지 라우팅만 담당
├── requirements.txt          # 패키지 목록
├── .gitignore                # 보안 파일 제외 목록
├── CLAUDE.md                 # 이 파일
├── TODO.md                   # 작업 계획 및 진행 추적
├── .streamlit/
│   ├── secrets.toml          # 로컬 전용 (gitignore됨)
│   └── config.toml           # 테마·서버 설정
├── pages/                    # 각 페이지 독립 모듈
│   ├── 1_catalog.py          # 카탈로그
│   ├── 2_quotation.py        # 견적서 작성
│   ├── 3_portfolio.py        # 시공 전/후
│   ├── 4_admin_items.py      # 자재 관리 (어드민)
│   └── 5_admin_portfolio.py  # 사진 등록 (어드민)
├── utils/
│   ├── auth.py               # 인증 로직
│   ├── data.py               # 데이터 읽기/쓰기
│   ├── pdf_gen.py            # 견적서 PDF 생성
│   └── image.py              # 이미지 처리
└── data/                     # 런타임 데이터 (gitignore됨)
    ├── items.json
    ├── images/
    └── before_after/
```

### 4-2. 변경 최소화 원칙 (핵심 규칙)

> **"하나의 기능 = 하나의 함수 = 하나의 파일"**
> 기능을 추가할 때 기존 파일을 수정하기보다 새 파일을 추가하는 방식 우선

- `app.py`는 라우팅과 공통 레이아웃만 담당, 비즈니스 로직 포함 금지
- 데이터 구조 변경 시 반드시 `utils/data.py`의 마이그레이션 함수 사용
- UI 스타일 변경은 `.streamlit/config.toml` 또는 CSS 파일에서만

### 4-3. 데이터 구조 표준

```python
# items.json 표준 스키마
{
  "items": [
    {
      "id": "item_20250329120000000000",  # datetime 기반 고유 ID
      "name": "이탈리아 세라믹 타일",
      "category": "욕실",                # CATEGORIES 상수에서만 선택
      "customer_price": 600000,          # 판매가 (고객 노출)
      "wholesale_price": 390000,         # 원가 (어드민 전용)
      "unit": "식",
      "note": "친환경 인증",
      "image": "data/images/20250329.jpg",  # 상대 경로
      "created_at": "2025-03-29T12:00:00"
    }
  ],
  "before_after": [
    {
      "id": "ba_20250329120000000000",
      "title": "○○아파트 32평 리모델링",
      "location": "부산 해운대구",
      "date": "2025년 3월",
      "description": "도배·장판 전체 교체",
      "before": "data/before_after/before_20250329.jpg",
      "after": "data/before_after/after_20250329.jpg",
      "created_at": "2025-03-29T12:00:00"
    }
  ]
}
```

### 4-4. 함수 작성 규칙

```python
# ✅ 올바른 패턴 — 단일 책임, 명확한 타입 힌트
def load_items(category: str = "전체") -> list[dict]:
    """카테고리별 자재 목록 반환. 전체이면 필터 없이 전체 반환."""
    data = load_data()
    if category == "전체":
        return data.get("items", [])
    return [i for i in data.get("items", []) if i["category"] == category]

# ❌ 금지 패턴 — 여러 책임 혼합
def load_and_display_and_filter_items():  # 이런 함수명은 사용 금지
    pass
```

### 4-5. 주석 작성 규칙

```python
# [이유] 왜 이렇게 했는지 기록 — 나중에 수정할 때 참고용
# [주의] 이 값을 바꾸면 기존 데이터 마이그레이션 필요
# [보안] 어드민 전용 — 조건문 없이 이 블록 밖으로 이동 금지
# [TODO] 향후 Google Drive 연동으로 교체 예정
```

---

## 5. 어드민 vs 고객 모드 동작 정의

### 5-1. 고객 모드 (기본값, 로그인 불필요)

| 기능 | 허용 여부 |
|------|-----------|
| 자재 카탈로그 열람 | ✅ |
| 판매가 확인 | ✅ |
| 견적 항목 추가/수정 | ✅ |
| 견적서 HTML 다운로드 | ✅ |
| 시공 전/후 사례 열람 | ✅ |
| 도매가·원가 열람 | ❌ 세션 레벨 차단 |
| 자재 등록·수정·삭제 | ❌ 페이지 접근 차단 |
| 시공 사진 등록 | ❌ 페이지 접근 차단 |

### 5-2. 어드민 모드 (bcrypt 비밀번호 인증 후)

| 기능 | 추가 허용 항목 |
|------|----------------|
| 위 고객 모드 전체 | ✅ |
| 도매가·원가·수익 열람 | ✅ |
| 자재 CRUD | ✅ |
| 시공 사진 CRUD | ✅ |
| 어드민 경고 배너 표시 | ✅ (고객 앞에서 로그아웃 유도) |

### 5-3. 모드 전환 로직 (단순 유지)

```python
# utils/auth.py — 인증 유틸리티
import bcrypt
import streamlit as st

def check_password(plain: str, hashed: str) -> bool:
    """입력 비밀번호와 저장된 해시 비교"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def is_admin() -> bool:
    """현재 세션의 어드민 여부 반환"""
    return st.session_state.get("is_admin", False)

def require_admin():
    """어드민 아닌 경우 페이지 접근 차단"""
    if not is_admin():
        st.warning("🔐 이 페이지는 관리자 전용입니다.")
        st.stop()
```

---

## 6. 현재 인테리어 견적 프로그램과의 보안 수준 비교

| 항목 | 한샘 등 대형 앱 | 이디스(Iidis) | 본 프로젝트 목표 |
|------|----------------|---------------|-----------------|
| 비밀번호 암호화 | bcrypt/argon2 | 자체 암호화 | bcrypt ✅ |
| HTTPS 통신 | ✅ | ✅ | Streamlit Cloud 기본 제공 ✅ |
| 모드 분리 | 역할 기반 | 사용자 권한 | 세션 기반 2단계 ✅ |
| 데이터 암호화 저장 | DB 암호화 | DB 암호화 | JSON (로컬, 소규모 적합) ⚠️ |
| 원격 해킹 방어 | 전문 인프라 | 전문 인프라 | GCP 기반 Streamlit Cloud ✅ |
| 고객 데이터 분리 | 완전 분리 | 완전 분리 | 세션 격리 (단일 사용자 앱) ✅ |

> **결론:** 소규모 1인 업체 수준에서 필요한 보안 요건(비밀번호 해시, HTTPS, 모드 분리)은 모두 충족.
> 대형 업체 수준의 DB 암호화나 감사 로그는 현재 규모에서 불필요.

---

## 7. GitHub Codespaces 개발 환경 규칙

### 7-1. 처음 시작할 때

```bash
# Codespaces 터미널에서 실행
pip install -r requirements.txt
streamlit run app.py
```

### 7-2. 배포할 때 (코드 변경 후)

```bash
git add .
git commit -m "feat: 자재 카드 UI 개선"   # 변경 내용을 한 줄로 요약
git push
# → Streamlit Cloud가 자동으로 재배포
```

### 7-3. 커밋 메시지 규칙

```
feat:  새 기능 추가
fix:   버그 수정
style: UI/CSS만 변경
refactor: 동작 변화 없는 코드 구조 개선
docs:  문서(MD 파일) 수정
```

---

## 8. 절대 하지 말아야 할 것 (Anti-patterns)

```python
# ❌ 1. 소스코드에 비밀번호 평문 기재
ADMIN_PASSWORD = "1234"

# ❌ 2. 고객 데이터를 GitHub에 커밋
# data/ 폴더를 git add 하지 말 것

# ❌ 3. 하나의 함수에 100줄 이상 작성
# 50줄 넘으면 분리를 고려

# ❌ 4. 기존에 잘 동작하는 함수를 무작정 수정
# 새 함수를 만들고 기존 함수를 대체하는 방식 사용

# ❌ 5. UI와 데이터 로직을 같은 블록에 혼합
# pages/*.py 에는 UI만, utils/*.py 에는 로직만
```

---

## 9. 교훈 기록 (Lessons Learned)

> 작업 중 발생한 문제와 해결책을 반드시 여기에 추가하세요.

| 날짜 | 문제 | 원인 | 해결책 | 재발 방지 규칙 |
|------|------|------|--------|----------------|
| (예시) 2025-03-29 | 사진 업로드 후 서버 재시작 시 사라짐 | Streamlit Cloud 임시 파일시스템 | Google Drive 링크 방식으로 전환 | `data/images/`는 gitignore, 이미지는 외부 스토리지 사용 |

---

*이 파일은 프로젝트가 진행되면서 지속적으로 업데이트됩니다.*
*마지막 업데이트: 2025-03-29*
