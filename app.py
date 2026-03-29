import streamlit as st
import json
import os
import base64
from datetime import datetime
from io import BytesIO
import pandas as pd
import copy

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="인테리어 견적 매니저",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 상수 ─────────────────────────────────────────────────────
DATA_FILE        = "data/items.json"
UPLOAD_DIR       = "data/images"
BEFORE_AFTER_DIR = "data/before_after"
ADMIN_PASSWORD   = "admin1234"   # [보안] 배포 시 secrets.toml로 이동 권장
CATEGORIES       = ["거실", "주방", "욕실", "침실", "현관", "베란다", "기타"]

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(BEFORE_AFTER_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

# ── 데이터 I/O ───────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "before_after": []}

def save_data(data: dict):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)   # [안전] 원자적 교체

def save_image(uploaded_file, folder: str) -> str | None:
    if uploaded_file is None:
        return None
    ext   = uploaded_file.name.rsplit(".", 1)[-1].lower()
    fname = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    fpath = os.path.join(folder, fname)
    with open(fpath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return fpath

def load_image_b64(path: str) -> str | None:
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext  = path.rsplit(".", 1)[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        return f"data:{mime};base64,{b64}"
    return None

# ── 견적 헬퍼 ────────────────────────────────────────────────
def calc_totals(items: list[dict]) -> tuple[int, int, int]:
    """소계, VAT(10%), 합계 반환. qty=0 항목은 0원으로 포함."""
    total     = sum(q["price"] * q.get("qty", 1) for q in items)
    vat       = int(total * 0.1)
    grand     = total + vat
    return total, vat, grand

def items_by_category(items: list[dict]) -> dict[str, list]:
    result: dict = {}
    for q in items:
        cat = q.get("category", "기타")
        result.setdefault(cat, []).append(q)
    return result

def already_in_quote(item_id: str) -> bool:
    return any(q.get("id") == item_id for q in st.session_state.quote_items)

def save_version_snapshot():
    """현재 견적 항목을 히스토리로 저장 (최대 10개)."""
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
        "is_admin":         False,
        "selected_category":"전체",
        "page":             "카탈로그",
        # [핵심] 견적 항목: qty=0 허용, active 플래그로 취소선 처리
        "quote_items":      [],
        # 버전 히스토리 (최대 10개 스냅샷)
        "quote_history":    [],
        # 고객 정보 유지
        "customer_name":    "",
        "customer_addr":    "",
        "customer_phone":   "",
        # 할인
        "discount_pct":     0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
data = load_data()

# ── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Playfair+Display:wght@600&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

/* 사이드바 */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg,#1a1a2e 0%,#16213e 60%,#0f3460 100%);
    border-right:1px solid rgba(255,255,255,0.08);
}
[data-testid="stSidebar"] * { color:#e8e8f0 !important; }
[data-testid="stSidebar"] .stButton>button {
    width:100%; background:rgba(255,255,255,0.08);
    border:1px solid rgba(255,255,255,0.15); color:#e8e8f0 !important;
    border-radius:8px; margin-bottom:4px; text-align:left;
    padding:10px 16px; transition:all 0.2s;
}
[data-testid="stSidebar"] .stButton>button:hover {
    background:rgba(255,200,100,0.2); border-color:#ffc864;
}

/* 카드 */
.item-card {
    background:white; border-radius:14px;
    box-shadow:0 2px 12px rgba(0,0,0,0.08);
    overflow:hidden; transition:transform 0.2s,box-shadow 0.2s; height:100%;
}
.item-card:hover { transform:translateY(-3px); box-shadow:0 8px 24px rgba(0,0,0,0.14); }
.card-img  { width:100%; height:180px; object-fit:cover; }
.card-body { padding:14px; }
.card-name { font-size:1rem; font-weight:600; color:#1a1a2e; margin-bottom:4px; }
.card-cat  { font-size:0.75rem; color:#888; margin-bottom:8px; }
.card-price { font-size:1.05rem; font-weight:700; color:#0f3460; }
.card-wholesale {
    font-size:0.8rem; color:#e05; margin-top:6px;
    background:#fff0f3; padding:6px 8px; border-radius:6px;
}
.card-note { font-size:0.82rem; color:#555; margin-top:6px; }

/* ── 견적 테이블 ── */
.q-table { width:100%; border-collapse:collapse; font-size:0.88rem; }
.q-table th {
    background:#1a1a2e; color:white; padding:9px 10px; text-align:left; font-weight:500;
}
.q-table td { padding:7px 10px; border-bottom:1px solid #eee; vertical-align:middle; }
.q-table tr.zero-row td { color:#aaa; }
.q-table tr.zero-row .item-name { text-decoration:line-through; color:#bbb; }
.q-table tr:nth-child(even):not(.zero-row) td { background:#f9f9f9; }
.q-table tr.group-header td {
    background:#e8ecf5; font-weight:600; font-size:0.82rem; color:#1a1a2e; padding:5px 10px;
}

/* 합계 바 */
.quote-total {
    background:linear-gradient(90deg,#1a1a2e,#0f3460);
    color:white; padding:14px 20px; border-radius:10px;
    font-size:1.1rem; font-weight:700; margin-top:12px;
}
.subtotal-bar {
    background:#f0f3fa; border:1px solid #d0d8ec;
    color:#1a1a2e; padding:8px 14px; border-radius:8px;
    font-size:0.88rem; margin-top:8px; display:flex; justify-content:space-between;
}

/* 비교 뱃지 */
.badge-zero  { background:#fce4ec; color:#b71c1c; border-radius:4px; padding:1px 7px; font-size:0.78rem; }
.badge-added { background:#e8f5e9; color:#1b5e20; border-radius:4px; padding:1px 7px; font-size:0.78rem; }
.badge-alt   { background:#fff3e0; color:#e65100; border-radius:4px; padding:1px 7px; font-size:0.78rem; }

/* 타이틀 */
.app-title {
    font-family:'Playfair Display',serif;
    font-size:1.8rem; font-weight:600;
    color:#ffc864; letter-spacing:0.02em; margin-bottom:2px;
}
.app-subtitle { font-size:0.8rem; color:#aab; margin-bottom:16px; }
.section-header {
    font-size:1.1rem; font-weight:700; color:#1a1a2e;
    padding-bottom:8px; border-bottom:2px solid #0f3460; margin-bottom:16px;
}

/* before-after */
.ba-wrap { display:flex; gap:12px; }
.ba-img  { flex:1; text-align:center; }
.ba-img img { width:100%; border-radius:10px; max-height:260px; object-fit:cover; }
.ba-label { font-size:0.8rem; font-weight:600; margin-top:6px; }
.label-before { color:#888; }
.label-after  { color:#0f3460; }

@media (max-width:768px) {
    .ba-wrap { flex-direction:column; }
    .card-img { height:140px; }
}

/* 히스토리 */
.hist-row {
    background:#f8f9ff; border:1px solid #dde; border-radius:8px;
    padding:10px 14px; margin-bottom:8px; cursor:pointer;
}
.hist-row:hover { border-color:#0f3460; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 사이드바
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="app-title">🏠 인테리어<br>견적 매니저</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">소규모 인테리어 전문 상담 도구</div>', unsafe_allow_html=True)

    mode_label = "🔴 어드민 모드" if st.session_state.is_admin else "🔵 고객 모드"
    badge_cls  = "badge-admin" if st.session_state.is_admin else "badge-customer"
    st.markdown(f"""
    <style>
    .badge-admin   {{ background:#ffe0e0; color:#c00; display:inline-block; padding:3px 10px; border-radius:20px; font-size:.75rem; font-weight:600; }}
    .badge-customer {{ background:#e0f0ff; color:#05c; display:inline-block; padding:3px 10px; border-radius:20px; font-size:.75rem; font-weight:600; }}
    </style>
    <span class="{badge_cls}">{mode_label}</span>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # 메뉴 네비게이션
    pages = ["카탈로그", "견적서 작성", "시공 전/후 사례"]
    if st.session_state.is_admin:
        pages += ["자재 등록/관리", "전/후 사진 등록"]

    icons = {"카탈로그":"📦","견적서 작성":"📋","시공 전/후 사례":"📸",
             "자재 등록/관리":"⚙️","전/후 사진 등록":"🖼️"}

    # 견적 항목 건수 표시
    active_cnt = sum(1 for q in st.session_state.quote_items if q.get("qty", 1) > 0)
    for p in pages:
        label = f"{icons.get(p,'')} {p}"
        if p == "견적서 작성" and active_cnt > 0:
            label += f"  ({active_cnt}건)"
        if st.button(label, key=f"nav_{p}"):
            st.session_state.page = p
            st.rerun()

    st.markdown("---")

    # 공간 필터 (카탈로그 전용)
    if st.session_state.page == "카탈로그":
        st.markdown("**🏷️ 공간 필터**")
        for c in ["전체"] + CATEGORIES:
            if st.button(c, key=f"cat_{c}"):
                st.session_state.selected_category = c
                st.rerun()

    st.markdown("---")

    # 어드민 로그인/로그아웃
    if not st.session_state.is_admin:
        with st.expander("🔐 관리자 로그인"):
            pw = st.text_input("비밀번호", type="password", key="pw_input")
            if st.button("로그인"):
                if pw == ADMIN_PASSWORD:
                    st.session_state.is_admin = True
                    st.success("✅ 로그인 성공")
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
    cat = st.session_state.selected_category
    st.markdown(f'<div class="section-header">📦 자재 카탈로그 — {cat}</div>',
                unsafe_allow_html=True)

    items = data.get("items", [])
    if cat != "전체":
        items = [i for i in items if i.get("category") == cat]

    if not items:
        st.info("등록된 자재가 없습니다. 어드민 모드에서 자재를 등록해 주세요.")
    else:
        cols = st.columns(3, gap="medium")
        for idx, item in enumerate(items):
            with cols[idx % 3]:
                img_src  = load_image_b64(item.get("image"))
                img_html = (f'<img class="card-img" src="{img_src}">' if img_src
                            else '<div style="background:#e8eaf0;height:180px;'
                                 'display:flex;align-items:center;justify-content:center;'
                                 'color:#aaa;font-size:2rem;">📷</div>')

                wholesale_html = ""
                if st.session_state.is_admin:
                    margin = item.get("customer_price", 0) - item.get("wholesale_price", 0)
                    wholesale_html = (f'<div class="card-wholesale">'
                                      f'💰 도매가: {item.get("wholesale_price",0):,}원 &nbsp;|&nbsp;'
                                      f'수익: <b>{margin:,}원</b></div>')

                note_html = (f'<div class="card-note">📝 {item.get("note","")}</div>'
                             if item.get("note") else "")

                # 이미 견적에 있는지 확인
                in_quote = already_in_quote(item.get("id"))
                in_q_badge = ('<span style="font-size:0.78rem;color:#1b5e20;'
                              'background:#e8f5e9;border-radius:4px;padding:1px 7px;">'
                              '✅ 견적 포함</span>' if in_quote else "")

                st.markdown(f"""
                <div class="item-card">
                    {img_html}
                    <div class="card-body">
                        <div class="card-cat">🏷️ {item.get("category","")}</div>
                        <div class="card-name">{item.get("name","")} {in_q_badge}</div>
                        <div class="card-price">💵 {item.get("customer_price",0):,}원 / {item.get("unit","식")}</div>
                        {wholesale_html}
                        {note_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                btn_label = "✏️ 수량 수정 (견적 포함)" if in_quote else "➕ 견적에 추가"
                if st.button(btn_label, key=f"add_{item.get('id')}"):
                    if in_quote:
                        # [핵심] 이미 있으면 견적 페이지로 이동해서 수정
                        st.session_state.page = "견적서 작성"
                        st.rerun()
                    else:
                        st.session_state.quote_items.append({
                            "id":       item.get("id"),
                            "name":     item.get("name"),
                            "price":    item.get("customer_price", 0),
                            "category": item.get("category"),
                            "unit":     item.get("unit", "식"),
                            "qty":      1,
                            "memo":     "",
                            "active":   True,
                        })
                        st.toast(f"'{item.get('name')}' 견적에 추가됨!", icon="✅")

# ══════════════════════════════════════════════════════════════
# 견적서 작성 페이지 (핵심 개선)
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "견적서 작성":
    st.markdown('<div class="section-header">📋 견적서 작성</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 2])

    # ── 왼쪽: 고객 정보 + 직접 추가 + 히스토리 ──────────────
    with col_left:
        with st.expander("👤 고객 정보", expanded=True):
            st.session_state.customer_name  = st.text_input(
                "고객 성함", value=st.session_state.customer_name,
                placeholder="홍길동")
            st.session_state.customer_addr  = st.text_input(
                "시공 주소", value=st.session_state.customer_addr,
                placeholder="○○시 ○○구 ○○아파트 00평")
            st.session_state.customer_phone = st.text_input(
                "연락처", value=st.session_state.customer_phone,
                placeholder="010-0000-0000")
            quote_date = st.date_input("견적 날짜", datetime.today())

        # ── 카탈로그 자재 선택 (견적서 탭에서 직접 고르기) ──
        with st.expander("📦 카탈로그에서 자재 추가", expanded=True):
            all_items = data.get("items", [])
            if not all_items:
                st.info("등록된 자재가 없습니다.\n자재 등록/관리 메뉴에서 먼저 등록하세요.")
            else:
                q_cat = st.selectbox(
                    "공간 선택", ["전체"] + CATEGORIES, key="q_cat_filter"
                )
                filtered_items = all_items if q_cat == "전체" else [
                    i for i in all_items if i.get("category") == q_cat
                ]
                for fi in filtered_items:
                    in_q    = already_in_quote(fi.get("id"))
                    img_src = load_image_b64(fi.get("image"))
                    row_c1, row_c2 = st.columns([1, 3])
                    with row_c1:
                        if img_src:
                            st.markdown(
                                f'<img src="{img_src}" style="width:100%;height:58px;'
                                f'object-fit:cover;border-radius:6px;">',
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                '<div style="width:100%;height:58px;background:#e8eaf0;'
                                'border-radius:6px;display:flex;align-items:center;'
                                'justify-content:center;font-size:1.3rem;">📷</div>',
                                unsafe_allow_html=True
                            )
                    with row_c2:
                        st.markdown(
                            f"**{fi['name']}**  \n"
                            f"`{fi.get('category','')}` · "
                            f"**{fi.get('customer_price',0):,}원**/{fi.get('unit','식')}"
                        )
                        if in_q:
                            st.markdown(
                                '<span style="font-size:0.75rem;color:#1b5e20;'
                                'background:#e8f5e9;border-radius:4px;padding:2px 8px;">'
                                '✅ 견적 포함 — 오른쪽 표에서 수량 수정</span>',
                                unsafe_allow_html=True
                            )
                        else:
                            if st.button(
                                "➕ 추가", key=f"qadd_{fi['id']}",
                                use_container_width=True, type="primary"
                            ):
                                st.session_state.quote_items.append({
                                    "id":       fi.get("id"),
                                    "name":     fi.get("name"),
                                    "price":    fi.get("customer_price", 0),
                                    "category": fi.get("category"),
                                    "unit":     fi.get("unit", "식"),
                                    "qty":      1,
                                    "memo":     "",
                                    "active":   True,
                                })
                                st.rerun()
                    st.markdown(
                        '<hr style="margin:4px 0;border:none;border-top:0.5px solid #eee;">',
                        unsafe_allow_html=True
                    )

        # 직접 항목 추가 (카탈로그에 없는 항목)
        with st.expander("✏️ 항목 직접 추가"):
            with st.form("manual_add", clear_on_submit=True):
                m_cat   = st.selectbox("공간", CATEGORIES)
                m_name  = st.text_input("항목명", placeholder="도배 - 실크벽지 (직접 입력)")
                m_price = st.number_input("단가 (원)", min_value=0, step=1000)
                m_qty   = st.number_input("수량", min_value=1, step=1)
                m_unit  = st.text_input("단위", value="식")
                m_memo  = st.text_input("메모", placeholder="특이사항")
                if st.form_submit_button("➕ 추가"):
                    if m_name:
                        st.session_state.quote_items.append({
                            "id":       f"manual_{datetime.now().strftime('%f')}",
                            "name":     m_name,
                            "price":    m_price,
                            "qty":      int(m_qty),
                            "unit":     m_unit,
                            "category": m_cat,
                            "memo":     m_memo,
                            "active":   True,
                        })
                        st.rerun()

        # 할인 설정
        with st.expander("💸 할인 설정"):
            st.session_state.discount_pct = st.slider(
                "할인율 (%)", 0, 30,
                value=st.session_state.discount_pct, step=1)
            if st.session_state.discount_pct > 0:
                total, _, _ = calc_totals(
                    [q for q in st.session_state.quote_items if q.get("qty", 0) > 0])
                disc_amt = int(total * st.session_state.discount_pct / 100)
                st.info(f"할인 금액: -{disc_amt:,}원")

        # 견적 버전 히스토리
        if st.session_state.quote_history:
            with st.expander(f"📜 이전 버전 ({len(st.session_state.quote_history)}개)"):
                for snap in reversed(st.session_state.quote_history):
                    active_items = [q for q in snap["items"] if q.get("qty",0) > 0]
                    snap_total, _, snap_grand = calc_totals(active_items)
                    if st.button(
                        f"🕐 {snap['label']} ({snap['ts']})  "
                        f"— {snap_grand:,}원",
                        key=f"hist_{snap['ts']}"
                    ):
                        st.session_state.quote_items = copy.deepcopy(snap["items"])
                        st.rerun()

    # ── 오른쪽: 견적 항목 테이블 (핵심) ─────────────────────
    with col_right:

        # ── 상단 액션 버튼 ──
        btn_cols = st.columns([1, 1, 1, 2])
        with btn_cols[0]:
            if st.button("📸 버전 저장"):
                save_version_snapshot()
                st.toast("현재 견적이 버전으로 저장되었습니다.", icon="✅")
        with btn_cols[1]:
            if st.button("🔍 0건 숨기기/보이기"):
                st.session_state["show_zero"] = not st.session_state.get("show_zero", True)
                st.rerun()
        with btn_cols[2]:
            if st.button("🗑️ 전체 초기화", type="secondary"):
                if st.session_state.quote_items:
                    save_version_snapshot()   # 초기화 전 자동 저장
                st.session_state.quote_items = []
                st.rerun()

        show_zero = st.session_state.get("show_zero", True)

        if not st.session_state.quote_items:
            st.info("카탈로그에서 항목을 추가하거나, 왼쪽에서 직접 입력하세요.")
        else:
            # [핵심] 공간별 그룹으로 표시
            by_cat = items_by_category(st.session_state.quote_items)
            to_remove: list[int] = []
            updated  = False

            for cat_name, cat_items in by_cat.items():
                # 공간 소계 (active 항목만)
                active_in_cat = [q for q in cat_items if q.get("qty", 0) > 0]
                cat_total     = sum(q["price"] * q["qty"] for q in active_in_cat)

                st.markdown(f"""
                <div class="subtotal-bar">
                    <span>🏷️ {cat_name}</span>
                    <span>소계: <b>{cat_total:,}원</b> ({len(active_in_cat)}건 선택)</span>
                </div>
                """, unsafe_allow_html=True)

                for qitem in cat_items:
                    # 전체 리스트에서 인덱스 찾기
                    gi = st.session_state.quote_items.index(qitem)

                    qty = qitem.get("qty", 1)
                    is_zero = (qty == 0)

                    # 0건이고 숨기기 모드면 건너뜀
                    if is_zero and not show_zero:
                        continue

                    row_cols = st.columns([3.5, 1.2, 1.5, 1.8, 0.7])

                    with row_cols[0]:
                        name_disp = qitem["name"]
                        if is_zero:
                            st.markdown(
                                f'<span style="text-decoration:line-through;color:#bbb;">'
                                f'{name_disp}</span> '
                                f'<span class="badge-zero">미선택</span>',
                                unsafe_allow_html=True)
                        else:
                            # 메모 인라인 표시
                            memo = qitem.get("memo", "")
                            memo_html = (f'<br><span style="font-size:0.75rem;color:#888;">'
                                         f'📝 {memo}</span>' if memo else "")
                            st.markdown(f"{name_disp}{memo_html}", unsafe_allow_html=True)

                    with row_cols[1]:
                        # [핵심] 수량 0 허용 (min_value=0)
                        new_qty = st.number_input(
                            "수량",
                            min_value=0,
                            value=qty,
                            key=f"qty_{gi}",
                            label_visibility="collapsed"
                        )
                        if new_qty != qty:
                            st.session_state.quote_items[gi]["qty"] = new_qty
                            updated = True

                    with row_cols[2]:
                        unit = qitem.get("unit", "식")
                        st.caption(f"{qitem['price']:,}원/{unit}")

                    with row_cols[3]:
                        subtotal = qitem["price"] * new_qty
                        if is_zero:
                            st.markdown(
                                f'<span style="color:#bbb;">—</span>',
                                unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f'<b style="color:#0f3460;">{subtotal:,}원</b>',
                                unsafe_allow_html=True)

                    with row_cols[4]:
                        if st.button("✕", key=f"del_{gi}", help="항목 완전 삭제"):
                            to_remove.append(gi)

            # 삭제 처리
            for idx in sorted(to_remove, reverse=True):
                st.session_state.quote_items.pop(idx)
            if to_remove or updated:
                st.rerun()

            # ── 합계 영역 ──
            st.markdown("---")

            # 활성 항목만으로 합계
            active_items = [q for q in st.session_state.quote_items if q.get("qty", 0) > 0]
            total, vat, grand_total = calc_totals(active_items)

            # 할인 적용
            disc_pct = st.session_state.discount_pct
            disc_amt = int(total * disc_pct / 100) if disc_pct > 0 else 0
            final_total = grand_total - disc_amt

            c_s, c_v, c_d, c_g = st.columns(4)
            c_s.metric("소계", f"{total:,}원")
            c_v.metric("VAT(10%)", f"{vat:,}원")
            if disc_pct > 0:
                c_d.metric(f"할인({disc_pct}%)", f"-{disc_amt:,}원", delta_color="inverse")
            c_g.metric("최종 합계", f"{final_total:,}원")

            # 비교 요약 (0건 항목이 있을 때만 표시)
            zero_items = [q for q in st.session_state.quote_items if q.get("qty", 0) == 0]
            if zero_items:
                zero_total = sum(q["price"] for q in zero_items)
                st.info(
                    f"📊 **미선택 항목 {len(zero_items)}건** (원가 합산: {zero_total:,}원) — "
                    f"수량을 1로 되돌리면 바로 재포함됩니다."
                )

            # 특이사항
            notes = st.text_area(
                "📝 특이사항/메모",
                placeholder="예) 기존 바닥재 철거 포함 · 자재 반입 3층 계단 이동 · 하자보증 2년",
                height=80,
                key="notes_area"
            )

            # ── 견적서 출력 ──
            st.markdown("---")
            out_cols = st.columns([2, 1])
            with out_cols[0]:
                gen_btn = st.button("📄 견적서 생성 및 다운로드", type="primary",
                                    use_container_width=True)
            with out_cols[1]:
                preview_btn = st.button("👁 미리보기", use_container_width=True)

            if gen_btn or preview_btn:
                customer_name  = st.session_state.customer_name or "고객"
                customer_addr  = st.session_state.customer_addr or "미입력"
                customer_phone = st.session_state.customer_phone or "미입력"

                # 공간별 행 그룹 생성
                rows_html = ""
                by_cat_out = items_by_category(active_items)

                for cat_name, cat_items in by_cat_out.items():
                    cat_sub = sum(q["price"] * q["qty"] for q in cat_items)
                    rows_html += f"""
                    <tr>
                      <td colspan="5" style="background:#e8ecf5;font-weight:600;
                        font-size:0.85rem;padding:6px 12px;color:#1a1a2e;">
                        🏷️ {cat_name} — 소계: {cat_sub:,}원
                      </td>
                    </tr>"""
                    for q in cat_items:
                        memo_td = (f'<br><span style="font-size:0.78rem;color:#888;">'
                                   f'{q.get("memo","")}</span>'
                                   if q.get("memo") else "")
                        rows_html += f"""
                        <tr>
                          <td>{q.get('category','')}</td>
                          <td>{q['name']}{memo_td}</td>
                          <td style="text-align:center">{q.get('qty',1)}{q.get('unit','식')}</td>
                          <td style="text-align:right">{q['price']:,}원</td>
                          <td style="text-align:right"><b>{q['price']*q['qty']:,}원</b></td>
                        </tr>"""

                disc_row = ""
                if disc_pct > 0:
                    disc_row = f"""
                    <tr class="total-row">
                      <td colspan="4" style="text-align:right">할인 ({disc_pct}%)</td>
                      <td style="text-align:right;color:#e05;">-{disc_amt:,}원</td>
                    </tr>"""

                html_content = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<style>
  body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;margin:40px;color:#222;font-size:14px;}}
  h1{{font-size:1.5rem;color:#1a1a2e;border-bottom:3px solid #1a1a2e;padding-bottom:8px;margin-bottom:16px;}}
  .company{{text-align:right;font-size:0.85rem;color:#555;margin-bottom:20px;}}
  .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:16px 0;}}
  .info-item{{background:#f5f5fa;padding:8px 12px;border-radius:6px;}}
  .info-label{{font-size:0.72rem;color:#666;margin-bottom:2px;}}
  .info-value{{font-weight:600;}}
  table{{width:100%;border-collapse:collapse;margin-top:16px;}}
  th{{background:#1a1a2e;color:white;padding:10px;text-align:left;font-size:0.88rem;}}
  td{{padding:8px 10px;border-bottom:1px solid #eee;font-size:0.88rem;}}
  tr:nth-child(even) td{{background:#f9f9f9;}}
  .total-row td{{font-weight:700;font-size:0.95rem;}}
  .grand-total td{{background:#1a1a2e;color:white;font-size:1.05rem;}}
  .footer{{margin-top:30px;padding:16px;background:#f5f5fa;border-radius:8px;font-size:0.82rem;color:#444;line-height:1.8;}}
  .sign-area{{display:flex;justify-content:flex-end;gap:60px;margin-top:40px;font-size:0.88rem;}}
  .sign-box{{text-align:center;}}
  .sign-line{{border-top:1px solid #999;width:100px;margin-top:40px;}}
  @media print{{button{{display:none!important;}} .no-print{{display:none;}}}}
</style>
</head><body>

<div class="company">
  <b>인테리어 견적서</b><br>
  발행일: {quote_date.strftime('%Y년 %m월 %d일')}
</div>

<h1>🏠 인테리어 공사 견적서</h1>

<div class="info-grid">
  <div class="info-item">
    <div class="info-label">고객 성함</div>
    <div class="info-value">{customer_name} 고객님</div>
  </div>
  <div class="info-item">
    <div class="info-label">견적 날짜</div>
    <div class="info-value">{quote_date.strftime('%Y년 %m월 %d일')}</div>
  </div>
  <div class="info-item">
    <div class="info-label">시공 주소</div>
    <div class="info-value">{customer_addr}</div>
  </div>
  <div class="info-item">
    <div class="info-label">연락처</div>
    <div class="info-value">{customer_phone}</div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th style="width:10%">공간</th>
      <th style="width:35%">항목</th>
      <th style="width:12%;text-align:center">수량</th>
      <th style="width:18%;text-align:right">단가</th>
      <th style="width:25%;text-align:right">금액</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
    <tr class="total-row">
      <td colspan="4" style="text-align:right">소계</td>
      <td style="text-align:right">{total:,}원</td>
    </tr>
    <tr class="total-row">
      <td colspan="4" style="text-align:right">부가세 (VAT 10%)</td>
      <td style="text-align:right">{vat:,}원</td>
    </tr>
    {disc_row}
    <tr class="grand-total">
      <td colspan="4" style="text-align:right">최종 합계</td>
      <td style="text-align:right;color:#ffc864;">{final_total:,}원</td>
    </tr>
  </tbody>
</table>

<div class="footer">
  <b>특이사항:</b> {notes if notes else "없음"}<br><br>
  ※ 본 견적서는 현장 실측 후 변동될 수 있습니다.<br>
  ※ 계약금 30% · 중도금 40% · 잔금 30% 조건입니다.<br>
  ※ 시공 완료 후 1년 무상 A/S를 보장합니다.<br>
  ※ 자재 변경 시 견적 금액이 달라질 수 있습니다.
</div>

<div class="sign-area">
  <div class="sign-box">
    <div>고객 확인</div>
    <div class="sign-line"></div>
    <div style="margin-top:4px;">(서명/날인)</div>
  </div>
  <div class="sign-box">
    <div>시공업체 확인</div>
    <div class="sign-line"></div>
    <div style="margin-top:4px;">(서명/날인)</div>
  </div>
</div>

<br>
<button onclick="window.print()"
  style="padding:10px 28px;background:#1a1a2e;color:white;border:none;
  border-radius:8px;cursor:pointer;font-size:1rem;">
  🖨️ 인쇄 / PDF 저장
</button>

</body></html>"""

                b64   = base64.b64encode(html_content.encode("utf-8")).decode()
                fname = f"견적서_{customer_name}_{quote_date.strftime('%Y%m%d')}.html"

                if gen_btn:
                    st.markdown(
                        f'<a href="data:text/html;base64,{b64}" download="{fname}" '
                        f'style="display:inline-block;padding:10px 22px;background:#0f3460;'
                        f'color:white;border-radius:8px;text-decoration:none;'
                        f'font-weight:600;margin-top:10px;">⬇️ 견적서 다운로드 ({fname})</a>',
                        unsafe_allow_html=True
                    )
                    st.success("견적서가 생성되었습니다. 위 링크를 클릭해 다운로드하세요.")

                if preview_btn:
                    with st.expander("📄 견적서 미리보기", expanded=True):
                        st.components.v1.html(html_content, height=700, scrolling=True)

# ══════════════════════════════════════════════════════════════
# 시공 전/후 사례 페이지
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "시공 전/후 사례":
    st.markdown('<div class="section-header">📸 시공 전/후 사례</div>',
                unsafe_allow_html=True)

    ba_list = data.get("before_after", [])
    if not ba_list:
        st.info("등록된 시공 사례가 없습니다. 어드민 모드에서 사진을 등록해 주세요.")
    else:
        for ba in ba_list:
            b_src = load_image_b64(ba.get("before"))
            a_src = load_image_b64(ba.get("after"))

            def _img_html(src, label):
                if src:
                    return (f'<img src="{src}" style="width:100%;border-radius:10px;'
                            f'max-height:260px;object-fit:cover;">')
                return (f'<div style="background:#eee;height:200px;border-radius:10px;'
                        f'display:flex;align-items:center;justify-content:center;'
                        f'color:#aaa;">{label} 없음</div>')

            st.markdown(f"""
            <div style="background:white;border-radius:14px;padding:18px;
                        box-shadow:0 2px 12px rgba(0,0,0,0.08);margin-bottom:20px;">
              <div style="font-weight:700;font-size:1.05rem;color:#1a1a2e;margin-bottom:4px;">
                {ba.get('title','제목 없음')}
              </div>
              <div style="font-size:0.82rem;color:#888;margin-bottom:12px;">
                📍 {ba.get('location','')} &nbsp;|&nbsp; 🗓️ {ba.get('date','')}
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
                <div>
                  {_img_html(b_src,'Before')}
                  <div style="text-align:center;font-size:0.82rem;font-weight:600;
                    color:#888;margin-top:6px;">⬛ 시공 전</div>
                </div>
                <div>
                  {_img_html(a_src,'After')}
                  <div style="text-align:center;font-size:0.82rem;font-weight:600;
                    color:#0f3460;margin-top:6px;">✨ 시공 후</div>
                </div>
              </div>
              <div style="margin-top:10px;font-size:0.85rem;color:#555;">
                {ba.get('description','')}
              </div>
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 어드민: 자재 등록/관리
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "자재 등록/관리" and st.session_state.is_admin:
    st.markdown('<div class="section-header">⚙️ 자재 등록 및 관리</div>',
                unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["➕ 새 자재 등록", "📋 등록 목록"])

    with tab1:
        with st.form("item_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name            = st.text_input("자재/항목명 *", placeholder="예: 아이보리 실크 도배")
                category        = st.selectbox("공간 분류", CATEGORIES)
                customer_price  = st.number_input("판매가 (원) *", min_value=0, step=1000)
            with c2:
                wholesale_price = st.number_input("도매가/원가 (원)", min_value=0, step=1000)
                unit            = st.text_input("단위", value="식",
                                                placeholder="평, 개, m², 식")
                note            = st.text_input("메모/설명",
                                                placeholder="예: 친환경 인증, 5년 보증")

            img_file  = st.file_uploader("자재 사진", type=["jpg","jpeg","png","webp"])
            submitted = st.form_submit_button("💾 저장", type="primary")

            if submitted:
                if not name:
                    st.error("항목명을 입력하세요.")
                else:
                    img_path = save_image(img_file, UPLOAD_DIR)
                    new_item = {
                        "id":              f"item_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                        "name":            name,
                        "category":        category,
                        "customer_price":  customer_price,
                        "wholesale_price": wholesale_price,
                        "unit":            unit,
                        "note":            note,
                        "image":           img_path,
                        "created_at":      datetime.now().isoformat(),
                    }
                    data["items"].append(new_item)
                    save_data(data)
                    st.success(f"✅ '{name}' 등록 완료!")
                    st.rerun()

    with tab2:
        items = data.get("items", [])
        if not items:
            st.info("등록된 자재가 없습니다. '새 자재 등록' 탭에서 추가하세요.")
        else:
            # 공간별 필터
            cat_filter = st.selectbox(
                "공간별 보기", ["전체"] + CATEGORIES, key="admin_cat_filter"
            )
            filtered = items if cat_filter == "전체" else [
                i for i in items if i.get("category") == cat_filter
            ]
            st.caption(f"총 {len(filtered)}개 자재 등록됨")
            st.markdown("---")

            # 3열 카드 그리드로 표시
            if filtered:
                grid_cols = st.columns(3, gap="medium")
                for idx, item in enumerate(filtered):
                    with grid_cols[idx % 3]:
                        margin   = item.get("customer_price",0) - item.get("wholesale_price",0)
                        img_src  = load_image_b64(item.get("image"))

                        # 썸네일
                        if img_src:
                            st.markdown(
                                f'<img src="{img_src}" style="width:100%;height:140px;'
                                f'object-fit:cover;border-radius:10px;margin-bottom:8px;">',
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                '<div style="width:100%;height:140px;background:#e8eaf0;'
                                'border-radius:10px;display:flex;align-items:center;'
                                'justify-content:center;font-size:2rem;margin-bottom:8px;">'
                                '📷</div>',
                                unsafe_allow_html=True
                            )

                        # 정보
                        st.markdown(
                            f"**{item['name']}**  \n"
                            f"`{item.get('category','')}` · {item.get('unit','식')}"
                        )
                        st.markdown(
                            f"판매가: **{item.get('customer_price',0):,}원**  \n"
                            f"<span style='color:#e05;font-size:0.85rem'>"
                            f"도매가: {item.get('wholesale_price',0):,}원 "
                            f"| 수익: **{margin:,}원**</span>",
                            unsafe_allow_html=True
                        )
                        if item.get("note"):
                            st.caption(f"📝 {item['note']}")

                        if st.button("🗑️ 삭제", key=f"itemdel_{item['id']}",
                                     use_container_width=True):
                            data["items"] = [i for i in data["items"]
                                             if i["id"] != item["id"]]
                            save_data(data)
                            st.rerun()
                        st.markdown("---")

# ══════════════════════════════════════════════════════════════
# 어드민: 시공 전/후 사진 등록
# ══════════════════════════════════════════════════════════════
elif st.session_state.page == "전/후 사진 등록" and st.session_state.is_admin:
    st.markdown('<div class="section-header">🖼️ 시공 전/후 사진 등록</div>',
                unsafe_allow_html=True)

    with st.form("ba_form", clear_on_submit=True):
        title       = st.text_input("제목 *",
                                    placeholder="예: ○○아파트 32평 풀패키지 리모델링")
        location    = st.text_input("위치",
                                    placeholder="예: 부산 해운대구 ○○아파트 32평")
        date_str    = st.text_input("시공 날짜",
                                    placeholder="예: 2025년 3월")
        description = st.text_area("시공 설명",
                                   placeholder="도배, 장판, 주방 상/하부장 교체, 욕실 타일 전체 교체")

        c1, c2 = st.columns(2)
        with c1:
            before_img = st.file_uploader("📷 시공 전 사진",
                                          type=["jpg","jpeg","png","webp"],
                                          key="before_img")
        with c2:
            after_img  = st.file_uploader("✨ 시공 후 사진",
                                          type=["jpg","jpeg","png","webp"],
                                          key="after_img")

        if st.form_submit_button("💾 저장", type="primary"):
            if not title:
                st.error("제목을 입력하세요.")
            else:
                before_path = save_image(before_img, BEFORE_AFTER_DIR)
                after_path  = save_image(after_img,  BEFORE_AFTER_DIR)
                new_ba = {
                    "id":          f"ba_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    "title":       title,
                    "location":    location,
                    "date":        date_str,
                    "description": description,
                    "before":      before_path,
                    "after":       after_path,
                    "created_at":  datetime.now().isoformat(),
                }
                data["before_after"].append(new_ba)
                save_data(data)
                st.success(f"✅ '{title}' 등록 완료!")
                st.rerun()

    st.markdown("---")
    st.markdown("**📋 등록된 시공 사례**")
    for ba in data.get("before_after", []):
        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"**{ba['title']}** — {ba.get('location','')} ({ba.get('date','')})"
            )
        with col_del:
            if st.button("🗑️", key=f"badel_{ba['id']}"):
                data["before_after"] = [b for b in data["before_after"]
                                        if b["id"] != ba["id"]]
                save_data(data)
                st.rerun()
        st.divider()
