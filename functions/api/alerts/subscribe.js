import { handleSubscribe } from "../../../lib/alert_signup.mjs";

export function onRequestPost(context) {
  return handleSubscribe(context.request, context.env);
}

export function onRequestGet() {
  return new Response(
    JSON.stringify({
      ok: false,
      status: "method",
      message: "POST로 신청해 주세요.",
    }),
    {
      status: 405,
      headers: {
        "content-type": "application/json; charset=utf-8",
        allow: "POST",
        "cache-control": "no-store",
        "x-robots-tag": "noindex",
      },
    },
  );
}
