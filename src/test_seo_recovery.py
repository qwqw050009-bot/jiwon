import json, os, sys, tempfile, unittest
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))
import bidinfo
import build


class BidArchiveTest(unittest.TestCase):
    def _row(self, i, close):
        return {"id": f"R{i}-000", "bid_no": f"R{i}", "seq": "000", "title": f"용역 {i}",
                "kind": "용역", "org": "기관", "close_dt": close.strftime("%Y-%m-%d %H:%M"),
                "open_dt": (close - timedelta(days=10)).strftime("%Y-%m-%d %H:%M")}

    def test_closed_bids_kept_180_days(self):
        now = bidinfo.now_kst(datetime(2026, 10, 13, 12, 0, tzinfo=bidinfo.KST))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.json")
            old = [self._row(1, now - timedelta(days=10)),
                   self._row(2, now - timedelta(days=200))]
            with open(p, "w") as f:
                json.dump(old, f)
            live = [self._row(3, now + timedelta(days=3))]
            out = bidinfo.archived_bids(live, now=now, path=p, save=True)
            self.assertEqual([r["id"] for r in out], ["R1-000"])
            self.assertEqual(out[0]["dlabel"], "마감")
            self.assertEqual(out[0]["status"], "closed")
            with open(p) as f:
                saved = {r["id"] for r in json.load(f)}
            self.assertIn("R3-000", saved)
            self.assertNotIn("R2-000", saved)


class NoticeCapTest(unittest.TestCase):
    def test_cap_raised(self):
        self.assertGreaterEqual(build.MAX_ARCHIVED, 5000)


class RedirectGuardTest(unittest.TestCase):
    def test_gone_redirects_prioritize_recent_and_budget(self):
        known = {"/notice/a/": "2026-10-01", "/notice/b/": "2026-09-01",
                 "/bid/notice/x/": "2026-10-05", "/notice/live/": "2026-10-13",
                 "/region/seoul/": "2026-10-13"}
        out = build.gone_redirects(known, ["/notice/live/"], 2)
        self.assertEqual(out, [("/bid/notice/x/", "/bid/"), ("/notice/a/", "/")])
        self.assertEqual(build.gone_redirects(known, [], 0), [])

    def test_detail_guard(self):
        self.assertIsNone(build.detail_guard(900, [1000, None]))
        self.assertIsNotNone(build.detail_guard(700, [1000, 600]))
        self.assertIsNone(build.detail_guard(5, [0, None]))


if __name__ == "__main__":
    unittest.main()
