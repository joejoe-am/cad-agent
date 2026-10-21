import React from "react";
import {
  ArrowUpRight,
  Box,
  FileText,
  FolderOpen,
  Image,
  Paperclip,
  ShieldCheck,
  Wrench,
} from "lucide-react";

import { basename, label } from "../lib/format.js";

const MODEL_KINDS = new Set(["model"]);
const IMAGE_KINDS = new Set(["image", "video"]);

const KindIcon = ({ kind, size = 17 }) =>
  IMAGE_KINDS.has(kind) ? (
    <Image size={size} />
  ) : MODEL_KINDS.has(kind) ? (
    <Box size={size} />
  ) : (
    <FileText size={size} />
  );

function Facts({ session, selected, locked, onEdit }) {
  const facts = session?.data.facts || {};
  return (
    <section>
      <div className="panel-section-title">
        Project facts
        {selected && (
          <button disabled={locked} onClick={onEdit}>
            Edit
          </button>
        )}
      </div>
      {Object.keys(facts).length ? (
        <dl className="facts">
          {Object.entries(facts).map(([key, value]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="empty-copy">
          Dimensions, materials, and decisions from your conversation will
          appear here.
        </p>
      )}
    </section>
  );
}

function References({ session }) {
  const attachments = session?.attachments || [];
  return (
    <section>
      <div className="panel-section-title">
        Reference files <span>{attachments.length}</span>
      </div>
      {attachments.map((a) => (
        <div className="reference" key={a.id}>
          <KindIcon kind={a.kind} />
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
      {!attachments.length && (
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
  );
}

function Jobs({ session, selected, locked, onImport }) {
  const jobs = session?.jobs || [];
  return (
    <section>
      <div className="panel-section-title">
        Linked jobs
        {selected && (
          <button disabled={locked} onClick={onImport}>
            Import
          </button>
        )}
      </div>
      {jobs.map((job) => (
        <div className="job-card" key={job.path}>
          <div>
            <Box size={15} />
            <strong>
              {job.target === "powermill" ? "PowerMill" : "SolidWorks"}
            </strong>
            <span className="job-state">{label(job.state)}</span>
          </div>
          <p>{job.task || basename(job.path)}</p>
          <span>{basename(job.path)}</span>
        </div>
      ))}
      {!jobs.length && (
        <p className="empty-copy">
          Design and machining jobs will be linked as the agent creates them.
        </p>
      )}
    </section>
  );
}

function Artifacts({ session, onPreview }) {
  const artifacts = session?.artifacts || [];
  return (
    <section>
      <div className="panel-section-title">Outputs &amp; previews</div>
      {artifacts.map((a) => (
        <button className="artifact" key={a.path} onClick={() => onPreview(a)}>
          <KindIcon kind={a.kind} />
          <div>
            <strong>{a.name}</strong>
            <span>{a.attempt}</span>
          </div>
          <ArrowUpRight size={14} />
        </button>
      ))}
      {!artifacts.length && (
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
  );
}

export default function ContextPanel({
  session,
  selected,
  locked,
  tab,
  onTab,
  onEditFacts,
  onImportJob,
  onPreview,
}) {
  return (
    <aside className="context-panel">
      <div className="context-header">
        <span>Project context</span>
        <span className="small-tag">LOCAL</span>
      </div>
      <div className="tabs">
        <button
          className={tab === "project" ? "selected" : ""}
          onClick={() => onTab("project")}
        >
          Overview
        </button>
        <button
          className={tab === "files" ? "selected" : ""}
          onClick={() => onTab("files")}
        >
          Files <span>{session?.artifacts.length || 0}</span>
        </button>
      </div>
      <div className="context-body">
        {tab === "project" ? (
          <>
            <Facts
              session={session}
              selected={selected}
              locked={locked}
              onEdit={onEditFacts}
            />
            <References session={session} />
            <Jobs
              session={session}
              selected={selected}
              locked={locked}
              onImport={onImportJob}
            />
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
                The agent chooses tools for each task. Desktop actions run one
                at a time.
              </p>
            </section>
          </>
        ) : (
          <Artifacts session={session} onPreview={onPreview} />
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
  );
}
