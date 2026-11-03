"""
한국환경공단_전기자동차 충전소 정보 API(getChargerInfo)로 송파구 충전기를 받아
올림픽공원 주변 충전기만 골라 저장합니다.

사용: EV_API_KEY=발급받은키 python analysis/collect_chargers.py --out data
인증키는 코드나 저장소에 넣지 말고 환경변수로만 전달합니다.
"""
import argparse, json, math, os, time
import requests

URL = "https://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
PARK_CENTER = (37.5206, 127.1215)   # 올림픽공원 중심(대략)
RADIUS_M = 1200                      # 공원 외곽 주차장 포함 반경
TYPE = {"01": "DC차데모", "02": "AC완속", "03": "DC차데모+AC3상", "04": "DC콤보", "05": "DC차데모+DC콤보",
        "06": "DC차데모+AC3상+DC콤보", "07": "AC3상", "08": "DC콤보(완속)", "09": "NACS", "10": "DC콤보+NACS"}
STAT = {"1": "통신이상", "2": "충전대기", "3": "충전중", "4": "운영중지", "5": "점검중", "9": "상태미확인"}


def dist_m(a, b):
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def get(params):
    for i in range(6):
        try:
            r = requests.get(URL, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print("retry", type(e).__name__)
            time.sleep(6)
    raise SystemExit("API 호출 실패")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    key = os.environ["EV_API_KEY"]
    items, page = [], 1
    while True:
        j = get({"serviceKey": key, "pageNo": page, "numOfRows": 1000, "zcode": "11", "zscode": "11710", "dataType": "JSON"})
        got = j["items"]["item"]
        items += got
        total = int(j["totalCount"])
        if len(items) >= total or not got:
            break
        page += 1
    near = []
    for it in items:
        try:
            d = dist_m(PARK_CENTER, (float(it["lat"]), float(it["lng"])))
        except ValueError:
            continue
        if d <= RADIUS_M and it.get("delYn") != "Y":
            near.append({
                "statNm": it["statNm"], "statId": it["statId"], "chgerId": it["chgerId"],
                "type": TYPE.get(it["chgerType"], it["chgerType"]),
                "fast": it["chgerType"] not in ("02", "08"),
                "output_kw": it.get("output"), "stat": STAT.get(it.get("stat"), it.get("stat")),
                "busiNm": it.get("busiNm"), "addr": it.get("addr"), "lat": it["lat"], "lng": it["lng"],
                "limitYn": it.get("limitYn"), "dist_m": round(d),
            })
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "chargers_near_park.json"), "w", encoding="utf-8") as f:
        json.dump({"collected_at": time.strftime("%Y-%m-%d %H:%M"), "songpa_total": len(items), "radius_m": RADIUS_M, "items": near},
                  f, ensure_ascii=False, indent=1)
    print("송파구", len(items), "/ 공원 반경", RADIUS_M, "m 이내", len(near))


if __name__ == "__main__":
    main()
