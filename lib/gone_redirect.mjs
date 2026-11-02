// 사라진 URL 301. 정적 파일이 404 를 낼 때만 동작한다(살아 있는 페이지는 건드리지 않음).
// Cloudflare 정적 _redirects 는 2,000 개 한도라 예전 상세 URL 수천 개를 다 못 담는다.
// 빌드가 dist/gone.json 을 쓰고, 여기서 패턴별 가장 가까운 허브로 보낸다.
//   /notice/<id>/      → 그 공고의 분야 허브(알면) 없으면 /
//   /bid/notice/<id>/  → 그 입찰의 종류 허브(알면) 없으면 /bid/
//   /region/a/b/...    → 존재하는 가장 가까운 상위 허브 (/region/a/ → /region/)
//   /category/x/..., /bid/kind/x/..., /bid/region/x/..., /guide/x/ 도 같은 방식
// 그 밖의 경로는 404 그대로.
export const GONE_JSON = "/gone.json";
const HUB_PREFIXES = ["/region/", "/category/", "/bid/", "/guide/"];

export function goneTarget(pathname, gone) {
  gone = gone || {};
  const hubs = new Set(gone.hubs || []);
  let p = pathname;
  if (!p.endsWith("/") && !/\.[a-z0-9]+$/i.test(p)) p += "/";
  let m = p.match(/^\/notice\/([^/]+)\/$/);
  if (m) return (gone.n || {})[m[1]] || "/";
  m = p.match(/^\/bid\/notice\/([^/]+)\/$/);
  if (m) return (gone.b || {})[m[1]] || "/bid/";
  if (!HUB_PREFIXES.some((x) => p.startsWith(x))) return null;
  const parts = p.split("/").filter(Boolean);
  while (parts.length > 1) {
    parts.pop();
    const up = "/" + parts.join("/") + "/";
    if (hubs.has(up) || up === "/bid/" || up === "/region/" || up === "/category/" || up === "/guide/") {
      return up === p ? null : up;
    }
  }
  return null;
}

let cache = null;
async function loadGone(context) {
  if (cache) return cache;
  try {
    const env = context.env || {};
    const url = new URL(GONE_JSON, context.request.url);
    const res = env.ASSETS ? await env.ASSETS.fetch(url) : await fetch(url);
    cache = res.ok ? await res.json() : {};
  } catch {
    cache = {};
  }
  return cache;
}

export function _resetCache() { cache = null; }

export async function goneMiddleware(context, res) {
  const method = context.request.method;
  if (res.status !== 404 || (method !== "GET" && method !== "HEAD")) return res;
  const u = new URL(context.request.url);
  if (u.pathname.startsWith("/api/")) return res;
  const to = goneTarget(u.pathname, await loadGone(context));
  if (!to) return res;
  return new Response(null, {
    status: 301,
    headers: { location: to + u.search, "cache-control": "public, max-age=86400" },
  });
}
