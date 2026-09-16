# -*- coding: utf-8 -*-
"""필터 URL 왕복. 새로고침·공유가 같은 목록을 복원하는 계약."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import urlstate


def test_grant_roundtrip_multi_and_aliases():
    raw = "q=특례보증&region=서울,경기&field=금융&deadline=week&org=충청남도&amount=10to50&src=bizinfo"
    st = urlstate.parse_grant(raw)
    assert st["q"] == "특례보증"
    assert st["region"] == ["서울", "경기"]
    assert st["field"] == ["금융"]
    assert st["deadline"] == ["week"]
    assert st["org"] == ["충청남도"]
    assert st["amount"] == ["10to50"]
    assert st["src"] == "bizinfo"
    assert st["open"] is True
    back = urlstate.serialize_grant(st)
    again = urlstate.parse_grant(back)
    assert again["region"] == st["region"]
    assert again["field"] == st["field"]
    assert again["deadline"] == st["deadline"]
    assert again["amount"] == st["amount"]
    assert "category=" not in back
    assert "field=금융" in back or "field=" in back
    alias = urlstate.parse_grant("category=창업&due=today")
    assert alias["field"] == ["창업"]
    assert alias["deadline"] == ["today"]
    locked = urlstate.serialize_grant(st, locked={"region": True})
    assert "region=" not in locked
    assert "field=" in locked


def test_grant_open_default_omitted_and_false_emitted():
    qs = urlstate.serialize_grant({"q": "a", "open": True, "sort": "dday"})
    assert "open=" not in qs
    assert "sort=" not in qs
    qs0 = urlstate.serialize_grant({"q": "a", "open": False})
    assert "open=0" in qs0
    st = urlstate.parse_grant("q=a&open=0")
    assert st["open"] is False


def test_bid_roundtrip_kind_and_due_alias():
    raw = "q=용역&kind=goods,service&deadline=today&org=중구청&amount=gte100&region=서울"
    st = urlstate.parse_bid(raw)
    assert st["kind"] == ["goods", "service"]
    assert st["deadline"] == ["today"]
    assert st["org"] == ["중구청"]
    again = urlstate.parse_bid(urlstate.serialize_bid(st))
    assert again["kind"] == st["kind"]
    assert again["amount"] == ["gte100"]
    due = urlstate.parse_bid("due=week&kind=construction")
    assert due["deadline"] == ["week"]
    assert due["kind"] == ["construction"]
    locked = urlstate.serialize_bid(st, locked={"kind": True})
    assert "kind=" not in locked


def test_js_state_roundtrip_if_node():
    import json
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        return
    root = os.path.join(os.path.dirname(__file__), "..")
    state_path = os.path.join(root, "static", "state.js")
    script = f"""
const fs = require('fs');
const vm = require('vm');
const ctx = {{ window: {{}}, console, URLSearchParams }};
vm.runInNewContext(fs.readFileSync({json.dumps(state_path)}, 'utf8'), ctx);
const S = ctx.window.MagampanState;
const g = S.parseGrant('q=특례&region=서울,경기&field=금융&deadline=week&org=중기부&amount=10to50&open=0');
const qs = S.serializeGrant(g);
const g2 = S.parseGrant(qs);
if (g2.q !== '특례') process.exit(2);
if (g2.region.join(',') !== '서울,경기') process.exit(3);
if (g2.field.join(',') !== '금융') process.exit(4);
if (g2.deadline.join(',') !== 'week') process.exit(5);
if (g2.open !== false) process.exit(6);
const b = S.parseBid('kind=goods,service&due=today&q=용역');
const bqs = S.serializeBid(b);
const b2 = S.parseBid(bqs);
if (b2.kind.join(',') !== 'goods,service') process.exit(7);
if (b2.deadline.join(',') !== 'today') process.exit(8);
process.stdout.write(JSON.stringify({{ grant: qs, bid: bqs }}));
"""
    r = subprocess.run(
        [node, "-e", script],
        cwd=root, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert "region=" in data["grant"]
    assert "field=" in data["grant"]
    assert "kind=" in data["bid"]


def test_describe_does_not_invent():
    assert urlstate.describe_grant({}) == "전체"
    assert "검색" in urlstate.describe_grant({"q": "보증"})
    assert urlstate.describe_bid({}) == "입찰 전체"


if __name__ == "__main__":
    test_grant_roundtrip_multi_and_aliases()
    test_grant_open_default_omitted_and_false_emitted()
    test_bid_roundtrip_kind_and_due_alias()
    test_describe_does_not_invent()
    test_js_state_roundtrip_if_node()
    print("urlstate tests ok")
