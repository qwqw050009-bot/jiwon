import { handleConfirm } from "../../../lib/alert_signup.mjs";

export function onRequest(context) {
  return handleConfirm(context.request, context.env);
}
