import React, { useEffect, useState } from "react";
import { AlertCircle, Box, Check, Copy, Wrench } from "lucide-react";

import { copyText, label, messageText, toolFailed } from "../lib/format.js";

const AUTHORS = {
  user: "You",
  error: "Operation needs attention",
  assistant: "CAD Agent",
};

/**
 * One copy control, in the same place on every message, revealed on hover or
 * keyboard focus. Confirmation stays on the button: copying is a local action
 * and should not take over the shared notification slot or the busy state.
 */
function CopyButton({ text }) {
  const [state, setState] = useState("idle");

  useEffect(() => {
    if (state === "idle") return;
    const timer = setTimeout(() => setState("idle"), 2000);
    return () => clearTimeout(timer);
  }, [state]);

  const names = {
    idle: "Copy message",
    copied: "Message copied",
    failed: "Copy failed",
  };
  return (
    <button
      type="button"
      className={`copy-button ${state}`}
      title={names[state]}
      aria-label={names[state]}
      onClick={async (event) => {
        // Tool copy sits inside <summary>; copying must not toggle the section.
        event.preventDefault();
        event.stopPropagation();
        try {
          await copyText(text);
          setState("copied");
        } catch {
          setState("failed");
        }
      }}
    >
      {state === "copied" ? <Check size={13} /> : <Copy size={13} />}
      {state !== "idle" && (
        <span>{state === "copied" ? "Copied" : "Copy failed"}</span>
      )}
    </button>
  );
}

function ToolMessage({ message }) {
  const failed = toolFailed(message.detail);
  return (
    <details
      className={`tool-message ${failed ? "failed" : ""}`}
      open={failed || undefined}
    >
      <summary>
        <Wrench size={14} />
        {label(message.content)}
        <span className="tool-state">
          {failed ? (
            <>
              Needs attention <AlertCircle size={13} />
            </>
          ) : (
            <Check size={13} />
          )}
        </span>
        <CopyButton text={messageText(message)} />
      </summary>
      <pre>{JSON.stringify(message.detail, null, 2)}</pre>
    </details>
  );
}

function ChatMessage({ message }) {
  return (
    <article className={`message ${message.role}`}>
      <div className="avatar">
        {message.role === "user" ? (
          "Y"
        ) : message.role === "error" ? (
          "!"
        ) : (
          <Box size={18} />
        )}
      </div>
      <div className="message-main">
        <div className="message-author">
          {AUTHORS[message.role] || "CAD Agent"}
        </div>
        <div className="message-body">{message.content}</div>
      </div>
      <CopyButton text={messageText(message)} />
    </article>
  );
}

export default function Messages({ messages }) {
  return messages.map((message) =>
    message.role === "tool" ? (
      <ToolMessage key={message.id} message={message} />
    ) : (
      <ChatMessage key={message.id} message={message} />
    ),
  );
}
