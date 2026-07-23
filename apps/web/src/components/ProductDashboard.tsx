"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import styles from "./ProductDashboard.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type DashboardView = "coverage" | "epaper" | "insights";
type CoverageMode = "recent" | "priority" | "saved";

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
  ingestion: { status: string; error: string | null } | null;
  ai_status: {
    deepseek: { enriched_articles: number };
  };
  generated_at: string;
};

type IconName =
  | "coverage"
  | "epaper"
  | "insights"
  | "reports"
  | "refresh"
  | "search"
  | "external"
  | "check"
  | "clock"
  | "bookmark"
  | "arrow"
  | "close"
  | "alert"
  | "tone";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
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
    insights: (
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
    arrow: <path d="m9 18 6-6-6-6" />,
    close: <path d="M6 6l12 12M18 6 6 18" />,
    alert: (
      <>
        <path d="M12 3 2.8 20h18.4L12 3Z" />
        <path d="M12 9v4M12 17h.01" />
      </>
    ),
    tone: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01" />
      </>
    ),
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
  { view: "coverage", label: "Coverage", href: "/", icon: "coverage" },
  { view: "insights", label: "Insights", href: "/insights", icon: "insights" },
  { view: "epaper", label: "E-paper", href: "/epaper", icon: "epaper" },
];

const VIEW_COPY: Record<DashboardView, { title: string; subtitle: string }> = {
  coverage: {
    title: "Media coverage",
    subtitle: "Review what is being said, understand what matters, and save key stories.",
  },
  insights: {
    title: "Insights",
    subtitle: "A clear view of the stories, themes, and reputational signals worth your attention.",
  },
  epaper: {
    title: "E-paper library",
    subtitle: "Browse recent newspaper editions and open the original publication.",
  },
};

function formatDate(value: string | null, withTime = false) {
  if (!value) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" as const } : {}),
  }).format(new Date(value));
}

function priorityLabel(article: Article) {
  if ((article.ai_importance ?? 0) >= 0.7) return "High priority";
  if ((article.ai_importance ?? 0) >= 0.45) return "Worth reviewing";
  return "Standard coverage";
}

function toneLabel(value: string | null) {
  const labels: Record<string, string> = {
    positive: "Positive tone",
    negative: "Negative tone",
    mixed: "Mixed tone",
    neutral: "Neutral tone",
  };
  return labels[value ?? "neutral"] ?? "Neutral tone";
}

function whyItMatters(article: Article) {
  if (article.ai_sentiment === "negative") {
    return "The tone may warrant a closer look from your communications team.";
  }
  if ((article.ai_importance ?? 0) >= 0.7) {
    return "This story ranks among the higher-priority coverage in your current news cycle.";
  }
  return "This story provides useful context for understanding the current media conversation.";
}

function editionStatus(value: string) {
  const labels: Record<string, string> = {
    ocr_done: "Ready to search",
    downloaded: "Available",
    discovered: "New edition",
    failed: "Unavailable",
  };
  return labels[value] ?? "Available";
}

function readStoredIds(key: string) {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(key) ?? "[]");
    return new Set(
      Array.isArray(value)
        ? value.filter((item): item is string => typeof item === "string")
        : [],
    );
  } catch {
    return new Set<string>();
  }
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

function ArticleCard({
  article,
  saved,
  reviewed,
  onOpen,
  onSave,
}: {
  article: Article;
  saved: boolean;
  reviewed: boolean;
  onOpen: () => void;
  onSave: () => void;
}) {
  const summary = article.ai_summary || article.snippet;
  const needsAttention =
    (article.ai_importance ?? 0) >= 0.7 || article.ai_sentiment === "negative";
  return (
    <article className={styles.articleCard}>
      <button className={styles.coverButton} type="button" onClick={onOpen}>
        <ArticleCover article={article} />
        <span className={styles.sourceChip}>{article.publisher_name_en}</span>
        {needsAttention ? <span className={styles.priorityChip}>Needs attention</span> : null}
      </button>
      <div className={styles.articleBody}>
        <div className={styles.articleMeta}>
          <span>{formatDate(article.published_at)}</span>
          <span>·</span>
          <span>{toneLabel(article.ai_sentiment)}</span>
          {reviewed ? (
            <>
              <span>·</span>
              <span className={styles.reviewedLabel}>Reviewed</span>
            </>
          ) : null}
        </div>
        <button
          className={styles.articleTitle}
          type="button"
          onClick={onOpen}
          dir={article.language === "ar" ? "rtl" : "ltr"}
        >
          {article.title}
        </button>
        {summary ? (
          <p className={styles.articleSummary} dir={article.language === "ar" ? "rtl" : "ltr"}>
            {summary}
          </p>
        ) : null}
        <div className={styles.cardFooter}>
          <button className={styles.reviewButton} type="button" onClick={onOpen}>
            Review story <Icon name="arrow" size={13} />
          </button>
          <button
            className={`${styles.saveButton} ${saved ? styles.saveButtonActive : ""}`}
            type="button"
            onClick={onSave}
            aria-label={saved ? "Remove from saved stories" : "Save story"}
          >
            <Icon name="bookmark" size={15} />
          </button>
        </div>
      </div>
    </article>
  );
}

function StoryPanel({
  article,
  saved,
  reviewed,
  onClose,
  onSave,
  onReview,
}: {
  article: Article;
  saved: boolean;
  reviewed: boolean;
  onClose: () => void;
  onSave: () => void;
  onReview: () => void;
}) {
  const summary = article.ai_summary || article.snippet || "A summary is not available yet.";
  return (
    <div className={styles.drawerBackdrop} role="presentation" onMouseDown={onClose}>
      <aside
        className={styles.storyPanel}
        role="dialog"
        aria-modal="true"
        aria-label="Story details"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className={styles.drawerHeader}>
          <div>
            <span>{article.publisher_name_en}</span>
            <small>{formatDate(article.published_at, true)}</small>
          </div>
          <button type="button" onClick={onClose} aria-label="Close story details">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className={styles.drawerCover}>
          <ArticleCover article={article} />
        </div>
        <div className={styles.drawerContent}>
          <div className={styles.storyBadges}>
            <span>{priorityLabel(article)}</span>
            <span>{toneLabel(article.ai_sentiment)}</span>
          </div>
          <h2 dir={article.language === "ar" ? "rtl" : "ltr"}>{article.title}</h2>
          <section>
            <h3>Story summary</h3>
            <p dir={article.language === "ar" ? "rtl" : "ltr"}>{summary}</p>
          </section>
          <section className={styles.whyPanel}>
            <span>
              <Icon name="insights" size={17} />
            </span>
            <div>
              <h3>Why it may matter</h3>
              <p>{whyItMatters(article)}</p>
            </div>
          </section>
          {article.ai_topics.length ? (
            <section>
              <h3>Topics</h3>
              <div className={styles.topicRow}>
                {article.ai_topics.map((topic) => (
                  <span key={topic}>{topic}</span>
                ))}
              </div>
            </section>
          ) : null}
        </div>
        <div className={styles.drawerActions}>
          <button type="button" className={styles.primaryAction} onClick={onSave}>
            <Icon name="bookmark" size={15} />
            {saved ? "Saved" : "Save story"}
          </button>
          <button type="button" className={styles.secondaryAction} onClick={onReview}>
            <Icon name="check" size={15} />
            {reviewed ? "Reviewed" : "Mark reviewed"}
          </button>
          <a href={article.url} target="_blank" rel="noreferrer">
            View original <Icon name="external" size={14} />
          </a>
        </div>
      </aside>
    </div>
  );
}

function EmptyCoverage({
  mode,
  onSync,
}: {
  mode: CoverageMode;
  onSync: () => void;
}) {
  const copy =
    mode === "saved"
      ? ["No saved stories yet", "Save useful coverage to build a focused shortlist."]
      : mode === "priority"
        ? ["Nothing needs urgent attention", "Higher-priority coverage will appear here."]
        : ["No coverage to show yet", "Update coverage to bring in the latest reporting."];
  return (
    <div className={styles.emptyState}>
      <span className={styles.emptyIcon}>
        <Icon name={mode === "priority" ? "alert" : "coverage"} size={22} />
      </span>
      <h3>{copy[0]}</h3>
      <p>{copy[1]}</p>
      {mode === "recent" ? (
        <button onClick={onSync} type="button" className={styles.primaryAction}>
          Update coverage
        </button>
      ) : null}
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
  const [mode, setMode] = useState<CoverageMode>("recent");
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [reviewedIds, setReviewedIds] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/dashboard?limit=100`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("workspace_unavailable");
      setData((await response.json()) as DashboardData);
      setError(null);
    } catch {
      setError("We couldn’t load your workspace. Please try again in a moment.");
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 20_000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    setSavedIds(readStoredIds("newsfetcher:saved"));
    setReviewedIds(readStoredIds("newsfetcher:reviewed"));
  }, []);

  useEffect(() => {
    if (!selectedArticle) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedArticle(null);
    };
    window.addEventListener("keydown", close);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", close);
    };
  }, [selectedArticle]);

  function updateStoredSet(
    key: "newsfetcher:saved" | "newsfetcher:reviewed",
    current: Set<string>,
    setCurrent: (value: Set<string>) => void,
    articleId: string,
  ) {
    const next = new Set(current);
    if (next.has(articleId)) next.delete(articleId);
    else next.add(articleId);
    setCurrent(next);
    window.localStorage.setItem(key, JSON.stringify([...next]));
  }

  async function syncCoverage() {
    setSyncing(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/dashboard/ingest`, { method: "POST" });
      if (!response.ok) throw new Error("sync_unavailable");
      await load();
    } catch {
      setError("We couldn’t start the update. Your existing coverage is still available.");
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

  const priorityIds = useMemo(
    () =>
      new Set(
        (data?.articles ?? [])
          .filter(
            (article) =>
              (article.ai_importance ?? 0) >= 0.7 || article.ai_sentiment === "negative",
          )
          .map((article) => article.id),
      ),
    [data],
  );

  const displayedArticles = filteredArticles.filter((article) => {
    if (mode === "priority") return priorityIds.has(article.id);
    if (mode === "saved") return savedIds.has(article.id);
    return true;
  });

  const ingestActive =
    data?.ingestion?.status === "queued" || data?.ingestion?.status === "running";
  const copy = VIEW_COPY[view];

  const articleProps = (article: Article) => ({
    article,
    saved: savedIds.has(article.id),
    reviewed: reviewedIds.has(article.id),
    onOpen: () => setSelectedArticle(article),
    onSave: () =>
      updateStoredSet("newsfetcher:saved", savedIds, setSavedIds, article.id),
  });

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
              <strong>{ingestActive ? "Updating coverage" : "Coverage is current"}</strong>
              <small>
                {ingestActive
                  ? "You can keep working"
                  : `${data?.stats.articles_total ?? 0} stories available`}
              </small>
            </div>
          </div>
          <div className={styles.workspaceIdentity}>
            <span>NF</span>
            <div>
              <strong>Kuwait Media Desk</strong>
              <small>Communications workspace</small>
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
            {syncing || ingestActive ? "Updating…" : "Update coverage"}
          </button>
        </header>

        {error ? <div className={styles.errorBanner}>{error}</div> : null}
        {ingestActive ? (
          <div className={styles.updateNotice}>
            <Icon name="refresh" size={14} />
            New coverage is being added. You can continue reviewing stories.
          </div>
        ) : null}

        {view === "coverage" ? (
          <Coverage
            data={data}
            articles={displayedArticles}
            allFilteredCount={filteredArticles.length}
            priorityCount={priorityIds.size}
            savedCount={savedIds.size}
            mode={mode}
            query={query}
            publisher={publisher}
            language={language}
            setMode={setMode}
            setQuery={setQuery}
            setPublisher={setPublisher}
            setLanguage={setLanguage}
            onSync={() => void syncCoverage()}
            articleProps={articleProps}
          />
        ) : null}
        {view === "epaper" ? <Epaper data={data} /> : null}
        {view === "insights" ? (
          <Insights
            data={data}
            savedIds={savedIds}
            reviewedIds={reviewedIds}
            onOpen={setSelectedArticle}
          />
        ) : null}
      </main>

      {selectedArticle ? (
        <StoryPanel
          article={selectedArticle}
          saved={savedIds.has(selectedArticle.id)}
          reviewed={reviewedIds.has(selectedArticle.id)}
          onClose={() => setSelectedArticle(null)}
          onSave={() =>
            updateStoredSet(
              "newsfetcher:saved",
              savedIds,
              setSavedIds,
              selectedArticle.id,
            )
          }
          onReview={() =>
            updateStoredSet(
              "newsfetcher:reviewed",
              reviewedIds,
              setReviewedIds,
              selectedArticle.id,
            )
          }
        />
      ) : null}
    </div>
  );
}

function MetricCard({
  label,
  value,
  note,
  icon,
}: {
  label: string;
  value: number | string;
  note: string;
  icon: IconName;
}) {
  return (
    <article className={styles.metricCard}>
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

function Coverage({
  data,
  articles,
  allFilteredCount,
  priorityCount,
  savedCount,
  mode,
  query,
  publisher,
  language,
  setMode,
  setQuery,
  setPublisher,
  setLanguage,
  onSync,
  articleProps,
}: {
  data: DashboardData | null;
  articles: Article[];
  allFilteredCount: number;
  priorityCount: number;
  savedCount: number;
  mode: CoverageMode;
  query: string;
  publisher: string;
  language: string;
  setMode: (value: CoverageMode) => void;
  setQuery: (value: string) => void;
  setPublisher: (value: string) => void;
  setLanguage: (value: string) => void;
  onSync: () => void;
  articleProps: (article: Article) => {
    article: Article;
    saved: boolean;
    reviewed: boolean;
    onOpen: () => void;
    onSave: () => void;
  };
}) {
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="Recent coverage"
          value={data?.stats.confirmed_in_lookback ?? "—"}
          note="stories from the last five days"
          icon="coverage"
        />
        <MetricCard
          label="Ready to review"
          value={data?.stats.articles_with_body ?? "—"}
          note="stories with complete details"
          icon="check"
        />
        <MetricCard
          label="Needs attention"
          value={priorityCount}
          note="higher-priority or negative coverage"
          icon="alert"
        />
        <MetricCard label="Saved stories" value={savedCount} note="your shortlist" icon="bookmark" />
      </section>

      <div className={styles.tabs}>
        <button
          className={mode === "recent" ? styles.tabActive : ""}
          type="button"
          onClick={() => setMode("recent")}
        >
          Recent <span>{allFilteredCount}</span>
        </button>
        <button
          className={mode === "priority" ? styles.tabActive : ""}
          type="button"
          onClick={() => setMode("priority")}
        >
          Needs attention <span>{priorityCount}</span>
        </button>
        <button
          className={mode === "saved" ? styles.tabActive : ""}
          type="button"
          onClick={() => setMode("saved")}
        >
          Saved <span>{savedCount}</span>
        </button>
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
          <option value="all">All publications</option>
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
      </section>

      <div className={styles.resultHeader}>
        <h2>
          {mode === "priority"
            ? "Stories that need attention"
            : mode === "saved"
              ? "Your saved stories"
              : "Latest stories"}
        </h2>
        <span>{articles.length} stories</span>
      </div>

      {!data ? (
        <div className={styles.loadingGrid}>
          {[0, 1, 2, 3].map((item) => (
            <div className={styles.loadingCard} key={item} />
          ))}
        </div>
      ) : articles.length ? (
        <div className={styles.coverageGrid}>
          {articles.map((article) => (
            <ArticleCard {...articleProps(article)} key={article.id} />
          ))}
        </div>
      ) : (
        <EmptyCoverage mode={mode} onSync={onSync} />
      )}
    </>
  );
}

function Epaper({ data }: { data: DashboardData | null }) {
  const searchable = data?.epaper_editions.filter((item) => item.status === "ocr_done").length;
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="Recent editions"
          value={data?.epaper_editions.length ?? "—"}
          note="available in your library"
          icon="epaper"
        />
        <MetricCard
          label="Ready to search"
          value={searchable ?? "—"}
          note="editions with searchable text"
          icon="search"
        />
        <MetricCard
          label="Total pages"
          value={data?.epaper_editions.reduce((sum, item) => sum + item.page_count, 0) ?? "—"}
          note="across recent editions"
          icon="coverage"
        />
        <MetricCard label="Saved cuttings" value="0" note="your selected clippings" icon="bookmark" />
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
              <span className={styles.readyBadge}>{editionStatus(edition.status)}</span>
              {edition.source_url ? (
                <a href={edition.source_url} target="_blank" rel="noreferrer">
                  Open edition <Icon name="external" size={14} />
                </a>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

function Insights({
  data,
  savedIds,
  reviewedIds,
  onOpen,
}: {
  data: DashboardData | null;
  savedIds: Set<string>;
  reviewedIds: Set<string>;
  onOpen: (article: Article) => void;
}) {
  const enriched = (data?.articles ?? []).filter((article) => article.ai_summary);
  const priority = enriched.filter(
    (article) => (article.ai_importance ?? 0) >= 0.7 || article.ai_sentiment === "negative",
  );
  const negative = enriched.filter((article) => article.ai_sentiment === "negative");
  const tones = enriched.reduce<Record<string, number>>((counts, article) => {
    const tone = article.ai_sentiment ?? "neutral";
    counts[tone] = (counts[tone] ?? 0) + 1;
    return counts;
  }, {});
  const dominantTone =
    Object.entries(tones).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "neutral";
  const topicCounts = enriched.reduce<Map<string, number>>((counts, article) => {
    article.ai_topics.forEach((topic) => counts.set(topic, (counts.get(topic) ?? 0) + 1));
    return counts;
  }, new Map());
  const topTopics = [...topicCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);

  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label="Stories understood"
          value={data?.ai_status.deepseek.enriched_articles ?? enriched.length}
          note="summarized in plain language"
          icon="insights"
        />
        <MetricCard
          label="Needs attention"
          value={priority.length}
          note="higher-priority stories shown here"
          icon="alert"
        />
        <MetricCard
          label="Negative coverage"
          value={negative.length}
          note="stories to review more closely"
          icon="tone"
        />
        <MetricCard
          label="Trending topics"
          value={topTopics.length}
          note="themes appearing across coverage"
          icon="coverage"
        />
      </section>

      <section className={styles.briefingPanel}>
        <div className={styles.briefingIntro}>
          <span className={styles.briefingIcon}>
            <Icon name="insights" size={21} />
          </span>
          <div>
            <p>Today’s media briefing</p>
            <h2>What deserves your attention</h2>
            <span>
              We reviewed {enriched.length} recent stories. {priority.length} stand out for a
              closer look{negative.length ? `, including ${negative.length} with negative tone` : ""}.
            </span>
          </div>
        </div>
        <div className={styles.signalGrid}>
          <article>
            <span>
              <Icon name="alert" size={16} />
            </span>
            <div>
              <small>Reputation watch</small>
              <strong>
                {negative.length
                  ? `${negative.length} negative ${negative.length === 1 ? "story" : "stories"}`
                  : "No negative stories"}
              </strong>
              <p>Review tone and context before deciding whether action is needed.</p>
            </div>
          </article>
          <article>
            <span>
              <Icon name="tone" size={16} />
            </span>
            <div>
              <small>Overall tone</small>
              <strong>{toneLabel(dominantTone)}</strong>
              <p>The most common tone across the stories reviewed today.</p>
            </div>
          </article>
          <article>
            <span>
              <Icon name="coverage" size={16} />
            </span>
            <div>
              <small>Trending conversation</small>
              <strong>{topTopics.slice(0, 3).map(([topic]) => topic).join(" · ") || "Building"}</strong>
              <p>The themes appearing most often across recent reporting.</p>
            </div>
          </article>
        </div>
      </section>

      <div className={styles.resultHeader}>
        <h2>Stories worth your attention</h2>
        <span>{priority.length} stories</span>
      </div>
      {priority.length ? (
        <div className={styles.insightList}>
          {priority.map((article) => (
            <button type="button" onClick={() => onOpen(article)} key={article.id}>
              <span
                className={`${styles.insightSignal} ${
                  article.ai_sentiment === "negative" ? styles.insightSignalNegative : ""
                }`}
              >
                <Icon
                  name={article.ai_sentiment === "negative" ? "alert" : "insights"}
                  size={17}
                />
              </span>
              <div>
                <div className={styles.articleMeta}>
                  <span>{article.publisher_name_en}</span>
                  <span>·</span>
                  <span>{toneLabel(article.ai_sentiment)}</span>
                  {savedIds.has(article.id) ? (
                    <>
                      <span>·</span>
                      <span>Saved</span>
                    </>
                  ) : null}
                  {reviewedIds.has(article.id) ? (
                    <>
                      <span>·</span>
                      <span className={styles.reviewedLabel}>Reviewed</span>
                    </>
                  ) : null}
                </div>
                <h3 dir={article.language === "ar" ? "rtl" : "ltr"}>{article.title}</h3>
                <p dir={article.language === "ar" ? "rtl" : "ltr"}>{article.ai_summary}</p>
              </div>
              <Icon name="arrow" size={16} />
            </button>
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <span className={styles.emptyIcon}>
            <Icon name="insights" size={22} />
          </span>
          <h3>Your briefing is being prepared</h3>
          <p>Important stories and themes will appear here as new coverage arrives.</p>
        </div>
      )}
    </>
  );
}
