// 정식 호스트 리다이렉트. *.pages.dev(프로덕션·프리뷰 별칭)와 www 는
// 같은 경로·쿼리로 https://magampan.com 에 301 한다. 중복 색인을 막는다.
export const CANONICAL_HOST = "magampan.com";

export function canonicalRedirect(url, canonicalHost = CANONICAL_HOST) {
  const u = new URL(url);
  const host = u.hostname.toLowerCase();
  if (host === canonicalHost && u.protocol === "https:") return null;
  const alias =
    host === canonicalHost ||
    host === "www." + canonicalHost ||
    host.endsWith(".pages.dev");
  if (!alias) return null; // localhost·wrangler dev 등은 그대로 둔다
  return "https://" + canonicalHost + u.pathname + u.search;
}

export function hostMiddleware(context) {
  const to = canonicalRedirect(context.request.url);
  if (to) {
    return new Response(null, {
      status: 301,
      headers: { location: to, "cache-control": "public, max-age=3600" },
    });
  }
  return context.next();
}
