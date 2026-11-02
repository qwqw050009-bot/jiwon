import assert from "node:assert/strict";
import test from "node:test";
import { goneTarget, goneMiddleware, _resetCache } from "./gone_redirect.mjs";

const G = { hubs: ["/region/seoul/", "/category/startup/", "/bid/kind/goods/"],
            n: { abc: "/category/startup/" }, b: { "R1-000": "/bid/kind/goods/" } };

test("사라진 지원 공고: 아는 id 는 분야 허브, 모르면 홈", () => {
  assert.equal(goneTarget("/notice/abc/", G), "/category/startup/");
  assert.equal(goneTarget("/notice/zzz/", G), "/");
  assert.equal(goneTarget("/notice/zzz", G), "/");
});
test("사라진 입찰: 종류 허브, 모르면 /bid/", () => {
  assert.equal(goneTarget("/bid/notice/R1-000/", G), "/bid/kind/goods/");
  assert.equal(goneTarget("/bid/notice/X/", G), "/bid/");
});
test("허브 조합은 가장 가까운 상위 허브", () => {
  assert.equal(goneTarget("/region/seoul/gangnam/startup/", G), "/region/seoul/");
  assert.equal(goneTarget("/region/nowhere/", G), "/region/");
  assert.equal(goneTarget("/bid/kind/goods/old/", G), "/bid/kind/goods/");
  assert.equal(goneTarget("/bid/region/x/", G), "/bid/");
  assert.equal(goneTarget("/guide/old-slug/", G), "/guide/");
});
test("그 밖의 경로는 404 유지", () => {
  assert.equal(goneTarget("/random/", G), null);
  assert.equal(goneTarget("/wp-login.php", G), null);
});
test("미들웨어: 404 만 301, 200 은 그대로", async () => {
  _resetCache();
  const env = { ASSETS: { fetch: async () => new Response(JSON.stringify(G)) } };
  const ctx = (p, m = "GET") => ({ request: new Request("https://magampan.com" + p, { method: m }), env });
  const r = await goneMiddleware(ctx("/notice/abc/"), new Response("x", { status: 404 }));
  assert.equal(r.status, 301);
  assert.equal(r.headers.get("location"), "/category/startup/");
  const ok = new Response("x", { status: 200 });
  assert.equal(await goneMiddleware(ctx("/notice/abc/"), ok), ok);
  const post = new Response("x", { status: 404 });
  assert.equal(await goneMiddleware(ctx("/notice/abc/", "POST"), post), post);
  const api = new Response("x", { status: 404 });
  assert.equal(await goneMiddleware(ctx("/api/x/"), api), api);
});
