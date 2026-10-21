import React from "react";
import { Box, MessageSquare, Plus, Search, Settings2 } from "lucide-react";

import { basename, label } from "../lib/format.js";

const day = (value) =>
  new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });

export default function Sidebar({
  boot,
  api,
  selected,
  search,
  onSearch,
  onSelect,
  onNew,
  onSettings,
}) {
  const sessions = boot.sessions.filter((s) =>
    s.title.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <Box size={23} />
        </div>
        <div>
          CAD Agent<span>DESIGN WORKSPACE</span>
        </div>
      </div>
      <button className="new-button" onClick={onNew} disabled={!api}>
        <Plus size={17} /> New conversation <span>+</span>
      </button>
      <label className="search">
        <Search size={15} />
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search conversations"
          aria-label="Search conversations"
        />
      </label>
      <div className="section-label">
        YOUR CONVERSATIONS <span>{boot.sessions.length}</span>
      </div>
      <nav className="session-list">
        {sessions.map((s) => (
          <button
            key={s.id}
            className={`session-item ${selected === s.id ? "active" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            <MessageSquare size={16} />
            <div>
              <strong>{s.title}</strong>
              <span>
                {s.provider} ·{" "}
                {s.status === "idle" ? day(s.updated) : label(s.status)}
              </span>
            </div>
            {s.status === "waiting" && <i className="waiting-dot" />}
          </button>
        ))}
        {!sessions.length && boot.sessions.length > 0 && (
          <p className="empty-copy">No conversation matches that search.</p>
        )}
      </nav>
      <div className="sidebar-bottom">
        <div className="local-badge">
          <span /> Saved on this computer
        </div>
        <p title={boot.workspace}>
          {boot.workspace ? basename(boot.workspace) : "Connecting to desktop…"}
        </p>
        <button onClick={onSettings}>
          <Settings2 size={16} /> Provider setup
        </button>
      </div>
    </aside>
  );
}
