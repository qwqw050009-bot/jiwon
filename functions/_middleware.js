import { hostMiddleware } from "../lib/host_redirect.mjs";
import { goneMiddleware } from "../lib/gone_redirect.mjs";

// 모든 요청(정적 파일 포함)에 앞서 호스트를 확인한다.
// magampan.com 이면 next() — api/alerts/* 등 기존 함수·정적 파일이 이어서 처리한다.
// 정적 파일이 404 면 gone.json 으로 사라진 URL 을 가장 가까운 허브로 301 한다.
export async function onRequest(context) {
  const res = await hostMiddleware(context);
  if (!res || res.status === 301) return res;
  return goneMiddleware(context, res);
}
