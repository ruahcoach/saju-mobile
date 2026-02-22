# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
import re, math, calendar as cal_mod, os
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import streamlit as st
from zoneinfo import ZoneInfo
try:
    from korean_lunar_calendar import KoreanLunarCalendar
    HAS_LUNAR = True
except Exception:
    HAS_LUNAR = False

def get_kasi_key():
    try:
        val = st.secrets.get('KASI_KEY')
        if val: return val
    except Exception: pass
    return os.getenv('KASI_KEY')

LOCAL_TZ = ZoneInfo('Asia/Seoul')
BASE_MIN = 8 * 60 + 30

def to_solar_time(dt_local):
    off = dt_local.utcoffset()
    if off is None: raise ValueError('dt_local must be timezone-aware')
    off_min = int(off.total_seconds() // 60)
    delta = off_min - BASE_MIN
    return dt_local - timedelta(minutes=delta)

KR_CITY_LON = {'서울':127.0,'가평':127.5,'대전':127.5,'부산':129.0,'대구':128.5,'제주':126.5,'인천':126.5,'울산':128.5,'광주':127.0,'울릉도':130.9}
BASE_MERIDIAN = 127.5
DEG2MIN = 4.0

def apply_longitude_correction(dt_solar, city_lon):
    if city_lon is None: return dt_solar
    delta_min = (BASE_MERIDIAN - float(city_lon)) * DEG2MIN
    return dt_solar + timedelta(minutes=delta_min)

CHEONGAN = ['갑','을','병','정','무','기','경','신','임','계']
JIJI = ['자','축','인','묘','진','사','오','미','신','유','술','해']
HANJA_GAN = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
HANJA_JI = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
MONTH_JI = ['인','묘','진','사','오','미','신','유','술','해','자','축']
JIE_TO_MONTH_JI = {'입춘':'인','경칩':'묘','청명':'진','입하':'사','망종':'오','소서':'미','입추':'신','백로':'유','한로':'술','입동':'해','대설':'자','소한':'축','(전년)대설':'자'}
MONTH_TO_2TERMS = {'인':('입춘','우수'),'묘':('경칩','춘분'),'진':('청명','곡우'),'사':('입하','소만'),'오':('망종','하지'),'미':('소서','대서'),'신':('입추','처서'),'유':('백로','추분'),'술':('한로','상강'),'해':('입동','소설'),'자':('대설','동지'),'축':('소한','대한')}
GAN_BG = {'갑':'#2ecc71','을':'#2ecc71','병':'#e74c3c','정':'#e74c3c','무':'#f1c40f','기':'#f1c40f','경':'#ffffff','신':'#ffffff','임':'#000000','계':'#000000'}
BR_BG = {'해':'#000000','자':'#000000','인':'#2ecc71','묘':'#2ecc71','사':'#e74c3c','오':'#e74c3c','신':'#ffffff','유':'#ffffff','진':'#f1c40f','술':'#f1c40f','축':'#f1c40f','미':'#f1c40f'}
def gan_fg(gan): bg=GAN_BG.get(gan,'#fff'); return '#000000' if bg in ('#ffffff','#f1c40f') else '#ffffff'
def br_fg(ji): bg=BR_BG.get(ji,'#fff'); return '#000000' if bg in ('#ffffff','#f1c40f') else '#ffffff'
STEM_ELEM = {'갑':'목','을':'목','병':'화','정':'화','무':'토','기':'토','경':'금','신':'금','임':'수','계':'수'}
STEM_YY = {'갑':'양','을':'음','병':'양','정':'음','무':'양','기':'음','경':'양','신':'음','임':'양','계':'음'}
BRANCH_MAIN = {'자':'계','축':'기','인':'갑','묘':'을','진':'무','사':'병','오':'정','미':'기','신':'경','유':'신','술':'무','해':'임'}
ELEM_PRODUCE = {'목':'화','화':'토','토':'금','금':'수','수':'목'}
ELEM_CONTROL = {'목':'토','화':'금','토':'수','금':'목','수':'화'}
ELEM_OVER_ME = {v:k for k,v in ELEM_CONTROL.items()}
ELEM_PROD_ME = {v:k for k,v in ELEM_PRODUCE.items()}
SAMHAP = {'화':{'인','오','술'},'목':{'해','묘','미'},'수':{'신','자','진'},'금':{'사','유','축'}}
MONTH_SAMHAP = {'인':'화','오':'화','술':'화','해':'목','묘':'목','미':'목','신':'수','자':'수','진':'수','사':'금','유':'금','축':'금'}
INSHINSAHAE = {'인','신','사','해'}
BRANCH_HIDDEN = {'자':['임','계'],'축':['계','신','기'],'인':['무','병','갑'],'묘':['갑','을'],'진':['을','계','무'],'사':['무','경','병'],'오':['병','기','정'],'미':['정','을','기'],'신':['무','임','경'],'유':['경','신'],'술':['신','정','무'],'해':['무','갑','임']}
NOTEARTH = {'갑','을','병','정','경','신','임','계'}
def stems_of_element(elem): return {'목':['갑','을'],'화':['병','정'],'토':['무','기'],'금':['경','신'],'수':['임','계']}[elem]
def stem_with_polarity(elem, parity): a,b=stems_of_element(elem); return a if parity=='양' else b
def is_yang_stem(gan): return gan in ['갑','병','무','경','임']
def ten_god_for_stem(day_stem, other_stem):
    d_e,d_p = STEM_ELEM[day_stem],STEM_YY[day_stem]
    o_e,o_p = STEM_ELEM[other_stem],STEM_YY[other_stem]
    if o_e==d_e: return '비견' if o_p==d_p else '겁재'
    if o_e==ELEM_PRODUCE[d_e]: return '식신' if o_p==d_p else '상관'
    if o_e==ELEM_CONTROL[d_e]: return '편재' if o_p==d_p else '정재'
    if o_e==ELEM_OVER_ME[d_e]: return '편관' if o_p==d_p else '정관'
    if o_e==ELEM_PROD_ME[d_e]: return '편인' if o_p==d_p else '정인'
    return '미정'
def ten_god_for_branch(day_stem, branch): return ten_god_for_stem(day_stem, BRANCH_MAIN[branch])
def six_for_stem(ds,s): return ten_god_for_stem(ds,s)
def six_for_branch(ds,b): return ten_god_for_branch(ds,b)
def all_hidden_stems(branches):
    s=set()
    for b in branches: s.update(BRANCH_HIDDEN.get(b,[]))
    return s
def picknon_earth_from(h, start_idx):
    for i in range(start_idx, len(h)):
        if h[i] in NOTEARTH: return h[i]
    return None
def is_first_half_by_terms(dt_solar, first_term_dt, mid_term_dt): return first_term_dt <= dt_solar < mid_term_dt

JIE_DEGREES = {'입춘':315,'경칩':345,'청명':15,'입하':45,'망종':75,'소서':105,'입추':135,'백로':165,'한로':195,'입동':225,'대설':255,'소한':285}
JIE_ORDER = ['입춘','경칩','청명','입하','망종','소서','입추','백로','한로','입동','대설','소한']
JIE24_DEGREES = {'입춘':315,'우수':330,'경칩':345,'춘분':0,'청명':15,'곡우':30,'입하':45,'소만':60,'망종':75,'하지':90,'소서':105,'대서':120,'입추':135,'처서':150,'백로':165,'추분':180,'한로':195,'상강':210,'입동':225,'소설':240,'대설':255,'동지':270,'소한':285,'대한':300}
JIE24_ORDER = ['입춘','우수','경칩','춘분','청명','곡우','입하','소만','망종','하지','소서','대서','입추','처서','백로','추분','한로','상강','입동','소설','대설','동지','소한','대한']

SIDU_START = {('갑','기'):'갑',('을','경'):'병',('병','신'):'무',('정','임'):'경',('무','계'):'임'}
def month_start_gan_idx(year_gan_idx): return ((year_gan_idx % 5) * 2 + 2) % 10
K_ANCHOR = 49

def jdn_0h_utc(y,m,d):
    if m<=2: y-=1; m+=12
    A=y//100; B=2-A+A//4
    return int(365.25*(y+4716))+int(30.6001*(m+1))+d+B-1524
def jd_from_utc(dt_utc):
    y=dt_utc.year; m=dt_utc.month
    d=dt_utc.day+(dt_utc.hour+dt_utc.minute/60+dt_utc.second/3600)/24
    if m<=2: y-=1; m+=12
    A=y//100; B=2-A+A//4
    return int(365.25*(y+4716))+int(30.6001*(m+1))+d+B-1524.5
def norm360(x): return x%360.0
def wrap180(x): return (x+180.0)%360.0-180.0
def solar_longitude_deg(dt_utc):
    JD=jd_from_utc(dt_utc); T=(JD-2451545.0)/36525.0
    L0=norm360(280.46646+36000.76983*T+0.0003032*T*T)
    M=norm360(357.52911+35999.05029*T-0.0001537*T*T)
    Mr=math.radians(M)
    C=((1.914602-0.004817*T-0.000014*T*T)*math.sin(Mr)
       +(0.019993-0.000101*T)*math.sin(2*Mr)
       +0.000289*math.sin(3*Mr))
    theta=L0+C
    Omega=125.04-1934.136*T
    lam=theta-0.00569-0.00478*math.sin(math.radians(Omega))
    return norm360(lam)

def find_longitude_time_local(year, target_deg, approx_dt_local):
    a=(approx_dt_local-timedelta(days=3)).astimezone(timezone.utc)
    b=(approx_dt_local+timedelta(days=3)).astimezone(timezone.utc)
    def f(dt_utc): return wrap180(solar_longitude_deg(dt_utc)-target_deg)
    scan,step=a,timedelta(hours=6); fa=f(scan); found=False
    while scan<b:
        scan2=scan+step; fb=f(scan2)
        if fa==0 or fb==0 or (fa<0 and fb>0) or (fa>0 and fb<0): a,b=scan,scan2; found=True; break
        scan,fa=scan2,fb
    if not found:
        a=(approx_dt_local-timedelta(days=1)).astimezone(timezone.utc)
        b=(approx_dt_local+timedelta(days=1)).astimezone(timezone.utc)
    for _ in range(70):
        mid=a+(b-a)/2; fm=f(mid); fa=f(a)
        if fm==0: a=b=mid; break
        if (fa<=0 and fm>=0) or (fa>=0 and fm<=0): b=mid
        else: a=mid
    res=(a+(b-a)/2).astimezone(LOCAL_TZ)
    return res.replace(second=0,microsecond=0)

def approx_guess_local(year):
    rough={'입춘':(2,4),'경칩':(3,6),'청명':(4,5),'입하':(5,6),'망종':(6,6),'소서':(7,7),'입추':(8,8),'백로':(9,8),'한로':(10,8),'입동':(11,7),'대설':(12,7),'소한':(1,6)}
    out={}
    for name,(m,d) in rough.items():
        out[name]=datetime(year,m,d,9,0,tzinfo=LOCAL_TZ)
    out['(전년)대설']=datetime(year-1,12,7,9,0,tzinfo=LOCAL_TZ)
    return out

def approx_guess_local_24(year):
    rough={'입춘':(2,4),'우수':(2,19),'경칩':(3,6),'춘분':(3,21),'청명':(4,5),'곡우':(4,20),
           '입하':(5,6),'소만':(5,21),'망종':(6,6),'하지':(6,21),'소서':(7,7),'대서':(7,23),
           '입추':(8,8),'처서':(8,23),'백로':(9,8),'추분':(9,23),'한로':(10,8),'상강':(10,23),
           '입동':(11,7),'소설':(11,22),'대설':(12,7),'동지':(12,22),'소한':(1,6),'대한':(1,20)}
    out={}
    for name,(m,d) in rough.items():
        out[name]=datetime(year,m,d,9,0,tzinfo=LOCAL_TZ)
    return out

def compute_jie_times_calc(year):
    guesses=approx_guess_local(year); terms={}
    for name in JIE_ORDER:
        terms[name]=find_longitude_time_local(year,JIE_DEGREES[name],guesses[name])
    terms['(전년)대설']=find_longitude_time_local(year-1,JIE_DEGREES['대설'],guesses['(전년)대설'])
    return terms

def compute_jie24_times_calc(year):
    guesses=approx_guess_local_24(year); out={}
    for name in JIE24_ORDER:
        deg=JIE24_DEGREES[name]
        approx=guesses[name]
        # 소한/대한은 해당 year의 1월(양력)로 계산
        calc_year=approx.year
        out[name]=find_longitude_time_local(calc_year,deg,approx)
    return out

def pillar_day_by_2300(dt_solar):
    return (dt_solar+timedelta(days=1)).date() if (dt_solar.hour,dt_solar.minute)>=(23,0) else dt_solar.date()

def day_ganji_solar(dt_solar, k_anchor=K_ANCHOR):
    d=pillar_day_by_2300(dt_solar)
    idx60=(jdn_0h_utc(d.year,d.month,d.day)+k_anchor)%60
    cidx,jidx=idx60%10,idx60%12
    return CHEONGAN[cidx]+JIJI[jidx],cidx,jidx

def hour_branch_idx_2300(dt_solar):
    mins=dt_solar.hour*60+dt_solar.minute
    off=(mins-(23*60))%1440
    return off//120

def sidu_zi_start_gan(day_gan):
    for pair,start in SIDU_START.items():
        if day_gan in pair: return start
    raise ValueError('invalid day gan')

def four_pillars_from_solar(dt_solar, k_anchor=K_ANCHOR):
    # 12절기 계산 (황경 기반)
    jie12=compute_jie_times_calc(dt_solar.year)
    # 모든 절기를 태양시로 변환
    jie_solar={name:to_solar_time(t) for name,t in jie12.items()}
    ipchun=jie_solar.get("입춘")
    # 입춘 기준 년주 결정
    y=dt_solar.year-1 if dt_solar<ipchun else dt_solar.year
    y_gidx=(y-4)%10; y_jidx=(y-4)%12
    year_pillar=CHEONGAN[y_gidx]+JIJI[y_jidx]
    # 절기 순서 정렬하여 월주 결정
    order=list(jie_solar.items()); order.sort(key=lambda x:x[1])
    last='(전년)대설'
    for name,t in order:
        if dt_solar>=t: last=name
        else: break
    m_branch=JIE_TO_MONTH_JI[last]
    m_bidx=MONTH_JI.index(m_branch)
    m_gidx=(month_start_gan_idx(y_gidx)+m_bidx)%10
    month_pillar=CHEONGAN[m_gidx]+m_branch
    # 일주 (K앵커=49 기반)
    day_pillar,d_cidx,d_jidx=day_ganji_solar(dt_solar,k_anchor)
    # 시주 (시두법)
    h_j_idx=hour_branch_idx_2300(dt_solar)
    zi_start=sidu_zi_start_gan(CHEONGAN[d_cidx])
    h_c_idx=(CHEONGAN.index(zi_start)+h_j_idx)%10
    hour_pillar=CHEONGAN[h_c_idx]+JIJI[h_j_idx]
    return {'year':year_pillar,'month':month_pillar,'day':day_pillar,'hour':hour_pillar,
            'y_gidx':y_gidx,'m_gidx':m_gidx,'m_bidx':m_bidx,'d_cidx':d_cidx}

def next_prev_jie(dt_solar, jie_solar_dict):
    items=[(n,t) for n,t in jie_solar_dict.items()]
    items.sort(key=lambda x:x[1])
    prev_t=items[0][1]
    for _,t in items:
        if t>dt_solar: return prev_t,t
        prev_t=t
    return prev_t,prev_t

def round_half_up(x): return int(math.floor(x+0.5))

def dayun_start_age(dt_solar, jie12_solar, forward):
    prev_t,next_t=next_prev_jie(dt_solar,jie12_solar)
    delta_days=(next_t-dt_solar).total_seconds()/86400.0 if forward else (dt_solar-prev_t).total_seconds()/86400.0
    return max(0,round_half_up(delta_days/3.0))

def build_dayun_list(month_gidx, month_bidx, forward, start_age, count=10):
    dirv=1 if forward else -1
    out=[]
    for i in range(1,count+1):
        g_i=(month_gidx+dirv*i)%10
        b_i=(month_bidx+dirv*i)%12
        out.append({'start_age':start_age+(i-1)*10,'g_idx':g_i,'b_idx':b_i})
    return out

def calc_age_on(dob, now_dt):
    today=now_dt.date() if hasattr(now_dt,"date") else now_dt
    return today.year-dob.year-((today.month,today.day)<(dob.month,dob.day))

def lunar_to_solar(y,m,d,is_leap=False):
    if not HAS_LUNAR: raise RuntimeError('korean-lunar-calendar 미설치')
    c=KoreanLunarCalendar(); c.setLunarDate(y,m,d,is_leap)
    return date(c.solarYear,c.solarMonth,c.solarDay)

@dataclass
class Inputs:
    day_stem: str
    month_branch: str
    month_stem: str
    stems_visible: list
    branches_visible: list
    solar_dt: datetime
    first_term_dt: datetime
    mid_term_dt: datetime
    day_from_jieqi: int

def decide_geok(inp):
    ds=inp.day_stem; mb=inp.month_branch; ms=inp.month_stem
    stems=list(inp.stems_visible); branches=list(inp.branches_visible)
    ds_e=STEM_ELEM[ds]; ds_p=STEM_YY[ds]
    mb_main=BRANCH_MAIN[mb]
    mb_e,mb_p=STEM_ELEM[mb_main],STEM_YY[mb_main]
    visible_set=set(stems); hidden_set=all_hidden_stems(branches)
    pool=visible_set|hidden_set
    if mb in {'자','오','묘','유','인','신','사','해'} and ds_e==mb_e:
        off_e=ELEM_OVER_ME[ds_e]
        jung_gwan=stem_with_polarity(off_e,'음' if ds_p=='양' else '양')
        pyeon_gwan=stem_with_polarity(off_e,ds_p)
        same_polarity=(ds_p==mb_p)
        any_jung_br=any(ten_god_for_branch(ds,b)=='정관' for b in branches)
        jung_branches=[b for b in branches if ten_god_for_branch(ds,b)=='정관']
        any_pyeon_br=any(ten_god_for_branch(ds,b)=='편관' for b in branches)
        pyeon_branches=[b for b in branches if ten_god_for_branch(ds,b)=='편관']
        if same_polarity:
            if (jung_gwan in visible_set) or any_jung_br:
                why=('정관 '+jung_gwan+' 천간 투간' if jung_gwan in visible_set else '지지 정관 존재')
                return '건록격',f'[특수] 월비+{why}→건록격'
            else: return '월비격','[특수] 월비·정관 없음→월비격'
        else:
            if (pyeon_gwan in visible_set) or any_pyeon_br:
                why=('편관 '+pyeon_gwan+' 천간 투간' if pyeon_gwan in visible_set else '지지 편관 존재')
                return '양인격',f'[특수] 월겁+{why}→양인격'
            else: return '월겁격','[특수] 월겁·편관 없음→월겁격'
    grp='자오묘유' if mb in {'자','오','묘','유'} else ('인신사해' if mb in {'인','신','사','해'} else '진술축미')
    if grp=='자오묘유':
        month_elem=STEM_ELEM[mb_main]
        same_elem_vis=[s for s in stems if STEM_ELEM.get(s)==month_elem]
        if same_elem_vis:
            pick=next((s for s in same_elem_vis if STEM_YY[s]!=ds_p),same_elem_vis[0])
            six=ten_god_for_stem(ds,pick)
            return f'{six}격',f'[자오묘유] {pick} 투간→{six}격'
        six=ten_god_for_stem(ds,mb_main)
        return f'{six}격',f'[자오묘유] 투간없음→체(본기 {mb_main}){six}격'
    if grp=='인신사해':
        rokji=mb_main; month_elem=STEM_ELEM[rokji]
        base_stems=set(stems_of_element(month_elem))
        base_vis=[s for s in inp.stems_visible if s in base_stems]
        if base_vis:
            pick=base_vis[0]
            if month_elem==STEM_ELEM[ds]:
                off_e=ELEM_OVER_ME[STEM_ELEM[ds]]
                jung_gwan=stem_with_polarity(off_e,'음' if STEM_YY[ds]=='양' else '양')
                pyeon_gwan=stem_with_polarity(off_e,STEM_YY[ds])
                if STEM_YY[pick]==STEM_YY[ds]:
                    if jung_gwan in inp.stems_visible: return '건록격',f'[인신사해] {pick}투간+정관{jung_gwan}→건록격'
                else:
                    if pyeon_gwan in inp.stems_visible: return '양인격',f'[인신사해] {pick}투간+편관{pyeon_gwan}→양인격'
            six=ten_god_for_stem(ds,pick)
            return f'{six}격',f'[인신사해] 록지{pick}투간→{six}격'
        tri_elem=MONTH_SAMHAP.get(mb,'')
        if tri_elem:
            tri_grp=SAMHAP[tri_elem]; others=set(tri_grp)-{mb}
            if others.issubset(set(inp.branches_visible)) and is_first_half_by_terms(inp.solar_dt,inp.first_term_dt,inp.mid_term_dt):
                tri_stems=stems_of_element(tri_elem)
                tri_vis=[s for s in tri_stems if s in inp.stems_visible]
                if tri_vis and tri_elem!=STEM_ELEM[ds]:
                    pick=tri_vis[0]; six=ten_god_for_stem(ds,pick)
                    return f'중기격({six})',f'[인신사해] 삼합+중기사령+{pick}투간→중기격'
        if ms: six=ten_god_for_stem(ds,ms); return f'{six}격',f'[인신사해] 록지투간없음→월간{ms}기준{six}격'
        six=ten_god_for_stem(ds,rokji)
        return f'{six}격',f'[인신사해] 폴백→본기({rokji}){six}격'
    if grp=='진술축미':
        h=BRANCH_HIDDEN.get(mb,[])
        mb_main_l=BRANCH_MAIN[mb]
        is_front12=(inp.day_from_jieqi<=11)
        tri_elem=MONTH_SAMHAP.get(mb,'')
        if tri_elem:
            tri_grp=SAMHAP[tri_elem]; others=set(tri_grp)-{mb}
            partners=others&set(branches)
            if partners:
                if tri_elem==STEM_ELEM[ds]:
                    six=ten_god_for_stem(ds,mb_main_l)
                    return f'{six}격',f'[진술축미] 반합{mb}+동일오행→체(본기){six}격'
                tri_stems=stems_of_element(tri_elem)
                tri_vis=[s for s in tri_stems if s in visible_set]
                mid_qi=h[1] if len(h)>=2 else (h[-1] if h else mb_main_l)
                mid_is_tri=(STEM_ELEM.get(mid_qi)==tri_elem)
                pick=tri_vis[0] if tri_vis else (mid_qi if mid_is_tri else stem_with_polarity(tri_elem,'음' if STEM_YY[ds]=='양' else '양'))
                six=ten_god_for_stem(ds,pick)
                return f'{six}격',f'[진술축미] 반합+{pick}기준{six}격'
        if is_front12:
            yeogi=h[0] if h else mb_main_l
            y_elem=STEM_ELEM[yeogi]
            same_vis=[s for s in stems if STEM_ELEM.get(s)==y_elem]
            opp=[s for s in same_vis if STEM_YY[s]!=ds_p]
            pick=opp[0] if opp else (same_vis[0] if same_vis else yeogi)
            six=ten_god_for_stem(ds,pick)
            return f'{six}격',f'[진술축미] 절입후12일이내→여기사령({pick}){six}격'
        else:
            earth_vis=[s for s in ('무','기') if s in visible_set]
            opp=[s for s in earth_vis if STEM_YY[s]!=ds_p]
            pick=opp[0] if opp else (earth_vis[0] if earth_vis else mb_main_l)
            six=ten_god_for_stem(ds,pick)
            return f'{six}격',f'[진술축미] 절입13일이후→주왕토({pick}){six}격'
    six=ten_god_for_stem(ds,BRANCH_MAIN[mb])
    return f'{six}격',f'[폴백]→체(본기{BRANCH_MAIN[mb]}){six}격'

def calc_wolun_accurate(year):
    # 황경 기반 정확한 월운 계산
    jie24=compute_jie24_times_calc(year)
    jie24_next=compute_jie24_times_calc(year+1)
    # 이전년도 소한/대한도 가져오기
    jie24_prev=compute_jie24_times_calc(year-1)
    y_gidx=(year-4)%10
    start_mg=month_start_gan_idx(y_gidx)
    items=[]
    for i in range(12):
        gidx=(start_mg+i)%10
        bidx=i
        gan,ji=CHEONGAN[gidx],MONTH_JI[bidx]
        t1_name,t2_name=MONTH_TO_2TERMS[ji]
        def get_t(name,sources):
            for src in sources:
                if name in src:
                    t=src[name]
                    return to_solar_time(t) if t.utcoffset() is not None else t
            return None
        # 모든 소스에서 찾기 (이전/현재/다음년도)
        sources=[jie24,jie24_next,jie24_prev]
        t1=get_t(t1_name,sources)
        t2=get_t(t2_name,sources)
        next_bidx=(bidx+1)%12
        next_t1_name=MONTH_TO_2TERMS[MONTH_JI[next_bidx]][0]
        t_end=get_t(next_t1_name,sources)
        items.append({'month':i+1,'gan':gan,'ji':ji,'t1':t1,'t2':t2,'t_end':t_end})
    return items

def calc_ilun_strip(start_dt, end_dt, day_stem, k_anchor=K_ANCHOR):
    items=[]
    cur=start_dt.replace(hour=12,minute=0,second=0,microsecond=0)
    if cur<start_dt: cur=cur+timedelta(days=1)
    while cur<end_dt:
        dj,dc,djidx=day_ganji_solar(cur,k_anchor)
        g,j=dj[0],dj[1]
        items.append({'date':cur.date(),'gan':g,'ji':j,'six':f'{six_for_stem(day_stem,g)}/{six_for_branch(day_stem,j)}'})
        cur=cur+timedelta(days=1)
    return items

MOBILE_CSS = """
<style>
:root{--bg:#ffffff;--bg2:#f5f5f0;--card:#e8e4d8;--acc:#8b6914;--text:#2c2416;--sub:#6b5a3e;--r:10px;--bdr:#c8b87a;}
*{box-sizing:border-box;}
body,.stApp{background:var(--bg)!important;color:var(--text)!important;font-family:"Noto Serif KR","Malgun Gothic",serif;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding:0.5rem!important;max-width:430px!important;margin:0 auto!important;}
.stTextInput input,.stNumberInput input{background:#fff!important;color:var(--text)!important;border:1px solid var(--bdr)!important;border-radius:8px!important;}
.stRadio label{color:var(--text)!important;}
.stButton>button{background:linear-gradient(135deg,#c8b87a,#a0945e)!important;color:#fff!important;border:1px solid var(--acc)!important;border-radius:4px!important;width:100%!important;font-size:10px!important;font-weight:bold!important;padding:1px 0px!important;white-space:nowrap!important;overflow:hidden;min-height:0!important;height:20px!important;line-height:1!important;}
.page-hdr{background:linear-gradient(135deg,#c8b87a,#a0945e);border-bottom:2px solid var(--acc);padding:10px;text-align:center;font-size:18px;font-weight:bold;color:#fff;letter-spacing:4px;margin-bottom:12px;}
.saju-wrap{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);padding:6px 4px;margin-bottom:4px;}
.saju-table{width:100%;border-collapse:separate;border-spacing:3px;table-layout:fixed;}
.saju-table th{font-size:11px;color:var(--sub);text-align:center;padding:4px 0;}
.saju-table .lb td{font-size:10px;color:var(--sub);text-align:center;padding:2px 0;}
.gcell,.jcell{text-align:center;padding:0;}
.gcell div,.jcell div{display:flex;align-items:center;justify-content:center;width:100%;height:44px;border-radius:8px;font-weight:900;font-size:24px;border:1px solid rgba(0,0,0,.15);margin:1px auto;}
.strip-outer{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:thin;padding:2px 0;}
.strip-inner{display:inline-flex;flex-wrap:nowrap;gap:4px;padding:2px 4px;}
.un-card{display:flex;flex-direction:column;align-items:center;min-width:52px;padding:4px 2px 6px;border:1px solid var(--bdr);border-radius:10px;background:var(--card);cursor:pointer;}
.un-card.active{border:2px solid var(--acc)!important;background:#d4c48a;}
.un-card .lbl{font-size:10px;color:var(--sub);margin-bottom:2px;}
.un-card .gbox,.un-card .jbox{width:44px;height:44px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;border:1px solid rgba(0,0,0,.1);margin-bottom:2px;}
.un-card .ss{font-size:9px;color:var(--sub);text-align:center;}
.sec-title{font-size:13px;color:var(--acc);font-weight:bold;padding:4px 6px;border-left:3px solid var(--acc);margin:10px 0 6px;}
.geok-box{background:rgba(200,184,122,.2);border:1px solid var(--acc);border-radius:8px;padding:10px 12px;margin:8px 0;font-size:12px;color:var(--text);}
.geok-name{font-size:16px;font-weight:900;color:#8b4513;margin-bottom:4px;}
.geok-why{font-size:11px;color:var(--sub);line-height:1.4;}
.today-banner{background:linear-gradient(135deg,#f5f0e8,#ede0c4);border:1px solid var(--acc);border-radius:8px;padding:6px 12px;margin-bottom:8px;font-size:12px;color:var(--sub);text-align:center;}
.sel-info{background:var(--card);border:1px solid var(--acc);border-radius:8px;padding:6px 12px;margin-bottom:8px;font-size:12px;color:var(--text);text-align:center;}
.cal-wrap{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden;margin-bottom:10px;}
.cal-header{background:#c8b87a;text-align:center;padding:8px;font-size:14px;color:#fff;font-weight:bold;}
.cal-table{width:100%;border-collapse:collapse;}
.cal-table th{background:#d4c48a;color:#5a3e0a;font-size:11px;text-align:center;padding:4px 2px;border:1px solid var(--bdr);}
.cal-table td{text-align:center;padding:2px 1px;border:1px solid var(--bdr);font-size:11px;color:var(--text);vertical-align:top;min-width:38px;height:72px;}
.cal-table td.empty{background:#f0ece4;}
.cal-table td .dn{font-size:13px;font-weight:bold;margin-bottom:1px;}
.cal-table td.today-cell{background:#ffe8a0;border:1px solid var(--acc);}
.cal-table td.sun .dn{color:#E53935;}
.cal-table td.sat .dn{color:#1565C0;}
.ai-btn{display:block;background:linear-gradient(135deg,#7b4fa0,#4a2a70);border:1px solid #a070c0;border-radius:12px;padding:12px;text-align:center;color:#e8d0ff;font-size:14px;font-weight:bold;text-decoration:none;margin:12px 0;}
label{color:var(--text)!important;font-size:13px!important;}
div[data-testid='stHorizontalBlock']{gap:4px!important;}
div[data-testid='column']{padding:0 2px!important;}
</style>
"""

def hanja_gan(g): return HANJA_GAN[CHEONGAN.index(g)]
def hanja_ji(j): return HANJA_JI[JIJI.index(j)]

def gan_card_html(g, size=52, fsize=26):
    bg=GAN_BG.get(g,"#888"); fg=gan_fg(g); hj=hanja_gan(g)
    return f'<div style="width:{size}px;height:{size}px;border-radius:8px;background:{bg};color:{fg};display:flex;align-items:center;justify-content:center;font-size:{fsize}px;font-weight:900;border:1px solid rgba(0,0,0,.15);">{hj}</div>'

def ji_card_html(j, size=52, fsize=26):
    bg=BR_BG.get(j,"#888"); fg=br_fg(j); hj=hanja_ji(j)
    return f'<div style="width:{size}px;height:{size}px;border-radius:8px;background:{bg};color:{fg};display:flex;align-items:center;justify-content:center;font-size:{fsize}px;font-weight:900;border:1px solid rgba(0,0,0,.15);">{hj}</div>'

def render_saju_table(fp, ilgan):
    yg,yj=fp['year'][0],fp['year'][1]
    mg,mj=fp['month'][0],fp['month'][1]
    dg,dj=fp['day'][0],fp['day'][1]
    sg,sj=fp['hour'][0],fp['hour'][1]
    cols=[(sg,sj,'시주'),(dg,dj,'일주'),(mg,mj,'월주'),(yg,yj,'년주')]
    ss_g=[six_for_stem(ilgan,sg),'일간',six_for_stem(ilgan,mg),six_for_stem(ilgan,yg)]
    ss_j=[six_for_branch(ilgan,sj),six_for_branch(ilgan,dj),six_for_branch(ilgan,mj),six_for_branch(ilgan,yj)]
    html='<div class="saju-wrap"><table class="saju-table"><thead><tr>'
    for g,j,lbl in cols: html+=f'<th>{lbl}</th>'
    html+='</tr><tr class="lb">'
    for i,(g,j,_) in enumerate(cols): html+=f'<td>{ss_g[i]}</td>'
    html+='</tr></thead><tbody><tr>'
    for g,j,_ in cols: html+=f'<td class="gcell">{gan_card_html(g)}</td>'
    html+='</tr><tr>'
    for g,j,_ in cols: html+=f'<td class="jcell">{ji_card_html(j)}</td>'
    html+='</tr><tr class="lb">'
    for i,(_,j,__) in enumerate(cols): html+=f'<td>{ss_j[i]}</td>'
    html+='</tr></tbody></table></div>'
    return html


def render_daeun_card(age, g, j, ilgan, active, btn_key, dy_year=0):
    bg_g=GAN_BG.get(g,"#888"); tc_g=gan_fg(g)
    bg_j=BR_BG.get(j,"#888"); tc_j=br_fg(j)
    hj_g=hanja_gan(g); hj_j=hanja_ji(j)
    bdr='2px solid #8b6914' if active else '1px solid #c8b87a'
    bg_card='#d4c48a' if active else '#e8e4d8'
    six_g=six_for_stem(ilgan,g)
    six_j=six_for_branch(ilgan,j)
    st.markdown(f'''<div style="text-align:center;font-size:10px;color:#6b5a3e;margin-bottom:1px">{age}세</div>
    <div style="display:flex;flex-direction:column;align-items:center;border:{bdr};border-radius:10px;background:{bg_card};padding:3px 2px;">
    <div style="font-size:9px;color:#5a3e0a;margin-bottom:1px;white-space:nowrap">{six_g}</div>
    <div style="width:30px;height:30px;border-radius:5px;background:{bg_g};color:{tc_g};display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;margin-bottom:1px">{hj_g}</div>
    <div style="width:30px;height:30px;border-radius:5px;background:{bg_j};color:{tc_j};display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;margin-bottom:1px">{hj_j}</div>
    <div style="font-size:9px;color:#5a3e0a;white-space:nowrap">{six_j}</div>
    </div>''', unsafe_allow_html=True)
    return st.button(f'{dy_year}', key=btn_key, use_container_width=True)


def main():
    st.set_page_config(page_title='이박사 만세력', layout='centered', page_icon='🔮', initial_sidebar_state='collapsed')
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
    st.markdown('<div class="page-hdr">만 세 력</div>', unsafe_allow_html=True)
    for key,val in [('page','input'),('saju_data',None),('sel_daeun',0),('sel_seun',0),('sel_wolun',0)]:
        if key not in st.session_state: st.session_state[key]=val
    if st.session_state.page=='input': page_input()
    elif st.session_state.page=='saju': page_saju()
    elif st.session_state.page=='wolun': page_wolun()
    elif st.session_state.page=='ilun': page_ilun()

def page_input():
    now=datetime.now(LOCAL_TZ)
    st.markdown('<div class="sec-title">📅 출생 정보 입력</div>', unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1: gender=st.radio('성별',['남','여'],horizontal=True)
    with c2: cal_type=st.radio('달력',['양력','음력'],horizontal=True)
    birth_str=st.text_input('생년월일 (YYYYMMDD)',value='19840202',max_chars=8)
    birth_time=st.text_input('출생시각 (HHMM, 모르면 0000)',value='0000',max_chars=4)
    is_leap=False
    if cal_type=='음력':
        if HAS_LUNAR: is_leap=st.checkbox('윤달',value=False)
        else: st.warning('음력 모듈 미설치')
    if st.button('🔮 사주 보기'):
        try:
            bs=re.sub(r'\D','',birth_str); bt=re.sub(r'\D','',birth_time)
            y=int(bs[:4]); m=int(bs[4:6]); d=int(bs[6:8])
            hh=int(bt[:2]) if len(bt)>=2 else 0
            mm_t=int(bt[2:4]) if len(bt)==4 else 0
            base_date=date(y,m,d)
            if cal_type=='음력' and HAS_LUNAR: base_date=lunar_to_solar(y,m,d,is_leap)
            dt_local=datetime.combine(base_date,time(hh,mm_t)).replace(tzinfo=LOCAL_TZ)
            dt_solar=to_solar_time(dt_local)
            fp=four_pillars_from_solar(dt_solar)
            ilgan=fp['day'][0]
            # 정확한 황경 기반 절기 계산
            jie12=compute_jie_times_calc(dt_solar.year)
            jie12_solar={n:to_solar_time(t) for n,t in jie12.items()}
            # 대운
            year_gan=fp['year'][0]
            forward=(is_yang_stem(year_gan)==(gender=='남'))
            start_age=dayun_start_age(dt_solar,jie12_solar,forward)
            daeun=build_dayun_list(fp['m_gidx'],fp['m_bidx'],forward,start_age)
            # 세운 (출생년도부터 100년치 생성)
            seun_start=base_date.year
            seun=[]
            for i in range(100):
                sy=seun_start+i; off=(sy-4)%60
                seun.append((sy,CHEONGAN[off%10],JIJI[off%12]))
            # 격 계산 (황경 기반)
            jie24=compute_jie24_times_calc(dt_solar.year)
            jie24_solar={n:to_solar_time(t) for n,t in jie24.items()}
            pair=MONTH_TO_2TERMS[fp['month'][1]]
            def nearest_t(name):
                cands=[(abs((t-dt_solar).total_seconds()),t) for n,t in jie24_solar.items() if n==name]
                if not cands: return dt_solar
                cands.sort(); return cands[0][1]
            t1=nearest_t(pair[0]); t2=nearest_t(pair[1])
            day_from_jieqi=int((dt_solar-t1).total_seconds()//86400)
            day_from_jieqi=max(0,min(29,day_from_jieqi))
            geok,why=decide_geok(Inputs(
                day_stem=fp['day'][0],month_branch=fp['month'][1],month_stem=fp['month'][0],
                stems_visible=[fp['year'][0],fp['month'][0],fp['day'][0],fp['hour'][0]],
                branches_visible=[fp['year'][1],fp['month'][1],fp['day'][1],fp['hour'][1]],
                solar_dt=dt_solar,first_term_dt=t1,mid_term_dt=t2,day_from_jieqi=day_from_jieqi
            ))
            # 현재 대운/세운 인덱스
            age_now=calc_age_on(base_date,now)
            sel_du=0
            for idx,item in enumerate(daeun):
                if item['start_age']<=age_now: sel_du=idx
            # 현재 나이에 해당하는 세운 인덱스 (인덱스=나이)
            sel_su=min(age_now, 99)
            st.session_state.saju_data={
                'birth':(base_date.year,base_date.month,base_date.day,hh,mm_t),
                'dt_solar':dt_solar,'gender':gender,'fp':fp,'daeun':daeun,
                'seun':seun,'seun_start':seun_start,'geok':geok,'why':why,
                't1':t1,'t2':t2,'day_from_jieqi':day_from_jieqi,
                'ilgan':ilgan,'start_age':start_age,'forward':forward,
            }
            st.session_state.sel_daeun=sel_du
            st.session_state.sel_seun=sel_su
            st.session_state.sel_wolun=now.month-1
            st.session_state.page='saju'
            st.rerun()
        except Exception as e: st.error(f'입력 오류: {e}')

def page_saju():
    data=st.session_state.saju_data
    if not data or 'fp' not in data: st.session_state.page='input'; st.rerun(); return
    now=datetime.now(LOCAL_TZ)
    fp=data['fp']; ilgan=data['ilgan']
    daeun=data['daeun']; seun=data['seun']
    geok=data['geok']; why=data['why']
    t1=data['t1']; t2=data['t2']
    sel_du=st.session_state.sel_daeun
    sel_su=st.session_state.sel_seun
    birth_year=data['birth'][0]
    if st.button('← 입력으로'): st.session_state.page='input'; st.rerun()
    # 오늘 일진 (황경 기반)
    now_solar=to_solar_time(now)
    today_fp=four_pillars_from_solar(now_solar)
    yg,yj=today_fp['year'][0],today_fp['year'][1]
    dg,dj=today_fp['day'][0],today_fp['day'][1]
    mg,mj=today_fp['month'][0],today_fp['month'][1]
    hj_yg=hanja_gan(yg); hj_yj=hanja_ji(yj)
    hj_mg=hanja_gan(mg); hj_mj=hanja_ji(mj)
    hj_dg=hanja_gan(dg); hj_dj=hanja_ji(dj)
    st.markdown(f'<div class="today-banner">오늘 {now.strftime("%Y.%m.%d")} · {hj_yg}{hj_yj}년 {hj_mg}{hj_mj}월 {hj_dg}{hj_dj}일</div>', unsafe_allow_html=True)
    # 사주 원국
    st.markdown(render_saju_table(fp,ilgan), unsafe_allow_html=True)
    # 格 박스 - 절입명칭 정확히 표시
    month_ji=fp['month'][1]
    pair=MONTH_TO_2TERMS[month_ji]
    term1_name=pair[0]  # 입절 이름 (입춘/경칩/청명/... 등)
    du_dir='순행' if data['forward'] else '역행'
    du_age=data['start_age']
    day_from=data['day_from_jieqi']
    st.markdown(f'''<div class="geok-box">
    <div class="geok-name">格 {geok}</div>
    <div class="geok-why">{why}</div>
    <div class="geok-why" style="margin-top:4px;">{month_ji}월 司令 ({term1_name} 절입 +{day_from}일) · 대운 {du_age}세 {du_dir}</div>
    </div>''', unsafe_allow_html=True)
    # 대운 (오른쪽->왼쪽, 스크롤, 클릭시 월운으로 이동)
    daeun_rev=list(reversed(daeun))
    cols_du=st.columns(len(daeun))
    for ci,col in enumerate(cols_du):
        real_idx=len(daeun)-1-ci
        item=daeun_rev[ci]
        age=item['start_age']
        g=CHEONGAN[item['g_idx']]; j=MONTH_JI[item['b_idx']]
        dy_year=birth_year+age
        with col:
            clicked=render_daeun_card(age,g,j,ilgan,real_idx==sel_du,f"du_{real_idx}",dy_year)
            if clicked:
                st.session_state.sel_daeun=real_idx
                birth_y=data['birth'][0]
                du_start_age=item['start_age']
                # 세운: 항상 출생년도부터 100년치
                new_seun=[]
                for i in range(100):
                    sy=birth_y+i; off=(sy-4)%60
                    new_seun.append((sy,CHEONGAN[off%10],JIJI[off%12]))
                st.session_state.saju_data['seun']=new_seun
                # 해당 대운 시작 나이에 맞는 세운 인덱스로 이동
                st.session_state.sel_seun=du_start_age
                st.session_state.page='saju'
                st.rerun()
    # 세운 - HTML 스크롤 스트립 (오른쪽=0세, 왼쪽=높은나이)
    sel_su=st.session_state.sel_seun
    seun=data["seun"]
    du_item=daeun[sel_du]
    du_start=du_item['start_age']
    birth_y=data['birth'][0]
    if sel_du==0:
        seun_age_start=0
    else:
        seun_age_start=du_start
    seun_age_end=du_start+9
    seun_range=[]
    for age_i in range(seun_age_start, seun_age_end+1):
        if age_i < len(seun):
            sy,sg,sj=seun[age_i]
            seun_range.append((age_i,sy,sg,sj))
    seun_range_disp=list(reversed(seun_range))
    seun_html='<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;padding:4px 0 2px;">'
    seun_html+='<div style="display:inline-flex;flex-wrap:nowrap;gap:2px;padding:0 2px;">'
    for age_i,sy,sg,sj in seun_range_disp:
        bg_g=GAN_BG.get(sg,"#888"); tc_g=gan_fg(sg)
        bg_j=BR_BG.get(sj,"#888"); tc_j=br_fg(sj)
        hj_sg=hanja_gan(sg); hj_sj=hanja_ji(sj)
        six_g=six_for_stem(ilgan,sg)
        six_j=six_for_branch(ilgan,sj)
        active=(age_i==sel_su)
        bdr='2px solid #8b6914' if active else '1px solid #c8b87a'
        bg_card='#d4c48a' if active else '#e8e4d8'
        seun_html+=f'''<div style="display:flex;flex-direction:column;align-items:center;min-width:34px;border:{bdr};border-radius:8px;background:{bg_card};padding:2px 1px 2px;">
<div style="font-size:7px;color:#6b5a3e;margin-bottom:1px;white-space:nowrap">{sy}</div>
<div style="font-size:7px;color:#5a3e0a;margin-bottom:1px;white-space:nowrap">{six_g}</div>
<div style="width:22px;height:22px;border-radius:4px;background:{bg_g};color:{tc_g};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;">{hj_sg}</div>
<div style="width:22px;height:22px;border-radius:4px;background:{bg_j};color:{tc_j};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;margin-top:1px;">{hj_sj}</div>
<div style="font-size:7px;color:#5a3e0a;margin-top:1px;white-space:nowrap">{six_j}</div>
</div>'''
    seun_html+='</div></div>'
    st.markdown(seun_html, unsafe_allow_html=True)
    n_btn=len(seun_range_disp)
    if n_btn>0:
        cols_su=st.columns(n_btn)
        for ci,(age_i,sy,sg,sj) in enumerate(seun_range_disp):
            with cols_su[ci]:
                if st.button(f'{age_i}세', key=f'su_{age_i}', use_container_width=True):
                    st.session_state.sel_seun=age_i
                    st.session_state.sel_wolun=0
                    st.session_state.page='wolun'
                    st.rerun()
    gpt_url='https://chatgpt.com/g/g-68d90b2d8f448191b87fb7511fa8f80a-rua-myeongrisajusangdamsa'
    st.markdown(f'<a href="{gpt_url}" target="_blank" class="ai-btn">🤖 AI 챗봇 무료 상담</a>', unsafe_allow_html=True)


def page_wolun():
    data=st.session_state.saju_data
    if not data or 'fp' not in data: st.session_state.page='input'; st.rerun(); return
    now=datetime.now(LOCAL_TZ)
    ilgan=data['ilgan']
    seun=data["seun"]
    sel_su=st.session_state.sel_seun
    sy,sg,sj=seun[sel_su]
    if st.button('← 사주로'): st.session_state.page='saju'; st.rerun()
    hj_sg=hanja_gan(sg); hj_sj=hanja_ji(sj)
    st.markdown(f'<div class="sel-info">{sy}년 {hj_sg}{hj_sj} 월운 ({six_for_stem(ilgan,sg)}/{six_for_branch(ilgan,sj)})</div>', unsafe_allow_html=True)
    # 황경 기반 월운 계산
    wolun=calc_wolun_accurate(sy)
    sel_wu=st.session_state.sel_wolun
    wolun_rev=list(reversed(wolun))
    MONTH_KR=['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월']
    for row_start in [6,0]:
        row_items=wolun_rev[row_start:row_start+6]
        cols=st.columns(len(row_items))
        for ci,col in enumerate(cols):
            if ci>=len(row_items): break
            real_idx_in_rev=row_start+ci
            real_wu=11-real_idx_in_rev
            wm=row_items[ci]["month"]
            wg=row_items[ci]["gan"]; wj=row_items[ci]["ji"]
            with col:
                active=(real_wu==sel_wu)
                bg_g=GAN_BG.get(wg,"#888"); tc_g=gan_fg(wg)
                bg_j=BR_BG.get(wj,"#888"); tc_j=br_fg(wj)
                hj_wg=hanja_gan(wg); hj_wj=hanja_ji(wj)
                bdr='2px solid #8b6914' if active else '1px solid #c8b87a'
                bg_card='#d4c48a' if active else '#e8e4d8'
                six_g=six_for_stem(ilgan,wg)
                six_j=six_for_branch(ilgan,wj)
                st.markdown(f'''<div style="text-align:center;font-size:10px;color:#6b5a3e;margin-bottom:1px">{MONTH_KR[wm-1]}</div>
                <div style="display:flex;flex-direction:column;align-items:center;border:{bdr};border-radius:10px;background:{bg_card};padding:2px 2px;">
                <div style="font-size:9px;color:#5a3e0a;margin-bottom:1px;white-space:nowrap">{six_g}</div>
                <div style="width:34px;height:34px;border-radius:6px;background:{bg_g};color:{tc_g};display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;margin-bottom:1px">{hj_wg}</div>
                <div style="width:34px;height:34px;border-radius:6px;background:{bg_j};color:{tc_j};display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;margin-bottom:1px">{hj_wj}</div>
                <div style="font-size:9px;color:#5a3e0a;white-space:nowrap">{six_j}</div>
                </div>''', unsafe_allow_html=True)
                if st.button(f'{wm}월',key=f'wu_{real_wu}',use_container_width=True):
                    st.session_state.sel_wolun=real_wu
                    st.session_state.page='ilun'
                    st.rerun()
    gpt_url='https://chatgpt.com/g/g-68d90b2d8f448191b87fb7511fa8f80a-rua-myeongrisajusangdamsa'
    st.markdown(f'<a href="{gpt_url}" target="_blank" class="ai-btn">🤖 AI 챗봇 무료 상담</a>', unsafe_allow_html=True)


def page_ilun():
    data=st.session_state.saju_data
    if not data or 'fp' not in data: st.session_state.page='input'; st.rerun(); return
    now=datetime.now(LOCAL_TZ)
    ilgan=data['ilgan']
    seun=data["seun"]
    sel_su=st.session_state.sel_seun
    sy,sg,sj=seun[sel_su]
    sel_wu=st.session_state.sel_wolun
    wolun=calc_wolun_accurate(sy)
    wm_data=wolun[sel_wu]
    wm=wm_data["month"]; wg=wm_data["gan"]; wj=wm_data["ji"]
    if st.button('← 월운으로'): st.session_state.page='wolun'; st.rerun()
    hj_wg=hanja_gan(wg); hj_wj=hanja_ji(wj)
    hj_sg=hanja_gan(sg); hj_sj=hanja_ji(sj)
    st.markdown(f'<div class="sel-info">{sy}년 {wm}월 ({hj_wg}{hj_wj}) 일운</div>', unsafe_allow_html=True)
    # 달력: 양력 1일~말일 기준, 황경 기반 일주 계산
    _,days_in_month=cal_mod.monthrange(sy,wm)
    first_weekday,_=cal_mod.monthrange(sy,wm)
    first_wd=(first_weekday+1)%7  # 0=일요일
    # 각 날짜의 일진+육신 계산
    day_items=[]
    for d in range(1, days_in_month+1):
        dt_local=datetime(sy,wm,d,12,0,tzinfo=LOCAL_TZ)
        dt_solar=to_solar_time(dt_local)
        dj,dc,djidx=day_ganji_solar(dt_solar)
        g,j=dj[0],dj[1]
        sg_six=six_for_stem(ilgan,g)
        sj_six=six_for_branch(ilgan,j)
        day_items.append({'day':d,'gan':g,'ji':j,'sg_six':sg_six,'sj_six':sj_six})
    # 달력 HTML (육신 포함)
    html='<div class="cal-wrap">'
    html+=f'<div class="cal-header">{sy}년({hj_sg}{hj_sj}) {wm}월({hj_wg}{hj_wj})</div>'
    html+='<table class="cal-table"><thead><tr>'
    for dn in ['일','월','화','수','목','금','토']: html+=f'<th>{dn}</th>'
    html+='</tr></thead><tbody><tr>'
    for _ in range(first_wd): html+='<td class="empty"></td>'
    col_pos=first_wd
    for item in day_items:
        if col_pos==7: html+='</tr><tr>'; col_pos=0
        d_num=item["day"]
        dow=(first_wd+d_num-1)%7
        is_today=(sy==now.year and wm==now.month and d_num==now.day)
        cls='today-cell' if is_today else ''
        if dow==0: cls+=' sun'
        elif dow==6: cls+=' sat'
        hj_dg=hanja_gan(item["gan"]); hj_dj=hanja_ji(item["ji"])
        sg6=item["sg_six"]; sj6=item["sj_six"]
        html+=f'<td class="{cls.strip()}"><div class="dn">{d_num}</div><div style="font-size:9px;color:#888;">{sg6}</div><div style="font-size:14px;font-weight:bold;">{hj_dg}</div><div style="font-size:14px;font-weight:bold;">{hj_dj}</div><div style="font-size:9px;color:#888;">{sj6}</div></td>'
        col_pos+=1
    while col_pos%7!=0 and col_pos>0: html+='<td class="empty"></td>'; col_pos+=1
    html+='</tr></tbody></table></div>'
    st.markdown(html,unsafe_allow_html=True)
    gpt_url='https://chatgpt.com/g/g-68d90b2d8f448191b87fb7511fa8f80a-rua-myeongrisajusangdamsa'
    st.markdown(f'<a href="{gpt_url}" target="_blank" class="ai-btn">🤖 AI 챗봇 무료 상담</a>', unsafe_allow_html=True)


if __name__=='__main__': main()
