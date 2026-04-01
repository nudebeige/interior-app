import streamlit as st
import base64
import copy
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="인테리어 견적 매니저",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 상수 ─────────────────────────────────────────────────────
ADMIN_PASSWORD = "admin1234"
CATEGORIES     = ["거실", "주방", "욕실", "침실", "현관", "베란다", "기타"]
SCOPES         = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Google Sheets 연결 ────────────────────────────────────────
@st.cache_resource(ttl=300)
def get_gsheet_client():
    """서비스 계정으로 Google Sheets 클라이언트 반환 (5분 캐시)"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_worksheet(sheet_name: str):
    client = get_gsheet_client()
    sid    = st.secrets["gsheets"]["spreadsheet_id"]
    return client.open_by_key(sid).worksheet(sheet_name)

# ── 데이터 읽기/쓰기 ─────────────────────────────────────────
@st.cache_data(ttl=60)   # 60초 캐시 — 다른 기기에서 변경해도 1분 내 반영
def load_items() -> list[dict]:
    """items 시트 전체 읽기"""
    try:
        ws   = get_worksheet("items")
        rows = ws.get_all_records()
        result = []
        for r in rows:
            if not r.get("name"):
                continue
            r["customer_price"]  = int(r.get("customer_price")  or 0)
            r["wholesale_price"] = int(r.get("wholesale_price") or 0)
            if not r.get("id"):
                r["id"] = f"item_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            result.append(r)
        return result
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ 오류: 스프레드시트를 찾을 수 없습니다. spreadsheet_id 또는 공유 설정을 확인하세요.")
        return []
    except gspread.exceptions.WorksheetNotFound:
        st.error("❌ 오류: 'items' 시트를 찾을 수 없습니다. Google Sheets 탭 이름이 정확히 'items' 인지 확인하세요.")
        return []
    except gspread.exceptions.APIError as e:
        st.error(f"❌ Google API 오류: {e.response.status_code} — {e.response.reason}")
        st.info("해결 방법: Google Cloud Console에서 Sheets API / Drive API 활성화 여부를 확인하세요.")
        return []
    except Exception as e:
        st.error(f"❌ 자재 목록 불러오기 실패: {type(e).__name__}: {e}")
        return []

@st.cache_data(ttl=60)
def load_before_after() -> list[dict]:
    """before_after 시트 전체 읽기"""
    try:
        ws   = get_worksheet("before_after")
        rows = ws.get_all_records()
        return [r for r in rows if r.get("title")]
    except Exception as e:
        st.error(f"시공사례 불러오기 실패: {e}")
        return []

def save_item(item: dict):
    """items 시트에 새 행 추가"""
    ws = get_worksheet("items")
    ws.append_row([
        item.get("id", ""),
        item.get("name", ""),
        item.get("category", ""),
        item.get("customer_price", 0),
        item.get("wholesale_price", 0),
        item.get("unit", "식"),
        item.get("note", ""),
        item.get("image", ""),
        item.get("created_at", ""),
    ], value_input_option="USER_ENTERED")
    load_items.clear()          # 캐시 즉시 무효화

def delete_item(item_id: str):
    """items 시트에서 해당 id 행 삭제"""
    ws    = get_worksheet("items")
    rows  = ws.get_all_values()
    for i, row in enumerate(rows):
        if row and row[0] == item_id:
            ws.delete_rows(i + 1)
            break
    load_items.clear()

def save_before_after(ba: dict):
    """before_after 시트에 새 행 추가"""
    ws = get_worksheet("before_after")
    ws.append_row([
        ba.get("id", ""),
        ba.get("title", ""),
        ba.get("location", ""),
        ba.get("date", ""),
        ba.get("description", ""),
        ba.get("before", ""),
        ba.get("after", ""),
        ba.get("created_at", ""),
    ], value_input_option="USER_ENTERED")
    load_before_after.clear()

def delete_before_after(ba_id: str):
    ws   = get_worksheet("before_after")
    rows = ws.get_all_values()
    for i, row in enumerate(rows):
        if row and row[0] == ba_id:
            ws.delete_rows(i + 1)
            break
    load_before_after.clear()

def update_item_image(item_id: str, image_b64: str):
    """items 시트의 image 열(H)을 base64로 업데이트"""
    ws   = get_worksheet("items")
    rows = ws.get_all_values()
    for i, row in enumerate(rows):
        if row and row[0] == item_id:
            ws.update_cell(i + 1, 8, image_b64)   # H열 = 8번째
            break
    load_items.clear()

def update_ba_images(ba_id: str, before_b64: str, after_b64: str):
    """before_after 시트의 before(F)/after(G) 열 업데이트"""
    ws   = get_worksheet("before_after")
    rows = ws.get_all_values()
    for i, row in enumerate(rows):
        if row and row[0] == ba_id:
            if before_b64:
                ws.update_cell(i + 1, 6, before_b64)
            if after_b64:
                ws.update_cell(i + 1, 7, after_b64)
            break
    load_before_after.clear()

# ── 이미지 헬퍼 ──────────────────────────────────────────────
def file_to_b64(uploaded_file) -> str | None:
    """업로드된 파일을 base64 data URI로 변환"""
    if uploaded_file is None:
        return None
    raw  = uploaded_file.read()
    b64  = base64.b64encode(raw).decode()
    ext  = uploaded_file.name.rsplit(".", 1)[-1].lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    return f"data:{mime};base64,{b64}"

def is_b64_image(s: str | None) -> bool:
    return bool(s and s.startswith("data:image"))

# ── 견적 헬퍼 ────────────────────────────────────────────────
def calc_totals(items: list[dict]) -> tuple[int, int, int]:
    total = sum(q["price"] * q.get("qty", 1) for q in items)
    vat   = int(total * 0.1)
    return total, vat, total + vat

def items_by_category(items: list[dict]) -> dict[str, list]:
    result: dict = {}
    for q in items:
        result.setdefault(q.get("category", "기타"), []).append(q)
    return result

def already_in_quote(item_id: str) -> bool:
    return any(q.get("id") == item_id for q in st.session_state.quote_items)

def save_version_snapshot():
    snap = {
        "ts":    datetime.now().strftime("%H:%M:%S"),
        "label": f"Ver {len(st.session_state.quote_history)+1}",
        "items": copy.deepcopy(st.session_state.quote_items),
    }
    st.session_state.quote_history.append(snap)
    if len(st.session_state.quote_history) > 10:
        st.session_state.quote_history.pop(0)

# ── 세션 초기화 ───────────────────────────────────────────────
def _init():
    defaults = {
        "is_admin":      False,
        "sel_cat":       "전체",
        "page":          "카탈로그",
        "quote_items":   [],
        "quote_history": [],
        "customer_name": "",
        "customer_addr": "",
        "customer_phone":"",
        "discount_pct":  0,
        "show_zero":     True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

# ── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Playfair+Display:wght@600&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans KR',sans-serif;}
[data-testid="stSidebar"]{background:linear-gradient(160deg,#1a1a2e 0%,#16213e 60%,#0f3460 100%);border-right:1px solid rgba(255,255,255,0.08);}
[data-testid="stSidebar"] *{color:#e8e8f0 !important;}
[data-testid="stSidebar"] .stButton>button{width:100%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#e8e8f0 !important;border-radius:8px;margin-bottom:4px;text-align:left;padding:10px 16px;transition:all 0.2s;}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(255,200,100,0.2);border-color:#ffc864;}
.item-card{background:white;border-radius:14px;box-shadow:0 2px 12px rgba(0,0,0,0.08);overflow:hidden;transition:transform 0.2s,box-shadow 0.2s;height:100%;}
.item-card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,0.14);}
.card-img{width:100%;height:180px;object-fit:cover;}
.card-body{padding:14px;}
.card-name{font-size:1rem;font-weight:600;color:#1a1a2e;margin-bottom:4px;}
.card-cat{font-size:0.75rem;color:#888;margin-bottom:8px;}
.card-price{font-size:1.05rem;font-weight:700;color:#0f3460;}
.card-wholesale{font-size:0.8rem;color:#e05;margin-top:6px;background:#fff0f3;padding:6px 8px;border-radius:6px;}
.card-note{font-size:0.82rem;color:#555;margin-top:6px;}
.subtotal-bar{background:#f0f3fa;border:1px solid #d0d8ec;color:#1a1a2e;padding:8px 14px;border-radius:8px;font-size:0.88rem;margin-top:8px;display:flex;justify-content:space-between;}
.section-header{font-size:1.1rem;font-weight:700;color:#1a1a2e;padding-bottom:8px;border-bottom:2px solid #0f3460;margin-bottom:16px;}
.app-title{font-family:'Playfair Display',serif;font-size:1.8rem;font-weight:600;color:#ffc864;letter-spacing:0.02em;margin-bottom:2px;}
.app-subtitle{font-size:0.8rem;color:#aab;margin-bottom:16px;}
.badge-admin{background:#ffe0e0;color:#c00;display:inline-block;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600;}
.badge-customer{background:#e0f0ff;color:#05c;display:inline-block;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 사이드바
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="app-title">🏠 인테리어<br>견적 매니저</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">소규모 인테리어 전문 상담 도구</div>', unsafe_allow_html=True)

    badge_cls = "badge-admin" if st.session_state.is_admin else "badge-customer"
    mode_txt  = "🔴 어드민 모드" if st.session_state.is_admin else "🔵 고객 모드"
    st.markdown(f'<span class="{badge_cls}">{mode_txt}</span>', unsafe_allow_html=True)
    st.markdown("---")

    pages = ["카탈로그", "견적서 작성", "시공 전/후 사례"]
    if st.session_state.is_admin:
        pages += ["자재 등록/관리", "전/후 사진 등록"]

    icons = {"카탈로그":"📦","견적서 작성":"📋","시공 전/후 사례":"📸",
             "자재 등록/관리":"⚙️","전/후 사진 등록":"🖼️"}
    active_cnt = sum(1 for q in st.session_state.quote_items if q.get("qty",1) > 0)

    for p in pages:
        label = f"{icons.get(p,'')} {p}"
        if p == "견적서 작성" and active_cnt > 0:
            label += f"  ({active_cnt}건)"
        if st.button(label, key=f"nav_{p}"):
            st.session_state.page = p
            st.rerun()

    st.markdown("---")

    if st.session_state.page == "카탈로그":
        st.markdown("**🏷️ 공간 필터**")
        for c in ["전체"] + CATEGORIES:
            if st.button(c, key=f"cat_{c}"):
                st.session_state.sel_cat = c
                st.rerun()

    st.markdown("---")

    if not st.session_state.is_admin:
        with st.expander("🔐 관리자 로그인"):
            pw = st.text_input("비밀번호", type="password", key="pw_input")
            if st.button("로그인"):
                if pw == ADMIN_PASSWORD:
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("비밀번호가 틀렸습니다")
    else:
        st.warning("⚠️ 어드민 모드입니다.\n고객 앞에서는 로그아웃하세요.", icon="🔴")
        if st.button("🔓 로그아웃"):
            st.session_state.is_admin = False
            st.session_state.page = "카탈로그"
            st.rerun()

# ══════════════════════════════════════════════════════════════
# 카탈로그 페이지
# ══════════════════════════════════════════════════════════════
if st.session_state.page == "카탈로그":
    cat   = st.session_state.sel_cat
    items = load_items()
    if cat != "전체":
        items = [i for i in items if i.get("category") == cat]

    st.markdown(f'<div class="section-header">📦 자재 카탈로그 — {cat} ({len(items)}건)</div>',
                unsafe_allow_html=True)

    if not items:
        st.info("등록된 자재가 없습니다. 어드민 모드 → 자재 등록/관리에서 추가하세요.")
    else:
        cols = st.columns(3, gap="medium")
        for idx, item in enumerate(items):
            with cols[idx % 3]:
                img_src   = item.get("image","")
                img_html  = (f'<img class="card-img" src="{img_src}">' if is_b64_image(img_src)
                             else '<div style="background:#e8eaf0;height:180px;display:flex;'
                                  'align-items:center;justify-content:center;font-size:2rem;">📷</div>')
                ws_html   = ""
                if st.session_state.is_admin:
                    margin  = item.get("customer_price",0) - item.get("wholesale_price",0)
                    ws_html = (f'<div class="card-wholesale">💰 도매가: '
                               f'{item.get("wholesale_price",0):,}원 | 수익: <b>{margin:,}원</b></div>')
                note_html = (f'<div class="card-note">📝 {item["note"]}</div>'
                             if item.get("note") else "")
                in_q      = already_in_quote(item.get("id",""))
                in_q_html = ('<span style="font-size:.78rem;color:#1b5e20;background:#e8f5e9;'
                             'border-radius:4px;padding:1px 7px;">✅ 견적 포함</span>'
                             if in_q else "")

                st.markdown(f"""
                <div class="item-card">
                  {img_html}
                  <div class="card-body">
                    <div class="card-cat">🏷️ {item.get("category","")}</div>
                    <div class="card-name">{item.get("name","")} {in_q_html}</div>
                    <div class="card-price">💵 {item.get("customer_price",0):,}원 / {item.get("unit","식")}</div>
                    {ws_html}{note_html}
                  </div>
                </div>""", unsafe_allow_html=True)

                btn_lbl = "✏️ 수량 수정 (견적 포함)" if in_q else "➕ 견적에 추가"
                if st.button(btn_lbl, key=f"add_{item.get('id')}"):
                    if in_q:
                        st.session_state.page = "견적서 작성"
                        st.rerun()
                    else:
                        st.session_state.quote_items.append({
                            "id":       item.get("id",""),
                            "name":     item.get("name",""),
                            "price":    item.get("customer_price",0),
                            "category": item.get("category",""),
                            "unit":     item.get("unit","식"),
                            "qty":      1,
                            "memo":     "",
                        })
                        st.toast(f"'{item.get('name')}' 견적에 추가됨!", icon="✅")

# ══════════════════════════════════════════════════════════════
# 견적서 작성 페이지
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "견적서 작성":
    st.markdown('<div class="section-header">📋 견적서 작성</div>', unsafe_allow_html=True)
    col_left, col_right = st.columns([1, 2])

    with col_left:
        with st.expander("👤 고객 정보", expanded=True):
            st.session_state.customer_name  = st.text_input("고객 성함",  value=st.session_state.customer_name,  placeholder="홍길동")
            st.session_state.customer_addr  = st.text_input("시공 주소",  value=st.session_state.customer_addr,  placeholder="○○시 ○○구 ○○아파트 00평")
            st.session_state.customer_phone = st.text_input("연락처",     value=st.session_state.customer_phone, placeholder="010-0000-0000")
            quote_date = st.date_input("견적 날짜", datetime.today())

        # 카탈로그 자재 선택
        with st.expander("📦 카탈로그에서 자재 추가", expanded=True):
            all_items = load_items()
            if not all_items:
                st.info("등록된 자재가 없습니다. 자재 등록/관리에서 먼저 등록하세요.")
            else:
                q_cat = st.selectbox("공간 선택", ["전체"] + CATEGORIES, key="q_cat_filter")
                filtered = all_items if q_cat == "전체" else [
                    i for i in all_items if i.get("category") == q_cat]
                for fi in filtered:
                    in_q    = already_in_quote(fi.get("id",""))
                    img_src = fi.get("image","")
                    r1, r2  = st.columns([1, 3])
                    with r1:
                        if is_b64_image(img_src):
                            st.markdown(f'<img src="{img_src}" style="width:100%;height:58px;object-fit:cover;border-radius:6px;">',unsafe_allow_html=True)
                        else:
                            st.markdown('<div style="width:100%;height:58px;background:#e8eaf0;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;">📷</div>',unsafe_allow_html=True)
                    with r2:
                        st.markdown(f"**{fi['name']}**  \n`{fi.get('category','')}` · **{fi.get('customer_price',0):,}원**/{fi.get('unit','식')}")
                        if in_q:
                            st.markdown('<span style="font-size:.75rem;color:#1b5e20;background:#e8f5e9;border-radius:4px;padding:2px 8px;">✅ 견적 포함 — 오른쪽 표에서 수량 수정</span>',unsafe_allow_html=True)
                        else:
                            if st.button("➕ 추가", key=f"qadd_{fi['id']}", use_container_width=True, type="primary"):
                                st.session_state.quote_items.append({
                                    "id": fi.get("id",""), "name": fi.get("name",""),
                                    "price": fi.get("customer_price",0),
                                    "category": fi.get("category",""),
                                    "unit": fi.get("unit","식"),
                                    "qty": 1, "memo": "",
                                })
                                st.rerun()
                    st.markdown('<hr style="margin:4px 0;border:none;border-top:.5px solid #eee;">',unsafe_allow_html=True)

        # 직접 추가
        with st.expander("✏️ 항목 직접 추가"):
            with st.form("manual_add", clear_on_submit=True):
                m_cat   = st.selectbox("공간", CATEGORIES)
                m_name  = st.text_input("항목명", placeholder="도배 - 실크벽지")
                m_price = st.number_input("단가 (원)", min_value=0, step=1000)
                m_qty   = st.number_input("수량", min_value=1, step=1)
                m_unit  = st.text_input("단위", value="식")
                m_memo  = st.text_input("메모", placeholder="특이사항")
                if st.form_submit_button("➕ 추가"):
                    if m_name:
                        st.session_state.quote_items.append({
                            "id": f"manual_{datetime.now().strftime('%f')}",
                            "name": m_name, "price": m_price,
                            "qty": int(m_qty), "unit": m_unit,
                            "category": m_cat, "memo": m_memo,
                        })
                        st.rerun()

        # 할인
        with st.expander("💸 할인 설정"):
            st.session_state.discount_pct = st.slider("할인율 (%)", 0, 30,
                value=st.session_state.discount_pct, step=1)

        # 버전 히스토리
        if st.session_state.quote_history:
            with st.expander(f"📜 이전 버전 ({len(st.session_state.quote_history)}개)"):
                for snap in reversed(st.session_state.quote_history):
                    ai = [q for q in snap["items"] if q.get("qty",0) > 0]
                    _, _, sg = calc_totals(ai)
                    if st.button(f"🕐 {snap['label']} ({snap['ts']}) — {sg:,}원", key=f"hist_{snap['ts']}"):
                        st.session_state.quote_items = copy.deepcopy(snap["items"])
                        st.rerun()

    with col_right:
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("📸 버전 저장"):
                save_version_snapshot()
                st.toast("버전 저장 완료!", icon="✅")
        with b2:
            if st.button("🔍 0건 숨기기/보이기"):
                st.session_state.show_zero = not st.session_state.get("show_zero", True)
                st.rerun()
        with b3:
            if st.button("🗑️ 전체 초기화"):
                if st.session_state.quote_items:
                    save_version_snapshot()
                st.session_state.quote_items = []
                st.rerun()

        show_zero = st.session_state.get("show_zero", True)

        if not st.session_state.quote_items:
            st.info("왼쪽에서 자재를 선택하거나 직접 입력하세요.")
        else:
            by_cat   = items_by_category(st.session_state.quote_items)
            to_remove = []
            updated   = False

            for cat_name, cat_items in by_cat.items():
                active_in_cat = [q for q in cat_items if q.get("qty",0) > 0]
                cat_total     = sum(q["price"] * q["qty"] for q in active_in_cat)
                st.markdown(f'<div class="subtotal-bar"><span>🏷️ {cat_name}</span>'
                            f'<span>소계: <b>{cat_total:,}원</b> ({len(active_in_cat)}건)</span></div>',
                            unsafe_allow_html=True)

                for qitem in cat_items:
                    gi     = st.session_state.quote_items.index(qitem)
                    qty    = qitem.get("qty", 1)
                    is_zero = (qty == 0)
                    if is_zero and not show_zero:
                        continue

                    rc = st.columns([3.5, 1.2, 1.5, 1.8, 0.7])
                    with rc[0]:
                        if is_zero:
                            st.markdown(f'<span style="text-decoration:line-through;color:#bbb;">{qitem["name"]}</span>'
                                        f' <span style="font-size:.78rem;background:#fce4ec;color:#b71c1c;border-radius:4px;padding:1px 7px;">미선택</span>',
                                        unsafe_allow_html=True)
                        else:
                            memo_h = (f'<br><span style="font-size:.75rem;color:#888;">📝 {qitem["memo"]}</span>'
                                      if qitem.get("memo") else "")
                            st.markdown(f"{qitem['name']}{memo_h}", unsafe_allow_html=True)
                    with rc[1]:
                        new_qty = st.number_input("수량", min_value=0, value=qty,
                                                  key=f"qty_{gi}", label_visibility="collapsed")
                        if new_qty != qty:
                            st.session_state.quote_items[gi]["qty"] = new_qty
                            updated = True
                    with rc[2]:
                        st.caption(f"{qitem['price']:,}원/{qitem.get('unit','식')}")
                    with rc[3]:
                        if is_zero:
                            st.markdown('<span style="color:#bbb;">—</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<b style="color:#0f3460;">{qitem["price"]*new_qty:,}원</b>', unsafe_allow_html=True)
                    with rc[4]:
                        if st.button("✕", key=f"del_{gi}"):
                            to_remove.append(gi)

            for idx in sorted(to_remove, reverse=True):
                st.session_state.quote_items.pop(idx)
            if to_remove or updated:
                st.rerun()

            st.markdown("---")
            active_items = [q for q in st.session_state.quote_items if q.get("qty",0) > 0]
            total, vat, grand = calc_totals(active_items)
            disc_pct = st.session_state.discount_pct
            disc_amt = int(total * disc_pct / 100)
            final    = grand - disc_amt

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("소계",    f"{total:,}원")
            c2.metric("VAT(10%)",f"{vat:,}원")
            if disc_pct > 0:
                c3.metric(f"할인({disc_pct}%)", f"-{disc_amt:,}원")
            c4.metric("최종 합계", f"{final:,}원")

            zero_items = [q for q in st.session_state.quote_items if q.get("qty",0) == 0]
            if zero_items:
                st.info(f"📊 미선택 항목 {len(zero_items)}건 — 수량을 1로 되돌리면 재포함됩니다.")

            notes = st.text_area("📝 특이사항/메모",
                placeholder="예) 기존 바닥재 철거 포함 · 자재 반입 3층 계단 이동",
                height=80, key="notes_area")

            st.markdown("---")
            oc1, oc2 = st.columns([2, 1])
            with oc1:
                gen_btn     = st.button("📄 견적서 생성 및 다운로드", type="primary", use_container_width=True)
            with oc2:
                preview_btn = st.button("👁 미리보기", use_container_width=True)

            if gen_btn or preview_btn:
                cname  = st.session_state.customer_name  or "고객"
                caddr  = st.session_state.customer_addr  or "미입력"
                cphone = st.session_state.customer_phone or "미입력"

                rows_html = ""
                for cn, ci in items_by_category(active_items).items():
                    cat_sub = sum(q["price"]*q["qty"] for q in ci)
                    rows_html += f'<tr><td colspan="5" style="background:#e8ecf5;font-weight:600;font-size:.85rem;padding:6px 12px;">🏷️ {cn} — 소계: {cat_sub:,}원</td></tr>'
                    for q in ci:
                        memo_td = (f'<br><span style="font-size:.78rem;color:#888;">{q["memo"]}</span>'
                                   if q.get("memo") else "")
                        rows_html += (f'<tr><td>{q.get("category","")}</td><td>{q["name"]}{memo_td}</td>'
                                      f'<td style="text-align:center">{q["qty"]}{q.get("unit","식")}</td>'
                                      f'<td style="text-align:right">{q["price"]:,}원</td>'
                                      f'<td style="text-align:right"><b>{q["price"]*q["qty"]:,}원</b></td></tr>')

                disc_row = (f'<tr class="total-row"><td colspan="4" style="text-align:right">할인({disc_pct}%)</td>'
                            f'<td style="text-align:right;color:#e05;">-{disc_amt:,}원</td></tr>'
                            if disc_pct > 0 else "")

                html_content = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<style>
body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;margin:40px;color:#222;font-size:14px;}}
h1{{font-size:1.5rem;color:#1a1a2e;border-bottom:3px solid #1a1a2e;padding-bottom:8px;margin-bottom:16px;}}
.company{{text-align:right;font-size:.85rem;color:#555;margin-bottom:20px;}}
.info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:16px 0;}}
.info-item{{background:#f5f5fa;padding:8px 12px;border-radius:6px;}}
.info-label{{font-size:.72rem;color:#666;margin-bottom:2px;}}
.info-value{{font-weight:600;}}
table{{width:100%;border-collapse:collapse;margin-top:16px;}}
th{{background:#1a1a2e;color:white;padding:10px;text-align:left;font-size:.88rem;}}
td{{padding:8px 10px;border-bottom:1px solid #eee;font-size:.88rem;}}
tr:nth-child(even) td{{background:#f9f9f9;}}
.total-row td{{font-weight:700;font-size:.95rem;}}
.grand-total td{{background:#1a1a2e;color:white;font-size:1.05rem;}}
.footer{{margin-top:30px;padding:16px;background:#f5f5fa;border-radius:8px;font-size:.82rem;color:#444;line-height:1.8;}}
.sign-area{{display:flex;justify-content:flex-end;gap:60px;margin-top:40px;font-size:.88rem;}}
.sign-box{{text-align:center;}}
.sign-line{{border-top:1px solid #999;width:100px;margin-top:40px;}}
@media print{{button{{display:none!important;}}}}
</style></head><body>
<div class="company"><b>인테리어 견적서</b><br>발행일: {quote_date.strftime('%Y년 %m월 %d일')}</div>
<h1>🏠 인테리어 공사 견적서</h1>
<div class="info-grid">
  <div class="info-item"><div class="info-label">고객 성함</div><div class="info-value">{cname} 고객님</div></div>
  <div class="info-item"><div class="info-label">견적 날짜</div><div class="info-value">{quote_date.strftime('%Y년 %m월 %d일')}</div></div>
  <div class="info-item"><div class="info-label">시공 주소</div><div class="info-value">{caddr}</div></div>
  <div class="info-item"><div class="info-label">연락처</div><div class="info-value">{cphone}</div></div>
</div>
<table>
  <thead><tr><th style="width:10%">공간</th><th style="width:35%">항목</th><th style="width:12%;text-align:center">수량</th><th style="width:18%;text-align:right">단가</th><th style="width:25%;text-align:right">금액</th></tr></thead>
  <tbody>
    {rows_html}
    <tr class="total-row"><td colspan="4" style="text-align:right">소계</td><td style="text-align:right">{total:,}원</td></tr>
    <tr class="total-row"><td colspan="4" style="text-align:right">부가세(VAT 10%)</td><td style="text-align:right">{vat:,}원</td></tr>
    {disc_row}
    <tr class="grand-total"><td colspan="4" style="text-align:right">최종 합계</td><td style="text-align:right;color:#ffc864;">{final:,}원</td></tr>
  </tbody>
</table>
<div class="footer">
  <b>특이사항:</b> {notes if notes else "없음"}<br><br>
  ※ 본 견적서는 현장 실측 후 변동될 수 있습니다.<br>
  ※ 계약금 30% · 중도금 40% · 잔금 30% 조건입니다.<br>
  ※ 시공 완료 후 1년 무상 A/S를 보장합니다.
</div>
<div class="sign-area">
  <div class="sign-box"><div>고객 확인</div><div class="sign-line"></div><div style="margin-top:4px;">(서명/날인)</div></div>
  <div class="sign-box"><div>시공업체 확인</div><div class="sign-line"></div><div style="margin-top:4px;">(서명/날인)</div></div>
</div>
<br>
<button onclick="window.print()" style="padding:10px 28px;background:#1a1a2e;color:white;border:none;border-radius:8px;cursor:pointer;font-size:1rem;">🖨️ 인쇄 / PDF 저장</button>
</body></html>"""

                b64n  = base64.b64encode(html_content.encode("utf-8")).decode()
                fname = f"견적서_{cname}_{quote_date.strftime('%Y%m%d')}.html"
                if gen_btn:
                    st.markdown(f'<a href="data:text/html;base64,{b64n}" download="{fname}" '
                                f'style="display:inline-block;padding:10px 22px;background:#0f3460;color:white;'
                                f'border-radius:8px;text-decoration:none;font-weight:600;margin-top:10px;">'
                                f'⬇️ 견적서 다운로드 ({fname})</a>', unsafe_allow_html=True)
                    st.success("견적서가 생성되었습니다.")
                if preview_btn:
                    with st.expander("📄 견적서 미리보기", expanded=True):
                        st.components.v1.html(html_content, height=700, scrolling=True)

# ══════════════════════════════════════════════════════════════
# 시공 전/후 사례
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "시공 전/후 사례":
    st.markdown('<div class="section-header">📸 시공 전/후 사례</div>', unsafe_allow_html=True)
    ba_list = load_before_after()
    if not ba_list:
        st.info("등록된 시공 사례가 없습니다. 어드민 모드에서 등록해 주세요.")
    else:
        for ba in ba_list:
            b_src = ba.get("before","")
            a_src = ba.get("after","")
            def _ph(src, lbl):
                if is_b64_image(src):
                    return f'<img src="{src}" style="width:100%;border-radius:10px;max-height:260px;object-fit:cover;">'
                return f'<div style="background:#eee;height:200px;border-radius:10px;display:flex;align-items:center;justify-content:center;color:#aaa;">{lbl} 없음</div>'
            st.markdown(f"""
            <div style="background:white;border-radius:14px;padding:18px;box-shadow:0 2px 12px rgba(0,0,0,.08);margin-bottom:20px;">
              <div style="font-weight:700;font-size:1.05rem;color:#1a1a2e;margin-bottom:4px;">{ba.get('title','')}</div>
              <div style="font-size:.82rem;color:#888;margin-bottom:12px;">📍 {ba.get('location','')} &nbsp;|&nbsp; 🗓️ {ba.get('date','')}</div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
                <div>{_ph(b_src,'Before')}<div style="text-align:center;font-size:.82rem;font-weight:600;color:#888;margin-top:6px;">⬛ 시공 전</div></div>
                <div>{_ph(a_src,'After')}<div style="text-align:center;font-size:.82rem;font-weight:600;color:#0f3460;margin-top:6px;">✨ 시공 후</div></div>
              </div>
              <div style="margin-top:10px;font-size:.85rem;color:#555;">{ba.get('description','')}</div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 어드민: 자재 등록/관리
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "자재 등록/관리" and st.session_state.is_admin:
    st.markdown('<div class="section-header">⚙️ 자재 등록 및 관리</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["➕ 새 자재 등록", "📋 등록 목록"])

    with tab1:
        with st.form("item_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name           = st.text_input("자재/항목명 *", placeholder="예: 아이보리 실크 도배")
                category       = st.selectbox("공간 분류", CATEGORIES)
                customer_price = st.number_input("판매가 (원) *", min_value=0, step=1000)
            with c2:
                wholesale_price = st.number_input("도매가/원가 (원)", min_value=0, step=1000)
                unit            = st.text_input("단위", value="식")
                note            = st.text_input("메모/설명", placeholder="예: 친환경 인증")
            img_file  = st.file_uploader("자재 사진", type=["jpg","jpeg","png","webp"])
            submitted = st.form_submit_button("💾 저장", type="primary")
            if submitted:
                if not name:
                    st.error("항목명을 입력하세요.")
                else:
                    img_b64  = file_to_b64(img_file) or ""
                    new_item = {
                        "id":              f"item_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                        "name":            name,
                        "category":        category,
                        "customer_price":  customer_price,
                        "wholesale_price": wholesale_price,
                        "unit":            unit,
                        "note":            note,
                        "image":           img_b64,
                        "created_at":      datetime.now().isoformat(),
                    }
                    with st.spinner("Google Sheets에 저장 중..."):
                        save_item(new_item)
                    st.success(f"✅ '{name}' 등록 완료!")
                    st.rerun()

    with tab2:
        items = load_items()
        if not items:
            st.info("등록된 자재가 없습니다.")
        else:
            cat_filter = st.selectbox("공간별 보기", ["전체"] + CATEGORIES, key="admin_cat_filter")
            filtered   = items if cat_filter == "전체" else [i for i in items if i.get("category") == cat_filter]
            st.caption(f"총 {len(filtered)}개")
            st.markdown("---")
            grid = st.columns(3, gap="medium")
            for idx, item in enumerate(filtered):
                with grid[idx % 3]:
                    img_src = item.get("image","")
                    if is_b64_image(img_src):
                        st.markdown(f'<img src="{img_src}" style="width:100%;height:140px;object-fit:cover;border-radius:10px;margin-bottom:8px;">', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="width:100%;height:140px;background:#e8eaf0;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:2rem;margin-bottom:8px;">📷</div>', unsafe_allow_html=True)
                    margin = item.get("customer_price",0) - item.get("wholesale_price",0)
                    st.markdown(f"**{item['name']}**  \n`{item.get('category','')}` · {item.get('unit','식')}")
                    st.markdown(f"판매가: **{item.get('customer_price',0):,}원**  \n"
                                f"<span style='color:#e05;font-size:.85rem'>도매가: {item.get('wholesale_price',0):,}원 | 수익: **{margin:,}원**</span>",
                                unsafe_allow_html=True)
                    if item.get("note"):
                        st.caption(f"📝 {item['note']}")
                    if st.button("🗑️ 삭제", key=f"del_{item['id']}", use_container_width=True):
                        with st.spinner("삭제 중..."):
                            delete_item(item["id"])
                        st.rerun()
                    st.markdown("---")

# ══════════════════════════════════════════════════════════════
# 어드민: 시공 전/후 사진 등록
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "전/후 사진 등록" and st.session_state.is_admin:
    st.markdown('<div class="section-header">🖼️ 시공 전/후 사진 등록</div>', unsafe_allow_html=True)
    with st.form("ba_form", clear_on_submit=True):
        title       = st.text_input("제목 *", placeholder="예: ○○아파트 32평 풀패키지 리모델링")
        location    = st.text_input("위치",   placeholder="예: 부산 해운대구 ○○아파트 32평")
        date_str    = st.text_input("시공 날짜", placeholder="예: 2025년 3월")
        description = st.text_area("시공 설명")
        c1, c2      = st.columns(2)
        with c1:
            before_img = st.file_uploader("📷 시공 전 사진", type=["jpg","jpeg","png","webp"], key="b_img")
        with c2:
            after_img  = st.file_uploader("✨ 시공 후 사진", type=["jpg","jpeg","png","webp"], key="a_img")
        if st.form_submit_button("💾 저장", type="primary"):
            if not title:
                st.error("제목을 입력하세요.")
            else:
                new_ba = {
                    "id":          f"ba_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    "title":       title, "location": location,
                    "date":        date_str, "description": description,
                    "before":      file_to_b64(before_img) or "",
                    "after":       file_to_b64(after_img)  or "",
                    "created_at":  datetime.now().isoformat(),
                }
                with st.spinner("Google Sheets에 저장 중..."):
                    save_before_after(new_ba)
                st.success(f"✅ '{title}' 등록 완료!")
                st.rerun()

    st.markdown("---")
    st.markdown("**📋 등록된 시공 사례**")
    for ba in load_before_after():
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{ba['title']}** — {ba.get('location','')} ({ba.get('date','')})")
        with c2:
            if st.button("🗑️", key=f"badel_{ba['id']}"):
                with st.spinner("삭제 중..."):
                    delete_before_after(ba["id"])
                st.rerun()
        st.divider()
