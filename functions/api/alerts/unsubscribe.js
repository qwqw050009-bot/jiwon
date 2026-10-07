import { handleUnsubscribe } from "../../../lib/alert_signup.mjs";

export function onRequest(context) {
  return handleUnsubscribe(context.request, context.env);
}
