import assert from "node:assert/strict";
import test from "node:test";
import { canonicalRedirect, hostMiddleware } from "./host_redirect.mjs";

test("pages.dev 별칭과 프리뷰는 같은 경로로 301", () => {
  assert.equal(canonicalRedirect("https://jiwon-5i5.pages.dev/about/"), "https://magampan.com/about/");
  assert.equal(canonicalRedirect("https://abc123.jiwon-5i5.pages.dev/bid/?q=1"), "https://magampan.com/bid/?q=1");
});
test("www 와 http 는 apex https 로", () => {
  assert.equal(canonicalRedirect("https://www.magampan.com/x/"), "https://magampan.com/x/");
  assert.equal(canonicalRedirect("http://magampan.com/x/"), "https://magampan.com/x/");
});
test("정식 호스트와 로컬은 통과", () => {
  assert.equal(canonicalRedirect("https://magampan.com/api/alerts/subscribe"), null);
  assert.equal(canonicalRedirect("http://localhost:8788/"), null);
});
test("미들웨어: 별칭은 301, 정식은 next()", async () => {
  const r = await hostMiddleware({ request: new Request("https://jiwon-5i5.pages.dev/a/"), next: () => "NEXT" });
  assert.equal(r.status, 301);
  assert.equal(r.headers.get("location"), "https://magampan.com/a/");
  const n = await hostMiddleware({ request: new Request("https://magampan.com/api/alerts/confirm?t=1"), next: () => "NEXT" });
  assert.equal(n, "NEXT");
});
