"""IndexNow 제출 (배포 뒤 실행).

예전에는 빌드 중(배포 전)에 전체 URL 1만여 개를 한 번에 보내 400 을 받았다.
- 프로토콜 상한은 요청당 10,000 URL. 나눠 보낸다.
- 바뀐 URL(최근 lastmod)과 허브만 보낸다. 매일 전체를 다시 보내지 않는다.
- 키 파일이 실제로 배포된 뒤에 보낸다(워크플로 deploy 다음 alert digest 단계가 호출).
실패해도 빌드를 깨지 않는다.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: E402
import deadline as dl  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10000
LIST_PATH = os.path.join(os.path.dirname(__file__), "..", "build", "indexnow_urls.json")
HUBS = ("/", "/all/", "/new/", "/urgent/", "/bid/", "/bid/urgent/")


def changed_urls(urls, meta, today, days=1):
    cutoff = (today - timedelta(days=days)).isoformat()
    out = [u for u in HUBS if u in urls]
    out += [u for u in urls if u not in out and ((meta.get(u) or {}).get("lastmod") or "") >= cutoff]
    return out


def save_list(urls, meta, today):
    os.makedirs(os.path.dirname(LIST_PATH), exist_ok=True)
    with open(LIST_PATH, "w", encoding="utf-8") as f:
        json.dump(changed_urls(urls, meta, today), f, ensure_ascii=False)


def payloads(paths, domain, key):
    host = domain.split("//")[-1].rstrip("/")
    for i in range(0, len(paths), BATCH):
        yield {
            "host": host,
            "key": key,
            "keyLocation": f"{domain}/{key}.txt",
            "urlList": [domain + p for p in paths[i:i + BATCH]],
        }


def submit(paths, domain=None, key=None, opener=urllib.request.urlopen):
    domain = domain or config.SITE["domain"]
    key = key or config.INDEXNOW_KEY
    ok = True
    for body in payloads(paths, domain, key):
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with opener(req, timeout=30) as r:
                print(f"IndexNow 제출: status={r.status}, {len(body['urlList'])}개 URL")
        except urllib.error.HTTPError as e:
            ok = False
            detail = e.read()[:300].decode("utf-8", "replace") if hasattr(e, "read") else ""
            print(f"IndexNow 실패: HTTP {e.code} {detail}")
        except Exception as e:  # 네트워크 오류도 빌드를 막지 않는다
            ok = False
            print(f"IndexNow 실패: {e}")
    return ok


def main():
    if not config.SITE.get("allow_index"):
        print("색인 비허용: IndexNow 건너뜀")
        return
    try:
        paths = json.load(open(LIST_PATH, encoding="utf-8"))
    except Exception as e:
        print(f"IndexNow 목록 없음: {e}")
        return
    if not paths:
        print("IndexNow: 바뀐 URL 없음")
        return
    submit(paths)


if __name__ == "__main__":
    main()
