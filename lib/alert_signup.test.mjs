import assert from "node:assert/strict";
import test from "node:test";

import {
  MSG,
  createLimiter,
  handleConfirm,
  handleSubscribe,
  handleUnsubscribe,
  kvTooMany,
  readUnsubscribe,
  resetForTests,
  signUnsubscribe,
} from "./alert_signup.mjs";

const FIXTURE =
  "dXNlckBleGFtcGxlLmNvbQrsoJzsobDsl4U." +
  "f8f94461a85fd248526fe00b3a4f15a3250a726e8417012b2a4eb3dfd27ba784";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function nested(props) {
  const out = {};
  Object.entries(props || {}).forEach(function (pair) {
    if (pair[1] == null) return;
    out[pair[0]] = { type: "string", value: String(pair[1]) };
  });
  return out;
}

function install() {
  resetForTests();
  const calls = [];
  const contacts = new Map();
  const fetchImpl = async function (url, init) {
    const method = (init && init.method) || "GET";
    const body = init && init.body ? JSON.parse(init.body) : null;
    const path = new URL(url).pathname;
    calls.push({ method, path, body });
    if (path === "/contact-properties" && method === "POST") {
      return jsonResponse(201, { id: "prop" });
    }
    if (path === "/emails" && method === "POST") {
      return jsonResponse(200, { id: "mail" });
    }
    if (path === "/contacts" && method === "POST") {
      contacts.set(body.email, {
        email: body.email,
        unsubscribed: !!body.unsubscribed,
        properties: nested(body.properties),
      });
      return jsonResponse(201, { id: "created" });
    }
    if (path.indexOf("/contacts/") === 0) {
      const email = decodeURIComponent(path.slice("/contacts/".length));
      if (method === "GET") {
        if (!contacts.has(email)) return jsonResponse(404, { message: "missing" });
        return jsonResponse(200, contacts.get(email));
      }
      if (method === "PATCH") {
        const cur = contacts.get(email) || {
          email: email,
          unsubscribed: false,
          properties: {},
        };
        if (body.unsubscribed != null) cur.unsubscribed = !!body.unsubscribed;
        cur.properties = Object.assign({}, cur.properties, nested(body.properties));
        Object.entries(body.properties || {}).forEach(function (pair) {
          if (pair[1] == null) delete cur.properties[pair[0]];
        });
        contacts.set(email, cur);
        return jsonResponse(200, { id: "updated" });
      }
    }
    return jsonResponse(500, { message: "unexpected " + method + " " + path });
  };
  return {
    calls: calls,
    contacts: contacts,
    fetchImpl: fetchImpl,
    env: { RESEND_API_KEY: "re_test", RESEND_FROM: "마감판 <alerts@magampan.com>" },
  };
}

function postJson(url, payload, origin) {
  return new Request(url, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/json",
      origin: origin || "https://magampan.com",
    },
    body: JSON.stringify(payload),
  });
}

const open = { fetch: null, limited: async function () { return false; }, randomToken: function () { return "fixed-token"; } };

test("unsubscribe token matches the python digest", async function () {
  const token = await signUnsubscribe("test-secret", "User@Example.com", "  제조업  ");
  assert.equal(token, FIXTURE);
  const parsed = await readUnsubscribe("test-secret", token);
  assert.deepEqual(parsed, { email: "user@example.com", keyword: "제조업" });
  const bad = token.slice(0, -1) + (token.endsWith("4") ? "5" : "4");
  assert.equal(await readUnsubscribe("test-secret", bad), null);
});

test("honeypot pretends success and stores nothing", async function () {
  const world = install();
  const res = await handleSubscribe(postJson("https://magampan.com/api/alerts/subscribe", {
    email: "person@example.com",
    keyword: "제조업",
    _gotcha: "bot",
  }), world.env, { fetch: world.fetchImpl, limited: open.limited, randomToken: open.randomToken });
  const data = await res.json();
  assert.equal(res.status, 200);
  assert.equal(data.ok, true);
  assert.equal(world.calls.length, 0);
});

test("invalid email and foreign origin do not call Resend", async function () {
  const world = install();
  const bad = await handleSubscribe(postJson("https://magampan.com/api/alerts/subscribe", {
    email: "not-an-email",
    keyword: "제조업",
  }), world.env, { fetch: world.fetchImpl, limited: open.limited });
  assert.equal(bad.status, 400);
  assert.equal((await bad.json()).message, MSG.invalid);
  const foreign = await handleSubscribe(postJson("https://magampan.com/api/alerts/subscribe", {
    email: "person@example.com",
    keyword: "제조업",
  }, "https://evil.example"), world.env, { fetch: world.fetchImpl, limited: open.limited });
  assert.equal(foreign.status, 403);
  assert.equal(world.calls.length, 0);
});

test("missing api key explains that signup is not connected", async function () {
  const world = install();
  const res = await handleSubscribe(postJson("https://magampan.com/api/alerts/subscribe", {
    email: "person@example.com",
    keyword: "제조업",
  }), {}, { fetch: world.fetchImpl, limited: open.limited });
  const data = await res.json();
  assert.equal(res.status, 503);
  assert.match(data.message, /qwqw050009@gmail.com/);
  assert.equal(world.calls.length, 0);
});

test("signup stores a pending contact and sends a confirm mail", async function () {
  const world = install();
  const res = await handleSubscribe(postJson("https://magampan.com/api/alerts/subscribe", {
    email: "User@Example.com",
    keyword: " 제조업 ",
    plan: "pro",
  }), world.env, { fetch: world.fetchImpl, limited: open.limited, randomToken: open.randomToken });
  const data = await res.json();
  assert.equal(res.status, 200);
  assert.equal(data.status, "confirm_sent");
  assert.match(data.message, /확인 메일/);
  const props = world.calls.filter(function (c) { return c.path === "/contact-properties"; }).map(function (c) {
    return c.body.key;
  });
  assert.deepEqual(props, ["keywords", "pending_keyword", "confirm_token", "blocked_keywords"]);
  const created = world.calls.find(function (c) { return c.method === "POST" && c.path === "/contacts"; });
  assert.equal(created.body.email, "user@example.com");
  assert.equal(created.body.unsubscribed, true);
  assert.equal(created.body.properties.pending_keyword, "제조업");
  assert.equal(created.body.properties.confirm_token, "fixed-token");
  assert.equal(created.body.properties.keywords, undefined);
  const mail = world.calls.find(function (c) { return c.path === "/emails"; });
  assert.deepEqual(mail.body.to, ["user@example.com"]);
  assert.match(mail.body.text, /알림 시작/);
  assert.match(mail.body.text, /fixed-token/);
  assert.match(mail.body.text, /결제/);
  assert.equal(mail.body.from, "마감판 <alerts@magampan.com>");
});

test("an active keyword does not send another confirm mail", async function () {
  const world = install();
  world.contacts.set("person@example.com", {
    email: "person@example.com",
    unsubscribed: false,
    properties: nested({ keywords: "제조업" }),
  });
  const res = await handleSubscribe(postJson("https://magampan.com/api/alerts/subscribe", {
    email: "person@example.com",
    keyword: "제조업",
  }), world.env, { fetch: world.fetchImpl, limited: open.limited, randomToken: open.randomToken });
  const data = await res.json();
  assert.equal(data.status, "already");
  assert.equal(world.calls.some(function (c) { return c.path === "/emails"; }), false);
});

test("rate limit returns 429 before storing", async function () {
  const world = install();
  const res = await handleSubscribe(postJson("https://magampan.com/api/alerts/subscribe", {
    email: "person@example.com",
    keyword: "제조업",
  }), world.env, { fetch: world.fetchImpl, limited: async function () { return true; } });
  assert.equal(res.status, 429);
  assert.equal(res.headers.get("retry-after"), "600");
  assert.equal(world.calls.length, 0);
  const limiter = createLimiter(1, 60 * 1000);
  assert.equal(await limiter("ip"), false);
  assert.equal(await limiter("ip"), true);
});

test("confirm GET shows a button and POST turns the keyword on", async function () {
  const world = install();
  world.contacts.set("person@example.com", {
    email: "person@example.com",
    unsubscribed: true,
    properties: nested({
      keywords: "옛키워드",
      pending_keyword: "제조업",
      confirm_token: "fixed-token",
      blocked_keywords: "제조업",
    }),
  });
  const url = "https://magampan.com/api/alerts/confirm?e=person@example.com&t=fixed-token";
  const preview = await handleConfirm(new Request(url), world.env, {
    fetch: world.fetchImpl,
    limited: open.limited,
  });
  const html = await preview.text();
  assert.equal(preview.status, 200);
  assert.match(html, /알림 시작/);
  assert.match(html, /<form method="post"/);
  assert.equal(world.calls.some(function (c) { return c.method === "PATCH"; }), false);
  const done = await handleConfirm(new Request(url, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: "e=person@example.com&t=fixed-token",
  }), world.env, { fetch: world.fetchImpl, limited: open.limited });
  const page = await done.text();
  assert.equal(done.status, 200);
  assert.match(page, /알림을 켰습니다/);
  const saved = world.contacts.get("person@example.com");
  assert.equal(saved.unsubscribed, false);
  assert.equal(saved.properties.keywords.value, "제조업");
  assert.equal(saved.properties.pending_keyword, undefined);
  assert.equal(saved.properties.confirm_token, undefined);
  assert.equal(saved.properties.blocked_keywords, undefined);
});

test("bad confirm token does not change the contact", async function () {
  const world = install();
  world.contacts.set("person@example.com", {
    email: "person@example.com",
    unsubscribed: true,
    properties: nested({ pending_keyword: "제조업", confirm_token: "fixed-token" }),
  });
  const res = await handleConfirm(new Request("https://magampan.com/api/alerts/confirm?e=person@example.com&t=nope", {
    method: "POST",
  }), world.env, { fetch: world.fetchImpl, limited: open.limited });
  assert.equal(res.status, 400);
  assert.equal(world.calls.some(function (c) { return c.method === "PATCH"; }), false);
});

test("unsubscribe GET waits for POST and then blocks that keyword", async function () {
  const world = install();
  world.contacts.set("person@example.com", {
    email: "person@example.com",
    unsubscribed: false,
    properties: nested({ keywords: "제조업\n수출" }),
  });
  const token = await signUnsubscribe("re_test", "person@example.com", "제조업");
  const url = "https://magampan.com/api/alerts/unsubscribe?token=" + encodeURIComponent(token);
  const preview = await handleUnsubscribe(new Request(url), world.env, {
    fetch: world.fetchImpl,
    limited: open.limited,
  });
  const html = await preview.text();
  assert.match(html, /수신 거부/);
  assert.equal(world.calls.some(function (c) { return c.method === "PATCH"; }), false);
  const done = await handleUnsubscribe(new Request(url, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: "List-Unsubscribe=One-Click",
  }), world.env, { fetch: world.fetchImpl, limited: open.limited });
  assert.equal(done.status, 200);
  assert.match(await done.text(), /알림을 끊었습니다/);
  const saved = world.contacts.get("person@example.com");
  assert.equal(saved.unsubscribed, false);
  assert.equal(saved.properties.keywords.value, "수출");
  assert.equal(saved.properties.blocked_keywords.value, "제조업");
});

test("unsubscribe creates a block when the address is only in the secret list", async function () {
  const world = install();
  const token = await signUnsubscribe("re_test", "secret@example.com", "수출");
  const res = await handleUnsubscribe(new Request(
    "https://magampan.com/api/alerts/unsubscribe?token=" + encodeURIComponent(token),
    { method: "POST" },
  ), world.env, { fetch: world.fetchImpl, limited: open.limited });
  assert.equal(res.status, 200);
  const saved = world.contacts.get("secret@example.com");
  assert.equal(saved.unsubscribed, true);
  assert.equal(saved.properties.blocked_keywords.value, "수출");
});

test("kv counter blocks at the limit", async function () {
  const store = new Map();
  const kv = {
    get: async function (key) { return store.has(key) ? store.get(key) : null; },
    put: async function (key, value) { store.set(key, value); },
  };
  assert.equal(await kvTooMany(kv, "ip:1", 2, 600), false);
  assert.equal(await kvTooMany(kv, "ip:1", 2, 600), false);
  assert.equal(await kvTooMany(kv, "ip:1", 2, 600), true);
});
