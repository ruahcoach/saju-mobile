# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
import re, math, calendar as cal_mod, os
import streamlit as st
from zoneinfo import ZoneInfo
try:
    from korean_lunar_calendar import KoreanLunarCalendar
    HAS_LUNAR = True
except Exception:
    HAS_LUNAR = False

LOCAL_TZ = ZoneInfo('Asia/Seoul')
BASE_MIN = 8 * 60 + 30

def to_solar_time(dt_local):
    off = dt_local.utcoffset()
    if off is None: raise ValueError('must be tz-aware')
    return dt_local - timedelta(minutes=int(off.total_seconds()//60) - BASE_MIN)

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
BRANCH_HIDDEN = {'자':['임','계'],'축':['계','신','기'],'인':['무','병','갑'],'묘':['갑','을'],'진':['을','계','무'],'사':['무','경','병'],'오':['병','기','정'],'미':['정','을','기'],'신':['무','임','경'],'유':['경','신'],'술':['신','정','무'],'해':['무','갑','임']}
NOTEARTH = {'갑','을','병','정','경','신','임','계'}
def stems_of_element(elem): return {'목':['갑','을'],'화':['병','정'],'토':['무','기'],'금':['경','신'],'수':['임','계']}[elem]
def stem_with_polarity(elem, parity): a,b=stems_of_element(elem); return a if parity=='양' else b
def is_yang_stem(gan): return gan in ['갑','병','무','경','임']
def ten_god_for_stem(day_stem, other_stem):
    d_e,d_p = STEM_ELEM[day_stem],STEM_YY[day_stem]; o_e,o_p = STEM_ELEM[other_stem],STEM_YY[other_stem]
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
def is_first_half_by_terms(dt_solar, first_term_dt, mid_term_dt): return first_term_dt <= dt_solar < mid_term_dt

JIE_DEGREES = {'입춘':315,'경칩':345,'청명':15,'입하':45,'망종':75,'소서':105,'입추':135,'백로':165,'한로':195,'입동':225,'대설':255,'소한':285}
JIE_ORDER = ['입춘','경칩','청명','입하','망종','소서','입추','백로','한로','입동','대설','소한']
JIE24_DEGREES = {'입춘':315,'우수':330,'경칩':345,'춘분':0,'청명':15,'곡우':30,'입하':45,'소만':60,'망종':75,'하지':90,'소서':105,'대서':120,'입추':135,'처서':150,'백로':165,'추분':180,'한로':195,'상강':210,'입동':225,'소설':240,'대설':255,'동지':270,'소한':285,'대한':300}
JIE24_ORDER = ['입춘','우수','경칩','춘분','청명','곡우','입하','소만','망종','하지','소서','대서','입추','처서','백로','추분','한로','상강','입동','소설','대설','동지','소한','대한']
SIDU_START = {('갑','기'):'갑',('을','경'):'병',('병','신'):'무',('정','임'):'경',('무','계'):'임'}
def month_start_gan_idx(year_gan_idx): return ((year_gan_idx % 5) * 2 + 2) % 10
K_ANCHOR = 49
