# -*- coding: utf-8 -*-
from __future__ import annotations

# ================= 기본 import =================
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
import re
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import math
from textwrap import dedent
import streamlit as st
from zoneinfo import ZoneInfo
import os

# ---- 음력 라이브러리(있으면 사용 / 없으면 양력만) ----
try:
    from korean_lunar_calendar import KoreanLunarCalendar
    HAS_LUNAR = True
except Exception:
    HAS_LUNAR = False

def get_kasi_key() -> str | None:
    """우선순위: Streamlit secrets → OS 환경변수 → None"""
    try:
        val = st.secrets.get("KASI_KEY")
        if val:
            return val
    except Exception:
        pass
    return os.getenv("KASI_KEY")

# ============== 전역 설정/비밀키 ==============
LOCAL_TZ = ZoneInfo("Asia/Seoul")
DEV_MODE = False  # 개발 디버그 출력 토글

# =====================================================
# 태양시(+8:30) 본판 엔진 — 핵심 로직
# =====================================================
BASE_MIN = 8 * 60 + 30  # +8:30 = 510분
def to_solar_time(dt_local: datetime) -> datetime:
    """벽시계(타임존 포함) → 태양시(+8:30)로 환산."""
    off = dt_local.utcoffset()
    if off is None:
        raise ValueError("dt_local must be timezone-aware")
    off_min = int(off.total_seconds() // 60)
    delta = off_min - BASE_MIN  # +9→30, +8:30→0 ...
    return dt_local - timedelta(minutes=delta)

# ── 한국 주요 도시 경도(°E) + 경도 보정 ─────────────────────────
KR_CITY_LON = {
    "서울": 127.0, "가평": 127.5, "대전": 127.5, "부산": 129.0, "대구": 128.5,
    "제주": 126.5, "인천": 126.5, "울산": 128.5, "광주": 127.0, "울릉도": 130.9,
}
BASE_MERIDIAN = 127.5  # +8:30 기준 자오선
DEG2MIN = 4.0  # 1도 = 4분
def apply_longitude_correction(dt_solar: datetime, city_lon: float | None) -> datetime:
    if city_lon is None:
        return dt_solar
    delta_min = (BASE_MERIDIAN - float(city_lon)) * DEG2MIN
    return dt_solar + timedelta(minutes=delta_min)

# ============== 간지/테이블 상수 ==============
CHEONGAN = ['갑','을','병','정','무','기','경','신','임','계']  # 0~9
JIJI = ['자','축','인','묘','진','사','오','미','신','유','술','해']  # 0~11
MONTH_JI = ['인','묘','진','사','오','미','신','유','술','해','자','축']  # 寅~丑

# 12절 → 월지 매핑
JIE_TO_MONTH_JI = {
    '입춘':'인','경칩':'묘','청명':'진','입하':'사','망종':'오','소서':'미',
    '입추':'신','백로':'유','한로':'술','입동':'해','대설':'자','소한':'축',
    '(전년)대설':'자',
}

# 월지에 속한 2개 절기(표시용)
MONTH_TO_2TERMS = {
    '인':('입춘','우수'), '묘':('경칩','춘분'), '진':('청명','곡우'),
    '사':('입하','소만'), '오':('망종','하지'), '미':('소서','대서'),
    '신':('입추','처서'), '유':('백로','추분'), '술':('한로','상강'),
    '해':('입동','소설'), '자':('대설','동지'), '축':('소한','대한'),
}

# ========================= 칩 색상/렌더 =========================
GAN_BG = {
    '갑':'#2ecc71','을':'#2ecc71',  # 목
    '병':'#e74c3c','정':'#e74c3c',  # 화
    '무':'#f1c40f','기':'#f1c40f',  # 토
    '경':'#ffffff','신':'#ffffff',  # 금
    '임':'#000000','계':'#000000',  # 수
}
BR_BG = {
    '해':'#000000','자':'#000000',  # 수
    '인':'#2ecc71','묘':'#2ecc71',  # 목
    '사':'#e74c3c','오':'#e74c3c',  # 화
    '신':'#ffffff','유':'#ffffff',  # 금
    '진':'#f1c40f','술':'#f1c40f','축':'#f1c40f','미':'#f1c40f',  # 토
}
def gan_fg(gan:str) -> str:
    bg = GAN_BG.get(gan, '#ffffff')
    return '#000000' if bg in ('#ffffff','#f1c40f') else '#ffffff'
def br_fg(ji:str) -> str:
    bg = BR_BG.get(ji, '#ffffff')
    return '#000000' if bg in ('#ffffff','#f1c40f') else '#ffffff'

def _chip(text:str, bg:str, fg:str, w:int=64, h:int=64, fs:int=28) -> str:
    return f"""
    <div style="display:flex;align-items:center;justify-content:center;
        width:{w}px;height:{h}px;border-radius:12px;background:{bg};color:{fg};
        border:1px solid #d0d0d0;font-weight:700;font-size:{fs}px;">
      {text}
    </div>
    """.strip()

def ganji_box_labeled(gan: str, ji: str, title: str = "", label: str = "") -> str:
    gbg, gfg = GAN_BG.get(gan, '#fff'), gan_fg(gan)
    bbg, bfg = BR_BG.get(ji, '#fff'), br_fg(ji)
    title_html = f'<div style="font-size:14px;margin-bottom:6px;color:#666;text-align:center">{title}</div>' if title else ''
    label_html = f'<div style="font-size:12px;color:#666;margin-top:6px;text-align:center">{label}</div>' if label else ''
    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;margin:6px 0;">
      {title_html}
      {_chip(gan, gbg, gfg)}
      <div style="height:6px"></div>
      {_chip(ji, bbg, bfg)}
      {label_html}
    </div>
    """.strip()

def calc_age_on(dob: date, now_dt: datetime) -> int:
    today = now_dt.date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def age_by_ipchun(birth_solar: datetime, now_local: datetime, service_key: str | None) -> int:
    j24_now = jie24_times_from_kasi_or_calc(now_local.year, service_key)
    ipchun_now = to_solar_time(j24_now['입춘'])
    y_now = now_local.year if now_local >= ipchun_now else (now_local.year - 1)
    return max(0, y_now - birth_solar.year)

def split_ganji(gj: str) -> tuple[str, str]:
    if not gj or len(gj) < 2:
        raise ValueError("ganji must be a 2-char string like '갑자'")
    return gj[0], gj[1]

# ============== (요약 카드) 대운/세운 렌더 유틸 ==============
def dayun_slim_box(age0: int, gan: str, ji: str, dg: str) -> str:
    gbg = GAN_BG.get(gan, '#fff'); bbg = BR_BG.get(ji, '#fff')
    gfg = '#000000' if gbg in ('#ffffff', '#f1c40f') else '#ffffff'
    bfg = '#000000' if bbg in ('#ffffff', '#f1c40f') else '#ffffff'
    label = f"{age0}~{age0+9}"
    six = f"{six_for_stem(dg, gan)}/{six_for_branch(dg, ji)}"
    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;width:58px;margin:1px 2px;">
      <div style="font-size:11px;color:#666;margin-bottom:4px">{label}</div>
      <div class="chip" style="display:flex;align-items:center;justify-content:center;width:41px;height:41px;border-radius:10px;background:{gbg};color:{gfg};border:1px solid #d0d0d0;font-weight:700;font-size:22px;">{gan}</div>
      <div style="height:4px"></div>
      <div class="chip" style="display:flex;align-items:center;justify-content:center;width:41px;height:41px;border-radius:10px;background:{bbg};color:{bfg};border:1px solid #d0d0d0;font-weight:700;font-size:22px;">{ji}</div>
      <div class="mini" style="font-size:10px;color:#666;margin-top:4px;white-space:nowrap">{six}</div>
    </div>
    """.strip()

def render_dayun_row(dayun_list, day_stem: str) -> str:
    cards = []
    for item in dayun_list:
        age0 = item["start_age"]
        gan = CHEONGAN[item["g_idx"]]; ji = MONTH_JI[item["b_idx"]]
        cards.append(dayun_slim_box(age0, gan, ji, day_stem))
    return f"""
    <div class="strip-outer">
      <div class="strip-inner">
        {''.join(cards)}
      </div>
    </div>
    """.strip()

# -------------------- 5행/음양/지장간/십성(육신) --------------------
STEM_ELEM = {'갑':'목','을':'목','병':'화','정':'화','무':'토','기':'토','경':'금','신':'금','임':'수','계':'수'}
STEM_YINYANG = {'갑':'양','을':'음','병':'양','정':'음','무':'양','기':'음','경':'양','신':'음','임':'양','계':'음'}
BRANCH_MAIN_STEM = {'자':'계','축':'기','인':'갑','묘':'을','진':'무','사':'병','오':'정','미':'기','신':'경','유':'신','술':'무','해':'임'}
INSHINSAHAE = {'인','신','사','해'}
SAMHAP_GROUP = {
    '화': {'인','오','술'}, '목': {'해','묘','미'}, '수': {'신','자','진'}, '금': {'사','유','축'},
}
MONTH_TO_SAMHAP_ELEM = {
    '인':'화','오':'화','술':'화','해':'목','묘':'목','미':'목','신':'수','자':'수','진':'수','사':'금','유':'금','축':'금','진':'수','술':'화','축':'금','미':'목',
}
ELEM_PRODUCE = {'목':'화','화':'토','토':'금','금':'수','수':'목'}
ELEM_CONTROL  = {'목':'토','화':'금','토':'수','금':'목','수':'화'}
ELEM_OVERCOME_ME = {v:k for k,v in ELEM_CONTROL.items()}
ELEM_PRODUCE_ME  = {v:k for k,v in ELEM_PRODUCE.items()}
def stems_of_element(elem:str) -> list[str]:
    return {'목':['갑','을'],'화':['병','정'],'토':['무','기'],'금':['경','신'],'수':['임','계']}[elem]
def stem_with_polarity(elem:str, parity:str) -> str:
    a, b = stems_of_element(elem); return a if parity=='양' else b
def ten_god_for_stem(day_stem:str, other_stem:str) -> str:
    d_e, d_p = STEM_ELEM[day_stem], STEM_YINYANG[day_stem]
    o_e, o_p = STEM_ELEM[other_stem], STEM_YINYANG[other_stem]
    if o_e == d_e: return '비견' if o_p == d_p else '겁재'
    if o_e == ELEM_PRODUCE[d_e]: return '식신' if o_p == d_p else '상관'
    if o_e == ELEM_CONTROL[d_e]: return '편재' if o_p == d_p else '정재'
    if o_e == ELEM_OVERCOME_ME[d_e]: return '편관' if o_p == d_p else '정관'
    if o_e == ELEM_PRODUCE_ME[d_e]: return '편인' if o_p == d_p else '정인'
    return '미정'
def ten_god_for_branch(day_stem:str, branch:str) -> str:
    main = BRANCH_MAIN_STEM[branch]; return ten_god_for_stem(day_stem, main)
def six_for_stem(day_stem:str, other_stem:str) -> str: return ten_god_for_stem(day_stem, other_stem)
def six_for_branch(day_stem:str, branch:str) -> str: return ten_god_for_branch(day_stem, branch)
def month_group(branch:str) -> str:
    if branch in {'자','오','묘','유'}: return '자오묘유'
    if branch in {'인','신','사','해'}: return '인신사해'
    return '진술축미'
def is_mid_ruling_by_time(dt_solar: datetime, first_term_dt: datetime) -> bool:
    return first_term_dt <= dt_solar < (first_term_dt + timedelta(days=15))

# ====================== 사령(司令) — 최종 통합 블록 ======================
BRANCH_HIDDEN = {
    '자': ['임','계'],
    '축': ['계','신','기'],
    '인': ['무','병','갑'],
    '묘': ['갑','을'],
    '진': ['을','계','무'],
    '사': ['무','경','병'],
    '오': ['병','기','정'],
    '미': ['정','을','기'],
    '신': ['무','임','경'],
    '유': ['경','신'],
    '술': ['신','정','무'],
    '해': ['무','갑','임'],
}
def all_hidden_stems(branches: list[str]) -> set[str]:
    s: set[str] = set()
    for b in branches: s.update(BRANCH_HIDDEN.get(b, []))
    return s
for _b in ('인','신','사','해'):
    assert len(BRANCH_HIDDEN[_b]) == 3, f"{_b}월 지장간은 3개(여기·중기·본기)여야 합니다."
_NOT_EARTH = {'갑','을','병','정','경','신','임','계'}
def _pick_non_earth_from(h: list[str], start_idx: int) -> str | None:
    for i in range(start_idx, len(h)):
        if h[i] in _NOT_EARTH: return h[i]
    return None
def _hidden_triplet(branch: str) -> tuple[str | None, str | None, str | None]:
    h = BRANCH_HIDDEN.get(branch, [])
    yeo = h[0] if len(h)>=1 else None
    mid = h[1] if len(h)>=2 else None
    main= h[2] if len(h)>=3 else (h[1] if len(h)==2 else (h[0] if h else None))
    return yeo, mid, main
def is_first_half_by_terms(dt_solar: datetime, first_term_dt: datetime, mid_term_dt: datetime) -> bool:
    return first_term_dt <= dt_solar < mid_term_dt
def _pick_saryeong_for_display(branch: str, dt_solar: datetime, first_term_dt: datetime, mid_term_dt: datetime) -> tuple[str, str]:
    h = BRANCH_HIDDEN.get(branch, [])
    is_first_half = is_first_half_by_terms(dt_solar, first_term_dt, mid_term_dt)
    if is_first_half:
        if branch in INSHINSAHAE:
            stem = (_pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 2) or _pick_non_earth_from(h, 0))
            label = "중기사령"
        else:
            stem = (_pick_non_earth_from(h, 0) or _pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 2))
            label = "여기사령"
    else:
        if branch in {'진','술','축','미'}:
            stem = (_pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 2) or _pick_non_earth_from(h, 0))
            label = "중기사령"
        elif branch in INSHINSAHAE:
            start = 2 if len(h) >= 3 else (1 if len(h) == 2 else 0)
            stem = (_pick_non_earth_from(h, start) or _pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 0))
            label = "본기사령"
        else:
            start = 2 if len(h) >= 3 else (1 if len(h) == 2 else 0)
            stem = (_pick_non_earth_from(h, start) or _pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 0))
            label = "본기사령"
    if stem is None:
        stem = next((x for x in h if x in _NOT_EARTH), '')
    return stem, label

def ruling_for_caption(mb: str, dt_solar: datetime, first_term_dt: datetime, mid_term_dt: datetime) -> tuple[str, str | None]:
    first_half = is_first_half_by_terms(dt_solar, first_term_dt, mid_term_dt)
    h = BRANCH_HIDDEN.get(mb, [])
    if first_half:
        if mb in INSHINSAHAE:
            stem = (_pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 2) or _pick_non_earth_from(h, 0))
            return ("전반(중기)", stem)
        else:
            stem = (_pick_non_earth_from(h, 0) or _pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 2))
            return ("전반(여기)", stem)
    else:
        if mb in {'진','술','축','미'}:
            stem = (_pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 2) or _pick_non_earth_from(h, 0))
            return ("후반(중기)", stem)
        elif mb in INSHINSAHAE:
            start = 2 if len(h) >= 3 else (1 if len(h) == 2 else 0)
            stem = (_pick_non_earth_from(h, start) or _pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 0))
            return ("후반(본기)", stem)
        else:
            start = 2 if len(h) >= 3 else (1 if len(h) == 2 else 0)
            stem = (_pick_non_earth_from(h, start) or _pick_non_earth_from(h, 1) or _pick_non_earth_from(h, 0))
            return ("후반(본기)", stem)

# ---- 격(格) 판정 ----
@dataclass
class Inputs:
    day_stem: str
    month_branch: str
    month_stem: str
    stems_visible: list[str]
    branches_visible: list[str]
    solar_dt: datetime
    first_term_dt: datetime
    mid_term_dt: datetime
    day_from_jieqi: int

def decide_geok(inp: Inputs) -> tuple[str, str]:
    ds = inp.day_stem
    mb = inp.month_branch
    ms = inp.month_stem
    stems = list(inp.stems_visible)
    branches = list(inp.branches_visible)
    after_mid = inp.solar_dt >= inp.mid_term_dt
    day_from_jieqi = inp.day_from_jieqi
    ds_e = STEM_ELEM[ds]; ds_p = STEM_YINYANG[ds]
    mb_main = BRANCH_MAIN_STEM[mb]
    mb_e, mb_p = STEM_ELEM[mb_main], STEM_YINYANG[mb_main]
    month_hiddens = BRANCH_HIDDEN[mb]
    visible_set = set(stems)
    hidden_set = all_hidden_stems(branches)
    pool = visible_set | hidden_set
    if mb in {'자','오','묘','유','인','신','사','해'} and ds_e == mb_e:
        off_e = ELEM_OVERCOME_ME[ds_e]
        jung_gwan = stem_with_polarity(off_e, '음' if ds_p=='양' else '양')
        pyeon_gwan = stem_with_polarity(off_e, ds_p)
        same_polarity = (ds_p == mb_p)
        any_jung_br = any(ten_god_for_branch(ds, b) == '정관' for b in branches)
        jung_branches = [b for b in branches if ten_god_for_branch(ds, b) == '정관']
        any_pyeon_br = any(ten_god_for_branch(ds, b) == '편관' for b in branches)
        pyeon_branches = [b for b in branches if ten_god_for_branch(ds, b) == '편관']
        if same_polarity:
            if (jung_gwan in visible_set) or any_jung_br:
                why = ("정관 {0} 천간 투간".format(jung_gwan) if (jung_gwan in visible_set) else f"지지 정관 존재({','.join(jung_branches)})")
                return ('건록격', f"[특수] 월비(일/월 음양 같음) + {why} → 건록격.")
            else:
                return ('월비격', f"[특수] 월비(일/월 음양 같음) · 정관(천간/지지) 없음 → 월비격.")
        else:
            if (pyeon_gwan in visible_set) or any_pyeon_br:
                why = ("편관 {0} 천간 투간".format(pyeon_gwan) if (pyeon_gwan in visible_set) else f"지지 편관 존재({','.join(pyeon_branches)})")
                return ('양인격', f"[특수] 월겁(일/월 음양 다름) + {why} → 양인격.")
            else:
                return ('월겁격', f"[특수] 월겁(일/월 음양 다름) · 편관(천간/지지) 없음 → 월겁격.")
    grp = '자오묘유' if mb in {'자','오','묘','유'} else ('인신사해' if mb in {'인','신','사','해'} else '진술축미')
    if grp == '자오묘유':
        month_elem = STEM_ELEM[mb_main]
        same_elem_visible = [s for s in stems if STEM_ELEM.get(s) == month_elem]
        if same_elem_visible:
            pick = next((s for s in same_elem_visible if STEM_YINYANG[s] != ds_p), same_elem_visible[0])
            six = ten_god_for_stem(ds, pick)
            return (f"{six}격", f"[자오묘유] 월지와 같은 오행({month_elem}) {pick} 투간 → {six}격.")
        base = mb_main
        six = ten_god_for_stem(ds, base)
        return (f"{six}격", f"[자오묘유] 같은 오행 투간 없음 → 체(본기 {base}) 기준 {six}격.")
    if grp == '인신사해':
        rokji = mb_main
        month_elem = STEM_ELEM[rokji]
        base_stems = set(stems_of_element(month_elem))
        base_visible = [s for s in inp.stems_visible if s in base_stems]
        if base_visible:
            pick = base_visible[0]
            if month_elem == STEM_ELEM[ds]:
                off_e = ELEM_OVERCOME_ME[STEM_ELEM[ds]]
                jung_gwan = stem_with_polarity(off_e, '음' if STEM_YINYANG[ds]=='양' else '양')
                pyeon_gwan = stem_with_polarity(off_e, STEM_YINYANG[ds])
                if STEM_YINYANG[pick] == STEM_YINYANG[ds]:
                    if jung_gwan in inp.stems_visible:
                        return ('건록격', f"[인신사해] 록지({month_elem}) {pick} 투간 + 정관({jung_gwan}) 투간 → 건록격.")
                else:
                    if pyeon_gwan in inp.stems_visible:
                        return ('양인격', f"[인신사해] 록지({month_elem}) {pick} 투간 + 편관({pyeon_gwan}) 투간 → 양인격.")
            six = ten_god_for_stem(ds, pick)
            return (f"{six}격", f"[인신사해] 록지({month_elem}) {pick} 투간자 원칙 → {six}격.")
        tri_elem = MONTH_TO_SAMHAP_ELEM[mb]
        tri_group = SAMHAP_GROUP[tri_elem]
        others = set(tri_group) - {mb}
        if others.issubset(set(inp.branches_visible)) and is_first_half_by_terms(inp.solar_dt, inp.first_term_dt, inp.mid_term_dt):
            tri_stems = stems_of_element(tri_elem)
            tri_visible = [s for s in tri_stems if s in inp.stems_visible]
            if tri_visible and tri_elem != STEM_ELEM[ds]:
                opp = [s for s in tri_visible if STEM_YINYANG[s] != STEM_YINYANG[ds]]
                pick = opp[0] if opp else tri_visible[0]
                six = ten_god_for_stem(ds, pick)
                return (f"중기격({six})", f"[인신사해] 삼합 성립 + 중기 사령 + {pick} 투간 → 중기격.")
            elif not tri_visible and tri_elem != STEM_ELEM[ds]:
                return ("중기상생격", "[인신사해] 삼합 성립 + 중기 사령(투간 없음) → 중기 상생격.")
        if inp.month_stem:
            six = ten_god_for_stem(ds, inp.month_stem)
            return (f"{six}격", f"[인신사해] 록지 투간 없음 → 월간 {inp.month_stem} 기준 {six}격.")
        six = ten_god_for_stem(ds, rokji)
        return (f"{six}격", f"[인신사해] 록지·중기·월간 투간 불성립 → 본기({rokji}) 기준 {six}격.")
    if grp == '진술축미':
        tri_elem = MONTH_TO_SAMHAP_ELEM[mb]
        tri_group = SAMHAP_GROUP[tri_elem]
        others = set(tri_group) - {mb}
        partners = (others & set(branches))
        month_hiddens = BRANCH_HIDDEN[mb]
        mb_main = BRANCH_MAIN_STEM[mb]
        is_front12 = (inp.day_from_jieqi <= 11)
        if partners:
            if tri_elem == STEM_ELEM[ds]:
                pick = mb_main
                six = ten_god_for_stem(ds, pick)
                why = (f"[진술축미] 반합 성립({mb}+{','.join(sorted(partners))}→{tri_elem}) "
                       f"하지만 합국이 일간({STEM_ELEM[ds]})과 동일 → 건록/양인 금지, 체(본기 {pick})로 {six}격.")
                return (f"{six}격", why)
            tri_stems = stems_of_element(tri_elem)
            tri_visible = [s for s in tri_stems if s in visible_set]
            mid_qi = month_hiddens[1] if len(month_hiddens)>=2 else month_hiddens[-1]
            mid_is_tri = (STEM_ELEM.get(mid_qi) == tri_elem)
            if tri_visible:
                if len(tri_visible) >= 2 and mid_is_tri and (mid_qi in tri_visible):
                    pick = mid_qi
                else:
                    pick = tri_visible[0] if len(tri_visible)==1 else (mid_qi if mid_is_tri else tri_visible[0])
            else:
                pick = mid_qi if mid_is_tri else stem_with_polarity(tri_elem, '음' if STEM_YINYANG[ds]=='양' else '양')
            six = ten_god_for_stem(ds, pick)
            why = (f"[진술축미] 반합 성립({mb}+{','.join(sorted(partners))}→{tri_elem}) "
                   f"+ 중기/투간 규칙 적용 → {pick} 기준 {six}격.")
            return (f"{six}격", why)
        if is_front12:
            yeogi = month_hiddens[0]
            y_elem = STEM_ELEM[yeogi]
            same_elem_visible = [s for s in stems if STEM_ELEM.get(s) == y_elem]
            opp_first = [s for s in same_elem_visible if STEM_YINYANG[s] != STEM_YINYANG[ds]]
            if opp_first:
                pick = opp_first[0]; note = f"여기사령·투간우선({pick})"
            elif same_elem_visible:
                pick = same_elem_visible[0]; note = f"여기사령·동일오행투간({pick})"
            else:
                pick = yeogi; note = f"여기사령({yeogi})"
            six = ten_god_for_stem(ds, pick)
            return (f"{six}격", f"[진술축미] 절입 후 12일({note}) → {pick} 기준 {six}격.")
        else:
            earth_vis = [s for s in ('무','기') if s in visible_set]
            if earth_vis:
                opp = [s for s in earth_vis if STEM_YINYANG[s] != STEM_YINYANG[ds]]
                pick = opp[0] if opp else earth_vis[0]; note = f"주왕토 투간({pick})"
            else:
                pick = mb_main; note = f"본기({pick})"
            six = ten_god_for_stem(ds, pick)
            return (f"{six}격", f"[진술축미] 절입 13~말일({note}) → {pick} 기준 {six}격.")
    six = ten_god_for_stem(ds, mb_main)
    return (f"{six}격", f"[폴백] 규칙 미적용 → 체(본기 {mb_main})로 {six}격.")

# ========================= 절기/황경 (12절 + 24절) =========================
JIE_DEGREES = {'입춘':315,'경칩':345,'청명': 15,'입하': 45,'망종': 75,'소서':105,'입추':135,'백로':165,'한로':195,'입동':225,'대설':255,'소한':285}
JIE_ORDER = ['입춘','경칩','청명','입하','망종','소서','입추','백로','한로','입동','대설','소한']
JIE24_DEGREES = {
 '입춘':315,'우수':330,'경칩':345,'춘분': 0,'청명': 15,'곡우': 30,'입하': 45,'소만': 60,
 '망종': 75,'하지': 90,'소서':105,'대서':120,'입추':135,'처서':150,'백로':165,'추분':180,
 '한로':195,'상강':210,'입동':225,'소설':240,'대설':255,'동지':270,'소한':285,'대한':300,
}
JIE24_ORDER = ['입춘','우수','경칩','춘분','청명','곡우','입하','소만','망종','하지','소서','대서','입추','처서','백로','추분','한로','상강','입동','소설','대설','동지','소한','대한']

# ===================== 시두법 & 월간 시작 계산 =====================
SIDU_START = {('갑','기'):'갑', ('을','경'):'병', ('병','신'):'무', ('정','임'):'경', ('무','계'):'임'}
def month_start_gan_idx(year_gan_idx: int) -> int:
    return ((year_gan_idx % 5) * 2 + 2) % 10
K_ANCHOR_DEFAULT = 49  # 일주 앵커 K

# ============== 줄리안/황경 계산 ==============
def jdn_0h_utc(y: int, m: int, d: int) -> int:
    if m <= 2: y -= 1; m += 12
    A = y // 100; B = 2 - A + A // 4
    return (int(365.25*(y + 4716)) + int(30.6001*(m + 1)) + d + B - 1524)
def jd_from_utc(dt_utc: datetime) -> float:
    y = dt_utc.year; m = dt_utc.month
    d = dt_utc.day + (dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)/24
    if m <= 2: y -= 1; m += 12
    A = y // 100; B = 2 - A + A // 4
    JD = int(365.25*(y + 4716)) + int(30.6001*(m + 1)) + d + B - 1524.5
    return JD
def _norm360(x: float) -> float: return x % 360.0
def _wrap180(x: float) -> float: return (x + 180.0) % 360.0 - 180.0
def solar_longitude_deg(dt_utc: datetime) -> float:
    JD = jd_from_utc(dt_utc); T = (JD - 2451545.0)/36525.0
    L0 = _norm360(280.46646 + 36000.76983*T + 0.0003032*T*T)
    M  = _norm360(357.52911 + 35999.05029*T - 0.0001537*T*T)
    Mr = math.radians(M)
    C  = ((1.914602 - 0.004817*T - 0.000014*T*T) * math.sin(Mr)
        + (0.019993 - 0.000101*T) * math.sin(2*Mr)
        + 0.000289 * math.sin(3*Mr))
    theta = L0 + C
    Omega = 125.04 - 1934.136*T
    lam = theta - 0.00569 - 0.00478*math.sin(math.radians(Omega))
    return _norm360(lam)
def find_longitude_time_local(year: int, target_deg: float, approx_dt_local: datetime) -> datetime:
    a = (approx_dt_local - timedelta(days=3)).astimezone(timezone.utc)
    b = (approx_dt_local + timedelta(days=3)).astimezone(timezone.utc)
    def f(dt_utc): return _wrap180(solar_longitude_deg(dt_utc) - target_deg)
    scan, step = a, timedelta(hours=6); fa = f(scan); found = False
    while scan < b:
        scan2 = scan + step; fb = f(scan2)
        if fa == 0 or fb == 0 or (fa < 0 and fb > 0) or (fa > 0 and fb < 0):
            a, b = scan, scan2; found = True; break
        scan, fa = scan2, fb
    if not found:
        a = (approx_dt_local - timedelta(days=1)).astimezone(timezone.utc)
        b = (approx_dt_local + timedelta(days=1)).astimezone(timezone.utc)
    for _ in range(70):
        mid = a + (b - a)/2
        fm = f(mid); fa = f(a)
        if fm == 0: a = b = mid; break
        if (fa <= 0 and fm >= 0) or (fa >= 0 and fm <= 0): b = mid
        else: a = mid
    res = (a + (b - a)/2).astimezone(LOCAL_TZ)
    return res.replace(second=0, microsecond=0)

# ============== 절기(KASI) 연동 + 폴백 ==============
@dataclass
class JieTimes:
    terms: dict[str, datetime]
def _xml_items(xml_bytes): return ET.fromstring(xml_bytes).findall('.//item')
def kasi_get_24divisions_dates(year: int, service_key: str, names: list[str]) -> dict:
    base = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/get24DivisionsInfo"
    out = {}
    for m in range(1, 13):
        params = {"ServiceKey": service_key, "solYear": str(year), "solMonth": f"{m:02d}", "numOfRows": "100", "pageNo": "1"}
        url = f"{base}?{urlencode(params, safe=':+')}"
        xml = urlopen(url).read()
        for it in _xml_items(xml):
            name = (it.findtext('dateName') or '').strip()
            locdate = (it.findtext('locdate') or '').strip()
            if name in names and len(locdate) == 8:
                out[name] = locdate
    return out
def kasi_get_monthly_events(year: int, month: int, service_key: str) -> list[dict]:
    base = "http://apis.data.go.kr/B090041/openapi/service/AstroEventInfoService/getAstroEventInfo"
    params = {"ServiceKey": service_key, "solYear": str(year), "solMonth": f"{month:02d}", "numOfRows": "200", "pageNo": "1"}
    url = f"{base}?{urlencode(params, safe=':+')}"
    xml = urlopen(url).read()
    items = []
    for it in _xml_items(xml):
        items.append({"title": (it.findtext('astroTitle') or '').strip(), "time": (it.findtext('astroTime') or '').strip(), "locdate": (it.findtext('locdate') or '').strip()})
    return items
def _merge_date_time_local(yyyymmdd: str, hhmm: str) -> datetime:
    y = int(yyyymmdd[:4]); m = int(yyyymmdd[4:6]); d = int(yyyymmdd[6:8])
    hh, mm = hhmm.split(':')
    return datetime(y, m, d, int(hh), int(mm), tzinfo=LOCAL_TZ)
def approx_guess_local(year: int) -> dict[str, datetime]:
    rough = {'입춘': (2,4), '경칩': (3,6), '청명': (4,5), '입하': (5,6), '망종': (6,6), '소서': (7,7),
             '입추': (8,8), '백로': (9,8), '한로': (10,8), '입동': (11,7), '대설': (12,7), '소한': (1,6)}
    out = {}
    for name, (m, d) in rough.items():
        out[name] = datetime(year, m, d, 9, 0, tzinfo=LOCAL_TZ)
    out['(전년)대설'] = datetime(year-1, 12, 7, 9, 0, tzinfo=LOCAL_TZ)
    return out
def approx_guess_local_24(year: int) -> dict[str, datetime]:
    rough = {'입춘':(2,4),'우수':(2,19),'경칩':(3,6),'춘분':(3,21),'청명':(4,5),'곡우':(4,20),
             '입하':(5,6),'소만':(5,21),'망종':(6,6),'하지':(6,21),'소서':(7,7),'대서':(7,23),
             '입추':(8,8),'처서':(8,23),'백로':(9,8),'추분':(9,23),'한로':(10,8),'상강':(10,23),
             '입동':(11,7),'소설':(11,22),'대설':(12,7),'동지':(12,22),'소한':(1,6),'대한':(1,20)}
    out = {}
    for name,(m,d) in rough.items():
        out[name] = datetime(year, m, d, 9, 0, tzinfo=LOCAL_TZ)
    return out
def compute_jie_times_calc(year: int) -> JieTimes:
    guesses = approx_guess_local(year); terms = {}
    for name in JIE_ORDER:
        terms[name] = find_longitude_time_local(year, JIE_DEGREES[name], guesses[name])
    terms['(전년)대설'] = find_longitude_time_local(year-1, JIE_DEGREES['대설'], guesses['(전년)대설'])
    return JieTimes(terms)
def compute_jie24_times_calc(year: int) -> dict[str, datetime]:
    guesses = approx_guess_local_24(year); out = {}
    for name in JIE24_ORDER:
        deg = JIE24_DEGREES[name]; approx = guesses[name]
        out[name] = find_longitude_time_local(approx.year, deg, approx)
    return out
def jie_times_from_kasi_or_calc(year: int, service_key: str | None) -> JieTimes:
    if not service_key: return compute_jie_times_calc(year)
    try:
        name_to_date = kasi_get_24divisions_dates(year, service_key, JIE_ORDER)
    except Exception:
        return compute_jie_times_calc(year)
    if len([n for n in name_to_date if n in JIE_ORDER]) < 10:
        return compute_jie_times_calc(year)
    try:
        prev = kasi_get_24divisions_dates(year-1, service_key, JIE_ORDER)
        if '대설' in prev:
            name_to_date['(전년)대설'] = prev['대설']
    except Exception:
        pass
    monthly_cache: dict[int, list] = {}
    terms: dict[str, datetime] = {}
    for name in (JIE_ORDER + ['(전년)대설']):
        if name not in name_to_date:
            approx = approx_guess_local(year if name!='(전년)대설' else year-1)[name if name!='(전년)대설' else '(전년)대설']
            deg = JIE_DEGREES['대설'] if name=='(전년)대설' else JIE_DEGREES[name]
            terms[name] = find_longitude_time_local(year if name!='(전년)대설' else year-1, deg, approx)
            continue
        ymd = name_to_date[name]
        y = int(ymd[:4]); m = int(ymd[4:6]); d = int(ymd[6:8])
        if m not in monthly_cache:
            try: monthly_cache[m] = kasi_get_monthly_events(y, m, service_key)
            except Exception: monthly_cache[m] = []
        hit = None
        for ev in monthly_cache[m]:
            if ev['title'] == ('대설' if name=='(전년)대설' else name) and ev['locdate'] == ymd and ev['time']:
                hit = ev['time']; break
        if hit:
            terms[name] = _merge_date_time_local(ymd, hit)
        else:
            approx = datetime(y, m, d, 12, 0, tzinfo=LOCAL_TZ)
            deg = JIE_DEGREES['대설'] if name=='(전년)대설' else JIE_DEGREES[name]
            year_for = y - 1 if name == '(전년)대설' else y
            terms[name] = find_longitude_time_local(year_for, deg, approx)
    return JieTimes(terms)
def jie24_times_from_kasi_or_calc(year: int, service_key: str | None) -> dict[str, datetime]:
    if not service_key: return compute_jie24_times_calc(year)
    try:
        name_to_date = kasi_get_24divisions_dates(year, service_key, JIE24_ORDER)
    except Exception:
        return compute_jie24_times_calc(year)
    if len([n for n in name_to_date if n in JIE24_ORDER]) < 18:
        return compute_jie24_times_calc(year)
    monthly_cache: dict[int, list] = {}
    terms: dict[str, datetime] = {}
    for name in JIE24_ORDER:
        if name not in name_to_date:
            approx = approx_guess_local_24(year)[name]
            terms[name] = find_longitude_time_local(year, JIE24_DEGREES[name], approx)
            continue
        ymd = name_to_date[name]
        y = int(ymd[:4]); m = int(ymd[4:6]); d = int(ymd[6:8])
        if m not in monthly_cache:
            try: monthly_cache[m] = kasi_get_monthly_events(y, m, service_key)
            except Exception: monthly_cache[m] = []
        hit = None
        for ev in monthly_cache[m]:
            if ev['title'] == name and ev['locdate'] == ymd and ev['time']:
                hit = ev['time']; break
        if hit:
            terms[name] = _merge_date_time_local(ymd, hit)
        else:
            approx = datetime(y, m, d, 12, 0, tzinfo=LOCAL_TZ)
            terms[name] = find_longitude_time_local(y, JIE24_DEGREES[name], approx)
    return terms

# ============== 사주 (태양시·정각 23시 경계 + 시두법) ==============
def pillar_day_by_2300(dt_solar: datetime) -> date:
    return (dt_solar + timedelta(days=1)).date() if (dt_solar.hour, dt_solar.minute) >= (23,0) else dt_solar.date()
def day_ganji_solar(dt_solar: datetime, k_anchor: int) -> tuple[str,int,int]:
    d = pillar_day_by_2300(dt_solar)
    idx60 = (jdn_0h_utc(d.year, d.month, d.day) + k_anchor) % 60
    cidx, jidx = idx60 % 10, idx60 % 12
    return CHEONGAN[cidx] + JIJI[jidx], cidx, jidx
def hour_branch_idx_2300(dt_solar: datetime) -> int:
    mins = dt_solar.hour*60 + dt_solar.minute
    off = (mins - (23*60)) % 1440
    return off // 120
def sidu_zi_start_gan(day_gan: str) -> str:
    for pair, start in SIDU_START.items():
        if day_gan in pair: return start
    raise ValueError("invalid day gan")
@dataclass
class FourPillars:
    year_pillar: str
    month_pillar: str
    day_pillar: str
    hour_pillar: str
    ipchun_solar: datetime
    y_gidx: int
    m_gidx: int
    m_bidx: int
def four_pillars_from_solar(dt_solar: datetime, k_anchor: int, service_key: str|None) -> FourPillars:
    jie_raw = jie_times_from_kasi_or_calc(dt_solar.year, service_key)
    jie_solar = { name: to_solar_time(t) for name, t in jie_raw.terms.items() }
    ipchun = jie_solar['입춘']
    y = dt_solar.year - 1 if dt_solar < ipchun else dt_solar.year
    y_gidx = (y - 4) % 10; y_jidx = (y - 4) % 12
    year_pillar = CHEONGAN[y_gidx] + JIJI[y_jidx]
    order = [(n, jie_solar[n]) for n in JIE_ORDER] + [('(전년)대설', jie_solar['(전년)대설'])]
    order.sort(key=lambda x: x[1])
    last = '(전년)대설'
    for name, t in order:
        if dt_solar >= t: last = name
        else: break
    m_branch = JIE_TO_MONTH_JI[last]
    m_bidx = MONTH_JI.index(m_branch)
    m_gidx = (month_start_gan_idx(y_gidx) + m_bidx) % 10
    month_pillar = CHEONGAN[m_gidx] + m_branch
    day_pillar, d_cidx, _ = day_ganji_solar(dt_solar, k_anchor)
    h_j_idx = hour_branch_idx_2300(dt_solar)
    zi_start = sidu_zi_start_gan(CHEONGAN[d_cidx])
    h_c_idx = (CHEONGAN.index(zi_start) + h_j_idx) % 10
    hour_pillar = CHEONGAN[h_c_idx] + JIJI[h_j_idx]
    return FourPillars(year_pillar, month_pillar, day_pillar, hour_pillar, ipchun, y_gidx, m_gidx, m_bidx)

# ============== 대운/세운 ==============
def is_yang_stem(gan: str) -> bool: return gan in ['갑','병','무','경','임']
def next_prev_jie(dt_solar: datetime, jie_solar: dict[str, datetime]) -> tuple[datetime, datetime]:
    items = [(n, jie_solar[n]) for n in JIE_ORDER] + [('(전년)대설', jie_solar['(전년)대설'])]
    items.sort(key=lambda x: x[1])
    prev_t = items[0][1]
    for _, t in items:
        if t > dt_solar: return prev_t, t
        prev_t = t
    return prev_t, prev_t
def round_half_up(x: float) -> int: return int(math.floor(x + 0.5))
def dayun_start_age(dt_solar: datetime, jie_solar: dict[str, datetime], forward: bool) -> int:
    prev_t, next_t = next_prev_jie(dt_solar, jie_solar)
    delta_days = (next_t - dt_solar).total_seconds()/86400.0 if forward else (dt_solar - prev_t).total_seconds()/86400.0
    return max(0, round_half_up(delta_days / 3.0))
def build_dayun_list_indices(month_gidx: int, month_bidx: int, forward: bool, start_age: int, count: int = 10):
    dirv = 1 if forward else -1
    out = []
    for i in range(1, count + 1):
        g_i = (month_gidx + dirv * i) % 10
        b_i = (month_bidx + dirv * i) % 12
        out.append({"start_age": start_age + (i - 1) * 10, "g_idx": g_i, "b_idx": b_i})
    return out

def build_seun_calendar_strip(birth_solar: datetime, years: int, day_stem: str, service_key: str|None, now_local: datetime) -> list[dict]:
    ipchun_cache: dict[int, datetime] = {}
    def ipchun_of(y: int) -> datetime:
        if y not in ipchun_cache:
            j24 = jie24_times_from_kasi_or_calc(y, service_key)
            ipchun_cache[y] = to_solar_time(j24['입춘'])
        return ipchun_cache[y]
    start_year = birth_solar.year - 1
    end_year = birth_solar.year + years + 1
    strip: list[dict] = []
    period_end = birth_solar + timedelta(days=int(365.2425 * years))
    for y in range(start_year, end_year + 1):
        s = ipchun_of(y); e = ipchun_of(y + 1)
        if e <= birth_solar or s >= period_end: continue
        y_gidx = (y - 4) % 10; y_jidx = (y - 4) % 12
        gan, ji = CHEONGAN[y_gidx], JIJI[y_jidx]
        a_from = calc_age_on(birth_solar.date(), s)
        a_to   = calc_age_on(birth_solar.date(), e - timedelta(seconds=1))
        six = f"{six_for_stem(day_stem, gan)}/{six_for_branch(day_stem, ji)}"
        strip.append({
            "year": y, "pillar": gan + ji, "start": s, "end": e,
            "age_from": max(0, a_from), "age_to": max(0, a_to),
            "six": six, "is_now": (now_local >= s and now_local < e),
        })
    strip = [x for x in strip if (x["age_to"] >= 0 and x["age_from"] <= years)]
    strip.sort(key=lambda x: (x["age_from"], x["year"]))
    return strip

def build_wolun_strip_for_year(year: int, day_stem: str, service_key: str | None, now_local: datetime):
    j24_this = jie24_times_from_kasi_or_calc(year, service_key)
    j24_next = jie24_times_from_kasi_or_calc(year + 1, service_key)
    ipchun_this = to_solar_time(j24_this['입춘'])
    ipchun_next = to_solar_time(j24_next['입춘'])
    y_gidx = (year - 4) % 10
    start_m_gidx = month_start_gan_idx(y_gidx)
    items = []
    for i in range(12):
        gidx = (start_m_gidx + i) % 10
        bidx = i
        gan, ji = CHEONGAN[gidx], MONTH_JI[bidx]
        term1, term2 = MONTH_TO_2TERMS[ji]
        def _nearest(term_name: str) -> datetime:
            cand = []
            for src in (j24_this, j24_next):
                if term_name in src:
                    cand.append(to_solar_time(src[term_name]))
            cand.sort()
            cand = [t for t in cand if ipchun_this <= t < ipchun_next] or cand
            return cand[0]
        t_start = _nearest(term1)
        t_mid   = _nearest(term2)
        next_bidx = (bidx + 1) % 12
        next_term1 = MONTH_TO_2TERMS[MONTH_JI[next_bidx]][0]
        t_end = _nearest(next_term1)
        six = f"{six_for_stem(day_stem, gan)}/{six_for_branch(day_stem, ji)}"
        items.append({
            "i": i, "pillar": gan + ji, "gan": gan, "ji": ji, "six": six,
            "start": t_start if t_start < t_mid else t_mid, "end": t_end,
            "is_now": (now_local >= (t_start if t_start < t_mid else t_mid) and now_local < t_end),
        })
    return items

def build_ilun_strip(start_dt: datetime, end_dt: datetime, day_stem: str, k_anchor: int, now_local: datetime):
    items = []
    cur = start_dt.replace(hour=12, minute=0, second=0, microsecond=0)
    if cur < start_dt:
        cur = cur + timedelta(days=1)
    today_anchor = pillar_day_by_2300(to_solar_time(now_local))
    while cur < end_dt:
        day_gj, d_cidx, d_jidx = day_ganji_solar(cur, k_anchor)
        d_gan, d_ji = day_gj[0], day_gj[1]
        items.append({
            "date_iso": cur.date().isoformat(),
            "date_label": cur.strftime("%m-%d"),
            "gan": d_gan,
            "ji": d_ji,
            "six": f"{six_for_stem(day_stem, d_gan)}/{six_for_branch(day_stem, d_ji)}",
            "is_today": (pillar_day_by_2300(cur) == today_anchor),
        })
        cur = cur + timedelta(days=1)
    return items

# ============== 음력→양력 변환 ==============
def lunar_to_solar(y: int, m: int, d: int, is_leap: bool) -> date:
    if not HAS_LUNAR:
        raise RuntimeError("korean-lunar-calendar 미설치")
    cal = KoreanLunarCalendar(); cal.setLunarDate(y, m, d, is_leap)
    Y, M, D = cal.solarYear, cal.solarMonth, cal.solarDay
    return date(Y, M, D)


# ╔══════════════════════════════════════════════════════════════╗
# ║  ★★★  아래부터 모바일 최적화 UI  ★★★                       ║
# ║  (위의 계산 로직은 원본 100% 동일)                            ║
# ╚══════════════════════════════════════════════════════════════╝

st.set_page_config(page_title="이박사 향기품 만세력", layout="centered", page_icon="🔮")

# ========== 모바일 최적화 CSS ==========
st.markdown("""<style>
/* ===== 글로벌 리셋 & 모바일 기본 ===== */
:root {
  --primary: #4A90D9;
  --primary-dark: #2C5F9E;
  --accent: #FF6B6B;
  --bg-main: #F5F7FA;
  --bg-card: #FFFFFF;
  --text-main: #2D3436;
  --text-sub: #636E72;
  --border: #DFE6E9;
  --shadow: 0 2px 8px rgba(0,0,0,0.08);
  --radius: 16px;
}
.block-container {
  padding: 12px 8px 90px 8px !important;
  max-width: 480px !important;
  margin: 0 auto !important;
}
/* 사이드바 숨기기 (모바일) */
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* ===== 앱 헤더 ===== */
.app-header {
  background: linear-gradient(135deg, var(--primary) 0%, #6C5CE7 100%);
  color: white;
  padding: 16px 16px 14px;
  border-radius: 0 0 20px 20px;
  margin: -12px -8px 16px -8px;
  text-align: center;
  box-shadow: 0 4px 15px rgba(74,144,217,0.3);
}
.app-header h1 { font-size: 22px; font-weight: 800; margin: 0; letter-spacing: -0.5px; }
.app-header .sub { font-size: 12px; opacity: 0.85; margin-top: 4px; }
</style>""", unsafe_allow_html=True)

st.markdown("""<style>
/* ===== 카드 스타일 ===== */
.m-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 16px;
  margin: 10px 0;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
}
.m-card-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--primary-dark);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ===== 사주 원국 테이블 ===== */
.saju-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 4px;
  table-layout: fixed;
}
.saju-table th {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-sub);
  padding: 6px 0;
  text-align: center;
}
.saju-table .six-row td {
  font-size: 11px;
  color: var(--text-sub);
  text-align: center;
  padding: 3px 0;
}
.saju-table .gan-cell, .saju-table .ji-cell {
  text-align: center;
  padding: 0;
}
.saju-table .gan-cell div, .saju-table .ji-cell div {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 56px;
  border-radius: 12px;
  font-weight: 800;
  font-size: 32px;
  border: 1px solid rgba(0,0,0,0.1);
  margin: 2px auto;
}
.saju-table .ji-six td {
  font-size: 11px;
  color: var(--text-sub);
  text-align: center;
  padding: 3px 0;
}

/* ===== 격국 박스 ===== */
.geok-card {
  background: linear-gradient(135deg, #F8F9FF 0%, #EEF2FF 100%);
  border: 2px solid var(--primary);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin: 12px 0;
}
.geok-card .geok-name {
  font-size: 20px;
  font-weight: 800;
  color: var(--primary-dark);
}
.geok-card .geok-why {
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 6px;
  line-height: 1.5;
}
.geok-card .geok-saryeong {
  font-size: 11px;
  color: #888;
  margin-top: 4px;
  line-height: 1.4;
}
</style>""", unsafe_allow_html=True)

st.markdown("""<style>
/* ===== 가로 스크롤 스트립 ===== */
.strip-outer {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  padding: 4px 0;
}
.strip-inner {
  display: inline-flex;
  flex-wrap: nowrap;
  gap: 4px;
  padding: 0 2px 4px;
}

/* ===== 대운/세운/일운 카드 ===== */
.un-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 52px;
  padding: 6px 4px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg-card);
  flex-shrink: 0;
}
.un-card.now { border: 2.5px solid var(--accent); background: #FFF5F5; }
.un-card .label { font-size: 10px; color: var(--text-sub); margin-bottom: 3px; white-space: nowrap; }
.un-card .chip {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  font-weight: 700;
  font-size: 20px;
  border: 1px solid rgba(0,0,0,0.1);
}
.un-card .six { font-size: 9px; color: var(--text-sub); margin-top: 3px; white-space: nowrap; }
</style>""", unsafe_allow_html=True)

st.markdown("""<style>
/* ===== 절기 캡션 ===== */
.term-caption {
  font-size: 11px;
  color: var(--text-sub);
  padding: 4px 8px;
  background: #F8F9FA;
  border-radius: 8px;
  margin: 6px 0;
  line-height: 1.5;
}

/* ===== 섹션 타이틀 ===== */
.sec-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
  margin: 14px 0 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sec-title .badge {
  font-size: 11px;
  font-weight: 500;
  color: var(--primary);
  background: #EEF2FF;
  padding: 2px 8px;
  border-radius: 10px;
}

/* ===== 하단 네비게이션 바 ===== */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-around;
  padding: 8px 0 env(safe-area-inset-bottom, 12px);
  z-index: 9999;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
}
.bottom-nav a {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-decoration: none;
  color: var(--text-sub);
  font-size: 10px;
  font-weight: 600;
  gap: 2px;
  padding: 4px 12px;
  border-radius: 8px;
  transition: all 0.2s;
}
.bottom-nav a:hover, .bottom-nav a.active {
  color: var(--primary);
  background: #EEF2FF;
}
.bottom-nav .nav-icon { font-size: 20px; }

/* ===== 현재 일진 바 ===== */
.today-bar {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 10px 14px;
  border-radius: 12px;
  margin: 8px 0;
  font-size: 12px;
  line-height: 1.5;
  box-shadow: 0 2px 8px rgba(102,126,234,0.3);
}
.today-bar .big { font-size: 15px; font-weight: 700; }

/* ===== Streamlit 기본 요소 재정의 ===== */
[data-testid="stVerticalBlock"] { gap: 4px !important; }
[data-testid="stHorizontalBlock"] { gap: 4px !important; }
.element-container { margin: 0 !important; padding: 0 !important; }
div[data-testid="stButton"] > button {
  width: 100% !important;
  padding: 14px !important;
  border-radius: 14px !important;
  font-weight: 700 !important;
  font-size: 16px !important;
  background: linear-gradient(135deg, var(--primary) 0%, #6C5CE7 100%) !important;
  color: white !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(74,144,217,0.3) !important;
}
div[data-testid="stButton"] > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(74,144,217,0.4) !important;
}
[data-testid="stRadio"] { margin: 0 !important; padding: 0 4px !important; }
[data-testid="stRadio"] div[role="radiogroup"] {
  display: flex !important;
  flex-wrap: nowrap !important;
  overflow-x: auto !important;
  -webkit-overflow-scrolling: touch !important;
  gap: 6px !important;
  padding: 4px 0 !important;
}
[data-testid="stRadio"] div[role="radiogroup"] > label {
  flex-shrink: 0 !important;
  padding: 4px 10px !important;
  font-size: 12px !important;
  border-radius: 20px !important;
}
[data-testid="stExpander"] { margin: 6px 0 !important; }
[data-testid="stExpander"] [data-testid="stExpanderHeader"] { padding: 10px 12px !important; font-size: 14px !important; }
h1,h2,h3,h4,h5,h6 { margin: 8px 0 4px !important; }
p,.stMarkdown { margin: 0 !important; line-height: 1.3 !important; }

/* 입력 필드 모바일 최적화 */
input[type="text"] { font-size: 16px !important; padding: 12px !important; border-radius: 12px !important; }
[data-testid="stTextInput"] label p { font-size: 13px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ========== 앱 헤더 ==========
st.markdown("""
<div class="app-header">
  <h1>🔮 이박사 향기품 만세력</h1>
  <div class="sub">香氣品 명리 · 태양시 기반 정밀 계산</div>
</div>
""", unsafe_allow_html=True)

# ========== Session State ==========
if "show_result" not in st.session_state: st.session_state["show_result"] = False
if "calc_run_id" not in st.session_state: st.session_state["calc_run_id"] = 0
if "seun_window_idx" not in st.session_state: st.session_state["seun_window_idx"] = 0
if "start_age_for_seun" not in st.session_state: st.session_state["start_age_for_seun"] = 0

# ========== 입력 섹션 ==========
with st.expander("📋 출생 정보 입력", expanded=not st.session_state.get("show_result", False)):
    col1, col2 = st.columns(2)
    with col1:
        cal_type = st.radio("달력", ["양력", "음력"], horizontal=True, key="cal_type_r")
    with col2:
        sex = st.radio("성별", ["남자", "여자"], horizontal=True, key="sex_r")

    col3, col4 = st.columns(2)
    with col3:
        ymd_raw = st.text_input("출생일 (YYYYMMDD)", value="19840202", placeholder="예) 19650504", max_chars=8)
        ymd = re.sub(r"\D", "", ymd_raw)
        if len(ymd) != 8:
            st.error("YYYYMMDD 8자리로 입력하세요."); st.stop()
        try:
            y, m, d = int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])
            date_input = date(y, m, d)
        except ValueError as e:
            st.error(f"날짜 오류: {e}"); st.stop()
    with col4:
        hm_raw = st.text_input("출생시각 (HHMM)", value="0000", placeholder="예) 0900", max_chars=4)
        hm = re.sub(r"\D", "", hm_raw)
        if len(hm) != 4:
            st.error("HHMM 4자리로 입력하세요."); st.stop()
        hh, mm = int(hm[:2]), int(hm[2:4])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            st.error("시각 범위 오류 (00:00~23:59)"); st.stop()
        time_input = time(hh, mm)

    is_leap = False
    if cal_type == "음력":
        if not HAS_LUNAR:
            st.warning("korean-lunar-calendar 패키지가 필요합니다.")
        is_leap = st.checkbox("윤달", value=False, disabled=not HAS_LUNAR)

    # 출생지
    overseas_mode = False
    sel_city_lon = KR_CITY_LON["서울"]
    tz_offset_minutes = 540
    with st.expander("🌏 출생지 선택", expanded=False):
        country = st.selectbox("국가", ["Korea(대한민국)", "해외"], index=0)
        if country == "Korea(대한민국)":
            city = st.selectbox("도시", list(KR_CITY_LON.keys()), index=0)
            sel_city_lon = KR_CITY_LON.get(city, KR_CITY_LON["서울"])
        else:
            overseas_mode = True
            preset_labels = [
                "UTC−12:00","UTC−11:00","UTC−10:00","UTC−09:30","UTC−09:00","UTC−08:00",
                "UTC−07:00","UTC−06:00","UTC−05:00","UTC−04:00","UTC−03:30","UTC−03:00",
                "UTC−02:00","UTC−01:00","UTC±00:00","UTC+01:00","UTC+02:00","UTC+03:00",
                "UTC+03:30","UTC+04:00","UTC+04:30","UTC+05:00","UTC+05:30","UTC+05:45",
                "UTC+06:00","UTC+06:30","UTC+07:00","UTC+08:00","UTC+08:45","UTC+09:00",
                "UTC+09:30","UTC+10:00","UTC+10:30","UTC+11:00","UTC+12:00","UTC+13:00","UTC+14:00"
            ]
            preset_values = [-720,-660,-600,-570,-540,-480,-420,-360,-300,-240,-210,-180,-120,-60,0,60,120,180,210,240,270,300,330,345,360,390,420,480,525,540,570,600,630,660,720,780,840]
            idx_default = preset_labels.index("UTC+09:00")
            sel_idx = st.selectbox("UTC 오프셋", list(range(len(preset_labels))),
                                   format_func=lambda i: preset_labels[i], index=idx_default)
            tz_offset_minutes = preset_values[sel_idx]

    k_anchor = K_ANCHOR_DEFAULT
    fast_mode = st.checkbox("빠른 계산 모드", value=True)

# ========== 현재 일진 바 ==========
now_local = datetime.now(LOCAL_TZ)
now_solar = to_solar_time(now_local)
today_fp = four_pillars_from_solar(now_solar, K_ANCHOR_DEFAULT, None)
dob_for_age = date_input
if cal_type == "음력" and HAS_LUNAR:
    try: dob_for_age = lunar_to_solar(date_input.year, date_input.month, date_input.day, is_leap)
    except Exception: pass
age_now = calc_age_on(dob_for_age, now_local)
st.markdown(f"""
<div class="today-bar">
  <span class="big">📅 {now_local.strftime("%Y.%m.%d %H:%M")}</span><br/>
  오늘 일진: {today_fp.day_pillar} · {today_fp.year_pillar}년 {today_fp.month_pillar}월 {today_fp.hour_pillar}시 · 만 {age_now}세
</div>
""", unsafe_allow_html=True)

# ========== 계산 버튼 ==========
run_calc = st.button("🔮 만세력 계산하기")
if run_calc:
    st.session_state["show_result"] = True
    st.session_state["calc_run_id"] = st.session_state.get("calc_run_id", 0) + 1

# ========== 렌더 헬퍼 ==========
def _un_card(label_text: str, gan: str, ji: str, six: str, is_now: bool = False) -> str:
    gbg, gfg = GAN_BG.get(gan, '#fff'), gan_fg(gan)
    bbg, bfg = BR_BG.get(ji, '#fff'), br_fg(ji)
    cls = "un-card now" if is_now else "un-card"
    return f"""
    <div class="{cls}">
      <div class="label">{label_text}</div>
      <div class="chip" style="background:{gbg};color:{gfg};">{gan}</div>
      <div style="height:3px"></div>
      <div class="chip" style="background:{bbg};color:{bfg};">{ji}</div>
      <div class="six">{six}</div>
    </div>
    """.strip()

def render_strip(cards_html: str):
    st.markdown(f'<div class="strip-outer"><div class="strip-inner">{cards_html}</div></div>', unsafe_allow_html=True)

# ========== 결과 표시 ==========
if st.session_state.get("show_result", False):
    try:
        service_key = None if fast_mode else get_kasi_key()

        base_date = date_input
        if cal_type == "음력":
            if not HAS_LUNAR:
                st.error("음력 변환 모듈 미설치"); st.stop()
            base_date = lunar_to_solar(date_input.year, date_input.month, date_input.day, is_leap)

        if overseas_mode:
            tz_overseas = timezone(timedelta(minutes=int(tz_offset_minutes)))
            dt_local = datetime.combine(base_date, time_input).replace(tzinfo=tz_overseas)
            dt_solar = to_solar_time(dt_local)
        else:
            dt_local = datetime.combine(base_date, time_input).replace(tzinfo=LOCAL_TZ)
            dt_solar = to_solar_time(dt_local)
        dt_solar = apply_longitude_correction(dt_solar, sel_city_lon)

        fp = four_pillars_from_solar(dt_solar, k_anchor, service_key)

        # 절기 표시 로직 (원본 그대로)
        j24_prev = jie24_times_from_kasi_or_calc(dt_solar.year - 1, service_key)
        j24_this = jie24_times_from_kasi_or_calc(dt_solar.year, service_key)
        j24_next = jie24_times_from_kasi_or_calc(dt_solar.year + 1, service_key)
        def _to_solar_map(d_dict):
            return {name: to_solar_time(t) for name, t in d_dict.items()}
        j24_prev_s = _to_solar_map(j24_prev); j24_this_s = _to_solar_map(j24_this); j24_next_s = _to_solar_map(j24_next)
        _all_terms = list(j24_prev_s.items()) + list(j24_this_s.items()) + list(j24_next_s.items())
        _all_terms.sort(key=lambda x: x[1])
        on_day_hit = None
        for name, tt in _all_terms:
            if tt.date() == dt_solar.date():
                on_day_hit = (name, tt); break
        if on_day_hit:
            cur_idx = next(i for i,(n,_) in enumerate(_all_terms) if n == on_day_hit[0] and _all_terms[i][1] == on_day_hit[1])
            disp_name1, disp_t1 = _all_terms[cur_idx]
            disp_name2, disp_t2 = _all_terms[cur_idx + 1]
        else:
            prev_pair = _all_terms[0]
            disp_name1, disp_t1 = _all_terms[0][0], _all_terms[0][1]
            disp_name2, disp_t2 = _all_terms[1][0], _all_terms[1][1]
            for name, tt in _all_terms:
                if tt <= dt_solar: prev_pair = (name, tt)
                else:
                    disp_name1, disp_t1 = prev_pair; disp_name2, disp_t2 = name, tt; break

        yy_g, yy_j = split_ganji(fp.year_pillar)
        mm_g, mm_j = split_ganji(fp.month_pillar)
        dd_g, dd_j = split_ganji(fp.day_pillar)
        hh_g, hh_j = split_ganji(fp.hour_pillar)
        pair_for_month = MONTH_TO_2TERMS[MONTH_JI[fp.m_bidx]]
        def _nearest_term_time(term_name: str) -> datetime:
            candidates = [(abs((t - dt_solar).total_seconds()), t) for n, t in _all_terms if n == term_name]
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        t1_month = _nearest_term_time(pair_for_month[0])
        t2_month = _nearest_term_time(pair_for_month[1])
        mid_dt_solar = t2_month
        day_from_jieqi = int((dt_solar - t1_month).total_seconds() // 86400)
        if day_from_jieqi < 0: day_from_jieqi = 0
        if day_from_jieqi > 29: day_from_jieqi = 29
        saryeong_stem, saryeong_label = _pick_saryeong_for_display(mm_j, dt_solar, t1_month, t2_month)
        first_term_name = pair_for_month[0]
        diff_days = (dt_solar.date() - t1_month.date()).days

        # ===== AI 상담 링크 =====
        gpt_link = "https://chatgpt.com/g/g-68d90b2d8f448191b87fb7511fa8f80a-rua-myeongrisajusangdamsa"

        if cal_type == "음력":
            st.info(f"음력 {date_input} (윤달:{'예' if is_leap else '아니오'}) → 양력 {base_date}")

        # ===== 사주 원국 카드 =====
        solar_label = f"{base_date:%Y.%m.%d} {time_input:%H:%M}"
        suffix = " (양력환산)" if cal_type == "음력" else ""

        # 육신 계산
        six_yg = six_for_stem(dd_g, yy_g)
        six_yj = six_for_branch(dd_g, yy_j)
        six_mg = six_for_stem(dd_g, mm_g)
        six_mj = six_for_branch(dd_g, mm_j)
        six_dj = six_for_branch(dd_g, dd_j)
        six_hg = six_for_stem(dd_g, hh_g)
        six_hj = six_for_branch(dd_g, hh_j)

        def _cell(text, bg, fg):
            return f'<div style="background:{bg};color:{fg};">{text}</div>'

        st.markdown(f"""
        <div class="m-card">
          <div class="m-card-title">🏛️ 사주 원국 — {solar_label}{suffix}</div>
          <table class="saju-table">
            <tr><th>시주</th><th>일주</th><th>월주</th><th>년주</th></tr>
            <tr class="six-row">
              <td>{six_hg}</td><td>일간</td><td>{six_mg}</td><td>{six_yg}</td>
            </tr>
            <tr>
              <td class="gan-cell">{_cell(hh_g, GAN_BG[hh_g], gan_fg(hh_g))}</td>
              <td class="gan-cell">{_cell(dd_g, GAN_BG[dd_g], gan_fg(dd_g))}</td>
              <td class="gan-cell">{_cell(mm_g, GAN_BG[mm_g], gan_fg(mm_g))}</td>
              <td class="gan-cell">{_cell(yy_g, GAN_BG[yy_g], gan_fg(yy_g))}</td>
            </tr>
            <tr>
              <td class="ji-cell">{_cell(hh_j, BR_BG[hh_j], br_fg(hh_j))}</td>
              <td class="ji-cell">{_cell(dd_j, BR_BG[dd_j], br_fg(dd_j))}</td>
              <td class="ji-cell">{_cell(mm_j, BR_BG[mm_j], br_fg(mm_j))}</td>
              <td class="ji-cell">{_cell(yy_j, BR_BG[yy_j], br_fg(yy_j))}</td>
            </tr>
            <tr class="ji-six">
              <td>{six_hj}</td><td>{six_dj}</td><td>{six_mj}</td><td>{six_yj}</td>
            </tr>
          </table>
        </div>
        """, unsafe_allow_html=True)

        # 절기 캡션
        st.markdown(f"""
        <div class="term-caption">
          🌿 {disp_name1} {disp_t1:%m/%d %H:%M} · {disp_name2} {disp_t2:%m/%d %H:%M} (태양시)
        </div>
        """, unsafe_allow_html=True)

        # ===== 격국 =====
        stems_visible = [yy_g, mm_g, dd_g, hh_g]
        branches_visible = [yy_j, mm_j, dd_j, hh_j]
        geok, why = decide_geok(Inputs(
            day_stem=dd_g, month_branch=mm_j, month_stem=mm_g,
            stems_visible=stems_visible, branches_visible=branches_visible,
            solar_dt=dt_solar, first_term_dt=t1_month, mid_term_dt=mid_dt_solar,
            day_from_jieqi=day_from_jieqi
        ))
        phase = saryeong_label.replace("사령", "")
        is_first_half = is_first_half_by_terms(dt_solar, t1_month, t2_month)
        next_idx = JIE24_ORDER.index(pair_for_month[1])
        next_term_name = JIE24_ORDER[(next_idx + 1) % len(JIE24_ORDER)]
        t3_month = _nearest_term_time(next_term_name)
        if is_first_half:
            range_s_name, range_s_time = pair_for_month[0], t1_month
            range_e_name, range_e_time = pair_for_month[1], t2_month
        else:
            range_s_name, range_s_time = pair_for_month[1], t2_month
            range_e_name, range_e_time = next_term_name, t3_month
        if diff_days >= 0:
            left_text = f"{mm_j}월 {saryeong_stem} 司令 ({phase}) · 절입 {first_term_name} +{day_from_jieqi}일"
        else:
            left_text = f"{mm_j}월 {saryeong_stem} 司令 ({phase}) · {first_term_name} {abs(diff_days)}일 전"
        range_text = f"{range_s_name} {range_s_time:%m/%d %H:%M} ~ {range_e_name} {range_e_time:%m/%d %H:%M}"

        st.markdown(f"""
        <div class="geok-card">
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:13px;color:#888;">격(格)</span>
            <span class="geok-name">{geok}</span>
          </div>
          <div class="geok-why">{why}</div>
          <div class="geok-saryeong">{left_text}<br/>{range_text}</div>
        </div>
        """, unsafe_allow_html=True)

        # ===== 대운 =====
        year_gan = fp.year_pillar[0]
        forward = (is_yang_stem(year_gan) and sex == "남자") or (not is_yang_stem(year_gan) and sex == "여자")
        jie12_solar = { name: to_solar_time(t) for name, t in jie_times_from_kasi_or_calc(dt_solar.year, service_key).terms.items() }
        start_age = dayun_start_age(dt_solar, jie12_solar, forward)
        st.session_state["start_age_for_seun"] = start_age
        dayun_list = build_dayun_list_indices(fp.m_gidx, fp.m_bidx, forward, start_age, count=10)

        st.markdown(f"""
        <div class="sec-title">
          📊 대운
          <span class="badge">{"순행" if forward else "역행"} · 시작 {start_age}세</span>
        </div>
        """, unsafe_allow_html=True)

        dayun_cards = ""
        for item in dayun_list:
            age0 = item["start_age"]
            gan = CHEONGAN[item["g_idx"]]; ji = MONTH_JI[item["b_idx"]]
            six = f"{six_for_stem(dd_g, gan)}/{six_for_branch(dd_g, ji)}"
            dayun_cards += _un_card(f"{age0}~{age0+9}", gan, ji, six)
        render_strip(dayun_cards)

        # ===== 세운 =====
        st.markdown('<div class="sec-title">📅 세운(歲運)</div>', unsafe_allow_html=True)

        seun_all = build_seun_calendar_strip(birth_solar=dt_solar, years=100, day_stem=dd_g, service_key=service_key, now_local=now_local)
        birth_year = dt_solar.year
        current_age_simple = age_by_ipchun(dt_solar, now_local, service_key)
        start_age_seun = int(st.session_state.get("start_age_for_seun", 0))
        first_end = max(9, start_age_seun + 9)
        first_end = min(99, first_end)
        windows = [(0, first_end)]
        s = first_end + 1
        while s <= 99:
            e = min(99, s + 9)
            windows.append((s, e))
            s = e + 1
        labels = [f"{a}–{b}" for (a, b) in windows]
        def find_idx(age):
            for i,(a,b) in enumerate(windows):
                if a <= age <= b: return i
            return 0
        default_idx = find_idx(current_age_simple)
        rid = st.session_state.get("calc_run_id", 0)
        key = "seun_age_radio"
        if st.session_state.get(f"{key}_init_for") != rid:
            st.session_state[key] = default_idx
            st.session_state[f"{key}_init_for"] = rid
        st.radio("구간", options=list(range(len(windows))), format_func=lambda i: labels[i],
                 horizontal=True, label_visibility="collapsed", key=key)
        selected_idx = int(st.session_state[key])
        a0, a1 = windows[selected_idx]
        def year_to_age(yr): return yr - birth_year
        seun_items = [it for it in seun_all if a0 <= year_to_age(it["year"]) <= a1]
        seun_items.sort(key=lambda x: x["year"])

        if seun_items:
            seun_cards = ""
            for it in seun_items:
                gan, ji = it["pillar"][0], it["pillar"][1]
                seun_cards += _un_card(str(it["year"]), gan, ji, it["six"], it["is_now"])
            render_strip(seun_cards)

            # ===== 월운 =====
            years = [it["year"] for it in seun_items]
            default_yr_idx = next((i for i, it in enumerate(seun_items) if it.get("is_now")), len(seun_items) - 1)
            yr_key = "seun_year_radio"
            st.session_state.setdefault(yr_key, years[default_yr_idx])
            st.markdown('<div class="sec-title">🗓️ 월운</div>', unsafe_allow_html=True)
            sel_year = st.radio("연도", options=years, horizontal=True, label_visibility="collapsed", key=yr_key)

            wolun_items = build_wolun_strip_for_year(sel_year, dd_g, service_key, now_local)
            wolun_cards = ""
            for it in wolun_items:
                gan, ji = it["gan"], it["ji"]
                wolun_cards += _un_card(f"{ji}월", gan, ji, it["six"], it["is_now"])
            render_strip(wolun_cards)

            # 월운 선택 → 일운
            month_labels = [it["ji"] for it in wolun_items]
            default_m_idx = next((i for i, it in enumerate(wolun_items) if it["is_now"]), 0)
            m_key = f"wolun_month_radio_{sel_year}"
            if st.session_state.get(f"{m_key}_init") is None:
                st.session_state[m_key] = default_m_idx
                st.session_state[f"{m_key}_init"] = True
            st.radio("월 선택", options=list(range(12)), format_func=lambda i: month_labels[i],
                     horizontal=True, label_visibility="collapsed", key=m_key)
            sel_month_idx = int(st.session_state[m_key])

            # ===== 일운 =====
            try:
                mit = wolun_items[sel_month_idx]
                m_start = mit["start"]; m_end = mit["end"]
                st.markdown('<div class="sec-title">📆 일운</div>', unsafe_allow_html=True)
                ilun_list = build_ilun_strip(m_start, m_end, dd_g, k_anchor, now_local)
                ilun_cards = ""
                for it in ilun_list:
                    g, j = it["gan"], it["ji"]
                    ilun_cards += _un_card(it["date_label"], g, j, it["six"], it["is_today"])
                render_strip(ilun_cards)
            except Exception:
                st.info("일운 표시 중 문제 발생")
        else:
            st.info("해당 구간에 표시할 세운이 없습니다.")

        # ===== 하단 네비게이션 바 =====
        st.markdown(f"""
        <div class="bottom-nav">
          <a href="#" onclick="window.scrollTo(0,0);return false;">
            <span class="nav-icon">🏠</span>
            처음으로
          </a>
          <a href="{gpt_link}" target="_blank">
            <span class="nav-icon">🤖</span>
            AI상담
          </a>
          <a href="#" onclick="window.scrollTo(0,0);return false;">
            <span class="nav-icon">✏️</span>
            수정하기
          </a>
          <a href="https://krcoach.kr" target="_blank">
            <span class="nav-icon">📞</span>
            문의
          </a>
        </div>
        """, unsafe_allow_html=True)

        # 푸터
        yr = datetime.now(LOCAL_TZ).year
        st.markdown(f"""
        <div style="text-align:center;padding:20px 0 60px;color:#999;font-size:11px;">
          <div style="font-weight:700;color:#666;margin-bottom:4px;">이박사 향기품 코칭</div>
          <a href="https://www.youtube.com/@psycologysalon" target="_blank" style="color:#999;text-decoration:none;">유튜브</a> ·
          <a href="https://brunch.co.kr/@healerlee" target="_blank" style="color:#999;text-decoration:none;">브런치</a> ·
          <a href="mailto:coachruah@gmail.com" style="color:#999;text-decoration:none;">이메일</a>
          <div style="margin-top:4px;">© {yr} coachruah</div>
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"오류: {e}")
