"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type DashboardArticle = {
  id: string;
  title: string;
  url: string;
  published_at: string | null;
  language: string;
  has_body: boolean;
  in_lookback: boolean;
  snippet: string | null;
  publisher_code: string;
  publisher_name_en: string;
  publisher_name_ar: string;
};

type DashboardPublisher = {
  code: string;
  name_en: string;
  name_ar: string;
  homepage_url: string;
  channel_count: number;
  article_stats: {
    total?: number;
    with_body?: number;
    confirmed_in_lookback?: number;
  };
};

type DashboardEdition = {
  id: string;
  edition_date: string;
  title: string | null;
  status: string;
  source_url: string | null;
  page_count: number;
  publisher_name_en: string;
  publisher_name_ar: string;
};

type DashboardPayload = {
  stats: {
    articles_total: number;
    articles_with_body: number;
    confirmed_in_lookback: number;
    lookback_days: number;
  };
  articles: DashboardArticle[];
  publishers: DashboardPublisher[];
  epaper_editions: DashboardEdition[];
  generated_at: string;
};

function formatWhen(value: string | null): string {
  if (!value) return "undated";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/dashboard`, { cache: "no-store" });
      if (!response.ok) throw new Error(await response.text());
      setData((await response.json()) as DashboardPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  async function startIngest() {
    setBusy(true);
    setIngestMsg(null);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/dashboard/ingest`, {
        method: "POST",
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await response.text());
      const body = (await response.json()) as { message?: string };
      setIngestMsg(body.message ?? "Ingest started.");
      window.setTimeout(() => void load(), 15_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed to start");
    } finally {
      setBusy(false);
    }
  }

  const stats = data?.stats;

  return (
    <main
      style={{
        maxWidth: 1120,
        margin: "0 auto",
        padding: "2.25rem 1.25rem 4rem",
      }}
    >
      <header
        style={{
          display: "grid",
          gap: "1rem",
          borderBottom: "1px solid rgba(18, 32, 51, 0.12)",
          paddingBottom: "1.5rem",
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            gap: "1rem",
            alignItems: "end",
          }}
        >
          <div>
            <p
              style={{
                margin: 0,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                fontSize: "0.75rem",
                opacity: 0.65,
              }}
            >
              Live Kuwait media desk
            </p>
            <h1
              style={{
                margin: "0.35rem 0 0",
                fontSize: "clamp(2.4rem, 7vw, 4.2rem)",
                lineHeight: 0.95,
                letterSpacing: "-0.03em",
              }}
            >
              NewsFetcher
            </h1>
            <p style={{ margin: "0.75rem 0 0", maxWidth: "34rem", lineHeight: 1.55, opacity: 0.9 }}>
              Recent articles and e-paper editions from Kuwait sources — no login.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => void load()}
              style={{
                border: "1px solid rgba(18,32,51,0.25)",
                background: "transparent",
                padding: "0.7rem 1rem",
                cursor: "pointer",
              }}
            >
              Refresh
            </button>
            <button
              type="button"
              onClick={() => void startIngest()}
              disabled={busy}
              style={{
                border: "none",
                background: "#0f3d3e",
                color: "#f4f7f5",
                padding: "0.7rem 1.1rem",
                cursor: busy ? "wait" : "pointer",
              }}
            >
              {busy ? "Starting…" : "Ingest last 5 days"}
            </button>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: "0.75rem",
          }}
        >
          {[
            ["Articles", stats?.articles_total ?? "—"],
            ["With body", stats?.articles_with_body ?? "—"],
            [`In ${stats?.lookback_days ?? 5}d`, stats?.confirmed_in_lookback ?? "—"],
            ["Sources", data?.publishers.length ?? "—"],
          ].map(([label, value]) => (
            <div key={String(label)} style={{ padding: "0.85rem 0 0.25rem" }}>
              <div style={{ fontSize: "0.75rem", letterSpacing: "0.08em", textTransform: "uppercase", opacity: 0.55 }}>
                {label}
              </div>
              <div style={{ fontSize: "1.85rem", fontWeight: 600, marginTop: "0.15rem" }}>{value}</div>
            </div>
          ))}
        </div>
        {ingestMsg ? <p style={{ margin: 0, opacity: 0.8 }}>{ingestMsg}</p> : null}
        {error ? (
          <p style={{ margin: 0, color: "#8B1E1E", whiteSpace: "pre-wrap" }}>{error}</p>
        ) : null}
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.7fr) minmax(260px, 0.9fr)",
          gap: "2rem",
          marginTop: "2rem",
        }}
      >
        <section>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.15rem" }}>Latest coverage</h2>
          {!data ? (
            <p style={{ opacity: 0.7 }}>Loading…</p>
          ) : data.articles.length === 0 ? (
            <p style={{ opacity: 0.8, lineHeight: 1.55 }}>
              No articles in the database yet. Hit <strong>Ingest last 5 days</strong> and refresh in a
              few minutes.
            </p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "1.15rem" }}>
              {data.articles.map((article) => (
                <li
                  key={article.id}
                  style={{
                    borderTop: "1px solid rgba(18,32,51,0.1)",
                    paddingTop: "1rem",
                  }}
                >
                  <div style={{ fontSize: "0.85rem", opacity: 0.65 }}>
                    {article.publisher_name_en}
                    {article.publisher_name_ar ? ` · ${article.publisher_name_ar}` : ""}
                    {" · "}
                    {formatWhen(article.published_at)}
                    {article.has_body ? "" : " · body pending"}
                  </div>
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: "inline-block",
                      marginTop: "0.35rem",
                      color: "inherit",
                      textDecoration: "none",
                      fontSize: "1.2rem",
                      lineHeight: 1.35,
                      fontWeight: 600,
                    }}
                  >
                    {article.title}
                  </a>
                  {article.snippet ? (
                    <p
                      dir={article.language === "ar" ? "rtl" : "ltr"}
                      style={{ margin: "0.55rem 0 0", lineHeight: 1.55, opacity: 0.88 }}
                    >
                      {article.snippet}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside style={{ display: "grid", gap: "1.75rem", alignContent: "start" }}>
          <section>
            <h2 style={{ margin: "0 0 0.85rem", fontSize: "1.15rem" }}>E-paper</h2>
            {!data?.epaper_editions.length ? (
              <p style={{ margin: 0, opacity: 0.7 }}>No editions ingested yet.</p>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.75rem" }}>
                {data.epaper_editions.map((edition) => (
                  <li key={edition.id}>
                    <div style={{ fontWeight: 600 }}>
                      {edition.publisher_name_en} · {edition.edition_date}
                    </div>
                    <div style={{ fontSize: "0.9rem", opacity: 0.7 }}>
                      {edition.status}
                      {edition.page_count ? ` · ${edition.page_count} pages` : ""}
                    </div>
                    {edition.source_url ? (
                      <a href={edition.source_url} target="_blank" rel="noreferrer">
                        Open PDF
                      </a>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 style={{ margin: "0 0 0.85rem", fontSize: "1.15rem" }}>Sources</h2>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.65rem" }}>
              {(data?.publishers ?? []).map((publisher) => (
                <li key={publisher.code} style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{publisher.name_en}</div>
                    <div dir="rtl" style={{ fontSize: "0.9rem", opacity: 0.7 }}>
                      {publisher.name_ar}
                    </div>
                  </div>
                  <div style={{ fontSize: "0.9rem", opacity: 0.7, whiteSpace: "nowrap" }}>
                    {publisher.article_stats.confirmed_in_lookback ?? 0} in window
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      <style>{`
        @media (max-width: 860px) {
          main > div {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </main>
  );
}
