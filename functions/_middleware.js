import { hostMiddleware } from "../lib/host_redirect.mjs";

// 모든 요청(정적 파일 포함)에 앞서 호스트를 확인한다.
// magampan.com 이면 그대로 next() — api/alerts/* 등 기존 함수가 이어서 처리한다.
export const onRequest = hostMiddleware;
