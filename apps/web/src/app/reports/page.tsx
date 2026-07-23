"use client";

import { FormEvent, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type ReportItem = {
  id: string;
  sort_order: number;
  included: boolean;
  note: string | null;
  title_snapshot: string | null;
  source_name_snapshot: string | null;
  url_snapshot: string | null;
  snippet_snapshot: string | null;
};

type Report = {
  id: string;
  title: string;
  status: string;
  notes: string | null;
  items: ReportItem[];
  versions: { version_number: number; content_hash: string; email_status: string }[];
};

export default function ReportsReviewPage() {
  const [token, setToken] = useState("");
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadReports(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/reports`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await response.text());
      const body = (await response.json()) as Report[];
      setReports(body);
      setSelected(body[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
    } finally {
      setBusy(false);
    }
  }

  async function patchItem(itemId: string, payload: { note?: string; included?: boolean }) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/reports/${selected.id}/items/${itemId}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await response.text());
      const body = (await response.json()) as Report;
      setSelected(body);
      setReports((prev) => prev.map((row) => (row.id === body.id ? body : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function approveSelected() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/reports/${selected.id}/approve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await response.text());
      const body = (await response.json()) as Report;
      setSelected(body);
      setReports((prev) => prev.map((row) => (row.id === body.id ? body : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "2.5rem 1.25rem" }}>
      <p style={{ letterSpacing: "0.08em", textTransform: "uppercase", opacity: 0.7 }}>
        Phase 6 review
      </p>
      <h1 style={{ fontSize: "clamp(2rem, 5vw, 3rem)", margin: "0.35rem 0 0.75rem" }}>
        Report review
      </h1>
      <p style={{ maxWidth: "40rem", lineHeight: 1.55, opacity: 0.9 }}>
        Load a tenant JWT to reorder notes, include/exclude clippings, and approve an immutable PDF
        version.
      </p>

      <form onSubmit={loadReports} style={{ marginTop: "1.75rem", display: "grid", gap: "0.75rem" }}>
        <label style={{ display: "grid", gap: "0.35rem" }}>
          Access token
          <textarea
            value={token}
            onChange={(event) => setToken(event.target.value)}
            rows={3}
            style={{ width: "100%", fontFamily: "ui-monospace, monospace" }}
            placeholder="Paste Bearer token from /api/v1/auth/login"
          />
        </label>
        <button type="submit" disabled={busy || !token.trim()}>
          {busy ? "Working…" : "Load reports"}
        </button>
      </form>

      {error ? (
        <p style={{ color: "#8B1E1E", marginTop: "1rem", whiteSpace: "pre-wrap" }}>{error}</p>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: "1.5rem", marginTop: "2rem" }}>
        <aside>
          <h2 style={{ fontSize: "1rem" }}>Reports</h2>
          <ul style={{ listStyle: "none", padding: 0, margin: "0.75rem 0", display: "grid", gap: "0.5rem" }}>
            {reports.map((report) => (
              <li key={report.id}>
                <button
                  type="button"
                  onClick={() => setSelected(report)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    border: selected?.id === report.id ? "1px solid #0B3D2E" : "1px solid #ccc",
                    background: selected?.id === report.id ? "#F3F7F5" : "transparent",
                    padding: "0.6rem 0.7rem",
                  }}
                >
                  <div>{report.title}</div>
                  <small>{report.status}</small>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section>
          {selected ? (
            <>
              <header style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
                <div>
                  <h2 style={{ margin: 0 }}>{selected.title}</h2>
                  <p style={{ margin: "0.35rem 0", opacity: 0.8 }}>
                    Status: {selected.status}
                    {selected.notes ? ` — ${selected.notes}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={approveSelected}
                  disabled={busy || !["draft", "in_review"].includes(selected.status)}
                >
                  Approve + PDF
                </button>
              </header>

              <ol style={{ marginTop: "1.25rem", paddingLeft: "1.1rem", display: "grid", gap: "1rem" }}>
                {selected.items.map((item) => (
                  <li key={item.id}>
                    <strong>{item.title_snapshot ?? "Untitled"}</strong>
                    <div style={{ opacity: 0.75, fontSize: "0.9rem" }}>
                      {item.source_name_snapshot} {item.url_snapshot ? `· ${item.url_snapshot}` : ""}
                    </div>
                    {item.snippet_snapshot ? <p>{item.snippet_snapshot}</p> : null}
                    <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                      <label>
                        <input
                          type="checkbox"
                          checked={item.included}
                          disabled={busy || !["draft", "in_review"].includes(selected.status)}
                          onChange={(event) =>
                            patchItem(item.id, { included: event.target.checked })
                          }
                        />{" "}
                        Included
                      </label>
                      <input
                        type="text"
                        defaultValue={item.note ?? ""}
                        disabled={busy || !["draft", "in_review"].includes(selected.status)}
                        placeholder="Editor note"
                        onBlur={(event) => {
                          if (event.target.value !== (item.note ?? "")) {
                            void patchItem(item.id, { note: event.target.value });
                          }
                        }}
                        style={{ flex: 1 }}
                      />
                    </div>
                  </li>
                ))}
              </ol>

              {selected.versions.length ? (
                <p style={{ marginTop: "1.5rem", fontSize: "0.9rem" }}>
                  Versions:{" "}
                  {selected.versions
                    .map((v) => `v${v.version_number} (${v.content_hash.slice(0, 8)}…, ${v.email_status})`)
                    .join(" · ")}
                </p>
              ) : null}
            </>
          ) : (
            <p>No report selected.</p>
          )}
        </section>
      </div>
    </main>
  );
}
