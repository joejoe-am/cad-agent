import React from "react";
import { ArrowUpRight, Check, FileText, ShieldCheck } from "lucide-react";

import { label } from "../lib/format.js";

const REVIEW = {
  run_job: {
    title: "Review before running",
    confirm: "I reviewed the code — run",
  },
  create_cam_job: {
    title: "Review geometry handoff",
    confirm: "Geometry reviewed — continue",
  },
  start_solidworks: {
    title: "Confirm application startup",
    confirm: "Open SolidWorks",
  },
};

/** "End turn" abandons the whole turn; it belongs with the pending action, not loose
 *  under it. Declining is different and stays a primary-flow choice. */
function EndTurn({ busy, onEndTurn }) {
  return (
    <button
      type="button"
      className="tertiary"
      disabled={busy}
      onClick={onEndTurn}
    >
      End turn
    </button>
  );
}

export default function PendingCards({
  pending,
  canResume,
  busy,
  onResume,
  onEndTurn,
  onPreview,
}) {
  if (pending?.kind === "review") {
    const copy = REVIEW[pending.tool] || REVIEW.start_solidworks;
    return (
      <section className="review-card">
        <div className="review-title">
          <ShieldCheck size={20} />
          <div>
            <strong>{copy.title}</strong>
            <p>
              {pending.notice ||
                "This action changes a desktop application. Review the details before continuing."}
            </p>
          </div>
        </div>
        <div className="review-arguments">
          {Object.entries(pending.arguments || {}).map(([key, value]) => (
            <div key={key}>
              <span>{label(key)}</span>
              <code>{String(value)}</code>
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
          <EndTurn busy={busy} onEndTurn={onEndTurn} />
          <button
            className="secondary"
            disabled={busy}
            onClick={() => onResume(false)}
          >
            Decline
          </button>
          <button
            className="primary"
            disabled={busy}
            onClick={() => onResume(true)}
          >
            <Check size={16} />
            {copy.confirm}
          </button>
        </div>
      </section>
    );
  }

  if (pending?.kind === "handoff") {
    return (
      <section className="handoff-card">
        <div className="review-title">
          <FileText size={21} />
          <div>
            <strong>Continue in your workspace conversation</strong>
            <p>
              This provider uses a file handoff. Ask your coding conversation to
              read the task and write its response.
            </p>
          </div>
        </div>
        <div className="handoff-path">{pending.task_file}</div>
        <div className="review-actions">
          <EndTurn busy={busy} onEndTurn={onEndTurn} />
          <button
            className="secondary"
            onClick={() => onPreview({ path: pending.task_file, kind: "text" })}
          >
            View task
          </button>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => onResume(false)}
          >
            Cancel handoff
          </button>
          <button
            className="primary"
            disabled={busy}
            onClick={() => onResume(true)}
          >
            Load response <ArrowUpRight size={15} />
          </button>
        </div>
      </section>
    );
  }

  if (!canResume) return null;
  return (
    <section className="resume-card">
      <p>
        An interrupted turn can be resumed from its saved state. Uncertain
        desktop actions will not be repeated automatically.
      </p>
      <div className="review-actions">
        <EndTurn busy={busy} onEndTurn={onEndTurn} />
        <button
          className="primary"
          disabled={busy}
          onClick={() => onResume(null)}
        >
          Resume turn
        </button>
      </div>
    </section>
  );
}
