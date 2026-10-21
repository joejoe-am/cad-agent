import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Plus,
  Search,
  ArrowUp,
  Paperclip,
  X,
  FileText,
  Image,
  FolderOpen,
  ChevronDown,
  Check,
  ShieldCheck,
  Settings2,
  Download,
  PanelRightClose,
  PanelRightOpen,
  LoaderCircle,
  Sparkles,
  Wrench,
  MessageSquare,
  ArrowUpRight,
  AlertCircle,
  Trash2,
  Copy,
} from "lucide-react";
import { waitForBridge } from "./bridge.js";

const basename = (path) => path?.split(/[\\/]/).pop();
const label = (text) => text?.replaceAll("_", " ");
const toolFailed = (detail) =>
  Boolean(
    detail?.error ||
    detail?.uncertain ||
    detail?.timed_out ||
    (detail?.returncode != null && detail.returncode !== 0),
  );

export default function App() {
  const [api, setApi] = useState(null);
  const [boot, setBoot] = useState({ sessions: [], providers: [] });
  const [selected, setSelected] = useState(null);
  const [session, setSession] = useState(null);
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState([]);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("project");
  const [panel, setPanel] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState(null);
  const [provider, setProvider] = useState("codex");
  const [requesting, setRequesting] = useState(false);
  const end = useRef(null);
  const selection = useRef(selected);
  selection.current = selected;

  useEffect(() => {
    let alive = true;
    waitForBridge()
      .then(async (bridge) => {
        const data = await bridge.bootstrap();
        if (!alive) return;
        setApi(bridge);
        setBoot(data);
        setProvider(data.default_provider || "codex");
        const remembered = localStorage.getItem("cad-agent-session");
        const initial =
          data.sessions.find((s) => s.id === remembered) || data.sessions[0];
        if (initial) setSelected(initial.id);
      })
      .catch((e) => setError(e.message || String(e)));
    return () => {
      alive = false;
    };
  }, []);

  async function refresh(id = selected) {
    if (!api) return;
    const [data, view] = await Promise.all([
      api.bootstrap(),
      id ? api.get_session(id) : null,
    ]);
    setBoot(data);
    if (id === selection.current) setSession(view);
  }

  useEffect(() => {
    if (!api) return;
    setSession(null);
    if (selected) localStorage.setItem("cad-agent-session", selected);
    else localStorage.removeItem("cad-agent-session");
    refresh(selected).catch((e) => setError(e.message || String(e)));
    const timer = setInterval(
      () => refresh(selected).catch((e) => setError(e.message || String(e))),
      1000,
    );
    return () => clearInterval(timer);
  }, [api, selected]);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages.length, session?.pending?.kind]);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 6000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  async function perform(action) {
    setError("");
    setRequesting(true);
    try {
      return await action();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setRequesting(false);
    }
  }

  async function create() {
    await perform(async () => {
      const next = await api.create_session(provider);
      setSelected(next.id);
      setModal(null);
      setDraft("");
      setFiles([]);
      setBoot(await api.bootstrap());
    });
  }

  async function send(event) {
    event?.preventDefault();
    if (!draft.trim() || !api) return;
    await perform(async () => {
      let id = selected;
      if (!id) {
        const next = await api.create_session(provider);
        id = next.id;
        setSelected(id);
      }
      await api.send_message(id, draft, files);
      setDraft("");
      setFiles([]);
      await refresh(id);
    });
  }

  async function deleteChat() {
    await perform(async () => {
      await api.delete_session(selected);
      const data = await api.bootstrap();
      const next = data.sessions[0]?.id || null;
      selection.current = next;
      setSelected(next);
      setSession(null);
      setBoot(data);
      setModal(null);
      setDraft("");
      setFiles([]);
      setToast("Conversation deleted. CAD files and job results were kept.");
    });
  }

  async function resume(approved) {
    await perform(async () => {
      await api.resume(selected, approved, session.pending?.operation_id);
      await refresh();
    });
  }

  async function preview(artifact) {
    await perform(async () => {
      if (artifact.kind === "model") {
        await api.open_model(selected, artifact.path);
        return;
      }
      setModal({
        type: "preview",
        ...(await api.read_artifact(selected, artifact.path)),
      });
    });
  }

  async function copyMessage(message) {
    await perform(async () => {
      const text =
        message.role === "tool"
          ? `${message.content}\n${JSON.stringify(message.detail, null, 2)}`
          : message.content;
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
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
      setToast("Message copied");
    });
  }

  const busy = requesting || Boolean(boot.busy_session || session?.busy);
  const pending = session?.pending;
  const locked = busy || Boolean(session?.can_resume);
  const currentProvider = boot.providers.find(
    (p) => p.id === session?.provider,
  );

  return (
    <div className={`shell ${panel ? "" : "no-panel"}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Box size={23} />
          </div>
          <div>
            CAD Agent<span>DESIGN WORKSPACE</span>
          </div>
        </div>
        <button
          className="new-button"
          onClick={() => setModal({ type: "new" })}
          disabled={!api}
        >
          <Plus size={17} /> New conversation <span>+</span>
        </button>
        <label className="search">
          <Search size={15} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
          />
        </label>
        <div className="section-label">
          YOUR CONVERSATIONS <span>{boot.sessions.length}</span>
        </div>
        <nav className="session-list">
          {boot.sessions
            .filter((s) => s.title.toLowerCase().includes(search.toLowerCase()))
            .map((s) => (
              <button
                key={s.id}
                className={`session-item ${selected === s.id ? "active" : ""}`}
                onClick={() => {
                  setSelected(s.id);
                  setFiles([]);
                  setError("");
                }}
              >
                <MessageSquare size={16} />
                <div>
                  <strong>{s.title}</strong>
                  <span>
                    {s.provider} ·{" "}
                    {s.status === "idle"
                      ? new Date(s.updated).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })
                      : label(s.status)}
                  </span>
                </div>
                {s.status === "waiting" && <i className="waiting-dot" />}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-badge">
            <span /> Saved on this computer
          </div>
          <p title={boot.workspace}>
            {boot.workspace
              ? basename(boot.workspace)
              : "Connecting to desktop…"}
          </p>
          <button onClick={() => setModal({ type: "settings" })}>
            <Settings2 size={16} /> Provider setup
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>{" "}
            <strong>{session?.title || "New conversation"}</strong>
          </div>
          <div className="header-actions">
            {selected && (
              <>
                <button
                  className="provider-badge"
                  title={currentProvider?.model || "Provider setup"}
                  onClick={() => setModal({ type: "settings" })}
                >
                  {session?.provider || "…"} <ChevronDown size={12} />
                </button>
                <button
                  className="icon-button"
                  title="Export conversation"
                  aria-label="Export conversation"
                  onClick={() =>
                    perform(async () =>
                      setToast(
                        `Conversation exported to ${await api.export_session(selected)}`,
                      ),
                    )
                  }
                >
                  <Download size={17} />
                </button>
                <button
                  className="icon-button"
                  title="Delete conversation"
                  aria-label="Delete conversation"
                  disabled={busy}
                  onClick={() => setModal({ type: "delete" })}
                >
                  <Trash2 size={17} />
                </button>
              </>
            )}
            <button
              className="icon-button"
              onClick={() => setPanel(!panel)}
              title="Toggle project panel"
              aria-label="Toggle project panel"
            >
              {panel ? (
                <PanelRightClose size={19} />
              ) : (
                <PanelRightOpen size={19} />
              )}
            </button>
          </div>
        </header>

        {error && (
          <div role="alert" className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Dismiss error">
              <X size={16} />
            </button>
          </div>
        )}
        <div className="conversation">
          {!session?.messages.length ? (
            <section className="welcome">
              <div className="welcome-mark">
                <Box size={34} />
              </div>
              <div className="eyebrow">YOUR NEXT IDEA STARTS HERE</div>
              <h1>
                From a thought
                <br />
                to something tangible.
              </h1>
              <p>
                Design, refine, and inspect with an assistant that
                <br />
                remembers your project and chooses the right tools.
              </p>
              <div className="starters">
                {[
                  [
                    "Design a part",
                    "Help me design a new part. Let’s discuss its dimensions and intended use first.",
                  ],
                  [
                    "Work in PowerMill",
                    "I want to work only in PowerMill. Inspect the current project before making changes.",
                  ],
                  [
                    "Refine a model",
                    "I want to refine an existing SolidWorks part using reference images. Help me plan the changes.",
                  ],
                ].map(([title, text], i) => (
                  <button key={title} onClick={() => setDraft(text)}>
                    <span>
                      {i === 0 ? (
                        <Sparkles size={19} />
                      ) : i === 1 ? (
                        <Wrench size={19} />
                      ) : (
                        <Box size={19} />
                      )}
                    </span>
                    {title}
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              </div>
              <div className="welcome-note">
                <ShieldCheck size={15} /> Conversation history is saved on this
                computer.
              </div>
            </section>
          ) : (
            <div className="messages">
              {session.messages.map((m) =>
                m.role === "tool" ? (
                  <details
                    className={`tool-message ${toolFailed(m.detail) ? "failed" : ""}`}
                    key={m.id}
                    open={toolFailed(m.detail) || undefined}
                  >
                    <summary>
                      <Wrench size={14} />
                      {label(m.content)}
                      {toolFailed(m.detail) ? (
                        <>
                          <span className="tool-state">Needs attention</span>
                          <AlertCircle size={13} />
                        </>
                      ) : (
                        <Check size={13} />
                      )}
                    </summary>
                    <pre>{JSON.stringify(m.detail, null, 2)}</pre>
                    <button
                      className="copy-message"
                      aria-label="Copy message"
                      onClick={() => copyMessage(m)}
                    >
                      <Copy size={13} /> Copy
                    </button>
                  </details>
                ) : (
                  <article className={`message ${m.role}`} key={m.id}>
                    <div className="avatar">
                      {m.role === "user" ? (
                        "Y"
                      ) : m.role === "error" ? (
                        "!"
                      ) : (
                        <Box size={18} />
                      )}
                    </div>
                    <div>
                      <div className="message-author">
                        {m.role === "user"
                          ? "You"
                          : m.role === "error"
                            ? "Operation needs attention"
                            : "CAD Agent"}
                        <button
                          className="copy-message"
                          aria-label="Copy message"
                          title="Copy message"
                          onClick={() => copyMessage(m)}
                        >
                          <Copy size={13} /> Copy
                        </button>
                      </div>
                      <div className="message-body">{m.content}</div>
                    </div>
                  </article>
                ),
              )}
              {session.busy && (
                <div className="working">
                  <LoaderCircle className="spin" size={15} /> Working on your
                  project…
                </div>
              )}
              {pending?.kind === "review" && (
                <section className="review-card">
                  <div className="review-title">
                    <ShieldCheck size={20} />
                    <div>
                      <strong>
                        {pending.tool === "run_job"
                          ? "Review before running"
                          : pending.tool === "create_cam_job"
                            ? "Review geometry handoff"
                            : "Confirm application startup"}
                      </strong>
                      <p>
                        {pending.notice ||
                          "This action changes a desktop application. Review the details before continuing."}
                      </p>
                    </div>
                  </div>
                  <div className="review-arguments">
                    {Object.entries(pending.arguments || {}).map(([k, v]) => (
                      <div key={k}>
                        <span>{label(k)}</span>
                        <code>{String(v)}</code>
                      </div>
                    ))}
                  </div>
                  {pending.script && (
                    <details className="script-review" open>
                      <summary>Generated Python script</summary>
                      <pre>{pending.script}</pre>
                    </details>
                  )}
                  <div className="review-actions">
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => resume(false)}
                    >
                      Decline
                    </button>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => resume(true)}
                    >
                      <Check size={16} />
                      {pending.tool === "run_job"
                        ? "I reviewed the code — run"
                        : pending.tool === "create_cam_job"
                          ? "Geometry reviewed — continue"
                          : "Open SolidWorks"}
                    </button>
                  </div>
                </section>
              )}
              {pending?.kind === "handoff" && (
                <section className="handoff-card">
                  <div className="review-title">
                    <FileText size={21} />
                    <div>
                      <strong>Continue in your workspace conversation</strong>
                      <p>
                        This provider uses a file handoff. Ask your coding
                        conversation to read the task and write its response.
                      </p>
                    </div>
                  </div>
                  <div className="handoff-path">{pending.task_file}</div>
                  <div className="review-actions">
                    <button
                      className="secondary"
                      onClick={() =>
                        preview({ path: pending.task_file, kind: "text" })
                      }
                    >
                      View task
                    </button>
                    <button
                      className="secondary"
                      onClick={() => resume(false)}
                      disabled={busy}
                    >
                      Cancel
                    </button>
                    <button
                      className="primary"
                      onClick={() => resume(true)}
                      disabled={busy}
                    >
                      Load response <ArrowUpRight size={15} />
                    </button>
                  </div>
                </section>
              )}
              {session.can_resume && !pending && !session.busy && (
                <div className="resume-card">
                  <p>
                    An interrupted turn can be resumed from its saved state.
                    Uncertain desktop actions will not be repeated
                    automatically.
                  </p>
                  <button
                    className="primary"
                    onClick={() => resume(null)}
                    disabled={busy}
                  >
                    Resume turn
                  </button>
                </div>
              )}
              {session.can_resume && !session.busy && (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    perform(async () => {
                      await api.cancel_turn(selected);
                      await refresh();
                    })
                  }
                >
                  Cancel pending turn
                </button>
              )}
              <div ref={end} />
            </div>
          )}
        </div>

        <div className="composer-wrap">
          <form
            className={`composer ${locked ? "is-locked" : ""}`}
            onSubmit={send}
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
                      onClick={() => setFiles(files.filter((p) => p !== path))}
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
              onChange={(e) => setDraft(e.target.value)}
              placeholder={
                pending
                  ? "Finish the pending action to continue…"
                  : "Describe your idea, ask a question, or attach a reference…"
              }
              disabled={!api || locked}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <div className="composer-bottom">
              <button
                type="button"
                className="attach-button"
                disabled={!api || locked}
                onClick={() =>
                  perform(async () => {
                    const picked = await api.pick_files();
                    setFiles((old) => [...new Set([...old, ...picked])]);
                  })
                }
              >
                <Paperclip size={17} />
                <span>Attach references</span>
              </button>
              <span className="composer-hint">
                Text, images, video, .SLDPRT
              </span>
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
      </main>

      {panel && (
        <aside className="context-panel">
          <div className="context-header">
            <span>Project context</span>
            <span className="small-tag">LOCAL</span>
          </div>
          <div className="tabs">
            <button
              className={tab === "project" ? "selected" : ""}
              onClick={() => setTab("project")}
            >
              Overview
            </button>
            <button
              className={tab === "files" ? "selected" : ""}
              onClick={() => setTab("files")}
            >
              Files <span>{session?.artifacts.length || 0}</span>
            </button>
          </div>
          <div className="context-body">
            {tab === "project" ? (
              <>
                <section>
                  <div className="panel-section-title">
                    Project facts
                    {selected && (
                      <button
                        disabled={locked}
                        onClick={() =>
                          setModal({
                            type: "facts",
                            text: JSON.stringify(
                              session?.data.facts || {},
                              null,
                              2,
                            ),
                          })
                        }
                      >
                        Edit
                      </button>
                    )}
                  </div>
                  {Object.keys(session?.data.facts || {}).length ? (
                    <dl className="facts">
                      {Object.entries(session.data.facts).map(([k, v]) => (
                        <div key={k}>
                          <dt>{label(k)}</dt>
                          <dd>{v}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="empty-copy">
                      Dimensions, materials, and decisions from your
                      conversation will appear here.
                    </p>
                  )}
                </section>
                <section>
                  <div className="panel-section-title">
                    Reference files{" "}
                    <span>{session?.attachments.length || 0}</span>
                  </div>
                  {session?.attachments.map((a) => (
                    <div className="reference" key={a.id}>
                      {a.kind === "image" || a.kind === "video" ? (
                        <Image size={17} />
                      ) : (
                        <FileText size={17} />
                      )}
                      <div>
                        <strong title={a.name}>{a.name}</strong>
                        <span>
                          {a.kind}
                          {a.images.length
                            ? ` · ${a.images.length} visual${a.images.length > 1 ? "s" : ""}`
                            : ""}
                        </span>
                      </div>
                    </div>
                  ))}
                  {!session?.attachments.length && (
                    <div className="attachment-empty">
                      <Paperclip size={23} />
                      <p>
                        Add photos, a short video,
                        <br />
                        or a SolidWorks part.
                      </p>
                    </div>
                  )}
                </section>
                <section>
                  <div className="panel-section-title">
                    Linked jobs
                    {selected && (
                      <button
                        disabled={locked}
                        onClick={() =>
                          perform(async () => {
                            await api.import_job(selected);
                            await refresh();
                          })
                        }
                      >
                        Import
                      </button>
                    )}
                  </div>
                  {session?.jobs.map((job) => (
                    <div className="job-card" key={job.path}>
                      <div>
                        <Box size={15} />
                        <strong>
                          {job.target === "powermill"
                            ? "PowerMill"
                            : "SolidWorks"}
                        </strong>
                        <span className="job-state">{label(job.state)}</span>
                      </div>
                      <p>{job.task || basename(job.path)}</p>
                      <span>{basename(job.path)}</span>
                    </div>
                  ))}
                  {!session?.jobs.length && (
                    <p className="empty-copy">
                      Design and machining jobs will be linked as the agent
                      creates them.
                    </p>
                  )}
                </section>
                <section>
                  <div className="panel-section-title">Tool workspace</div>
                  <div className="capabilities">
                    <span>
                      <Box size={15} /> SolidWorks
                    </span>
                    <span>
                      <Wrench size={15} /> PowerMill
                    </span>
                    <span>
                      <FileText size={15} /> File inspection
                    </span>
                  </div>
                  <p className="empty-copy">
                    The agent chooses tools for each task. Desktop actions run
                    one at a time.
                  </p>
                </section>
              </>
            ) : (
              <section>
                <div className="panel-section-title">Outputs & previews</div>
                {session?.artifacts.map((a) => (
                  <button
                    className="artifact"
                    key={a.path}
                    onClick={() => preview(a)}
                  >
                    {a.kind === "image" ? (
                      <Image size={17} />
                    ) : a.kind === "model" ? (
                      <Box size={17} />
                    ) : (
                      <FileText size={17} />
                    )}
                    <div>
                      <strong>{a.name}</strong>
                      <span>{a.attempt}</span>
                    </div>
                    <ArrowUpRight size={14} />
                  </button>
                ))}
                {!session?.artifacts.length && (
                  <div className="attachment-empty">
                    <FolderOpen size={28} />
                    <p>
                      Models, previews, scripts,
                      <br />
                      and reports appear here.
                    </p>
                  </div>
                )}
              </section>
            )}
          </div>
          <div className="context-footer">
            <ShieldCheck size={16} />
            <span>
              Execution is separate from
              <br />
              engineering approval.
            </span>
          </div>
        </aside>
      )}

      {toast && (
        <div className="toast" role="status">
          <Check size={17} />
          {toast}
          <button
            onClick={() => setToast("")}
            aria-label="Dismiss notification"
          >
            <X size={14} />
          </button>
        </div>
      )}
      {modal && (
        <div className="modal-shade" onClick={() => setModal(null)}>
          <section
            className={`modal ${modal.type === "preview" ? "wide" : ""}`}
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close icon-button"
              aria-label="Close dialog"
              onClick={() => setModal(null)}
            >
              <X size={20} />
            </button>
            {modal.type === "delete" && (
              <>
                <h2>Delete this conversation?</h2>
                <p>
                  This permanently deletes its messages, project facts, and
                  saved conversation state. CAD files, attachments, exported
                  chats, and job results are kept. Pending actions will not
                  continue.
                </p>
                <button
                  className="primary full"
                  onClick={deleteChat}
                  disabled={busy}
                >
                  Delete permanently
                </button>
                <button onClick={() => setModal(null)} disabled={busy}>
                  Cancel
                </button>
              </>
            )}
            {modal.type === "new" && (
              <>
                <div className="modal-icon">
                  <MessageSquare size={25} />
                </div>
                <h2>A fresh conversation</h2>
                <p>
                  Your project history and files will be saved automatically.
                </p>
                <label className="field-label">
                  Provider
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
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
                  onClick={create}
                  disabled={!api || requesting}
                >
                  Create conversation <Plus size={16} />
                </button>
              </>
            )}
            {modal.type === "settings" && (
              <>
                <div className="modal-icon">
                  <Settings2 size={25} />
                </div>
                <h2>Provider setup</h2>
                <p>
                  Choose an API provider for an automatic agent loop, or use the
                  Codex workspace handoff.
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
                  Set models in the file below and keys in environment variables
                  before starting the app. Enable supports_images for vision
                  models. Keys are never stored in the UI.
                </p>
                <p className="muted">
                  API providers receive conversation context and prepared
                  reference images. Native CAD files stay local.
                </p>
                <code className="config-path">{boot.configuration}</code>
              </>
            )}
            {modal.type === "facts" && (
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
                  onChange={(e) => setModal({ ...modal, text: e.target.value })}
                />
                <button
                  className="primary full"
                  disabled={requesting}
                  onClick={() =>
                    perform(async () => {
                      await api.set_facts(selected, JSON.parse(modal.text));
                      setModal(null);
                      await refresh();
                    })
                  }
                >
                  Save project facts <Check size={16} />
                </button>
              </>
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
      )}
    </div>
  );
}
