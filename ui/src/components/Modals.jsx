import React, { useEffect, useRef } from "react";
import { Check, MessageSquare, Plus, Settings2, X } from "lucide-react";

function DeleteModal({ busy, onDelete, onClose }) {
  return (
    <>
      <h2>Delete this conversation?</h2>
      <p>
        This permanently deletes its messages, project facts, and saved
        conversation state. CAD files, attachments, exported chats, and job
        results are kept. Pending actions will not continue.
      </p>
      <button className="primary full" onClick={onDelete} disabled={busy}>
        Delete permanently
      </button>
      <button onClick={onClose} disabled={busy}>
        Cancel
      </button>
    </>
  );
}

function NewModal({ api, boot, provider, onProvider, onCreate, requesting }) {
  return (
    <>
      <div className="modal-icon">
        <MessageSquare size={25} />
      </div>
      <h2>A fresh conversation</h2>
      <p>Your project history and files will be saved automatically.</p>
      <label className="field-label">
        Provider
        <select value={provider} onChange={(e) => onProvider(e.target.value)}>
          {boot.providers.map((p) => (
            <option key={p.id} value={p.id} disabled={!p.ready}>
              {p.id} · {p.mode}
              {!p.ready ? " (configure first)" : ""}
            </option>
          ))}
        </select>
      </label>
      <p className="muted">
        {provider === "codex"
          ? "Workspace handoff uses task files and requires no API key."
          : "The configured API model selects tools and continues the conversation automatically."}
      </p>
      <button
        className="primary full"
        onClick={onCreate}
        disabled={!api || requesting}
      >
        Create conversation <Plus size={16} />
      </button>
    </>
  );
}

function SettingsModal({ boot }) {
  return (
    <>
      <div className="modal-icon">
        <Settings2 size={25} />
      </div>
      <h2>Provider setup</h2>
      <p>
        Choose an API provider for an automatic agent loop, or use the Codex
        workspace handoff.
      </p>
      {boot.providers.map((p) => (
        <div className="provider-row" key={p.id}>
          <div>
            <strong>{p.id}</strong>
            <span>{p.model || p.mode}</span>
            {p.key_environment && <code>{p.key_environment}</code>}
          </div>
          <span className={`ready ${p.ready ? "yes" : ""}`}>
            {p.ready ? "Ready" : "Not configured"}
          </span>
        </div>
      ))}
      <p className="muted">
        Set models in the file below and keys in environment variables before
        starting the app. Enable supports_images for vision models. Keys are
        never stored in the UI.
      </p>
      <p className="muted">
        API providers receive conversation context and prepared reference
        images. Native CAD files stay local.
      </p>
      <code className="config-path">{boot.configuration}</code>
    </>
  );
}

function FactsModal({ modal, onModal, onSave, requesting }) {
  let invalid = null;
  try {
    const parsed = JSON.parse(modal.text);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
      invalid = "Project facts must be a JSON object.";
  } catch (e) {
    invalid = e.message;
  }
  return (
    <>
      <h2>Project facts</h2>
      <p>
        Keep explicit requirements here. These stay available when a
        conversation gets long.
      </p>
      <textarea
        className="facts-editor"
        value={modal.text}
        aria-label="Project facts JSON"
        onChange={(e) => onModal({ ...modal, text: e.target.value })}
      />
      {/* Invalid JSON used to surface as a raw parser message in the error banner. */}
      {invalid && <p className="field-error">{invalid}</p>}
      <button
        className="primary full"
        disabled={requesting || Boolean(invalid)}
        onClick={onSave}
      >
        Save project facts <Check size={16} />
      </button>
    </>
  );
}

export default function Modals({
  modal,
  onModal,
  api,
  boot,
  provider,
  onProvider,
  onCreate,
  onDelete,
  onSaveFacts,
  busy,
  requesting,
}) {
  const close = useRef(null);

  useEffect(() => {
    close.current?.focus();
    const onKey = (event) => event.key === "Escape" && onModal(null);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onModal]);

  return (
    <div className="modal-shade" onClick={() => onModal(null)}>
      <section
        className={`modal ${modal.type === "preview" ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={modal.name || modal.type}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          ref={close}
          className="modal-close icon-button"
          aria-label="Close dialog"
          onClick={() => onModal(null)}
        >
          <X size={20} />
        </button>
        {modal.type === "delete" && (
          <DeleteModal
            busy={busy}
            onDelete={onDelete}
            onClose={() => onModal(null)}
          />
        )}
        {modal.type === "new" && (
          <NewModal
            api={api}
            boot={boot}
            provider={provider}
            onProvider={onProvider}
            onCreate={onCreate}
            requesting={requesting}
          />
        )}
        {modal.type === "settings" && <SettingsModal boot={boot} />}
        {modal.type === "facts" && (
          <FactsModal
            modal={modal}
            onModal={onModal}
            onSave={onSaveFacts}
            requesting={requesting}
          />
        )}
        {modal.type === "preview" && (
          <>
            <h2>{modal.name}</h2>
            {modal.kind === "image" ? (
              <img
                className="preview-image"
                src={modal.content}
                alt={modal.name}
              />
            ) : (
              <pre className="file-preview">{modal.content}</pre>
            )}
          </>
        )}
      </section>
    </div>
  );
}
