export const basename = (path) => path?.split(/[\\/]/).pop();

export const label = (text) => text?.replaceAll("_", " ");

export const toolFailed = (detail) =>
  Boolean(
    detail?.error ||
    detail?.uncertain ||
    detail?.timed_out ||
    (detail?.returncode != null && detail.returncode !== 0),
  );

/** Text for the clipboard: a tool message is only useful with its result. */
export const messageText = (message) =>
  message.role === "tool"
    ? `${message.content}\n${JSON.stringify(message.detail, null, 2)}`
    : message.content;

/** Copy without the Clipboard API where the webview does not expose it. */
export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const field = document.createElement("textarea");
  field.value = text;
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.appendChild(field);
  const focused = document.activeElement;
  try {
    field.select();
    if (!document.execCommand("copy"))
      throw new Error("Could not copy this message.");
  } finally {
    field.remove();
    focused?.focus();
  }
}
