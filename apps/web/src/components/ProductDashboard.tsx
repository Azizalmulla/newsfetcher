"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import styles from "./ProductDashboard.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type DashboardView = "overview" | "coverage" | "epaper" | "sources" | "ai";

type Article = {
  id: string;
  title: string;
  url: string;
  published_at: string | null;
  language: string;
  has_body: boolean;
  snippet: string | null;
  cover_image_url: string | null;
  ai_summary: string | null;
  ai_topics: string[];
  ai_sentiment: string | null;
  ai_importance: number | null;
  ai_model: string | null;
  publisher_code: string;
  publisher_name_en: string;
  publisher_name_ar: string;
};

type Publisher = {
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

type Edition = {
  id: string;
  edition_date: string;
  title: string | null;
  status: string;
  source_url: string | null;
  page_count: number;
  publisher_code: string;
  publisher_name_en: string;
  publisher_name_ar: string;
};

type IngestionJob = {
  id: string;
  status: string;
  attempt_count: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
};

type AIStatus = {
  deepseek: {
    configured: boolean;
    model: string;
    enriched_articles: number;
  };
  voyage: {
    configured: boolean;
    embedding_model: string;
    rerank_model: string;
    embedded_articles: number;
  };
  semantic_candidates: number;
  pending_review: number;
  index_coverage: number;
};

type DashboardData = {
  stats: {
    articles_total: number;
    articles_with_body: number;
    confirmed_in_lookback: number;
    lookback_days: number;
  };
  articles: Article[];
  publishers: Publisher[];
  epaper_editions: Edition[];
  ingestion: IngestionJob | null;
  ai_status: AIStatus;
  generated_at: string;
};

type IconName =
  | "overview"
  | "coverage"
  | "epaper"
  | "sources"
  | "ai"
  | "reports"
  | "settings"
  | "refresh"
  | "search"
  | "external"
  | "check"
  | "clock"
  | "bookmark"
  | "filter"
  | "arrow";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    overview: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    coverage: (
      <>
        <path d="M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
        <path d="M7 8h5M7 12h10M7 16h8" />
      </>
    ),
    epaper: (
      <>
        <path d="M6 2h9l4 4v16H6z" />
        <path d="M14 2v5h5M9 12h7M9 16h7" />
      </>
    ),
    sources: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19 5a10 10 0 0 1 0 14M5 19A10 10 0 0 1 5 5M16 8a6 6 0 0 1 0 8M8 16a6 6 0 0 1 0-8" />
      </>
    ),
    ai: (
      <>
        <path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3Z" />
        <path d="m18 14 .8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8L18 14ZM5 13l.7 2.3L8 16l-2.3.7L5 19l-.7-2.3L2 16l2.3-.7L5 13Z" />
      </>
    ),
    reports: (
      <>
        <path d="M4 4h16v16H4z" />
        <path d="M8 15V9M12 15v-3M16 15V7" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 6v5h-5" />
        <path d="M18.4 15a7 7 0 1 1-1-8.4L20 11" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    external: (
      <>
        <path d="M14 3h7v7M10 14 21 3" />
        <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    bookmark: <path d="M6 3h12v18l-6-4-6 4V3Z" />,
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
    arrow: <path d="m9 18 6-6-6-6" />,
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

const NAV_ITEMS: Array<{ view: DashboardView; label: string; href: string; icon: IconName }> = [
  { view: "overview", label: "Overview", href: "/", icon: "overview" },
  { view: "coverage", label: "Coverage", href: "/coverage", icon: "coverage" },
  { view: "epaper", label: "E-paper", href: "/epaper", icon: "epaper" },
  { view: "sources", label: "Sources", href: "/sources", icon: "sources" },
  { view: "ai", label: "AI Intelligence", href: "/ai", icon: "ai" },
];

const VIEW_COPY: Record<DashboardView, { title: string; subtitle: string }> = {
  overview: {
    title: "Media overview",
    subtitle: "The coverage, signals, and editions that matter today.",
  },
  coverage: {
    title: "Coverage inbox",
    subtitle: "Search and review recent reporting across Kuwait.",
  },
  epaper: {
    title: "E-paper library",
    subtitle: "Browse the latest newspaper editions and open original PDFs.",
  },
  sources: {
    title: "News sources",
    subtitle: "Coverage health and output across your monitored publications.",
  },
  ai: {
    title: "AI Intelligence",
    subtitle: "Semantic indexing, AI enrichment, and relevance review in one place.",
  },
};

function formatDate(value: string | null, withTime = false) {
  if (!value) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" as const } : {}),
  }).format(new Date(value));
}

function ArticleCover({ article }: { article: Article }) {
  const [failed, setFailed] = useState(false);
  if (!article.cover_image_url || failed) {
    return (
      <div className={styles.coverFallback}>
        <span>{article.publisher_code.slice(0, 2)}</span>
        <small>{article.publisher_name_en}</small>
      </div>
    );
  }
  return (
    <img
      className={styles.coverImage}
      src={article.cover_image_url}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

function ArticleCard({ article }: { article: Article }) {
  const summary = article.ai_summary || article.snippet;
  return (
    <article className={styles.articleCard}>
      <a className={styles.coverLink} href={article.url} target="_blank" rel="noreferrer">
        <ArticleCover article={article} />
        <span className={styles.sourceChip}>{article.publisher_name_en}</span>
        {article.ai_importance !== null && article.ai_importance >= 0.7 ? (
          <span className={styles.priorityChip}>Priority</span>
        ) : null}
      </a>
      <div className={styles.articleBody}>
        <div className={styles.articleMeta}>
          <span>{formatDate(article.published_at)}</span>
          <span>·</span>
          <span>{article.language.toUpperCase()}</span>
          {article.ai_model ? (
            <>
              <span>·</span>
              <span className={styles.aiLabel}>AI reviewed</span>
            </>
          ) : null}
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
        {summary ? (
          <p className={styles.articleSummary} dir={article.language === "ar" ? "rtl" : "ltr"}>
            {summary}
          </p>
        ) : null}
        {article.ai_topics.length ? (
          <div className={styles.topicRow}>
            {article.ai_topics.slice(0, 3).map((topic) => (
              <span key={topic}>{topic}</span>
            ))}
          </div>
        ) : null}
        <div className={styles.cardFooter}>
          <span className={styles.publisherArabic} dir="rtl">
            {article.publisher_name_ar}
          </span>
          <a href={article.url} target="_blank" rel="noreferrer" aria-label="Open original article">
            <Icon name="external" size={15} />
          </a>
        </div>
      </div>
    </article>
  );
}

function EmptyCoverage({ onSync }: { onSync: () => void }) {
  return (
    <div className={styles.emptyState}>
      <span className={styles.emptyIcon}>
        <Icon name="coverage" size={22} />
      </span>
      <h3>No coverage to show yet</h3>
      <p>Sync the latest five days to fill your workspace with current reporting.</p>
      <button onClick={onSync} type="button" className={styles.primaryButton}>
        Sync coverage
      </button>
    </div>
  );
}

export default function ProductDashboard({ view }: { view: DashboardView }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [query, setQuery] = useState("");
  const [publisher, setPublisher] = useState("all");
  const [language, setLanguage] = useState("all");

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/dashboard?limit=100`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await response.text());
      setData((await response.json()) as DashboardData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load NewsFetcher");
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 20_000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function syncCoverage() {
    setSyncing(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/dashboard/ingest`, { method: "POST" });
      if (!response.ok) throw new Error(await response.text());
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start synchronization");
    } finally {
      setSyncing(false);
    }
  }

  const filteredArticles = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (data?.articles ?? []).filter((article) => {
      const matchesQuery =
        !normalized ||
        article.title.toLowerCase().includes(normalized) ||
        (article.ai_summary || article.snippet || "").toLowerCase().includes(normalized);
      const matchesPublisher = publisher === "all" || article.publisher_code === publisher;
      const matchesLanguage = language === "all" || article.language === language;
      return matchesQuery && matchesPublisher && matchesLanguage;
    });
  }, [data, language, publisher, query]);

  const ingestActive =
    data?.ingestion?.status === "queued" || data?.ingestion?.status === "running";
  const copy = VIEW_COPY[view];

  return (
    <div className={styles.app}>
      <aside className={styles.sidebar}>
        <Link className={styles.logo} href="/">
          <span className={styles.logoMark}>
            <Icon name="coverage" size={17} />
          </span>
          <span>NewsFetcher</span>
        </Link>

        <nav className={styles.sidebarNav} aria-label="Workspace">
          <span className={styles.navLabel}>Workspace</span>
          {NAV_ITEMS.map((item) => (
            <Link
              className={`${styles.navItem} ${item.view === view ? styles.navItemActive : ""}`}
              href={item.href}
              key={item.view}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
              {item.view === "coverage" && data?.stats.confirmed_in_lookback ? (
                <span className={styles.navCount}>{data.stats.confirmed_in_lookback}</span>
              ) : null}
            </Link>
          ))}
          <span className={styles.navLabel}>Output</span>
          <span className={styles.navItemDisabled}>
            <Icon name="reports" size={17} />
            <span>Reports</span>
            <small>Soon</small>
          </span>
        </nav>

        <div className={styles.sidebarBottom}>
          <div className={styles.syncStatus}>
            <span
              className={`${styles.statusDot} ${ingestActive ? styles.statusDotBusy : ""}`}
            />
            <div>
              <strong>{ingestActive ? "Sync in progress" : "Workspace live"}</strong>
              <small>
                {data?.ingestion?.status === "failed"
                  ? "Last sync failed"
                  : `${data?.stats.articles_total ?? 0} indexed articles`}
              </small>
            </div>
          </div>
          <div className={styles.workspaceIdentity}>
            <span>NF</span>
            <div>
              <strong>Kuwait Media Desk</strong>
              <small>Public workspace</small>
            </div>
          </div>
        </div>
      </aside>

      <main className={styles.main}>
        <header className={styles.pageHeader}>
          <div>
            <p className={styles.breadcrumb}>NewsFetcher / {copy.title}</p>
            <h1>{copy.title}</h1>
            <p>{copy.subtitle}</p>
          </div>
          <button
            type="button"
            className={styles.syncButton}
            onClick={() => void syncCoverage()}
            disabled={syncing || ingestActive}
          >
            <Icon name="refresh" size={15} />
            {syncing ? "Starting…" : ingestActive ? "Syncing…" : "Sync latest news"}
          </button>
        </header>

        {error ? <div className={styles.errorBanner}>{error}</div> : null}
        {data?.ingestion?.status === "failed" ? (
          <div className={styles.errorBanner}>
            Latest synchronization failed: {data.ingestion.error ?? "Unknown worker error"}
          </div>
        ) : null}

        {view === "overview" ? (
          <Overview data={data} articles={filteredArticles} onSync={() => void syncCoverage()} />
        ) : null}
        {view === "coverage" ? (
          <Coverage
            data={data}
            articles={filteredArticles}
            query={query}
            publisher={publisher}
            language={language}
            setQuery={setQuery}
            setPublisher={setPublisher}
            setLanguage={setLanguage}
            onSync={() => void syncCoverage()}
          />
        ) : null}
        {view === "epaper" ? <Epaper data={data} /> : null}
        {view === "sources" ? <Sources data={data} /> : null}
        {view === "ai" ? <AIIntelligence data={data} /> : null}
      </main>
    </div>
  );
}

function MetricCard({
  label,
  value,
  note,
  tone,
  icon,
}: {
  label: string;
  value: number | string;
  note: string;
  tone: "blue" | "purple" | "coral" | "sand";
  icon: IconName;
}) {
  return (
    <article className={`${styles.metricCard} ${styles[`metric_${tone}`]}`}>
      <div className={styles.metricTop}>
        <span>{label}</span>
        <span className={styles.metricIcon}>
          <Icon name={icon} size={16} />
        </span>
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function Overview({
  data,
  articles,
  onSync,
}: {
  data: DashboardData | null;
  articles: Article[];
  onSync: () => void;
}) {
  const ai = data?.ai_status;
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="Coverage inbox"
          value={data?.stats.confirmed_in_lookback ?? "—"}
          note="verified in the last 5 days"
          tone="blue"
          icon="coverage"
        />
        <MetricCard
          label="Full-text articles"
          value={data?.stats.articles_with_body ?? "—"}
          note="ready for semantic search"
          tone="purple"
          icon="check"
        />
        <MetricCard
          label="AI enriched"
          value={ai?.deepseek.enriched_articles ?? "—"}
          note={`using ${ai?.deepseek.model ?? "DeepSeek"}`}
          tone="coral"
          icon="ai"
        />
        <MetricCard
          label="E-paper editions"
          value={data?.epaper_editions.length ?? "—"}
          note="latest PDFs and OCR"
          tone="sand"
          icon="epaper"
        />
      </section>

      <section className={styles.sectionHeader}>
        <div>
          <h2>Latest coverage</h2>
          <p>Recent reporting across your active sources.</p>
        </div>
        <Link href="/coverage">
          View all <Icon name="arrow" size={14} />
        </Link>
      </section>

      {!data ? (
        <div className={styles.loadingGrid}>
          {[0, 1, 2].map((item) => (
            <div className={styles.loadingCard} key={item} />
          ))}
        </div>
      ) : articles.length ? (
        <div className={styles.articleGrid}>
          {articles.slice(0, 6).map((article) => (
            <ArticleCard article={article} key={article.id} />
          ))}
        </div>
      ) : (
        <EmptyCoverage onSync={onSync} />
      )}
    </>
  );
}

function Coverage({
  data,
  articles,
  query,
  publisher,
  language,
  setQuery,
  setPublisher,
  setLanguage,
  onSync,
}: {
  data: DashboardData | null;
  articles: Article[];
  query: string;
  publisher: string;
  language: string;
  setQuery: (value: string) => void;
  setPublisher: (value: string) => void;
  setLanguage: (value: string) => void;
  onSync: () => void;
}) {
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="All indexed"
          value={data?.stats.articles_total ?? "—"}
          note="across every active source"
          tone="blue"
          icon="coverage"
        />
        <MetricCard
          label="Recent"
          value={data?.stats.confirmed_in_lookback ?? "—"}
          note="inside the current window"
          tone="purple"
          icon="clock"
        />
        <MetricCard
          label="AI reviewed"
          value={data?.ai_status.deepseek.enriched_articles ?? "—"}
          note="summarized and tagged"
          tone="coral"
          icon="ai"
        />
        <MetricCard label="Saved" value="0" note="your shortlist" tone="sand" icon="bookmark" />
      </section>

      <div className={styles.tabs}>
        <button className={styles.tabActive} type="button">
          Recent coverage <span>{articles.length}</span>
        </button>
        <button type="button">AI priority</button>
        <button type="button">Saved</button>
      </div>

      <section className={styles.filterPanel}>
        <label className={styles.searchField}>
          <Icon name="search" size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search headlines, summaries, or topics…"
          />
        </label>
        <select value={publisher} onChange={(event) => setPublisher(event.target.value)}>
          <option value="all">All sources</option>
          {(data?.publishers ?? []).map((item) => (
            <option value={item.code} key={item.code}>
              {item.name_en}
            </option>
          ))}
        </select>
        <select value={language} onChange={(event) => setLanguage(event.target.value)}>
          <option value="all">All languages</option>
          <option value="ar">Arabic</option>
          <option value="en">English</option>
        </select>
        <button type="button" className={styles.filterButton}>
          <Icon name="filter" size={15} />
          More filters
        </button>
      </section>

      <div className={styles.resultHeader}>
        <h2>Coverage results</h2>
        <span>{articles.length} articles</span>
      </div>

      {!data ? (
        <div className={styles.loadingGrid}>
          {[0, 1, 2].map((item) => (
            <div className={styles.loadingCard} key={item} />
          ))}
        </div>
      ) : articles.length ? (
        <div className={styles.articleGrid}>
          {articles.map((article) => (
            <ArticleCard article={article} key={article.id} />
          ))}
        </div>
      ) : (
        <EmptyCoverage onSync={onSync} />
      )}
    </>
  );
}

function Epaper({ data }: { data: DashboardData | null }) {
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="Available editions"
          value={data?.epaper_editions.length ?? "—"}
          note="in your digital library"
          tone="blue"
          icon="epaper"
        />
        <MetricCard
          label="OCR complete"
          value={data?.epaper_editions.filter((item) => item.status === "ocr_done").length ?? "—"}
          note="ready for text search"
          tone="purple"
          icon="check"
        />
        <MetricCard
          label="Total pages"
          value={data?.epaper_editions.reduce((sum, item) => sum + item.page_count, 0) ?? "—"}
          note="across recent editions"
          tone="coral"
          icon="coverage"
        />
        <MetricCard label="Cuttings" value="0" note="ready for review" tone="sand" icon="bookmark" />
      </section>

      <div className={styles.resultHeader}>
        <h2>Recent editions</h2>
        <span>Newest first</span>
      </div>
      <div className={styles.editionGrid}>
        {(data?.epaper_editions ?? []).map((edition) => (
          <article className={styles.editionCard} key={edition.id}>
            <div className={styles.paperCover}>
              <span className={styles.paperMasthead}>{edition.publisher_name_ar}</span>
              <strong>{edition.publisher_name_en}</strong>
              <div className={styles.paperRule} />
              <span>{formatDate(edition.edition_date)}</span>
              <div className={styles.paperLines}>
                <i />
                <i />
                <i />
                <i />
              </div>
              <small>{edition.page_count} pages</small>
            </div>
            <div className={styles.editionBody}>
              <div>
                <h3>{edition.publisher_name_en}</h3>
                <p>{formatDate(edition.edition_date)}</p>
              </div>
              <span className={styles.readyBadge}>{edition.status.replaceAll("_", " ")}</span>
              {edition.source_url ? (
                <a href={edition.source_url} target="_blank" rel="noreferrer">
                  Open original PDF <Icon name="external" size={14} />
                </a>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

function Sources({ data }: { data: DashboardData | null }) {
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="Active publishers"
          value={data?.publishers.length ?? "—"}
          note="monitored continuously"
          tone="blue"
          icon="sources"
        />
        <MetricCard
          label="Recent coverage"
          value={data?.stats.confirmed_in_lookback ?? "—"}
          note="verified articles"
          tone="purple"
          icon="coverage"
        />
        <MetricCard
          label="Full text"
          value={data?.stats.articles_with_body ?? "—"}
          note="successfully extracted"
          tone="coral"
          icon="check"
        />
        <MetricCard
          label="Languages"
          value="2"
          note="Arabic and English"
          tone="sand"
          icon="reports"
        />
      </section>
      <section className={styles.tablePanel}>
        <div className={styles.tableHeader}>
          <div>
            <h2>Source performance</h2>
            <p>Output and extraction coverage by publication.</p>
          </div>
          <span className={styles.liveTag}>All systems active</span>
        </div>
        <div className={styles.sourceTable}>
          <div className={styles.sourceTableHead}>
            <span>Publication</span>
            <span>Channels</span>
            <span>Indexed</span>
            <span>Full text</span>
            <span>Recent</span>
            <span>Status</span>
          </div>
          {(data?.publishers ?? []).map((item) => (
            <div className={styles.sourceTableRow} key={item.code}>
              <span className={styles.sourceIdentity}>
                <b>{item.code.slice(0, 2)}</b>
                <span>
                  <strong>{item.name_en}</strong>
                  <small dir="rtl">{item.name_ar}</small>
                </span>
              </span>
              <span>{item.channel_count}</span>
              <span>{item.article_stats.total ?? 0}</span>
              <span>{item.article_stats.with_body ?? 0}</span>
              <span>{item.article_stats.confirmed_in_lookback ?? 0}</span>
              <span className={styles.statusActive}>
                <i /> Active
              </span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function AIIntelligence({ data }: { data: DashboardData | null }) {
  const ai = data?.ai_status;
  const enriched = (data?.articles ?? []).filter((article) => article.ai_model);
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="DeepSeek enriched"
          value={ai?.deepseek.enriched_articles ?? "—"}
          note={ai?.deepseek.model ?? "article intelligence"}
          tone="blue"
          icon="ai"
        />
        <MetricCard
          label="Semantic index"
          value={`${Math.round((ai?.index_coverage ?? 0) * 100)}%`}
          note={`${ai?.voyage.embedded_articles ?? 0} Voyage embeddings`}
          tone="purple"
          icon="coverage"
        />
        <MetricCard
          label="Match candidates"
          value={ai?.semantic_candidates ?? "—"}
          note="semantic relevance signals"
          tone="coral"
          icon="sources"
        />
        <MetricCard
          label="Needs review"
          value={ai?.pending_review ?? "—"}
          note="never auto-finalized"
          tone="sand"
          icon="clock"
        />
      </section>

      <section className={styles.aiModelPanel}>
        <div className={styles.aiModelHeader}>
          <span className={styles.aiOrb}>
            <Icon name="ai" size={22} />
          </span>
          <div>
            <p>Intelligence pipeline</p>
            <h2>DeepSeek + Voyage</h2>
            <span>Real enrichment, semantic retrieval, and explainable reranking.</span>
          </div>
          <span className={styles.liveTag}>
            <i /> {ai?.deepseek.configured && ai?.voyage.configured ? "Connected" : "Setup needed"}
          </span>
        </div>
        <div className={styles.pipelineSteps}>
          <div>
            <span>01</span>
            <strong>Understand</strong>
            <p>DeepSeek summarizes articles, identifies topics, sentiment, and priority.</p>
          </div>
          <Icon name="arrow" size={18} />
          <div>
            <span>02</span>
            <strong>Retrieve</strong>
            <p>Voyage embeddings find semantically related coverage beyond exact keywords.</p>
          </div>
          <Icon name="arrow" size={18} />
          <div>
            <span>03</span>
            <strong>Rerank</strong>
            <p>Voyage reranking and DeepSeek review explain ambiguous relevance.</p>
          </div>
          <Icon name="arrow" size={18} />
          <div>
            <span>04</span>
            <strong>Review</strong>
            <p>Uncertain matches remain in a human review queue—never silently finalized.</p>
          </div>
        </div>
      </section>

      <div className={styles.resultHeader}>
        <h2>Recent AI insights</h2>
        <span>{enriched.length} shown</span>
      </div>
      {enriched.length ? (
        <div className={styles.insightList}>
          {enriched.map((article) => (
            <article key={article.id}>
              <span className={styles.insightScore}>
                {Math.round((article.ai_importance ?? 0.5) * 100)}
              </span>
              <div>
                <div className={styles.articleMeta}>
                  <span>{article.publisher_name_en}</span>
                  <span>·</span>
                  <span>{article.ai_sentiment ?? "neutral"}</span>
                </div>
                <h3 dir={article.language === "ar" ? "rtl" : "ltr"}>{article.title}</h3>
                <p dir={article.language === "ar" ? "rtl" : "ltr"}>{article.ai_summary}</p>
                <div className={styles.topicRow}>
                  {article.ai_topics.map((topic) => (
                    <span key={topic}>{topic}</span>
                  ))}
                </div>
              </div>
              <a href={article.url} target="_blank" rel="noreferrer">
                <Icon name="external" size={16} />
              </a>
            </article>
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <span className={styles.emptyIcon}>
            <Icon name="ai" size={22} />
          </span>
          <h3>AI enrichment is preparing</h3>
          <p>DeepSeek summaries and topics will appear here as the worker processes coverage.</p>
        </div>
      )}
    </>
  );
}
