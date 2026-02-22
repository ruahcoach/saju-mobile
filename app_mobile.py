# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import streamlit as st
import math, calendar, os

try:
    from korean_lunar_calendar import KoreanLunarCalendar
    HAS_LUNAR = True
except Exception:
    HAS_LUNAR = False

LOCAL_TZ = ZoneInfo('Asia/Seoul')
CHEONGAN = ['갑','을','병','정','무','기','경','신','임','계']
JIJI     = ['자','축','인','묘','진','사','오','미','신','유','술','해']
HANJA_GAN = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
HANJA_JI  = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
OHAENG_GAN = ['목','목','화','화','토','토','금','금','수','수']
OHAENG_JI  = ['수','토','목','목','토','화','화','토','금','금','토','수']
COLOR_MAP = {'목':'#4CAF50','화':'#E53935','토':'#FFC107','금':'#EEEEEE','수':'#1A1A2E'}
TEXT_COLOR = {'목':'#fff','화':'#fff','토':'#222','금':'#222','수':'#fff'}
SIPSIN_TABLE = [
    ['비견','겁재','식신','상관','편재','정재','편관','정관','편인','정인'],
    ['겁재','비견','상관','식신','정재','편재','정관','편관','정인','편인'],
    ['편인','정인','비견','겁재','식신','상관','편재','정재','편관','정관'],
    ['정인','편인','겁재','비견','상관','식신','정재','편재','정관','편관'],
    ['편관','정관','편인','정인','비견','겁재','식신','상관','편재','정재'],
    ['정관','편관','정인','편인','겁재','비견','상관','식신','정재','편재'],
    ['편재','정재','편관','정관','편인','정인','비견','겁재','식신','상관'],
    ['정재','편재','정관','편관','정인','편인','겁재','비견','상관','식신'],
    ['식신','상관','편재','정재','편관','정관','편인','정인','비견','겁재'],
    ['상관','식신','정재','편재','정관','편관','정인','편인','겁재','비견'],
]
JEOLGI_DAYS = {1:6,2:4,3:6,4:5,5:6,6:6,7:7,8:8,9:8,10:8,11:7,12:7}
JIJANGGAN_MAIN = ['계','기','갑','을','무','병','정','기','경','신','무','임']
def get_gan_idx(g): return CHEONGAN.index(g) if g in CHEONGAN else 0
def get_ji_idx(j):  return JIJI.index(j) if j in JIJI else 0
def ohaeng_gan(g):  return OHAENG_GAN[get_gan_idx(g)]
def ohaeng_ji(j):   return OHAENG_JI[get_ji_idx(j)]
def color_gan(g):   return COLOR_MAP[ohaeng_gan(g)]
def color_ji(j):    return COLOR_MAP[ohaeng_ji(j)]
def textc_gan(g):   return TEXT_COLOR[ohaeng_gan(g)]
def textc_ji(j):    return TEXT_COLOR[ohaeng_ji(j)]

def sipsin(ilgan, other_gan):
    i = get_gan_idx(ilgan); j = get_gan_idx(other_gan)
    return SIPSIN_TABLE[i][j]

def sipsin_ji(ilgan, ji):
    return sipsin(ilgan, JIJANGGAN_MAIN[get_ji_idx(ji)])

def solar_to_saju(year, month, day, hour, minute):
    y_off = (year - 4) % 60
    y_gan = CHEONGAN[y_off % 10]; y_ji = JIJI[y_off % 12]
    jd = JEOLGI_DAYS.get(month, 6)
    m_num = month if day >= jd else month - 1
    if m_num <= 0: m_num += 12
    base_y = year if (day >= jd or month > 1) else year - 1
    m_off = (base_y - 4) * 12 + (m_num - 1)
    m_gan = CHEONGAN[m_off % 10]; m_ji = JIJI[(m_num + 1) % 12]
    delta = (date(year, month, day) - date(1900, 1, 1)).days
    d_gan = CHEONGAN[delta % 10]; d_ji = JIJI[delta % 12]
    si_idx = ((hour + 1) // 2) % 12
    si_base = (get_gan_idx(d_gan) % 5) * 2
    si_gan = CHEONGAN[(si_base + si_idx) % 10]; si_ji = JIJI[si_idx]
    return (y_gan, y_ji), (m_gan, m_ji), (d_gan, d_ji), (si_gan, si_ji)

def calc_daeun(year, month, day, gender):
    y_off = (year - 4) % 60
    y_gan_idx = y_off % 10
    go_fwd = (y_gan_idx % 2 == 0) == (gender == '남')
    jd = JEOLGI_DAYS.get(month, 6)
    m_num = month if day >= jd else month - 1
    if m_num <= 0: m_num += 12
    base_y = year if (day >= jd or month > 1) else year - 1
    m_off = (base_y - 4) * 12 + (m_num - 1)
    mg = m_off % 10; mj = (m_num + 1) % 12
    result = []
    for i in range(1, 9):
        g = CHEONGAN[(mg + i) % 10 if go_fwd else (mg - i) % 10]
        j = JIJI[(mj + i) % 12 if go_fwd else (mj - i) % 12]
        result.append((8 + (i-1)*10, g, j))
    return result

def calc_seun(start=2015, count=20):
    result = []
    for i in range(count):
        y = start + i
        off = (y - 4) % 60
        result.append((y, CHEONGAN[off%10], JIJI[off%12]))
    return result

def calc_wolun(year):
    y_off = (year - 4) % 60
    base_mg = [2,4,6,8,0][y_off % 10 % 5]
    months = []
    for m in range(1, 13):
        mji = (m + 1) % 12
        mgan = (base_mg + m - 1) % 10
        months.append((m, CHEONGAN[mgan], JIJI[mji]))
    return months

def calc_ilun(year, month):
    _, days = calendar.monthrange(year, month)
    base = date(1900, 1, 1)
    result = []
    for d in range(1, days+1):
        delta = (date(year, month, d) - base).days
        result.append((d, CHEONGAN[delta%10], JIJI[delta%12]))
    return result
MOBILE_CSS = """
<style>
:root{--bg:#2C3650;--bg2:#1e2840;--card:#3a4565;--acc:#a0945e;--text:#e8dfc8;--sub:#b0a888;--r:10px;--bdr:#4a5580;}
*{box-sizing:border-box;}
body,.stApp{background:var(--bg)!important;color:var(--text)!important;font-family:'Noto Serif KR','Malgun Gothic',serif;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding:0.5rem!important;max-width:430px!important;margin:0 auto!important;}
.stTextInput input,.stNumberInput input{background:#3a4565!important;color:var(--text)!important;border:1px solid var(--bdr)!important;border-radius:8px!important;}
.stRadio label{color:var(--text)!important;}
.stButton>button{background:linear-gradient(135deg,#6b7fa3,#3a4565)!important;color:var(--text)!important;border:1px solid var(--acc)!important;border-radius:8px!important;width:100%!important;font-size:18px!important;font-weight:bold!important;padding:12px!important;}
.page-hdr{background:linear-gradient(135deg,#3d4f7a,#2C3650);border-bottom:2px solid var(--acc);padding:10px;text-align:center;font-size:18px;font-weight:bold;color:var(--acc);letter-spacing:4px;margin-bottom:12px;}
.saju-wrap{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);padding:10px 4px;margin-bottom:10px;}
.saju-table{width:100%;border-collapse:separate;border-spacing:3px;table-layout:fixed;}
.saju-table th{font-size:11px;color:var(--sub);text-align:center;padding:4px 0;}
.saju-table .lb td{font-size:10px;color:var(--sub);text-align:center;padding:2px 0;}
.gcell,.jcell{text-align:center;padding:0;}
.gcell div,.jcell div{display:flex;align-items:center;justify-content:center;width:100%;height:52px;border-radius:8px;font-weight:900;font-size:28px;border:1px solid rgba(0,0,0,.15);margin:2px auto;}
.strip-outer{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:thin;padding:2px 0;}
.strip-inner{display:inline-flex;flex-wrap:nowrap;gap:4px;padding:2px 4px;}
.un-card{display:flex;flex-direction:column;align-items:center;min-width:52px;padding:4px 2px 6px;border:1px solid var(--bdr);border-radius:10px;background:var(--card);cursor:pointer;transition:border-color .2s;}
.un-card.active{border:2px solid var(--acc)!important;background:#4a5580;}
.un-card .lbl{font-size:10px;color:var(--sub);margin-bottom:2px;}
.un-card .gbox,.un-card .jbox{width:44px;height:44px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;border:1px solid rgba(0,0,0,.1);margin-bottom:2px;}
.un-card .ss{font-size:9px;color:var(--sub);text-align:center;}
.sec-title{font-size:13px;color:var(--acc);font-weight:bold;padding:4px 6px;border-left:3px solid var(--acc);margin:10px 0 6px;}
.today-banner{background:linear-gradient(135deg,#3d4f7a,#2C3650);border:1px solid var(--acc);border-radius:8px;padding:6px 12px;margin-bottom:8px;font-size:12px;color:var(--sub);text-align:center;}
.sel-info{background:var(--card);border:1px solid var(--acc);border-radius:8px;padding:6px 12px;margin-bottom:8px;font-size:12px;color:var(--text);text-align:center;}
.cal-wrap{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden;margin-bottom:10px;}
.cal-header{background:#4a3c28;text-align:center;padding:8px;font-size:14px;color:var(--acc);font-weight:bold;}
.cal-table{width:100%;border-collapse:collapse;}
.cal-table th{background:#3a3020;color:var(--sub);font-size:11px;text-align:center;padding:4px 2px;border:1px solid var(--bdr);}
.cal-table td{text-align:center;padding:3px 1px;border:1px solid var(--bdr);font-size:11px;color:var(--text);vertical-align:top;min-width:38px;height:50px;}
.cal-table td.empty{background:#262e45;}
.cal-table td .dn{font-size:13px;font-weight:bold;margin-bottom:1px;}
.cal-table td.today-cell{background:#4a3c28;border:1px solid var(--acc);}
.cal-table td.sun .dn{color:#E53935;}
.cal-table td.sat .dn{color:#5b8fd4;}
label{color:var(--text)!important;font-size:13px!important;}
div[data-testid='stHorizontalBlock']{gap:4px!important;}
div[data-testid='column']{padding:0 2px!important;}
</style>
"""
def gan_card(g, size=52, fsize=28):
    bg = COLOR_MAP[ohaeng_gan(g)]
    tc = TEXT_COLOR[ohaeng_gan(g)]
    hj = HANJA_GAN[get_gan_idx(g)]
    return f'<div style="width:{size}px;height:{size}px;border-radius:8px;background:{bg};color:{tc};display:flex;align-items:center;justify-content:center;font-size:{fsize}px;font-weight:900;border:1px solid rgba(0,0,0,.15);">{hj}</div>'

def ji_card(j, size=52, fsize=28):
    bg = COLOR_MAP[ohaeng_ji(j)]
    tc = TEXT_COLOR[ohaeng_ji(j)]
    hj = HANJA_JI[get_ji_idx(j)]
    return f'<div style="width:{size}px;height:{size}px;border-radius:8px;background:{bg};color:{tc};display:flex;align-items:center;justify-content:center;font-size:{fsize}px;font-weight:900;border:1px solid rgba(0,0,0,.15);">{hj}</div>'

def render_saju_table(saju, ilgan):
    """사주 원국 HTML 테이블 - 시/일/월/년 오른쪽에서 왼쪽 순서"""
    (yg,yj),(mg,mj),(dg,dj),(sg,sj) = saju
    cols = [(sg,sj,'시주'),(dg,dj,'일주'),(mg,mj,'월주'),(yg,yj,'년주')]
    # 십신 계산
    ss_g = [sipsin(ilgan, sg), '일간', sipsin(ilgan, mg), sipsin(ilgan, yg)]
    ss_j = [sipsin_ji(ilgan, sj), sipsin_ji(ilgan, dj), sipsin_ji(ilgan, mj), sipsin_ji(ilgan, yj)]
    html = '<div class="saju-wrap"><table class="saju-table"><thead><tr>'
    for (g,j,lbl) in cols:
        html += f'<th>{lbl}</th>'
    html += '</tr><tr class="lb">'
    for i,(g,j,_) in enumerate(cols):
        html += f'<td>{ss_g[i]}</td>'
    html += '</tr></thead><tbody><tr>'
    for g,j,_ in cols:
        html += f'<td class="gcell">{gan_card(g)}</td>'
    html += '</tr><tr>'
    for g,j,_ in cols:
        html += f'<td class="jcell">{ji_card(j)}</td>'
    html += '</tr><tr class="lb">'
    for i,(_,j,__) in enumerate(cols):
        html += f'<td>{ss_j[i]}</td>'
    html += '</tr></tbody></table></div>'
    return html

def render_strip_cards(items, active_idx, key_prefix, label_fn, show_sipsin=False, ilgan=''):
    """대운/세운/월운 가로 스트립 HTML"""
    html = '<div class="strip-outer"><div class="strip-inner">'
    for i, item in enumerate(items):
        if len(item) == 3:
            lbl, g, j = item
        else:
            lbl, g, j = item[0], item[1], item[2]
        active_cls = ' active' if i == active_idx else ''
        ss = sipsin(ilgan, g) + '/' + sipsin_ji(ilgan, j) if show_sipsin and ilgan else ''
        bg_g = COLOR_MAP[ohaeng_gan(g)]
        tc_g = TEXT_COLOR[ohaeng_gan(g)]
        bg_j = COLOR_MAP[ohaeng_ji(j)]
        tc_j = TEXT_COLOR[ohaeng_ji(j)]
        hj_g = HANJA_GAN[get_gan_idx(g)]
        hj_j = HANJA_JI[get_ji_idx(j)]
        html += f'''<div class="un-card{active_cls}" onclick="window.parent.postMessage({{type:'streamlit:setComponentValue',key:'{key_prefix}',value:{i}}}, '*')">
  <div class="lbl">{label_fn(lbl)}</div>
  <div class="gbox" style="background:{bg_g};color:{tc_g}">{hj_g}</div>
  <div class="jbox" style="background:{bg_j};color:{tc_j}">{hj_j}</div>
  <div class="ss">{ss}</div>
</div>'''
    html += '</div></div>'
    return html
# ============================================================
# 메인 앱
# ============================================================
def main():
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
    st.markdown('<div class="page-hdr">만 세 력</div>', unsafe_allow_html=True)
    if 'page' not in st.session_state: st.session_state.page = 'input'
    if 'saju_data' not in st.session_state: st.session_state.saju_data = None
    if 'sel_daeun' not in st.session_state: st.session_state.sel_daeun = None
    if 'sel_seun' not in st.session_state: st.session_state.sel_seun = None
    if 'sel_wolun' not in st.session_state: st.session_state.sel_wolun = None

    if st.session_state.page == 'input':
        page_input()
    elif st.session_state.page == 'saju':
        page_saju()
    elif st.session_state.page == 'wolun':
        page_wolun()
    elif st.session_state.page == 'ilun':
        page_ilun()


def page_input():
    now = datetime.now(LOCAL_TZ)
    st.markdown('<div class="sec-title">📅 출생 정보 입력</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        gender = st.radio('성별', ['남', '여'], horizontal=True)
    with c2:
        cal_type = st.radio('달력', ['양력', '음력'], horizontal=True)
    birth_str = st.text_input('생년월일 (YYYYMMDD)', value='19840202', max_chars=8)
    birth_time = st.text_input('출생시각 (HHMM, 모르면 0000)', value='0000', max_chars=4)
    if st.button('🔮 사주 보기'):
        try:
            y = int(birth_str[:4]); m = int(birth_str[4:6]); d = int(birth_str[6:8])
            hh = int(birth_time[:2]) if len(birth_time) >= 2 else 0
            mm = int(birth_time[2:4]) if len(birth_time) == 4 else 0
            saju = solar_to_saju(y, m, d, hh, mm)
            daeun = calc_daeun(y, m, d, gender)
            seun_start = max(y, now.year - 5)
            seun = calc_seun(seun_start, 20)
            st.session_state.saju_data = {
                'birth': (y, m, d, hh, mm),
                'gender': gender,
                'saju': saju,
                'daeun': daeun,
                'seun': seun,
                'seun_year': seun_start,
            }
            # 현재 나이에 해당 대운 자동 선택
            age = now.year - y
            sel_du = 0
            for idx, (da, dg, dj) in enumerate(daeun):
                if da <= age: sel_du = idx
            st.session_state.sel_daeun = sel_du
            # 현재 년도 세운 자동 선택
            sel_su = 0
            for idx, (sy, sg, sj) in enumerate(seun):
                if sy == now.year: sel_su = idx; break
            st.session_state.sel_seun = sel_su
            st.session_state.sel_wolun = now.month - 1
            st.session_state.page = 'saju'
            st.rerun()
        except Exception as e:
            st.error(f'입력 오류: {e}')
def page_saju():
    data = st.session_state.saju_data
    if not data: st.session_state.page='input'; st.rerun(); return
    now = datetime.now(LOCAL_TZ)
    y,m,d,hh,mm = data['birth']
    saju = data['saju']
    ilgan = saju[2][0]  # 일간
    daeun = data['daeun']
    seun  = data['seun']
    sel_du = st.session_state.sel_daeun or 0
    sel_su = st.session_state.sel_seun or 0

    # 뒤로가기
    if st.button('← 입력으로'):
        st.session_state.page = 'input'; st.rerun()

    # 오늘 일진
    today_delta = (now.date() - date(1900,1,1)).days
    tg = CHEONGAN[today_delta%10]; tj = JIJI[today_delta%12]
    thj_g = HANJA_GAN[get_gan_idx(tg)]; thj_j = HANJA_JI[get_ji_idx(tj)]
    off = (now.year-4)%60
    yg = CHEONGAN[off%10]; yj = JIJI[off%12]
    st.markdown(f'<div class="today-banner">오늘 {now.strftime("%Y.%m.%d")} · {HANJA_GAN[get_gan_idx(yg)]}{HANJA_JI[get_ji_idx(yj)]}년 {thj_g}{thj_j}일</div>', unsafe_allow_html=True)

    # 사주 원국
    st.markdown('<div class="sec-title">🏛 사주 원국</div>', unsafe_allow_html=True)
    st.markdown(render_saju_table(saju, ilgan), unsafe_allow_html=True)

    # 대운 - 오른쪽에서 왼쪽 (역순 표시 후 클릭)
    st.markdown('<div class="sec-title">🎴 대운</div>', unsafe_allow_html=True)
    daeun_rev = list(reversed(daeun))
    rev_sel_du = len(daeun) - 1 - sel_du
    cols_du = st.columns(len(daeun))
    new_sel_du = sel_du
    for ci, (col, (age, g, j)) in enumerate(zip(cols_du, daeun_rev)):
        real_idx = len(daeun) - 1 - ci
        with col:
            active = (real_idx == sel_du)
            bg_g = COLOR_MAP[ohaeng_gan(g)]; tc_g = TEXT_COLOR[ohaeng_gan(g)]
            bg_j = COLOR_MAP[ohaeng_ji(j)]; tc_j = TEXT_COLOR[ohaeng_ji(j)]
            hj_g = HANJA_GAN[get_gan_idx(g)]; hj_j = HANJA_JI[get_ji_idx(j)]
            border = '2px solid #a0945e' if active else '1px solid #4a5580'
            bg_card = '#4a5580' if active else '#3a4565'
            st.markdown(f'''<div style="text-align:center;font-size:10px;color:#b0a888;margin-bottom:2px">{age}세</div>
<div style="display:flex;flex-direction:column;align-items:center;border:{border};border-radius:10px;background:{bg_card};padding:3px 2px;cursor:pointer;">
<div style="width:38px;height:38px;border-radius:6px;background:{bg_g};color:{tc_g};display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900;margin-bottom:2px">{hj_g}</div>
<div style="width:38px;height:38px;border-radius:6px;background:{bg_j};color:{tc_j};display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900;margin-bottom:2px">{hj_j}</div>
<div style="font-size:9px;color:#b0a888">{sipsin(ilgan,g)}/{sipsin_ji(ilgan,j)}</div>
</div>''', unsafe_allow_html=True)
            if st.button(f'{age}', key=f'du_{real_idx}', help=f'{age}세 대운', use_container_width=True):
                st.session_state.sel_daeun = real_idx
                # 해당 대운의 첫 년도로 세운 업데이트
                new_seun_start = y + age - 10
                st.session_state.saju_data['seun'] = calc_seun(max(new_seun_start, y), 20)
                st.session_state.saju_data['seun_year'] = new_seun_start
                st.session_state.sel_seun = 0
                st.rerun()
    # 세운 - 오른쪽에서 왼쪽
    sel_su = st.session_state.sel_seun or 0
    seun = data['seun']
    st.markdown('<div class="sec-title">📅 세운(歲運)</div>', unsafe_allow_html=True)
    seun_rev = list(reversed(seun))
    du_age, du_g, du_j = daeun[sel_du]
    st.markdown(f'<div class="sel-info">선택 대운: {du_age}세 {HANJA_GAN[get_gan_idx(du_g)]}{HANJA_JI[get_ji_idx(du_j)]} ({sipsin(ilgan,du_g)}/{sipsin_ji(ilgan,du_j)})</div>', unsafe_allow_html=True)
    n_seun = len(seun)
    cols_su = st.columns(min(n_seun, 10))
    # 최대 10개씩 표시
    display_seun = seun_rev[:10]
    rev_sel_su = len(seun) - 1 - sel_su
    for ci, col in enumerate(st.columns(len(display_seun))):
        if ci >= len(display_seun): break
        real_idx = len(seun) - 1 - ci
        sy, sg, sj = display_seun[ci]
        with col:
            active = (real_idx == sel_su)
            bg_g = COLOR_MAP[ohaeng_gan(sg)]; tc_g = TEXT_COLOR[ohaeng_gan(sg)]
            bg_j = COLOR_MAP[ohaeng_ji(sj)]; tc_j = TEXT_COLOR[ohaeng_ji(sj)]
            hj_g = HANJA_GAN[get_gan_idx(sg)]; hj_j = HANJA_JI[get_ji_idx(sj)]
            border = '2px solid #a0945e' if active else '1px solid #4a5580'
            bg_card = '#4a5580' if active else '#3a4565'
            st.markdown(f'''<div style="text-align:center;font-size:10px;color:#b0a888;margin-bottom:2px">{sy}</div>
<div style="display:flex;flex-direction:column;align-items:center;border:{border};border-radius:10px;background:{bg_card};padding:3px 2px;">
<div style="width:34px;height:34px;border-radius:6px;background:{bg_g};color:{tc_g};display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;margin-bottom:2px">{hj_g}</div>
<div style="width:34px;height:34px;border-radius:6px;background:{bg_j};color:{tc_j};display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;margin-bottom:2px">{hj_j}</div>
<div style="font-size:9px;color:#b0a888">{sipsin(ilgan,sg)}/{sipsin_ji(ilgan,sj)}</div>
</div>''', unsafe_allow_html=True)
            if st.button(f'{sy}', key=f'su_{real_idx}', use_container_width=True):
                st.session_state.sel_seun = real_idx
                st.session_state.sel_wolun = 0
                st.session_state.page = 'wolun'
                st.rerun()
def page_wolun():
    data = st.session_state.saju_data
    if not data: st.session_state.page='input'; st.rerun(); return
    saju = data['saju']
    ilgan = saju[2][0]
    seun = data['seun']
    sel_su = st.session_state.sel_seun or 0
    sy, sg, sj = seun[sel_su]
    if st.button('← 사주로'):
        st.session_state.page = 'saju'; st.rerun()
    hj_g = HANJA_GAN[get_gan_idx(sg)]; hj_j = HANJA_JI[get_ji_idx(sj)]
    st.markdown(f'<div class="sel-info">{sy}년 {hj_g}{hj_j} 월운 ({sipsin(ilgan,sg)}/{sipsin_ji(ilgan,sj)})</div>', unsafe_allow_html=True)
    wolun = list(reversed(calc_wolun(sy)))
    sel_wu = st.session_state.sel_wolun or 0
    n = len(wolun)
    MONTH_KR = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월']
    for row_start in range(0, n, 6):
        row_items = wolun[row_start:row_start+6]
        cols = st.columns(len(row_items))
        for ci, col in enumerate(cols):
            real_i = row_start + ci
            real_month_idx = n - 1 - real_i
            wm, wg, wj = row_items[ci]
            with col:
                active = (real_month_idx == sel_wu)
                bg_g = COLOR_MAP[ohaeng_gan(wg)]; tc_g = TEXT_COLOR[ohaeng_gan(wg)]
                bg_j = COLOR_MAP[ohaeng_ji(wj)]; tc_j = TEXT_COLOR[ohaeng_ji(wj)]
                hj_g = HANJA_GAN[get_gan_idx(wg)]; hj_j = HANJA_JI[get_ji_idx(wj)]
                border = '2px solid #a0945e' if active else '1px solid #4a5580'
                bg_card = '#4a5580' if active else '#3a4565'
                st.markdown(f'''<div style="text-align:center;font-size:10px;color:#b0a888;margin-bottom:2px">{MONTH_KR[wm-1]}</div>
<div style="display:flex;flex-direction:column;align-items:center;border:{border};border-radius:10px;background:{bg_card};padding:3px 2px;">
<div style="width:38px;height:38px;border-radius:6px;background:{bg_g};color:{tc_g};display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900;margin-bottom:2px">{hj_g}</div>
<div style="width:38px;height:38px;border-radius:6px;background:{bg_j};color:{tc_j};display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900;margin-bottom:2px">{hj_j}</div>
<div style="font-size:9px;color:#b0a888">{sipsin(ilgan,wg)}/{sipsin_ji(ilgan,wj)}</div>
</div>''', unsafe_allow_html=True)
                if st.button(f'{wm}월', key=f'wu_{real_i}', use_container_width=True):
                    st.session_state.sel_wolun = real_month_idx
                    st.session_state.page = 'ilun'
                    st.rerun()
def page_ilun():
    data = st.session_state.saju_data
    if not data: st.session_state.page='input'; st.rerun(); return
    saju = data['saju']
    ilgan = saju[2][0]
    seun = data['seun']
    sel_su = st.session_state.sel_seun or 0
    sy, sg, sj = seun[sel_su]
    sel_wu = st.session_state.sel_wolun or 0
    wolun = calc_wolun(sy)
    wm, wg, wj = wolun[sel_wu]
    if st.button('← 월운으로'):
        st.session_state.page = 'wolun'; st.rerun()
    hj_g = HANJA_GAN[get_gan_idx(wg)]; hj_j = HANJA_JI[get_ji_idx(wj)]
    st.markdown(f'<div class="sel-info">{sy}년 {wm}월 ({hj_g}{hj_j}) 일운</div>', unsafe_allow_html=True)
    ilun = calc_ilun(sy, wm)
    now = datetime.now(LOCAL_TZ)
    # 달력 HTML 생성
    import calendar as cal_mod
    first_weekday, _ = cal_mod.monthrange(sy, wm)
    # 0=월요일, 6=일요일 -> 일요일 시작으로 변환
    first_wd = (first_weekday + 1) % 7  # 0=일,1=월,...,6=토
    html = '<div class="cal-wrap">'
    hj_yg = HANJA_GAN[get_gan_idx(sg)]; hj_yj = HANJA_JI[get_ji_idx(sj)]
    html += f'<div class="cal-header">{sy}년({hj_yg}{hj_yj}) {wm}월({hj_g}{hj_j})</div>'
    html += '<table class="cal-table"><thead><tr>'
    for dname in ['일','월','화','수','목','금','토']:
        html += f'<th>{dname}</th>'
    html += '</tr></thead><tbody><tr>'
    # 빈칸
    for _ in range(first_wd):
        html += '<td class="empty"></td>'
    col_pos = first_wd
    for d_num, dg, dj in ilun:
        if col_pos == 7:
            html += '</tr><tr>'
            col_pos = 0
        dow = (first_wd + d_num - 1) % 7  # 0=일, 6=토
        is_today = (sy == now.year and wm == now.month and d_num == now.day)
        cls = 'today-cell' if is_today else ''
        if dow == 0: cls += ' sun'
        elif dow == 6: cls += ' sat'
        hj_dg = HANJA_GAN[get_gan_idx(dg)]; hj_dj = HANJA_JI[get_ji_idx(dj)]
        html += f'<td class="{cls.strip()}"><div class="dn">{d_num}</div><div class="day-gan">{hj_dg}</div><div class="day-ji">{hj_dj}</div></td>'
        col_pos += 1
    while col_pos < 7 and col_pos > 0:
        html += '<td class="empty"></td>'
        col_pos += 1
    html += '</tr></tbody></table></div>'
    st.markdown(html, unsafe_allow_html=True)


if __name__ == '__main__':
    main()
