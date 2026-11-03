import json, csv, math, os, base64, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = sys.argv[1]  # 그림 폴더
s = json.load(open(os.path.join(BASE, "data/summary.json"), encoding="utf8"))
sc = list(csv.DictReader(open(os.path.join(BASE, "data/scenarios.csv"), encoding="utf-8-sig")))
img = lambda p: "data:image/png;base64," + base64.b64encode(open(os.path.join(FIG, p), "rb").read()).decode()
EX_SLOW, EX_FAST = 34, 4
p95 = s["peaks"]["slow"]["p95"]; wkd = s["peaks"]["slow"]["weekday_median"]
cross30 = EX_SLOW / (p95 * 0.3) * 100
fast_h30 = s["fast_type_daily_entries"] * 0.032 * 0.3 * s["fastcharge"]["median"] / 60
cong = s["congestion"]["by_zone"]
order = sorted(cong, key=lambda z: (int(''.join(c for c in z[1:] if c.isdigit())), z))
def st(n):
    return ("부족", "crit") if n > EX_SLOW else (("여유", "good") if n <= EX_SLOW * 0.6 else ("적정", "warn"))
rows = ""
for r in sc:
    ev, w = float(r["ev_ratio"]), float(r["wish"])
    a, b = math.ceil(float(r["slow_need_weekday"])), math.ceil(float(r["slow_need_p95"]))
    lab, cls = st(b)
    rows += f"<tr><td>{ev*100:.1f}%</td><td>{int(w*100)}%</td><td class=n>{a}</td><td class=n>{b}</td><td><span class='pill {cls}'>{lab}</span></td></tr>"
crows = ""
for z in order:
    c = cong[z]; tot = sum(c.values())
    crows += f"<tr><td>{z}</td><td class=n>{c.get('만차',0)}</td><td class=n>{c.get('혼잡',0)}</td><td class=n>{c.get('원활',0)}</td><td class=n>{round(c.get('만차',0)/tot*100)}%</td></tr>"
high = [z for z in order if cong[z].get('만차', 0) / sum(cong[z].values()) >= 0.40]
q = s["quality"]

html = f"""<!doctype html><html lang=ko><head><meta charset=utf-8><style>
@page{{size:A4;margin:0}}
body{{font-family:'Inter','Noto Sans CJK KR','Noto Sans CJK JP',Arial,sans-serif;color:#141414;font-size:10pt;line-height:1.45;margin:0}}
.page{{padding:10mm 15mm 8mm}}
.cover{{background:#141414;color:#FFFFFF;padding:12mm 15mm 9mm}}
.cover .meta{{font-size:8.5pt;color:#ADADAD}}
.cover h1{{font-size:24pt;font-weight:700;line-height:1.05;margin:6px 0 6px}}
.cover .sub{{color:#ADADAD;font-size:10pt;margin:0}}
h2{{font-size:12.5pt;font-weight:700;line-height:1.15;margin:12px 0 4px}}
.eyebrow{{font-size:8pt;color:#707070;margin:12px 0 0}}
.lead{{color:#707070;margin:0 0 8px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:0 0 4px}}
.k{{background:#F3F3F3;border-radius:16px;padding:10px 12px}} .k b{{display:block;font-size:18pt;font-weight:700;line-height:1.1;margin-top:4px}} .k span{{font-size:8pt;color:#707070}}
.acc{{color:#0066FF;font-weight:700}}
ol{{padding-left:18px;margin:4px 0}} ol li{{margin:3px 0}}
table{{border-collapse:collapse;width:100%;font-size:8.8pt;margin:6px 0}}
th,td{{border-bottom:0.75pt solid #E0E0E0;padding:3.5px 8px;text-align:left}} th{{background:#F3F3F3;font-weight:700;border-bottom:0}} td.n{{text-align:right;font-variant-numeric:tabular-nums}}
.pill{{display:inline-block;font-size:7.5pt;font-weight:700;padding:1px 9px;border-radius:999px}}
.good{{background:#FFFFFF;border:0.75pt solid #E0E0E0;color:#141414}} .warn{{background:#F3F3F3;color:#141414}} .crit{{background:#141414;color:#FFFFFF}}
img{{width:100%}} .pb{{page-break-before:always}} .note{{font-size:8pt;color:#ADADAD;margin:4px 0}} .two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
</style></head><body>
<div class=cover><div class=meta>2026년도 공공데이터 활용 경진대회 · 팀 고종현 · 김규년 · 문준석</div>
<h1>올림픽공원 충전기 배치 권고.</h1>
<p class=sub>예비 분석판 · 입출차 {s['period'][0]} ~ {s['period'][1]} · 공원 전체 단위 · 구역별 권고는 2025년 데이터 반영 후 발행</p></div>
<div class=page>
<p class=eyebrow>핵심 수치</p><h2>방문객은 오래 머물고, 충전기는 완속이 맞습니다.</h2>
<div class=kpis>
<div class=k><span>방문 차량 체류시간 중앙값</span><b>{s['dwell']['median']:.0f}분</b></div>
<div class=k><span>급속 충전 1회 시간 중앙값</span><b>{s['fastcharge']['median']:.0f}분</b></div>
<div class=k><span>완속형(102분 이상) 체류 비중</span><b>{s['band_share']['slow']}%</b></div>
<div class=k><span>확인된 기존 충전기</span><b style='font-size:14pt;padding-top:3px'>급속 4 · 완속 34</b></div>
</div>
<p class=eyebrow>권고 요약</p><h2>지금은 배치를 점검하고, 증설 착수 기준을 정해 두십시오.</h2>
<ol>
<li><b>충전 유형: 완속 중심 유지.</b> 방문 차량의 {s['band_share']['slow']}%가 {s['thresholds']['slow_ge']:.0f}분 이상 머물러, 급속 충전(중앙값 {s['fastcharge']['median']:.0f}분) 후 차를 옮기지 않으면 방치 기준(완료 후 1시간)을 넘습니다. 반면 완속 방치 기준(14시간)을 넘는 차량은 {s['dwell']['over_14h_pct']}%입니다.</li>
<li><b>총량: 현재는 충분, 증설 착수 기준을 정해 둘 것.</b> 충전 희망 30% 기준 피크일(상위 5% 날) 필요 완속은 {math.ceil(p95*0.032*0.3)}기로 기존 34기보다 적습니다. 같은 기준에서 방문 차량의 전기차 비율이 <span class=acc>{cross30:.1f}%</span>를 넘으면 부족해지므로, 이 비율을 증설 계획 착수 기준으로 권고합니다(서울시 2025년 3.2%).</li>
<li><b>배치: 남쪽 외 구역 점검.</b> 확인된 충전기는 남2문·남4문 두 곳에 있습니다. 혼잡도 기록에서 만차 비율이 40% 이상인 구역({', '.join(high)})의 장기 체류 수요를 2025년 구역별 데이터로 확인해 신규 완속 후보지를 정합니다.</li>
<li><b>급속: 증설 불필요.</b> 단기 체류 차량의 급속 수요는 충전 희망 30% 기준 하루 약 {fast_h30:.1f}시간 분량으로 기존 급속 4기로 처리할 수 있습니다. 급속 충전기에는 방치 기준 안내를 강화합니다.</li>
</ol>
<p class=eyebrow>시나리오</p><h2>전기차가 3배로 늘면 피크일에는 부족해질 수 있습니다.</h2>
<table><thead><tr><th>전기차 비율</th><th>충전 희망</th><th>평일 중앙값 기준</th><th>상위 5% 날 기준</th><th>기존 34기 대비(상위 5% 날)</th></tr></thead><tbody>{rows}</tbody></table>
<p class=note>필요 완속 = 기준일 완속형 최대 동시 주차(평일 중앙 {wkd:.0f}대, 상위 5% 날 {p95:.0f}대) × 전기차 비율 × 충전 희망 비율. 여유: 기존의 60% 이하, 적정: 60% 초과~100%, 부족: 기존 초과.</p>

</div><div class=pb></div><div class=page>
<p class=eyebrow>근거 1. 체류시간과 급속 충전시간</p>
<img src="{img('m_그림1_체류시간_vs_급속충전시간.png')}">
<p>방문 차량(통과 차량 제외 {q['visits']:,}대) 체류시간은 중앙값 {s['dwell']['median']:.0f}분, 하위 25% {s['dwell']['p25']:.0f}분, 상위 25% {s['dwell']['p75']:.0f}분입니다. 공원주차장 유형 급속 충전 {s['fastcharge']['sessions']:,}건은 90%가 {s['fastcharge']['p90']:.0f}분 안에 끝납니다.</p>
<p class=eyebrow>근거 2. 시간대별 동시 주차</p>
<img src="{img('m_그림2_시간대별_동시주차.png')}">
<p>평일은 오전 {int(s['hourly_peak']['weekday']['time'])}시대(평균 {s['hourly_peak']['weekday']['value']:.0f}대), 주말은 오후 {int(s['hourly_peak']['weekend']['time'])-12}시대(평균 {s['hourly_peak']['weekend']['value']:.0f}대)에 가장 붐빕니다. 충전기 수량은 일 최대 동시 주차의 상위 5% 날을 설계 기준으로 권고합니다.</p>

</div><div class=pb></div><div class=page>
<p class=eyebrow>기존 충전기와 주차구역</p><h2>확인된 충전기는 남쪽 주차장 두 곳에 있습니다.</h2>
<div class=two><div>
<table><thead><tr><th>주차장</th><th>급속</th><th>완속</th><th>확인 출처</th></tr></thead><tbody>
<tr><td>남2문</td><td class=n>4 (100kW)</td><td class=n>11 (7kW)</td><td>충전소 찾기 서비스</td></tr>
<tr><td>남4문</td><td class=n>0</td><td class=n>23</td><td>지도 서비스</td></tr>
<tr><td>그 외</td><td colspan=3>환경공단 API 조회 후 반영</td></tr></tbody></table>
<p class=note>남2문·남4문과 구역 코드의 대응은 주차 안내도와 대조해 확정합니다.</p></div>
<div><table><thead><tr><th>구역</th><th>만차</th><th>혼잡</th><th>원활</th><th>만차 비율</th></tr></thead><tbody>{crows}</tbody></table>
<p class=note>주차장 혼잡도 정보 {s['congestion']['period'][0]} ~ {s['congestion']['period'][1]} 기록 건수. 기록이 불규칙해 경향 확인용.</p></div></div>
<p class=eyebrow>가정값과 데이터</p><h2>모든 수치는 공개된 가정값과 정제 기준에서 나옵니다.</h2>
<table><thead><tr><th>항목</th><th>값</th><th>근거</th></tr></thead><tbody>
<tr><td>전기차 비율</td><td>3.2%</td><td>서울시 2025년 자동차 등록 현황 (101,331대 ÷ 3,158,598대)</td></tr>
<tr><td>충전 희망 비율</td><td>30% (10~100% 범위 제시)</td><td>근거 자료 없음, 민감도 분석으로 대체</td></tr>
<tr><td>급속 충전시간</td><td>중앙값 {s['fastcharge']['median']:.0f}분, 90분위 {s['fastcharge']['p90']:.0f}분</td><td>환경공단 충전건별 충전량 합성데이터 (2025.1~6, 공원주차장 유형)</td></tr>
<tr><td>방치 기준</td><td>급속 1시간, 완속 14시간</td><td>친환경자동차법 충전방해행위 기준 (2024.7 보도)</td></tr>
<tr><td>완속 출력</td><td>7kW</td><td>남2문 설치 완속 기준</td></tr>
</tbody></table>
<table><thead><tr><th>정제 단계</th><th>건수</th></tr></thead><tbody>
<tr><td>입출차 기록</td><td class=n>{q['rows_total']:,}</td></tr><tr><td>통과 차량(10분 미만) 제외</td><td class=n>{q['pass_under10']:,}</td></tr>
<tr><td>장기주차(3일 이상) 제외</td><td class=n>{q['over_3d']:,}</td></tr><tr><td>분석 대상 방문 차량</td><td class=n>{q['visits']:,}</td></tr></tbody></table>
<p class=note>한계: 입출차 데이터에 차종 정보가 없어 전기차 비율은 서울 평균을 가정했습니다. 2024년 7월 1개월·공원 전체 단위 예비 분석이며, 구역별 권고는 2025년 입출차정보(전체구역) 반영 후 발행합니다. 충전 이력은 합성데이터로 전국 평균 경향만 반영합니다.</p>
</div></body></html>"""
out = os.path.join(BASE, "report", "report.html")
open(out, "w", encoding="utf8").write(html)
print(out, round(cross30, 1), high)
