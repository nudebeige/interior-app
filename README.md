# 🏠 인테리어 견적 매니저

소규모 인테리어 업체를 위한 **무료 상담·견적 도구**입니다.  
PC, 태블릿, 모바일 모두에서 사용 가능하며 GitHub + Streamlit Cloud로 무료 배포됩니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 📦 자재 카탈로그 | 공간별(거실/주방/욕실 등) 자재 사진·가격 표시 |
| 📋 견적서 작성 | 클릭으로 항목 추가 → HTML 견적서 출력/다운로드 |
| 📸 시공 전/후 사례 | 비포·애프터 사진 나란히 비교 표시 |
| ⚙️ 어드민 모드 | 비밀번호 로그인 → 자재 등록, 도매가 관리 (고객에게 비공개) |

---

## 🚀 배포 방법 (무료)

### 1단계: GitHub에 올리기
```bash
git init
git add .
git commit -m "첫 배포"
git remote add origin https://github.com/본인계정/interior-app.git
git push -u origin main
```

### 2단계: Streamlit Cloud 배포
1. https://share.streamlit.io 접속
2. GitHub 계정 연동
3. Repository 선택 → `app.py` 선택
4. **Deploy** 클릭

→ 예시 URL: `https://본인계정-interior-app-app-xxxxx.streamlit.app`

---

## 💻 로컬 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 🔐 관리자 비밀번호 변경

`app.py` 8번째 줄:
```python
ADMIN_PASSWORD = "admin1234"  # ← 여기를 원하는 비밀번호로 변경
```

---

## 📁 폴더 구조

```
interior_app/
├── app.py              # 메인 앱
├── requirements.txt    # 패키지 목록
├── README.md           # 이 파일
└── data/               # 자동 생성됨
    ├── items.json      # 자재 데이터
    ├── images/         # 자재 사진
    └── before_after/   # 시공 전후 사진
```

---

## ⚠️ Streamlit Cloud 사용 시 주의사항

Streamlit Cloud는 **서버가 재시작되면 업로드한 이미지가 초기화**됩니다.  
장기 운영을 위해서는 다음 중 하나를 추가 설정하세요:

- **추천**: Google Drive 연동 (무료)  
- 또는: AWS S3, Cloudinary (무료 플랜 있음)

단기 상담 데모 용도라면 매번 재업로드로도 충분합니다.
