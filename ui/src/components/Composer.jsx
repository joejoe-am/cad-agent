import React from "react";
import { ArrowUp, LoaderCircle, Paperclip, X } from "lucide-react";

import { basename } from "../lib/format.js";

export default function Composer({
  api,
  draft,
  onDraft,
  files,
  onFiles,
  onAttach,
  onSend,
  busy,
  locked,
  pending,
}) {
  return (
    <div className="composer-wrap">
      <form
        className={`composer ${locked ? "is-locked" : ""}`}
        onSubmit={onSend}
      >
        {files.length > 0 && (
          <div className="attachment-chips">
            {files.map((path) => (
              <span key={path}>
                <Paperclip size={12} />
                {basename(path)}
                <button
                  type="button"
                  aria-label={`Remove ${basename(path)}`}
                  onClick={() => onFiles(files.filter((p) => p !== path))}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        <textarea
          aria-label="Message"
          value={draft}
          onChange={(e) => onDraft(e.target.value)}
          placeholder={
            pending
              ? "Finish the pending action to continue…"
              : "Describe your idea, ask a question, or attach a reference…"
          }
          disabled={!api || locked}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
        />
        <div className="composer-bottom">
          <button
            type="button"
            className="attach-button"
            disabled={!api || locked}
            onClick={onAttach}
          >
            <Paperclip size={17} />
            <span>Attach references</span>
          </button>
          <span className="composer-hint">Text, images, video, .SLDPRT</span>
          <button
            className="send-button"
            aria-label="Send message"
            type="submit"
            disabled={!api || locked || !draft.trim()}
          >
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <ArrowUp size={19} />
            )}
          </button>
        </div>
      </form>
      <p className="composer-disclaimer">
        Saved conversations. Original files preserved. Engineering results
        require verification.
      </p>
    </div>
  );
}
