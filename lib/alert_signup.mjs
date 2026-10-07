/**
 * 키워드 알림 셀프 신청.
 *
 * 저장소는 Resend 연락처다. 키워드는 연락처 속성으로 둔다.
 *   keywords          확인된 키워드. 줄바꿈으로 구분
 *   pending_keyword   확인 메일을 기다리는 키워드 하나
 *   confirm_token     확인 링크 토큰
 *   blocked_keywords  수신 거부한 키워드. 시크릿 명단과 합칠 때 다시 넣지 않는다
 *
 * 확인 전 연락처는 unsubscribed=true 라 다이제스트가 보내지 않는다.
 * 수신 거부 토큰은 "<소문자 이메일>\n<키워드>" 의 HMAC-SHA256.
 * Python src/alert_digest.py sign_unsubscribe 과 바이트가 같다.
 *
 * 확인·수신 거부 GET 은 안내만 하고, POST 가 상태를 바꾼다.
 * 메일 앱의 링크 미리보기가 신청을 켜거나 끄지 않게 하기 위해서다.
 */
const RESEND = "https://api.resend.com";
export const SITE_ORIGIN = "https://magampan.com";
export const SITE_EMAIL = "qwqw050009@gmail.com";
const SITE_NAME = "지원사업 마감판";
const FROM_DEFAULT = "마감판 <alerts@magampan.com>";
const MAX_KEYWORDS = 12;
const MAX_BLOCKED = 20;

export const PROPS = {
  keywords: "keywords",
  pending: "pending_keyword",
  token: "confirm_token",
  blocked: "blocked_keywords",
};

export const MSG = {
  confirmSent:
    "확인 메일을 보냈습니다. 받은편지함(스팸함 포함)에서 링크를 눌러야 알림이 시작됩니다. 결제·계정은 없습니다.",
  already:
    "이미 이 키워드 알림을 받고 있습니다. 새 공고가 있으면 하루 1회 메일로 갑니다.",
  invalid: "이메일 주소와 키워드를 확인해 주세요. 키워드는 80자 이내여야 합니다.",
  rate: "같은 주소로 신청이 잠시 막혀 있습니다. 10분 뒤에 다시 시도해 주세요.",
  unconfigured:
    "알림 자동 등록이 아직 연결되지 않았습니다. 이메일과 키워드를 " +
    SITE_EMAIL +
    " 로 보내 주세요.",
  saveFailed:
    "신청을 저장하지 못했습니다. 잠시 뒤 다시 시도하거나 " +
    SITE_EMAIL +
    " 로 보내 주세요.",
  origin: "이 사이트에서만 신청할 수 있습니다.",
  tooMany:
    "키워드는 12개까지 받을 수 있습니다. 쓰던 키워드 알림을 끈 뒤 다시 신청해 주세요.",
  confirmBad:
    "확인 링크가 유효하지 않거나 이미 사용했습니다. 신청 화면에서 다시 요청해 주세요.",
  unsubBad: "수신 거부 링크가 유효하지 않습니다.",
};

export function confirmOk(keyword) {
  return (
    "알림을 켰습니다. 키워드 「" +
    keyword +
    "」에 맞는 새 공고가 있으면 하루 1회 메일로 보냅니다."
  );
}

export function confirmPrompt(keyword) {
  return (
    "키워드 「" +
    keyword +
    "」 알림을 시작하려면 아래 버튼을 누르세요. 누르기 전에는 메일이 나가지 않습니다."
  );
}

export function unsubOk(keyword) {
  return (
    "키워드 「" +
    keyword +
    "」 알림을 끊었습니다. 이 주소로는 그 키워드 메일을 다시 보내지 않습니다."
  );
}

export function unsubPrompt(keyword) {
  return "키워드 「" + keyword + "」 알림을 끊으려면 아래 버튼을 누르세요.";
}

let propsReady = false;

export function resetForTests() {
  propsReady = false;
}

export function normalizeKeyword(raw) {
  return String(raw == null ? "" : raw).replace(/\s+/g, " ").trim();
}

export function validEmail(raw) {
  const email = String(raw == null ? "" : raw).trim().toLowerCase();
  if (!email || email.length > 254) return "";
  if (!/^[a-z0-9._%+\-]+@[a-z0-9.-]+\.[a-z]{2,}$/.test(email)) return "";
  if (email.includes("..")) return "";
  return email;
}

export function validKeyword(raw) {
  const kw = normalizeKeyword(raw);
  if (!kw || kw.length > 80) return "";
  if (/[\u0000-\u001f\u007f]/.test(kw)) return "";
  return kw;
}

export function splitKeywords(raw) {
  const out = [];
  const seen = new Set();
  String(raw == null ? "" : raw).split("\n").forEach(function (part) {
    const kw = normalizeKeyword(part);
    if (!kw) return;
    const key = kw.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push(kw);
  });
  return out;
}

export function joinKeywords(list) {
  return splitKeywords((list || []).join("\n")).join("\n");
}

function sameKeyword(a, b) {
  return normalizeKeyword(a).toLowerCase() === normalizeKeyword(b).toLowerCase();
}

function addKeyword(list, kw) {
  const clean = normalizeKeyword(kw);
  if (!clean) return list.slice();
  if (list.some(function (item) { return sameKeyword(item, clean); })) return list.slice();
  return list.concat([clean]);
}

function removeKeyword(list, kw) {
  return list.filter(function (item) { return !sameKeyword(item, kw); });
}

export function propValue(contact, key) {
  const props = contact && contact.properties;
  if (!props || typeof props !== "object") return "";
  const raw = props[key];
  if (raw == null) return "";
  if (typeof raw === "string" || typeof raw === "number") return String(raw);
  if (typeof raw === "object" && raw.value != null) return String(raw.value);
  return "";
}

export function maskEmail(email) {
  const parts = String(email || "").split("@");
  if (!parts[0] || !parts[1]) return "***";
  return parts[0].slice(0, 1) + "***@" + parts[1];
}

function bytesToB64url(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function b64urlToString(s) {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const b64 = String(s).replace(/-/g, "+").replace(/_/g, "/") + pad;
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

function timingSafeEqual(a, b) {
  const aa = new TextEncoder().encode(String(a));
  const bb = new TextEncoder().encode(String(b));
  if (aa.length !== bb.length) return false;
  let out = 0;
  for (let i = 0; i < aa.length; i++) out |= aa[i] ^ bb[i];
  return out === 0;
}

export async function signUnsubscribe(secret, email, keyword) {
  const payload = String(email || "").trim().toLowerCase() + "\n" + normalizeKeyword(keyword);
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(String(secret || "")),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  const hex = Array.from(new Uint8Array(sig)).map(function (b) {
    return b.toString(16).padStart(2, "0");
  }).join("");
  return bytesToB64url(new TextEncoder().encode(payload)) + "." + hex;
}

export async function readUnsubscribe(secret, token) {
  const text = String(token || "");
  const dot = text.lastIndexOf(".");
  if (dot <= 0) return null;
  const sig = text.slice(dot + 1);
  if (!/^[0-9a-f]{64}$/.test(sig)) return null;
  let payload;
  try {
    payload = b64urlToString(text.slice(0, dot));
  } catch (err) {
    return null;
  }
  const nl = payload.indexOf("\n");
  if (nl <= 0) return null;
  const email = payload.slice(0, nl);
  const keyword = normalizeKeyword(payload.slice(nl + 1));
  if (!email || !keyword || payload.indexOf("\n", nl + 1) !== -1) return null;
  const expected = await signUnsubscribe(secret, email, keyword);
  const expSig = expected.slice(expected.lastIndexOf(".") + 1);
  if (!timingSafeEqual(expSig, sig)) return null;
  if (payload !== email + "\n" + keyword) return null;
  return { email: email, keyword: keyword };
}

export function createLimiter(limit, windowMs) {
  const buckets = new Map();
  return async function tooMany(key) {
    const now = Date.now();
    const prev = (buckets.get(key) || []).filter(function (t) { return now - t < windowMs; });
    if (prev.length >= limit) {
      buckets.set(key, prev);
      return true;
    }
    prev.push(now);
    buckets.set(key, prev);
    return false;
  };
}

const ipLimiter = createLimiter(10, 10 * 60 * 1000);
const emailLimiter = createLimiter(5, 60 * 60 * 1000);

export async function kvTooMany(kv, key, limit, ttlSec) {
  const cur = parseInt(await kv.get(key), 10) || 0;
  if (cur >= limit) return true;
  await kv.put(key, String(cur + 1), { expirationTtl: ttlSec });
  return false;
}

async function cacheTooMany(key, limit, ttlSec) {
  if (typeof caches === "undefined" || !caches.default) return false;
  const cache = caches.default;
  const req = new Request(SITE_ORIGIN + "/__alert_rl/" + encodeURIComponent(key), { method: "GET" });
  const hit = await cache.match(req);
  const cur = hit ? (parseInt(await hit.text(), 10) || 0) : 0;
  if (cur >= limit) return true;
  await cache.put(req, new Response(String(cur + 1), {
    headers: { "Cache-Control": "public, max-age=" + ttlSec },
  }));
  return false;
}

async function layerTooMany(env, key, limit, ttlSec) {
  let blocked = false;
  if (env && env.ALERTS_KV) {
    try {
      if (await kvTooMany(env.ALERTS_KV, key, limit, ttlSec)) blocked = true;
    } catch (err) {
      /* KV 가 없어도 신청은 받는다 */
    }
  }
  try {
    if (await cacheTooMany(key, limit, ttlSec)) blocked = true;
  } catch (err) {
    /* 캐시 API 는 있으면 쓰고, 없으면 메모리 한도만 쓴다 */
  }
  return blocked;
}

export async function defaultLimited(request, email, env) {
  const ip = clientIp(request);
  if (await ipLimiter(ip)) return true;
  if (await layerTooMany(env, "ip:" + ip, 10, 600)) return true;
  if (email) {
    if (await emailLimiter(email)) return true;
    if (await layerTooMany(env, "em:" + email, 5, 3600)) return true;
  }
  return false;
}

function clientIp(request) {
  return (
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("cf-connecting-ip") ||
    String(request.headers.get("x-forwarded-for") || "").split(",")[0].trim() ||
    "0"
  );
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function htmlPage(title, bodyHtml) {
  return (
    "<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"utf-8\">" +
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" +
    "<meta name=\"robots\" content=\"noindex\"><meta name=\"referrer\" content=\"no-referrer\">" +
    "<title>" + esc(title) + "</title><style>" +
    "body{margin:0;background:#F4F4F2;color:#1A1A1A;font:16px/1.65 system-ui,sans-serif}" +
    "main{max-width:36rem;margin:0 auto;padding:32px 20px}" +
    "h1{font-size:22px;line-height:1.35;letter-spacing:-.03em}" +
    "button{margin-top:8px;background:#2F5BEA;color:#fff;border:0;border-radius:999px;padding:12px 18px;font:inherit;font-weight:700;cursor:pointer}" +
    "a{color:#2F5BEA}p.note{color:#4E4E4A}</style></head><body><main><h1>" +
    esc(title) + "</h1>" + bodyHtml +
    "<p class=\"note\"><a href=\"" + SITE_ORIGIN + "/\" rel=\"noreferrer\">" + SITE_NAME + "</a></p>" +
    "</main></body></html>"
  );
}

function wantsJson(request) {
  const accept = (request && request.headers.get("accept")) || "";
  return accept.indexOf("application/json") !== -1;
}

export function respond(request, status, payload, forceHtml) {
  const headers = {
    "cache-control": "no-store",
    "x-robots-tag": "noindex",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
  };
  if (status === 429) headers["retry-after"] = "600";
  if (status === 405) headers.allow = "POST";
  const html = forceHtml || !wantsJson(request);
  if (html) {
    headers["content-type"] = "text/html; charset=utf-8";
    const title = payload.title || (payload.ok ? "알림" : "알림 신청");
    const inner = payload.html || ("<p>" + esc(payload.message || "") + "</p>");
    return new Response(htmlPage(title, inner), { status: status, headers: headers });
  }
  headers["content-type"] = "application/json; charset=utf-8";
  return new Response(JSON.stringify({
    ok: !!payload.ok,
    status: payload.status || "",
    message: payload.message || "",
  }), { status: status, headers: headers });
}

function result(request, status, ok, code, message) {
  return respond(request, status, {
    ok: ok,
    status: code,
    message: message,
    title: "알림 신청",
  }, false);
}

async function readPayload(request) {
  const type = ((request.headers.get("content-type") || "")).toLowerCase();
  if (type.indexOf("application/json") !== -1) {
    const text = await request.text();
    if (text.length > 8000) {
      const err = new Error("large");
      err.code = "large";
      throw err;
    }
    try {
      const data = JSON.parse(text || "{}");
      if (!data || typeof data !== "object" || Array.isArray(data)) return {};
      return data;
    } catch (err) {
      const bad = new Error("json");
      bad.code = "json";
      throw bad;
    }
  }
  try {
    const form = await request.formData();
    const out = {};
    for (const pair of form.entries()) {
      if (typeof pair[1] === "string") out[pair[0]] = pair[1];
    }
    return out;
  } catch (err) {
    return {};
  }
}

function field(request, payload, key) {
  try {
    const q = new URL(request.url).searchParams.get(key);
    if (q) return q;
  } catch (err) { /* ignore */ }
  if (payload && payload[key] != null) return String(payload[key]);
  return "";
}

function originOk(request) {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  let url;
  try { url = new URL(origin); } catch (err) { return false; }
  if (url.origin === SITE_ORIGIN || url.origin === "https://www.magampan.com") return true;
  if (url.origin === "https://jiwon-5i5.pages.dev") return true;
  if (url.protocol === "https:" && (url.hostname === "jiwon.pages.dev" || url.hostname.endsWith(".jiwon.pages.dev"))) {
    return true;
  }
  if (url.hostname === "localhost" || url.hostname === "127.0.0.1") return true;
  return false;
}

function fromAddr(env) {
  const raw = String((env && env.RESEND_FROM) || "").trim();
  if (!raw || /[\r\n]/.test(raw)) return FROM_DEFAULT;
  return raw;
}

function apiKey(env) {
  return String((env && env.RESEND_API_KEY) || "").trim();
}

function signingSecret(env) {
  return String((env && (env.ALERT_SIGNING_SECRET || env.RESEND_API_KEY)) || "").trim();
}

async function resend(env, method, path, body, fetchImpl) {
  const doFetch = fetchImpl || fetch;
  const init = {
    method: method,
    headers: {
      Authorization: "Bearer " + apiKey(env),
      Accept: "application/json",
    },
  };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const res = await doFetch(RESEND + path, init);
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); }
    catch (err) { data = { message: text.slice(0, 180) }; }
  }
  return { status: res.status, data: data };
}

function existsMessage(status, data) {
  if (status === 409) return true;
  const msg = JSON.stringify(data || "").toLowerCase();
  return msg.indexOf("already") !== -1 || msg.indexOf("exist") !== -1;
}

async function ensureProperties(env, fetchImpl) {
  if (propsReady) return;
  const keys = [PROPS.keywords, PROPS.pending, PROPS.token, PROPS.blocked];
  for (let i = 0; i < keys.length; i++) {
    const res = await resend(env, "POST", "/contact-properties", {
      key: keys[i],
      type: "string",
    }, fetchImpl);
    if (res.status >= 200 && res.status < 300) continue;
    if (existsMessage(res.status, res.data)) continue;
    console.error("alert signup property status", res.status);
    const err = new Error("properties");
    err.code = "resend";
    throw err;
  }
  propsReady = true;
}

function contactPath(email) {
  return "/contacts/" + encodeURIComponent(email).replace(/%40/g, "@");
}

async function getContact(env, email, fetchImpl) {
  const res = await resend(env, "GET", contactPath(email), undefined, fetchImpl);
  if (res.status === 404) return null;
  if (res.status >= 400) {
    console.error("alert signup get status", res.status);
    const err = new Error("get");
    err.code = "resend";
    throw err;
  }
  return res.data;
}

async function saveContact(env, email, body, exists, fetchImpl) {
  if (!exists) {
    const created = await resend(env, "POST", "/contacts", Object.assign({ email: email }, body), fetchImpl);
    if (created.status < 400) return created;
    if (!existsMessage(created.status, created.data)) {
      console.error("alert signup create status", created.status);
      const err = new Error("create");
      err.code = "resend";
      throw err;
    }
  }
  const updated = await resend(env, "PATCH", contactPath(email), body, fetchImpl);
  if (updated.status >= 400) {
    console.error("alert signup patch status", updated.status);
    const err = new Error("patch");
    err.code = "resend";
    throw err;
  }
  return updated;
}

async function sendMail(env, to, subject, text, html, fetchImpl) {
  const res = await resend(env, "POST", "/emails", {
    from: fromAddr(env),
    to: [to],
    subject: subject,
    text: text,
    html: html,
    reply_to: SITE_EMAIL,
  }, fetchImpl);
  if (res.status < 200 || res.status >= 300) {
    console.error("alert signup mail status", res.status);
    const err = new Error("mail");
    err.code = "resend";
    throw err;
  }
}

function defaultToken() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return bytesToB64url(bytes);
}

function fail(request, err, forceHtml) {
  if (err && err.code === "json") {
    return respond(request, 400, { ok: false, status: "invalid", message: MSG.invalid, title: "알림 신청" }, forceHtml);
  }
  if (err && err.code === "large") {
    return respond(request, 413, { ok: false, status: "invalid", message: MSG.invalid, title: "알림 신청" }, forceHtml);
  }
  console.error("alert signup failed", err && err.code ? err.code : "error");
  return respond(request, 502, { ok: false, status: "error", message: MSG.saveFailed, title: "알림 신청" }, forceHtml);
}

async function gate(request, env, deps, email) {
  const check = deps.limited || function (req, em) { return defaultLimited(req, em, env); };
  return check(request, email || "");
}

function postButton(action, label, fields) {
  const inputs = Object.keys(fields).map(function (key) {
    return "<input type=\"hidden\" name=\"" + esc(key) + "\" value=\"" + esc(fields[key]) + "\">";
  }).join("");
  return (
    "<form method=\"post\" action=\"" + esc(action) + "\">" + inputs +
    "<button type=\"submit\">" + esc(label) + "</button></form>"
  );
}

export async function handleSubscribe(request, env, deps) {
  deps = deps || {};
  const fetchImpl = deps.fetch;
  try {
    if (!originOk(request)) {
      return result(request, 403, false, "origin", MSG.origin);
    }
    const payload = await readPayload(request);
    const email = validEmail(payload.email);
    const keyword = validKeyword(payload.keyword);
    if (await gate(request, env, deps, email)) {
      return result(request, 429, false, "rate_limited", MSG.rate);
    }
    if (!email || !keyword) return result(request, 400, false, "invalid", MSG.invalid);
    if (String(payload._gotcha || "").trim()) {
      return result(request, 200, true, "confirm_sent", MSG.confirmSent);
    }
    if (!apiKey(env)) return result(request, 503, false, "unconfigured", MSG.unconfigured);
    await ensureProperties(env, fetchImpl);
    const contact = await getContact(env, email, fetchImpl);
    const active = contact && contact.unsubscribed !== true
      ? splitKeywords(propValue(contact, PROPS.keywords))
      : [];
    if (active.some(function (item) { return sameKeyword(item, keyword); })) {
      return result(request, 200, true, "already", MSG.already);
    }
    if (active.length >= MAX_KEYWORDS) {
      return result(request, 400, false, "limit", MSG.tooMany);
    }
    const token = (deps.randomToken || defaultToken)();
    const properties = {};
    properties[PROPS.pending] = keyword;
    properties[PROPS.token] = token;
    await saveContact(env, email, {
      unsubscribed: active.length === 0,
      properties: properties,
    }, !!contact, fetchImpl);
    const link = SITE_ORIGIN + "/api/alerts/confirm?" + new URLSearchParams({ e: email, t: token }).toString();
    const text = [
      SITE_NAME + " 알림 확인",
      "",
      "키워드 「" + keyword + "」 마감 알림을 신청했습니다.",
      "아래 주소를 열고 「알림 시작」 버튼을 눌러야 메일이 시작됩니다.",
      "버튼을 누르기 전에는 알림을 보내지 않습니다.",
      "",
      link,
      "",
      "본인이 신청하지 않았다면 이 메일을 무시하세요.",
      "하루 1회, 키워드에 맞는 새 공고가 있을 때만 보냅니다. 결제는 없습니다.",
    ].join("\n");
    const html =
      "<p>" + esc(SITE_NAME) + " 알림 확인</p>" +
      "<p>키워드 「" + esc(keyword) + "」 마감 알림을 신청했습니다.</p>" +
      "<p>아래 링크를 열고 「알림 시작」 버튼을 눌러야 메일이 시작됩니다. 버튼을 누르기 전에는 알림을 보내지 않습니다.</p>" +
      "<p><a href=\"" + esc(link) + "\">알림 신청 확인</a></p>" +
      "<p>본인이 신청하지 않았다면 이 메일을 무시하세요. 하루 1회, 키워드에 맞는 새 공고가 있을 때만 보냅니다. 결제는 없습니다.</p>";
    await sendMail(env, email, "[" + SITE_NAME + "] 알림 신청을 확인해 주세요", text, html, fetchImpl);
    return result(request, 200, true, "confirm_sent", MSG.confirmSent);
  } catch (err) {
    return fail(request, err, false);
  }
}

export async function handleConfirm(request, env, deps) {
  deps = deps || {};
  const method = String(request.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "POST") {
    return respond(request, 405, { ok: false, status: "method", message: "확인할 수 없습니다.", title: "알림 확인" }, true);
  }
  try {
    const payload = method === "POST" ? await readPayload(request) : {};
    const email = validEmail(field(request, payload, "e") || field(request, payload, "email"));
    const token = String(field(request, payload, "t") || field(request, payload, "token") || "").trim();
    if (method === "POST" && await gate(request, env, deps, email)) {
      return respond(request, 429, { ok: false, status: "rate_limited", message: MSG.rate, title: "알림 확인" }, true);
    }
    if (!email || !token) {
      return respond(request, 400, { ok: false, status: "invalid", message: MSG.confirmBad, title: "알림 확인" }, true);
    }
    if (!apiKey(env)) {
      return respond(request, 503, { ok: false, status: "unconfigured", message: MSG.unconfigured, title: "알림 확인" }, true);
    }
    await ensureProperties(env, deps.fetch);
    const contact = await getContact(env, email, deps.fetch);
    const pending = validKeyword(propValue(contact, PROPS.pending));
    const saved = String(propValue(contact, PROPS.token) || "");
    if (!contact || !pending || !saved || !timingSafeEqual(saved, token)) {
      return respond(request, 400, { ok: false, status: "invalid", message: MSG.confirmBad, title: "알림 확인" }, true);
    }
    if (method === "GET") {
      const action = "/api/alerts/confirm?" + new URLSearchParams({ e: email, t: token }).toString();
      return respond(request, 200, {
        ok: true,
        status: "confirm_needed",
        message: confirmPrompt(pending),
        title: "알림 확인",
        html: "<p>" + esc(confirmPrompt(pending)) + "</p><p>주소 " + esc(maskEmail(email)) + "</p>" +
          postButton(action, "알림 시작", { e: email, t: token }),
      }, true);
    }
    const kept = contact.unsubscribed === true ? [] : splitKeywords(propValue(contact, PROPS.keywords));
    const keywords = addKeyword(kept, pending);
    const blocked = removeKeyword(splitKeywords(propValue(contact, PROPS.blocked)), pending);
    const properties = {};
    properties[PROPS.keywords] = joinKeywords(keywords);
    properties[PROPS.pending] = null;
    properties[PROPS.token] = null;
    properties[PROPS.blocked] = blocked.length ? joinKeywords(blocked) : null;
    await saveContact(env, email, { unsubscribed: false, properties: properties }, true, deps.fetch);
    return respond(request, 200, {
      ok: true,
      status: "confirmed",
      message: confirmOk(pending),
      title: "알림을 켰습니다",
      html: "<p>" + esc(confirmOk(pending)) + "</p><p>주소 " + esc(maskEmail(email)) + ". 결제·계정은 없습니다.</p>",
    }, true);
  } catch (err) {
    return fail(request, err, true);
  }
}

export async function handleUnsubscribe(request, env, deps) {
  deps = deps || {};
  const method = String(request.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "POST") {
    return respond(request, 405, { ok: false, status: "method", message: MSG.unsubBad, title: "수신 거부" }, true);
  }
  try {
    const payload = method === "POST" ? await readPayload(request) : {};
    const token = String(field(request, payload, "token") || "").trim();
    const secret = signingSecret(env);
    if (!secret) {
      return respond(request, 503, { ok: false, status: "unconfigured", message: MSG.unconfigured, title: "수신 거부" }, true);
    }
    const parsed = await readUnsubscribe(secret, token);
    if (!parsed || !validEmail(parsed.email) || !validKeyword(parsed.keyword)) {
      return respond(request, 400, { ok: false, status: "invalid", message: MSG.unsubBad, title: "수신 거부" }, true);
    }
    const email = validEmail(parsed.email);
    const keyword = validKeyword(parsed.keyword);
    if (method === "POST" && await gate(request, env, deps, email)) {
      return respond(request, 429, { ok: false, status: "rate_limited", message: MSG.rate, title: "수신 거부" }, true);
    }
    if (method === "GET") {
      const action = "/api/alerts/unsubscribe?token=" + encodeURIComponent(token);
      return respond(request, 200, {
        ok: true,
        status: "unsubscribe_needed",
        message: unsubPrompt(keyword),
        title: "수신 거부",
        html: "<p>" + esc(unsubPrompt(keyword)) + "</p><p>주소 " + esc(maskEmail(email)) + "</p>" +
          postButton(action, "수신 거부", { token: token }),
      }, true);
    }
    if (!apiKey(env)) {
      return respond(request, 503, { ok: false, status: "unconfigured", message: MSG.unconfigured, title: "수신 거부" }, true);
    }
    await ensureProperties(env, deps.fetch);
    const contact = await getContact(env, email, deps.fetch);
    const keywords = removeKeyword(splitKeywords(propValue(contact, PROPS.keywords)), keyword);
    let blocked = addKeyword(splitKeywords(propValue(contact, PROPS.blocked)), keyword);
    if (blocked.length > MAX_BLOCKED) blocked = blocked.slice(blocked.length - MAX_BLOCKED);
    const pending = propValue(contact, PROPS.pending);
    const clearPending = sameKeyword(pending, keyword);
    const properties = {};
    properties[PROPS.keywords] = keywords.length ? joinKeywords(keywords) : null;
    properties[PROPS.blocked] = joinKeywords(blocked);
    if (clearPending) {
      properties[PROPS.pending] = null;
      properties[PROPS.token] = null;
    }
    await saveContact(env, email, {
      unsubscribed: keywords.length === 0,
      properties: properties,
    }, !!contact, deps.fetch);
    return respond(request, 200, {
      ok: true,
      status: "unsubscribed",
      message: unsubOk(keyword),
      title: "알림을 끊었습니다",
      html: "<p>" + esc(unsubOk(keyword)) + "</p>",
    }, true);
  } catch (err) {
    return fail(request, err, true);
  }
}
