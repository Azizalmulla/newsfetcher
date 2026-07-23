"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import styles from "./dashboard.module.css";

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

type IngestionJob = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | string;
  attempt_count: number;
  error: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
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
  ingestion: IngestionJob | null;
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

type IconName =
  | "articles"
  | "body"
  | "calendar"
  | "sources"
  | "refresh"
  | "download"
  | "feed"
  | "paper"
  | "external"
  | "check";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    articles: (
      <>
        <path d="M6 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
        <path d="M8 8h8M8 12h8M8 16h5" />
      </>
    ),
    body: (
      <>
        <path d="M4 4h16v16H4z" />
        <path d="m8 12 2.5 2.5L16 9" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M16 3v4M8 3v4M3 10h18" />
      </>
    ),
    sources: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.1 4.9a10 10 0 0 1 0 14.2M4.9 19.1a10 10 0 0 1 0-14.2M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 6v5h-5" />
        <path d="M18.5 15a7 7 0 1 1-1.1-8.4L20 11" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v12M7 10l5 5 5-5" />
        <path d="M5 21h14" />
      </>
    ),
    feed: (
      <>
        <path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16" />
        <circle cx="5" cy="19" r="1" />
      </>
    ),
    paper: (
      <>
        <path d="M6 2h9l4 4v16H6z" />
        <path d="M14 2v5h5M9 12h7M9 16h7" />
      </>
    ),
    external: (
      <>
        <path d="M14 3h7v7M10 14 21 3" />
        <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
  };

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

function LoadingArticles() {
  return (
    <>
      {[0, 1, 2].map((row) => (
        <div className={styles.loadingRow} key={row}>
          <div className={styles.skeleton} style={{ width: "28%" }} />
          <div className={styles.skeleton} style={{ width: "84%", height: 21 }} />
          <div className={styles.skeleton} style={{ width: "68%" }} />
        </div>
      ))}
    </>
  );
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
    const id = window.setInterval(() => void load(), 15_000);
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
      const body = (await response.json()) as { message?: string; ingestion?: IngestionJob };
      setIngestMsg(body.message ?? "Ingest started.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed to start");
    } finally {
      setBusy(false);
    }
  }

  const stats = data?.stats;
  const ingestion = data?.ingestion;
  const ingestActive = ingestion?.status === "queued" || ingestion?.status === "running";
  const jobMessage =
    ingestion?.status === "queued"
      ? "Ingest queued — waiting for the background worker."
      : ingestion?.status === "running"
        ? `Ingest running · attempt ${ingestion.attempt_count}`
        : ingestion?.status === "failed"
          ? `Ingest failed: ${ingestion.error ?? "unknown worker error"}`
          : null;
  const updatedAt = data?.generated_at
    ? new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(
        new Date(data.generated_at),
      )
    : null;
  const statCards: Array<{
    label: string;
    value: number | string;
    meta: string;
    icon: IconName;
  }> = [
    {
      label: "Total articles",
      value: stats?.articles_total ?? "—",
      meta: "indexed",
      icon: "articles",
    },
    {
      label: "Full text",
      value: stats?.articles_with_body ?? "—",
      meta: "ready to search",
      icon: "body",
    },
    {
      label: `Recent · ${stats?.lookback_days ?? 5} days`,
      value: stats?.confirmed_in_lookback ?? "—",
      meta: "verified",
      icon: "calendar",
    },
    {
      label: "Live sources",
      value: data?.publishers.length ?? "—",
      meta: "Kuwait outlets",
      icon: "sources",
    },
  ];

  return (
    <div className={styles.page}>
      <main className={styles.shell}>
        <header className={styles.topbar}>
          <div className={styles.brand}>
            <span className={styles.brandMark}>
              <Icon name="feed" size={18} />
            </span>
            NewsFetcher
          </div>
          <nav className={styles.nav} aria-label="Primary navigation">
            <a className={styles.navActive} href="#coverage">
              Dashboard
            </a>
            <a href="#sources">Sources</a>
            <a href="#epaper">E-paper</a>
          </nav>
          <span className={styles.liveBadge}>
            <span className={styles.liveDot} />
            API connected
          </span>
        </header>

        <section className={styles.hero}>
          <div>
            <p className={styles.eyebrow}>
              <span className={styles.liveDot} />
              Kuwait media intelligence
            </p>
            <h1>Your live news command center.</h1>
            <p className={styles.heroCopy}>
              Monitor recent coverage across Kuwait&apos;s leading publications, inspect full-text
              articles, and open daily e-paper editions from one focused workspace.
            </p>
          </div>
          <div className={styles.actions}>
            <button
              type="button"
              onClick={() => void load()}
              className={styles.button}
            >
              <Icon name="refresh" size={16} />
              Refresh
            </button>
            <button
              type="button"
              onClick={() => void startIngest()}
              disabled={busy || ingestActive}
              className={`${styles.button} ${styles.buttonPrimary}`}
            >
              <Icon name="download" size={16} />
              {busy
                ? "Queuing…"
                : ingestion?.status === "queued"
                  ? "Queued"
                  : ingestion?.status === "running"
                    ? "Ingesting…"
                    : "Ingest last 5 days"}
            </button>
          </div>
        </section>

        {jobMessage || ingestMsg ? (
          <div
            className={`${styles.notice} ${
              ingestion?.status === "failed" ? styles.error : ""
            }`}
          >
            {ingestion?.status === "failed" ? <span>!</span> : <Icon name="check" size={16} />}
            {jobMessage ?? ingestMsg}
          </div>
        ) : null}
        {error ? (
          <div className={`${styles.notice} ${styles.error}`}>
            <span>!</span>
            {error}
          </div>
        ) : null}

        <section className={styles.stats} aria-label="Coverage overview">
          {statCards.map((stat) => (
            <article className={styles.statCard} key={stat.label}>
              <div className={styles.statTop}>
                <span className={styles.statLabel}>{stat.label}</span>
                <span className={styles.iconBox}>
                  <Icon name={stat.icon} size={17} />
                </span>
              </div>
              <div className={styles.statValue}>
                {stat.value}
                <span className={styles.statMeta}>{stat.meta}</span>
              </div>
            </article>
          ))}
        </section>

        <div className={styles.contentGrid}>
          <section className={styles.panel} id="coverage">
            <div className={styles.panelHeader}>
              <div className={styles.panelTitle}>
                <h2>Latest coverage</h2>
                <span className={styles.countBadge}>{data?.articles.length ?? 0}</span>
              </div>
              <span className={styles.updated}>
                {updatedAt ? `Updated ${updatedAt}` : "Connecting…"}
              </span>
            </div>
            {!data ? (
              <LoadingArticles />
            ) : data.articles.length === 0 ? (
              <div className={styles.empty}>
                <div>
                  <span className={styles.emptyIcon}>
                    <Icon name="feed" size={22} />
                  </span>
                  <strong>Your live feed is ready</strong>
                  <p>Run the five-day ingest to populate this workspace with recent coverage.</p>
                </div>
              </div>
            ) : (
              <ul className={styles.articleList}>
                {data.articles.map((article) => (
                  <li className={styles.article} key={article.id}>
                    <div className={styles.publisherAvatar}>
                      {article.publisher_code.slice(0, 2)}
                    </div>
                    <div>
                      <div className={styles.articleMeta}>
                        <span>{article.publisher_name_en}</span>
                        {article.publisher_name_ar ? (
                          <>
                            <span>·</span>
                            <span dir="rtl">{article.publisher_name_ar}</span>
                          </>
                        ) : null}
                        <span>·</span>
                        <span>{formatWhen(article.published_at)}</span>
                        <span
                          className={`${styles.statusPill} ${
                            article.has_body ? "" : styles.pendingPill
                          }`}
                        >
                          {article.has_body ? "Full text" : "Pending"}
                        </span>
                      </div>
                      <a
                        className={styles.articleTitle}
                        href={article.url}
                        target="_blank"
                        rel="noreferrer"
                        dir={article.language === "ar" ? "rtl" : "ltr"}
                      >
                        {article.title}
                      </a>
                      {article.snippet ? (
                        <p
                          className={styles.snippet}
                          dir={article.language === "ar" ? "rtl" : "ltr"}
                        >
                          {article.snippet}
                        </p>
                      ) : null}
                    </div>
                    <a
                      className={styles.externalLink}
                      href={article.url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`Open ${article.title}`}
                    >
                      <Icon name="external" size={15} />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <aside className={styles.sideStack}>
            <section className={styles.panel} id="epaper">
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <span className={styles.iconBox}>
                    <Icon name="paper" size={17} />
                  </span>
                  <h2>E-paper editions</h2>
                </div>
              </div>
              {!data?.epaper_editions.length ? (
                <div className={styles.empty}>
                  <div>
                    <span className={styles.emptyIcon}>
                      <Icon name="paper" size={21} />
                    </span>
                    <strong>No editions yet</strong>
                    <p>Newspaper PDFs will appear here after ingestion.</p>
                  </div>
                </div>
              ) : (
                <ul className={styles.editionList}>
                  {data.epaper_editions.map((edition) => (
                    <li className={styles.edition} key={edition.id}>
                      <div className={styles.editionTop}>
                        <span className={styles.editionName}>{edition.publisher_name_en}</span>
                        <span className={styles.editionDate}>{edition.edition_date}</span>
                      </div>
                      <div className={styles.editionMeta}>
                        <span>
                          {edition.status}
                          {edition.page_count ? ` · ${edition.page_count} pages` : ""}
                        </span>
                        {edition.source_url ? (
                          <a href={edition.source_url} target="_blank" rel="noreferrer">
                            Open PDF ↗
                          </a>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className={styles.panel} id="sources">
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <span className={styles.iconBox}>
                    <Icon name="sources" size={17} />
                  </span>
                  <h2>Active sources</h2>
                </div>
                <span className={styles.countBadge}>{data?.publishers.length ?? 0}</span>
              </div>
              {!data ? (
                <div className={styles.loadingRow}>
                  <div className={styles.skeleton} />
                  <div className={styles.skeleton} />
                </div>
              ) : (
                <ul className={styles.sourceList}>
                  {data.publishers.map((publisher) => (
                    <li className={styles.source} key={publisher.code}>
                      <span className={styles.sourceAvatar}>{publisher.code.slice(0, 2)}</span>
                      <div>
                        <div className={styles.sourceName}>{publisher.name_en}</div>
                        <div className={styles.sourceArabic} dir="rtl">
                          {publisher.name_ar}
                        </div>
                      </div>
                      <span
                        className={styles.sourceCount}
                        title="Confirmed articles in current window"
                      >
                        {publisher.article_stats.confirmed_in_lookback ?? 0}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
}
