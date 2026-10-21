import React, { useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  Download,
  LoaderCircle,
  PanelRightClose,
  PanelRightOpen,
  Trash2,
  X,
} from "lucide-react";

import { waitForBridge } from "./bridge.js";
import Composer from "./components/Composer.jsx";
import ContextPanel from "./components/ContextPanel.jsx";
import Messages from "./components/Messages.jsx";
import Modals from "./components/Modals.jsx";
import PendingCards from "./components/PendingCards.jsx";
import Sidebar from "./components/Sidebar.jsx";
import Welcome from "./components/Welcome.jsx";

// Poll quickly only while the agent can change state on its own.
const ACTIVE_POLL_MS = 1000;
const IDLE_POLL_MS = 5000;

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

  const working = Boolean(
    boot.busy_session || session?.busy || session?.can_resume,
  );

  useEffect(() => {
    if (!api) return;
    setSession(null);
    if (selected) localStorage.setItem("cad-agent-session", selected);
    else localStorage.removeItem("cad-agent-session");
    const tick = () =>
      refresh(selected).catch((e) => setError(e.message || String(e)));
    tick();
    const timer = setInterval(tick, working ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    return () => clearInterval(timer);
  }, [api, selected, working]);

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

  async function endTurn() {
    await perform(async () => {
      await api.cancel_turn(selected);
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

  const busy = requesting || Boolean(boot.busy_session || session?.busy);
  const pending = session?.pending;
  const locked = busy || Boolean(session?.can_resume);
  const currentProvider = boot.providers.find(
    (p) => p.id === session?.provider,
  );

  return (
    <div className={`shell ${panel ? "" : "no-panel"}`}>
      <Sidebar
        boot={boot}
        api={api}
        selected={selected}
        search={search}
        onSearch={setSearch}
        onSelect={(id) => {
          setSelected(id);
          setFiles([]);
          setError("");
        }}
        onNew={() => setModal({ type: "new" })}
        onSettings={() => setModal({ type: "settings" })}
      />

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
              title={panel ? "Hide project panel" : "Show project panel"}
              aria-label={panel ? "Hide project panel" : "Show project panel"}
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
            <Welcome onStarter={setDraft} />
          ) : (
            <div className="messages">
              <Messages messages={session.messages} />
              {session.busy && (
                <div className="working">
                  <LoaderCircle className="spin" size={15} /> Working on your
                  project…
                </div>
              )}
              {!session.busy && (
                <PendingCards
                  pending={pending}
                  canResume={session.can_resume}
                  busy={busy}
                  onResume={resume}
                  onEndTurn={endTurn}
                  onPreview={preview}
                />
              )}
              <div ref={end} />
            </div>
          )}
        </div>

        <Composer
          api={api}
          draft={draft}
          onDraft={setDraft}
          files={files}
          onFiles={setFiles}
          onAttach={() =>
            perform(async () => {
              const picked = await api.pick_files();
              setFiles((old) => [...new Set([...old, ...picked])]);
            })
          }
          onSend={send}
          busy={busy}
          locked={locked}
          pending={pending}
        />
      </main>

      {panel && (
        <ContextPanel
          session={session}
          selected={selected}
          locked={locked}
          tab={tab}
          onTab={setTab}
          onEditFacts={() =>
            setModal({
              type: "facts",
              text: JSON.stringify(session?.data.facts || {}, null, 2),
            })
          }
          onImportJob={() =>
            perform(async () => {
              await api.import_job(selected);
              await refresh();
            })
          }
          onPreview={preview}
        />
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
        <Modals
          modal={modal}
          onModal={setModal}
          api={api}
          boot={boot}
          provider={provider}
          onProvider={setProvider}
          onCreate={create}
          onDelete={deleteChat}
          onSaveFacts={() =>
            perform(async () => {
              await api.set_facts(selected, JSON.parse(modal.text));
              setModal(null);
              await refresh();
            })
          }
          busy={busy}
          requesting={requesting}
        />
      )}
    </div>
  );
}
