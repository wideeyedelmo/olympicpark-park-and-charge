"""
올림픽공원 Park & Charge - 분석 파이프라인

입력
  --parking   입출차 CSV (필수 컬럼: 입차일시, 출차일시 / 선택 컬럼: 주차구역)
              예) 한국체육산업개발_올림픽공원 입출차 정보(2024.7) 파일,
                  2025년 입출차정보(전체구역) API 수집 결과를 같은 컬럼으로 저장한 CSV
  --charging  환경공단 충전건별 충전량 합성데이터 zip 또는 csv
  --congestion 주차장 혼잡도 정보 CSV (선택)
  --out       결과 폴더

출력
  summary.json            대시보드·리포트가 읽는 집계 결과
  dwell_hist.csv          체류시간·급속 충전시간 분포(10분 구간, %)
  hourly_occupancy.csv    평일·주말 시간대별 평균 동시 주차대수
  scenarios.csv           전기차 비율·충전 희망 비율별 필요 완속 수
  zone_summary.csv        (주차구역 컬럼이 있을 때) 구역별 체류 구간 비중·피크

정제 규칙
  - 체류 10분 미만: 통과·회차 차량으로 분리(분석 제외)
  - 체류 3일 이상: 장기주차로 분리(분석 제외)
  - 출차일시 결측, 출차가 입차보다 빠른 건: 제외
판정 기준
  - 급속형 < 42분 <= 혼합형 < 102분 <= 완속형
    (42분 = 급속 충전시간 90분위, 102분 = 42분 + 급속 방치 허용 1시간)
"""
import argparse, json, os, zipfile
import numpy as np
import pandas as pd

FAST_P90 = None  # 합성데이터에서 산출
PASS_MIN = 10
LONG_MIN = 3 * 24 * 60
EV_RATIOS = [0.032, 0.064, 0.096]
WISH = [0.1, 0.3, 0.5, 1.0]


def read_csv_any(path, **kw):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없음: {path}")


def load_parking(path):
    d = read_csv_any(path)
    d["in"] = pd.to_datetime(d["입차일시"], errors="coerce")
    d["out"] = pd.to_datetime(d["출차일시"], errors="coerce")
    d["dw"] = (d["out"] - d["in"]).dt.total_seconds() / 60
    q = {
        "rows_total": int(len(d)),
        "missing_out": int(d["out"].isna().sum()),
        "negative": int((d["dw"] < 0).sum()),
        "pass_under10": int((d["dw"] < PASS_MIN).sum()),
        "over_24h": int((d["dw"] >= 1440).sum()),
        "over_3d": int((d["dw"] >= LONG_MIN).sum()),
    }
    v = d[(d["dw"] >= PASS_MIN) & (d["dw"] < LONG_MIN)].copy()
    q["visits"] = int(len(v))
    return v, q


def load_charging(path):
    cols = ["충전소 유형(소분류)", "충전시간", "충전기용량(KW)", "충전시작일시"]
    frames = []
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        with z.open(z.namelist()[0]) as f:
            for ch in pd.read_csv(f, encoding="utf-8-sig", usecols=cols, dtype=str, chunksize=1_000_000):
                frames.append(ch[ch["충전소 유형(소분류)"] == "공원주차장"])
    else:
        for ch in pd.read_csv(path, encoding="utf-8-sig", usecols=cols, dtype=str, chunksize=1_000_000):
            frames.append(ch[ch["충전소 유형(소분류)"] == "공원주차장"])
    k = pd.concat(frames)
    hms = k["충전시간"].str.split(":", expand=True).astype(int)
    k["min"] = hms[0] * 60 + hms[1] + hms[2] / 60
    return k


def occupancy(df, grid):
    ins = np.sort(df["in"].values)
    outs = np.sort(df["out"].values)
    return pd.Series(np.searchsorted(ins, grid.values, "right") - np.searchsorted(outs, grid.values, "right"), index=grid)


def daily_peaks(o):
    dm = o.groupby(o.index.date).max()
    we = np.array([pd.Timestamp(x).dayofweek >= 5 for x in dm.index])
    return {
        "weekday_median": float(np.median(dm[~we])) if (~we).any() else None,
        "weekend_median": float(np.median(dm[we])) if we.any() else None,
        "p95": float(np.percentile(dm, 95)),
        "max": float(dm.max()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parking", required=True)
    ap.add_argument("--charging", required=True)
    ap.add_argument("--congestion")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    v, q = load_parking(a.parking)
    k = load_charging(a.charging)
    fast_med = float(k["min"].median())
    fast_p90 = float(np.round(k["min"].quantile(0.9)))
    long_thr = fast_p90 + 60

    days = v["in"].dt.normalize().nunique()
    band = pd.cut(v["dw"], [PASS_MIN, fast_p90, long_thr, np.inf], right=False, labels=["fast", "mixed", "slow"])
    shares = (band.value_counts(normalize=True) * 100).round(1).to_dict()

    start = v["in"].min().normalize() + pd.Timedelta(days=1)  # 첫날은 전날 입차분이 빠져 제외
    end = v["in"].max().normalize() + pd.Timedelta(hours=23, minutes=50)
    grid = pd.date_range(start, end, freq="10min")

    o_all = occupancy(v, grid)
    o_slow = occupancy(v[v["dw"] >= long_thr], grid)
    o_mixed = occupancy(v[(v["dw"] >= fast_p90) & (v["dw"] < long_thr)], grid)
    fast_daily = float(len(v[v["dw"] < fast_p90]) / days)

    we = o_all.index.dayofweek >= 5
    key = o_all.index.hour + o_all.index.minute / 60
    hourly = pd.DataFrame({
        "time": sorted(set(key)),
    })
    hourly["weekday"] = hourly["time"].map(o_all[~we].groupby(key[~we]).mean()).round(1)
    hourly["weekend"] = hourly["time"].map(o_all[we].groupby(key[we]).mean()).round(1)
    hourly.to_csv(os.path.join(a.out, "hourly_occupancy.csv"), index=False, encoding="utf-8-sig")

    bins = np.arange(0, 310, 10)
    hv, _ = np.histogram(v["dw"].clip(upper=300), bins=bins)
    hk, _ = np.histogram(k["min"].clip(upper=300), bins=bins)
    hist = pd.DataFrame({"from_min": bins[:-1], "dwell_pct": (hv / len(v) * 100).round(2), "fastcharge_pct": (hk / len(k) * 100).round(2)})
    hist.to_csv(os.path.join(a.out, "dwell_hist.csv"), index=False, encoding="utf-8-sig")

    peaks_slow = daily_peaks(o_slow)
    rows = []
    for r in EV_RATIOS:
        for w in WISH:
            rows.append({
                "ev_ratio": r, "wish": w,
                "slow_need_weekday": round(peaks_slow["weekday_median"] * r * w, 1),
                "slow_need_weekend": round(peaks_slow["weekend_median"] * r * w, 1),
                "slow_need_p95": round(peaks_slow["p95"] * r * w, 1),
                "fast_hours_per_day": round(fast_daily * r * w * fast_med / 60, 1),
            })
    pd.DataFrame(rows).to_csv(os.path.join(a.out, "scenarios.csv"), index=False, encoding="utf-8-sig")

    summary = {
        "period": [str(v["in"].min().date()), str(v["in"].max().date())],
        "quality": q,
        "visits_per_day": round(len(v) / days),
        "dwell": {
            "median": float(v["dw"].median()), "p25": float(v["dw"].quantile(0.25)), "p75": float(v["dw"].quantile(0.75)),
            "weekday_median": float(v.loc[v["in"].dt.dayofweek < 5, "dw"].median()),
            "weekend_median": float(v.loc[v["in"].dt.dayofweek >= 5, "dw"].median()),
            "over_14h": int((v["dw"] > 840).sum()), "over_14h_pct": round(float((v["dw"] > 840).mean() * 100), 1),
        },
        "fastcharge": {"sessions": int(len(k)), "median": fast_med, "p90": fast_p90,
                       "kw_share": (k["충전기용량(KW)"].value_counts(normalize=True) * 100).round(1).head(3).to_dict()},
        "thresholds": {"fast_lt": fast_p90, "slow_ge": long_thr},
        "band_share": {"fast": shares.get("fast"), "mixed": shares.get("mixed"), "slow": shares.get("slow")},
        "peaks": {"all": daily_peaks(o_all), "slow": peaks_slow, "mixed": daily_peaks(o_mixed)},
        "hourly_peak": {
            "weekday": {"value": float(hourly["weekday"].max()), "time": float(hourly.loc[hourly["weekday"].idxmax(), "time"])},
            "weekend": {"value": float(hourly["weekend"].max()), "time": float(hourly.loc[hourly["weekend"].idxmax(), "time"])},
        },
        "fast_type_daily_entries": round(fast_daily),
    }

    if "주차구역" in v.columns:
        zrows = []
        for z, g in v.groupby("주차구역"):
            b = pd.cut(g["dw"], [PASS_MIN, fast_p90, long_thr, np.inf], right=False, labels=["fast", "mixed", "slow"]).value_counts(normalize=True) * 100
            pk = daily_peaks(occupancy(g[g["dw"] >= long_thr], grid))
            zrows.append({"zone": z, "visits": len(g), "dwell_median": g["dw"].median(),
                          "fast_pct": round(b.get("fast", 0), 1), "mixed_pct": round(b.get("mixed", 0), 1), "slow_pct": round(b.get("slow", 0), 1),
                          "slow_peak_weekday": pk["weekday_median"], "slow_peak_p95": pk["p95"]})
        pd.DataFrame(zrows).to_csv(os.path.join(a.out, "zone_summary.csv"), index=False, encoding="utf-8-sig")
        summary["zones"] = zrows

    if a.congestion:
        c = read_csv_any(a.congestion)
        ct = c.groupby(["주차구역", "혼잡도"]).size().unstack(fill_value=0)
        summary["congestion"] = {
            "period": [str(c["등록일"].min()), str(c["등록일"].max())],
            "by_zone": {z: {k2: int(vv) for k2, vv in row.items()} for z, row in ct.iterrows()},
        }

    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
    print(json.dumps({k3: summary[k3] for k3 in ["period", "visits_per_day", "dwell", "band_share", "thresholds"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
