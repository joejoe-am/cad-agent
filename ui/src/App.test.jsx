import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";

let api, view;
beforeEach(() => {
  view = {
    id: "one",
    title: "Toy walker",
    provider: "codex",
    status: "idle",
    data: { facts: { width_mm: "100" }, jobs: [] },
    jobs: [],
    messages: [],
    attachments: [],
    artifacts: [],
    pending: null,
    can_resume: false,
    busy: false,
    tools: [],
  };
  api = {
    bootstrap: vi.fn(async () => ({
      sessions: [
        {
          id: "one",
          title: "Toy walker",
          provider: "codex",
          status: "idle",
          updated: new Date().toISOString(),
        },
      ],
      providers: [{ id: "codex", ready: true, mode: "workspace handoff" }],
      workspace: "C:/CAD",
      configuration: "C:/CAD/providers.toml",
    })),
    get_session: vi.fn(async () => view),
    send_message: vi.fn(async () => ({ started: true })),
    pick_files: vi.fn(async () => ["C:/style.png"]),
    resume: vi.fn(async () => ({ started: true })),
    create_session: vi.fn(async () => ({ id: "two" })),
    export_session: vi.fn(async () => "export.json"),
  };
  window.pywebview = { api };
});

describe("desktop chat", () => {
  it("copies the full message including line breaks and confirms on the button", async () => {
    const user = userEvent.setup();
    view.messages = [
      { id: "m", role: "error", content: "First line\nC:\\CAD\\response.json" },
    ];
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Copy message" }),
    );
    expect(await navigator.clipboard.readText()).toBe(view.messages[0].content);
    // Confirmation stays on the control; copying must not take the toast slot.
    expect(
      await screen.findByRole("button", { name: "Message copied" }),
    ).toHaveTextContent("Copied");
  });

  it("keeps the composer usable while copying a message", async () => {
    const user = userEvent.setup();
    view.messages = [{ id: "m", role: "assistant", content: "Ready" }];
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Copy message" }),
    );
    expect(screen.getByRole("textbox", { name: "Message" })).not.toBeDisabled();
  });

  it("copies a tool result without expanding or collapsing it", async () => {
    const user = userEvent.setup();
    view.messages = [
      { id: "m", role: "tool", content: "run_job", detail: { returncode: 0 } },
    ];
    render(<App />);
    const copy = await screen.findByRole("button", { name: "Copy message" });
    const section = copy.closest("details");
    expect(section.open).toBe(false);
    await user.click(copy);
    expect(section.open).toBe(false);
    expect(await navigator.clipboard.readText()).toContain("run_job");
  });
  it("deletes a chat only after confirmation and clears the selection", async () => {
    const user = userEvent.setup();
    api.delete_session = vi.fn(async () => {
      api.bootstrap.mockResolvedValue({ sessions: [], providers: [] });
    });
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Delete conversation" }),
    );
    expect(api.delete_session).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.delete_session).not.toHaveBeenCalled();
    await user.click(
      screen.getByRole("button", { name: "Delete conversation" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Delete permanently" }),
    );
    await waitFor(() => expect(api.delete_session).toHaveBeenCalledWith("one"));
    await waitFor(() =>
      expect(localStorage.getItem("cad-agent-session")).toBeNull(),
    );
  });
  it("restores saved conversation and project facts", async () => {
    view.messages = [
      { id: "m", role: "user", content: "Keep the width at 100 mm" },
    ];
    render(<App />);
    expect(
      await screen.findByText("Keep the width at 100 mm"),
    ).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(localStorage.getItem("cad-agent-session")).toBe("one");
  });
  it("sends references and the message to the Python bridge", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: /From a thought/ });
    await waitFor(() =>
      expect(
        screen.getByRole("textbox", { name: "Message" }),
      ).not.toBeDisabled(),
    );
    await user.click(screen.getByText("Attach references"));
    expect(await screen.findByText("style.png")).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Refine this shape",
    );
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() =>
      expect(api.send_message).toHaveBeenCalledWith(
        "one",
        "Refine this shape",
        ["C:/style.png"],
      ),
    );
  });
  it("shows the actual script and binds approval to the pending operation", async () => {
    view.messages = [{ id: "m", role: "assistant", content: "Ready to run" }];
    view.pending = {
      kind: "review",
      tool: "run_job",
      operation_id: "op-42",
      arguments: { job: "job-1" },
      script: 'print("review this")',
    };
    view.can_resume = true;
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText('print("review this")')).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    await user.click(screen.getByText("I reviewed the code — run"));
    await waitFor(() =>
      expect(api.resume).toHaveBeenCalledWith("one", true, "op-42"),
    );
  });
  it("renders a handoff without claiming an automatic API conversation", async () => {
    view.messages = [{ id: "m", role: "user", content: "Design a part" }];
    view.pending = {
      kind: "handoff",
      task_file: "C:/task.md",
      response_file: "C:/response.json",
    };
    view.can_resume = true;
    render(<App />);
    expect(
      await screen.findByText("Continue in your workspace conversation"),
    ).toBeInTheDocument();
    expect(screen.getByText("C:/task.md")).toBeInTheDocument();
  });
});
