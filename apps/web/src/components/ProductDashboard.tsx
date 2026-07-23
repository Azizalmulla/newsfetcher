"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import styles from "./ProductDashboard.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type DashboardView = "coverage" | "epaper" | "insights";
type CoverageMode = "recent" | "priority" | "saved";
type Locale = "en" | "ar";

const EN = {
  workspace: "Workspace",
  coverage: "Coverage",
  insights: "Insights",
  epaper: "E-paper",
  output: "Output",
  reports: "Reports",
  soon: "Soon",
  coverageTitle: "Media coverage",
  coverageSubtitle:
    "Review what is being said, understand what matters, and save key stories.",
  insightsTitle: "Insights",
  insightsSubtitle:
    "A clear view of the stories, themes, and reputational signals worth your attention.",
  epaperTitle: "E-paper library",
  epaperSubtitle: "Browse recent newspaper editions and open the original publication.",
  updatingCoverage: "Updating coverage",
  coverageCurrent: "Coverage is current",
  keepWorking: "You can keep working",
  storiesAvailable: "stories available",
  communicationsWorkspace: "Communications workspace",
  updating: "Updating…",
  updateCoverage: "Update coverage",
  newCoverage: "New coverage is being added. You can continue reviewing stories.",
  loadError: "We couldn’t load your workspace. Please try again in a moment.",
  updateError: "We couldn’t start the update. Your existing coverage is still available.",
  monitoringFocus: "Monitoring focus",
  focusActive: "Priorities are personalized for",
  focusEmpty:
    "Add an organization, person, competitor, or topic to personalize priorities.",
  focusPlaceholder: "e.g. Kuwait Airways or وزارة الصحة",
  apply: "Apply",
  clear: "Clear",
  dateUnavailable: "Date unavailable",
  positiveTone: "Positive tone",
  negativeTone: "Negative tone",
  mixedTone: "Mixed tone",
  neutralTone: "Neutral tone",
  needsAttention: "Needs attention",
  reviewed: "Reviewed",
  reviewStory: "Review story",
  saveStory: "Save story",
  saved: "Saved",
  markReviewed: "Mark reviewed",
  viewOriginal: "View original",
  highPriority: "High priority",
  worthReviewing: "Worth reviewing",
  standardCoverage: "Standard coverage",
  storySummary: "Story summary",
  whyMatter: "Why it may matter",
  topics: "Topics",
  negativeWhy: "The tone may warrant a closer look from your communications team.",
  priorityWhy:
    "This story ranks among the higher-priority coverage in your current news cycle.",
  contextWhy:
    "This story provides useful context for understanding the current media conversation.",
  noSaved: "No saved stories yet",
  noSavedHelp: "Save useful coverage to build a focused shortlist.",
  noPriority: "Nothing needs urgent attention",
  noPriorityHelp: "Higher-priority coverage will appear here.",
  noCoverage: "No coverage to show yet",
  noCoverageHelp: "Update coverage to bring in the latest reporting.",
  recentCoverage: "Recent coverage",
  recentCoverageHelp: "stories from the last five days",
  readyReview: "Ready to review",
  readyReviewHelp: "stories with complete details",
  attentionHelp: "personalized higher-priority coverage",
  savedStories: "Saved stories",
  shortlist: "your shortlist",
  recent: "Recent",
  allPublications: "All publications",
  allLanguages: "All languages",
  arabic: "Arabic",
  english: "English",
  searchPlaceholder: "Search headlines, summaries, or topics…",
  priorityResults: "Stories that need attention",
  savedResults: "Your saved stories",
  latestStories: "Latest stories",
  stories: "stories",
  loadMore: "Load more stories",
  recentEditions: "Recent editions",
  libraryHelp: "available in your library",
  readySearch: "Ready to search",
  searchableHelp: "editions with searchable text",
  totalPages: "Total pages",
  pagesHelp: "across recent editions",
  savedCuttings: "Saved cuttings",
  selectedClippings: "your selected clippings",
  newestFirst: "Newest first",
  pages: "pages",
  openEdition: "Open edition",
  available: "Available",
  newEdition: "New edition",
  unavailable: "Unavailable",
  todaysBriefing: "Today’s briefing",
  closerLook: "stories deserve a closer look",
  noUrgent: "No urgent issues in recent coverage",
  reviewedPrefix: "We reviewed",
  recentStories: "recent stories",
  overallTone: "The overall tone is",
  negativeCoverageSuffix: "carrying negative coverage.",
  noNegative: "with no negative stories requiring immediate attention.",
  trendingConversations: "Trending conversations",
  topicsPending: "Topics will appear as coverage develops",
  reputationPulse: "Reputation pulse",
  startNegative:
    "Start with the negative stories below, then decide whether monitoring or a response is appropriate.",
  stableCoverage: "Coverage is stable. Continue monitoring the leading conversations.",
  positive: "Positive",
  neutral: "Neutral",
  mixed: "Mixed",
  negative: "Negative",
  priorityCoverage: "Priority coverage",
  startStories: "Start with these stories",
  selectionReason: "Selected dynamically for relevance, impact, tone, and source context.",
  reputationWatch: "Reputation watch",
  negativeCoverage: "Negative coverage",
  priorityStory: "Priority story",
  suggestedNext: "Suggested next step",
  reviewClosely: "Review closely",
  shareInternally: "Share internally",
  keepMonitoring: "Keep monitoring",
  noPriorityNow: "No priority stories right now",
  noPriorityNowHelp: "Your briefing will highlight stories when closer attention is useful.",
};

const AR: typeof EN = {
  workspace: "مساحة العمل",
  coverage: "التغطية",
  insights: "الرؤى",
  epaper: "الصحف الإلكترونية",
  output: "المخرجات",
  reports: "التقارير",
  soon: "قريباً",
  coverageTitle: "التغطية الإعلامية",
  coverageSubtitle: "راجع ما يُقال، وافهم ما يهم، واحفظ الأخبار الرئيسية.",
  insightsTitle: "الرؤى",
  insightsSubtitle: "نظرة واضحة على الأخبار والمواضيع والإشارات التي تستحق اهتمامك.",
  epaperTitle: "مكتبة الصحف الإلكترونية",
  epaperSubtitle: "تصفح أحدث الأعداد وافتح النسخة الأصلية.",
  updatingCoverage: "جاري تحديث التغطية",
  coverageCurrent: "التغطية محدثة",
  keepWorking: "يمكنك متابعة العمل",
  storiesAvailable: "خبر متاح",
  communicationsWorkspace: "مساحة عمل فريق الاتصال",
  updating: "جاري التحديث…",
  updateCoverage: "تحديث التغطية",
  newCoverage: "تتم إضافة أخبار جديدة. يمكنك متابعة مراجعة الأخبار.",
  loadError: "تعذر تحميل مساحة العمل. يرجى المحاولة بعد قليل.",
  updateError: "تعذر بدء التحديث. تغطيتك الحالية ما زالت متاحة.",
  monitoringFocus: "محور المتابعة",
  focusActive: "تم تخصيص الأولويات لـ",
  focusEmpty: "أضف جهة أو شخصاً أو منافساً أو موضوعاً لتخصيص الأولويات.",
  focusPlaceholder: "مثال: الخطوط الجوية الكويتية أو وزارة الصحة",
  apply: "تطبيق",
  clear: "مسح",
  dateUnavailable: "التاريخ غير متاح",
  positiveTone: "نبرة إيجابية",
  negativeTone: "نبرة سلبية",
  mixedTone: "نبرة مختلطة",
  neutralTone: "نبرة محايدة",
  needsAttention: "يحتاج اهتماماً",
  reviewed: "تمت المراجعة",
  reviewStory: "مراجعة الخبر",
  saveStory: "حفظ الخبر",
  saved: "محفوظ",
  markReviewed: "تحديد كمراجَع",
  viewOriginal: "عرض المصدر الأصلي",
  highPriority: "أولوية عالية",
  worthReviewing: "يستحق المراجعة",
  standardCoverage: "تغطية عادية",
  storySummary: "ملخص الخبر",
  whyMatter: "لماذا قد يهم",
  topics: "المواضيع",
  negativeWhy: "قد تستدعي نبرة الخبر مراجعة أقرب من فريق الاتصال.",
  priorityWhy: "يُصنف هذا الخبر ضمن التغطيات الأعلى أولوية في الدورة الحالية.",
  contextWhy: "يوفر هذا الخبر سياقاً مفيداً لفهم الحوار الإعلامي الحالي.",
  noSaved: "لا توجد أخبار محفوظة",
  noSavedHelp: "احفظ التغطيات المهمة لبناء قائمة مختصرة.",
  noPriority: "لا توجد أخبار عاجلة",
  noPriorityHelp: "ستظهر التغطيات الأعلى أولوية هنا.",
  noCoverage: "لا توجد تغطية بعد",
  noCoverageHelp: "حدّث التغطية لجلب أحدث الأخبار.",
  recentCoverage: "التغطية الحديثة",
  recentCoverageHelp: "أخبار من آخر خمسة أيام",
  readyReview: "جاهز للمراجعة",
  readyReviewHelp: "أخبار بتفاصيل مكتملة",
  attentionHelp: "تغطيات مخصصة ذات أولوية أعلى",
  savedStories: "الأخبار المحفوظة",
  shortlist: "قائمتك المختصرة",
  recent: "الأحدث",
  allPublications: "جميع الصحف",
  allLanguages: "جميع اللغات",
  arabic: "العربية",
  english: "الإنجليزية",
  searchPlaceholder: "ابحث في العناوين أو الملخصات أو المواضيع…",
  priorityResults: "أخبار تحتاج إلى اهتمام",
  savedResults: "أخبارك المحفوظة",
  latestStories: "أحدث الأخبار",
  stories: "خبر",
  loadMore: "عرض المزيد من الأخبار",
  recentEditions: "أحدث الأعداد",
  libraryHelp: "متاحة في مكتبتك",
  readySearch: "جاهزة للبحث",
  searchableHelp: "أعداد بنص قابل للبحث",
  totalPages: "إجمالي الصفحات",
  pagesHelp: "في أحدث الأعداد",
  savedCuttings: "القصاصات المحفوظة",
  selectedClippings: "قصاصاتك المختارة",
  newestFirst: "الأحدث أولاً",
  pages: "صفحة",
  openEdition: "فتح العدد",
  available: "متاح",
  newEdition: "عدد جديد",
  unavailable: "غير متاح",
  todaysBriefing: "موجز اليوم",
  closerLook: "أخبار تستحق نظرة أقرب",
  noUrgent: "لا توجد قضايا عاجلة في التغطية الحديثة",
  reviewedPrefix: "راجعنا",
  recentStories: "خبراً حديثاً",
  overallTone: "النبرة العامة",
  negativeCoverageSuffix: "بتغطية سلبية.",
  noNegative: "من دون أخبار سلبية تتطلب اهتماماً فورياً.",
  trendingConversations: "المواضيع الرائجة",
  topicsPending: "ستظهر المواضيع مع تطور التغطية",
  reputationPulse: "مؤشر السمعة",
  startNegative: "ابدأ بالأخبار السلبية أدناه ثم قرر ما إذا كانت تحتاج متابعة أو استجابة.",
  stableCoverage: "التغطية مستقرة. واصل متابعة المواضيع الرئيسية.",
  positive: "إيجابي",
  neutral: "محايد",
  mixed: "مختلط",
  negative: "سلبي",
  priorityCoverage: "التغطية ذات الأولوية",
  startStories: "ابدأ بهذه الأخبار",
  selectionReason: "اختيار ديناميكي حسب الصلة والتأثير والنبرة وسياق المصدر.",
  reputationWatch: "مراقبة السمعة",
  negativeCoverage: "تغطية سلبية",
  priorityStory: "خبر ذو أولوية",
  suggestedNext: "الخطوة المقترحة",
  reviewClosely: "مراجعة دقيقة",
  shareInternally: "مشاركة داخلية",
  keepMonitoring: "استمرار المتابعة",
  noPriorityNow: "لا توجد أخبار ذات أولوية حالياً",
  noPriorityNowHelp: "سيُظهر الموجز الأخبار عندما تستحق اهتماماً أقرب.",
};

type UIStrings = typeof EN;

type Article = {
  id: string;
  story_cluster_id: string | null;
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

const NAV_ITEMS: Array<{
  view: DashboardView;
  label: keyof UIStrings;
  href: string;
  icon: IconName;
}> = [
  { view: "coverage", label: "coverage", href: "/", icon: "coverage" },
  { view: "epaper", label: "epaper", href: "/epaper", icon: "epaper" },
];

const VIEW_COPY: Record<
  DashboardView,
  { title: keyof UIStrings; subtitle: keyof UIStrings }
> = {
  coverage: {
    title: "coverageTitle",
    subtitle: "coverageSubtitle",
  },
  insights: {
    title: "insightsTitle",
    subtitle: "insightsSubtitle",
  },
  epaper: {
    title: "epaperTitle",
    subtitle: "epaperSubtitle",
  },
};

function formatDate(
  value: string | null,
  locale: Locale,
  ui: UIStrings,
  withTime = false,
) {
  if (!value) return ui.dateUnavailable;
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-KW" : "en-GB", {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" as const } : {}),
  }).format(new Date(value));
}

function priorityLabel(article: Article, ui: UIStrings) {
  if ((article.ai_importance ?? 0) >= 0.7) return ui.highPriority;
  if ((article.ai_importance ?? 0) >= 0.45) return ui.worthReviewing;
  return ui.standardCoverage;
}

function toneLabel(value: string | null, ui: UIStrings) {
  const labels: Record<string, string> = {
    positive: ui.positiveTone,
    negative: ui.negativeTone,
    mixed: ui.mixedTone,
    neutral: ui.neutralTone,
  };
  return labels[value ?? "neutral"] ?? ui.neutralTone;
}

function whyItMatters(article: Article, ui: UIStrings) {
  if (article.ai_sentiment === "negative") {
    return ui.negativeWhy;
  }
  if ((article.ai_importance ?? 0) >= 0.7) {
    return ui.priorityWhy;
  }
  return ui.contextWhy;
}

function editionStatus(value: string, ui: UIStrings) {
  const labels: Record<string, string> = {
    ocr_done: ui.readySearch,
    downloaded: ui.available,
    discovered: ui.newEdition,
    failed: ui.unavailable,
  };
  return labels[value] ?? ui.available;
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

function rankPriorityArticles(articles: Article[], focus: string) {
  const normalizedFocus = focus.trim().toLowerCase();
  const focusTokens = [
    normalizedFocus,
    ...normalizedFocus.split(/[\s,،]+/).filter((token) => token.length >= 2),
  ].filter(Boolean);
  const ranked = articles
    .map((article) => {
      const text = [
        article.title,
        article.ai_summary ?? "",
        article.snippet ?? "",
        article.ai_topics.join(" "),
      ]
        .join(" ")
        .toLowerCase();
      const relevance = focusTokens.length
        ? focusTokens.filter((token) => text.includes(token)).length / focusTokens.length
        : 0;
      const toneWeight =
        article.ai_sentiment === "negative"
          ? 0.2
          : article.ai_sentiment === "mixed"
            ? 0.08
            : 0;
      const importance = article.ai_importance ?? 0.35;
      const score = focusTokens.length
        ? relevance * 0.68 + importance * 0.24 + toneWeight * 0.08
        : importance * 0.8 + toneWeight;
      return { article, relevance, score };
    })
    .filter((item) => !focusTokens.length || item.relevance > 0)
    .sort((left, right) => right.score - left.score);

  if (!ranked.length) return [];
  const scores = ranked.map((item) => item.score).sort((a, b) => a - b);
  const percentileIndex = Math.max(0, Math.floor(scores.length * 0.72) - 1);
  const adaptiveThreshold = focusTokens.length
    ? Math.max(0.3, scores[percentileIndex])
    : Math.max(0.68, scores[percentileIndex]);
  const seen = new Set<string>();
  return ranked
    .filter((item) => item.score >= adaptiveThreshold)
    .filter(({ article }) => {
      const key =
        article.story_cluster_id ??
        article.title.toLowerCase().replace(/\s+/g, " ").slice(0, 80);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((item) => item.article);
}

function ArticleCover({ article, locale }: { article: Article; locale: Locale }) {
  const [failed, setFailed] = useState(false);
  if (!article.cover_image_url || failed) {
    return (
      <div
        className={styles.coverFallback}
        dir={article.language === "ar" ? "rtl" : "ltr"}
      >
        <small>
          {locale === "ar" ? article.publisher_name_ar : article.publisher_name_en}
        </small>
        <i className={styles.coverFallbackRule} />
        <strong>{article.title}</strong>
        <span className={styles.coverFallbackLines}>
          <i />
          <i />
          <i />
        </span>
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
  locale,
  ui,
  onOpen,
  onSave,
}: {
  article: Article;
  saved: boolean;
  reviewed: boolean;
  locale: Locale;
  ui: UIStrings;
  onOpen: () => void;
  onSave: () => void;
}) {
  const summary = article.ai_summary || article.snippet;
  const needsAttention =
    (article.ai_importance ?? 0) >= 0.7 || article.ai_sentiment === "negative";
  return (
    <article className={styles.articleCard}>
      <button className={styles.coverButton} type="button" onClick={onOpen}>
        <ArticleCover article={article} locale={locale} />
        <span className={styles.sourceChip}>
          {locale === "ar" ? article.publisher_name_ar : article.publisher_name_en}
        </span>
        {needsAttention ? <span className={styles.priorityChip}>{ui.needsAttention}</span> : null}
      </button>
      <div className={styles.articleBody}>
        <div className={styles.articleMeta}>
          <span>{formatDate(article.published_at, locale, ui)}</span>
          <span>·</span>
          <span>{toneLabel(article.ai_sentiment, ui)}</span>
          {reviewed ? (
            <>
              <span>·</span>
              <span className={styles.reviewedLabel}>{ui.reviewed}</span>
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
            {ui.reviewStory} <Icon name="arrow" size={13} />
          </button>
          <button
            className={`${styles.saveButton} ${saved ? styles.saveButtonActive : ""}`}
            type="button"
            onClick={onSave}
            aria-label={saved ? ui.saved : ui.saveStory}
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
  locale,
  ui,
  onClose,
  onSave,
  onReview,
}: {
  article: Article;
  saved: boolean;
  reviewed: boolean;
  locale: Locale;
  ui: UIStrings;
  onClose: () => void;
  onSave: () => void;
  onReview: () => void;
}) {
  const summary = article.ai_summary || article.snippet || ui.storySummary;
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
            <span>{locale === "ar" ? article.publisher_name_ar : article.publisher_name_en}</span>
            <small>{formatDate(article.published_at, locale, ui, true)}</small>
          </div>
          <button type="button" onClick={onClose} aria-label="Close story details">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className={styles.drawerCover}>
          <ArticleCover article={article} locale={locale} />
        </div>
        <div className={styles.drawerContent}>
          <div className={styles.storyBadges}>
            <span>{priorityLabel(article, ui)}</span>
            <span>{toneLabel(article.ai_sentiment, ui)}</span>
          </div>
          <h2 dir={article.language === "ar" ? "rtl" : "ltr"}>{article.title}</h2>
          <section>
            <h3>{ui.storySummary}</h3>
            <p dir={article.language === "ar" ? "rtl" : "ltr"}>{summary}</p>
          </section>
          <section className={styles.whyPanel}>
            <span>
              <Icon name="insights" size={17} />
            </span>
            <div>
              <h3>{ui.whyMatter}</h3>
              <p>{whyItMatters(article, ui)}</p>
            </div>
          </section>
          {article.ai_topics.length ? (
            <section>
              <h3>{ui.topics}</h3>
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
            {saved ? ui.saved : ui.saveStory}
          </button>
          <button type="button" className={styles.secondaryAction} onClick={onReview}>
            <Icon name="check" size={15} />
            {reviewed ? ui.reviewed : ui.markReviewed}
          </button>
          <a href={article.url} target="_blank" rel="noreferrer">
            {ui.viewOriginal} <Icon name="external" size={14} />
          </a>
        </div>
      </aside>
    </div>
  );
}

function EmptyCoverage({
  mode,
  ui,
  onSync,
}: {
  mode: CoverageMode;
  ui: UIStrings;
  onSync: () => void;
}) {
  const copy =
    mode === "saved"
      ? [ui.noSaved, ui.noSavedHelp]
      : mode === "priority"
        ? [ui.noPriority, ui.noPriorityHelp]
        : [ui.noCoverage, ui.noCoverageHelp];
  return (
    <div className={styles.emptyState}>
      <span className={styles.emptyIcon}>
        <Icon name={mode === "priority" ? "alert" : "coverage"} size={22} />
      </span>
      <h3>{copy[0]}</h3>
      <p>{copy[1]}</p>
      {mode === "recent" ? (
        <button onClick={onSync} type="button" className={styles.primaryAction}>
          {ui.updateCoverage}
        </button>
      ) : null}
    </div>
  );
}

function MonitoringFocus({
  focus,
  draft,
  ui,
  setDraft,
  onSave,
  onClear,
}: {
  focus: string;
  draft: string;
  ui: UIStrings;
  setDraft: (value: string) => void;
  onSave: () => void;
  onClear: () => void;
}) {
  return (
    <section className={styles.focusBar}>
      <span className={styles.focusIcon}>
        <Icon name="insights" size={17} />
      </span>
      <div className={styles.focusCopy}>
        <strong>{ui.monitoringFocus}</strong>
        <small>
          {focus
            ? `${ui.focusActive} “${focus}”.`
            : ui.focusEmpty}
        </small>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave();
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={ui.focusPlaceholder}
          aria-label="Monitoring focus"
        />
        <button type="submit">{ui.apply}</button>
        {focus ? (
          <button type="button" onClick={onClear}>
            {ui.clear}
          </button>
        ) : null}
      </form>
    </section>
  );
}

export default function ProductDashboard({ view }: { view: DashboardView }) {
  const [locale, setLocale] = useState<Locale>("en");
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
  const [focus, setFocus] = useState("");
  const [focusDraft, setFocusDraft] = useState("");
  const [visibleCount, setVisibleCount] = useState(24);
  const ui = locale === "ar" ? AR : EN;

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/dashboard?limit=600`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("workspace_unavailable");
      setData((await response.json()) as DashboardData);
      setError(null);
    } catch {
      setError(ui.loadError);
    }
  }, [ui.loadError]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setSavedIds(readStoredIds("newsfetcher:saved"));
    setReviewedIds(readStoredIds("newsfetcher:reviewed"));
    const storedLocale = window.localStorage.getItem("newsfetcher:locale");
    const initialLocale =
      storedLocale === "ar" || storedLocale === "en"
        ? storedLocale
        : navigator.language.toLowerCase().startsWith("ar")
          ? "ar"
          : "en";
    setLocale(initialLocale);
    const storedFocus = window.localStorage.getItem("newsfetcher:focus") ?? "";
    setFocus(storedFocus);
    setFocusDraft(storedFocus);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
  }, [locale]);

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
      setError(ui.updateError);
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

  const priorityArticles = useMemo(
    () => rankPriorityArticles(data?.articles ?? [], focus),
    [data, focus],
  );
  const priorityIds = useMemo(
    () => new Set(priorityArticles.map((article) => article.id)),
    [priorityArticles],
  );

  const displayedArticles = filteredArticles.filter((article) => {
    if (mode === "priority") return priorityIds.has(article.id);
    if (mode === "saved") return savedIds.has(article.id);
    return true;
  });

  const ingestActive =
    data?.ingestion?.status === "queued" || data?.ingestion?.status === "running";
  const visibleArticles = displayedArticles.slice(0, visibleCount);
  const copy = VIEW_COPY[view];

  useEffect(() => {
    if (!ingestActive) return;
    const timer = window.setInterval(() => void load(), 8_000);
    return () => window.clearInterval(timer);
  }, [ingestActive, load]);

  useEffect(() => {
    setVisibleCount(24);
  }, [focus, language, mode, publisher, query]);

  const articleProps = (article: Article) => ({
    article,
    saved: savedIds.has(article.id),
    reviewed: reviewedIds.has(article.id),
    locale,
    ui,
    onOpen: () => setSelectedArticle(article),
    onSave: () =>
      updateStoredSet("newsfetcher:saved", savedIds, setSavedIds, article.id),
  });

  return (
    <div className={styles.app} dir={locale === "ar" ? "rtl" : "ltr"} lang={locale}>
      <aside className={styles.sidebar}>
        <Link className={styles.logo} href="/">
          <span>NewsFetcher</span>
        </Link>
        <nav className={styles.sidebarNav} aria-label={ui.workspace}>
          <span className={styles.navLabel}>{ui.workspace}</span>
          {NAV_ITEMS.map((item) => (
            <Link
              className={`${styles.navItem} ${item.view === view ? styles.navItemActive : ""}`}
              href={item.href}
              key={item.view}
            >
              <Icon name={item.icon} size={17} />
              <span>{ui[item.label]}</span>
              {item.view === "coverage" && data?.stats.confirmed_in_lookback ? (
                <span className={styles.navCount}>{data.stats.confirmed_in_lookback}</span>
              ) : null}
            </Link>
          ))}
          <span className={styles.navLabel}>{ui.output}</span>
          <span className={styles.navItemDisabled}>
            <Icon name="reports" size={17} />
            <span>{ui.reports}</span>
            <small>{ui.soon}</small>
          </span>
        </nav>
        <div className={styles.sidebarBottom}>
          <div className={styles.syncStatus}>
            <span
              className={`${styles.statusDot} ${ingestActive ? styles.statusDotBusy : ""}`}
            />
            <div>
              <strong>{ingestActive ? ui.updatingCoverage : ui.coverageCurrent}</strong>
              <small>
                {ingestActive
                  ? ui.keepWorking
                  : `${data?.stats.articles_total ?? 0} ${ui.storiesAvailable}`}
              </small>
            </div>
          </div>
          <div className={styles.workspaceIdentity}>
            <span>NF</span>
            <div>
              <strong>Kuwait Media Desk</strong>
              <small>{ui.communicationsWorkspace}</small>
            </div>
          </div>
        </div>
      </aside>

      <main className={styles.main}>
        <header className={styles.pageHeader}>
          <div>
            <p className={styles.breadcrumb}>NewsFetcher / {ui[copy.title]}</p>
            <h1>{ui[copy.title]}</h1>
            <p>{ui[copy.subtitle]}</p>
          </div>
          <div className={styles.headerActions}>
            <div className={styles.localeToggle} aria-label="Interface language">
              <button
                type="button"
                className={locale === "en" ? styles.localeActive : ""}
                onClick={() => {
                  setLocale("en");
                  window.localStorage.setItem("newsfetcher:locale", "en");
                }}
              >
                EN
              </button>
              <button
                type="button"
                className={locale === "ar" ? styles.localeActive : ""}
                onClick={() => {
                  setLocale("ar");
                  window.localStorage.setItem("newsfetcher:locale", "ar");
                }}
              >
                عربي
              </button>
            </div>
            <button
              type="button"
              className={styles.syncButton}
              onClick={() => void syncCoverage()}
              disabled={syncing || ingestActive}
            >
              <Icon name="refresh" size={15} />
              {syncing || ingestActive ? ui.updating : ui.updateCoverage}
            </button>
          </div>
        </header>

        {error ? <div className={styles.errorBanner}>{error}</div> : null}
        {ingestActive && view === "coverage" ? (
          <div className={styles.updateNotice}>
            <Icon name="refresh" size={14} />
            {ui.newCoverage}
          </div>
        ) : null}
        {view !== "epaper" ? (
          <MonitoringFocus
            focus={focus}
            draft={focusDraft}
            ui={ui}
            setDraft={setFocusDraft}
            onSave={() => {
              const next = focusDraft.trim();
              setFocus(next);
              window.localStorage.setItem("newsfetcher:focus", next);
            }}
            onClear={() => {
              setFocus("");
              setFocusDraft("");
              window.localStorage.removeItem("newsfetcher:focus");
            }}
          />
        ) : null}

        {view === "coverage" ? (
          <Coverage
            data={data}
            articles={visibleArticles}
            resultCount={displayedArticles.length}
            hasMore={visibleArticles.length < displayedArticles.length}
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
            onLoadMore={() => setVisibleCount((count) => count + 24)}
            articleProps={articleProps}
            ui={ui}
          />
        ) : null}
        {view === "epaper" ? <Epaper data={data} locale={locale} ui={ui} /> : null}
        {view === "insights" ? (
          <Insights
            data={data}
            savedIds={savedIds}
            reviewedIds={reviewedIds}
            priorityArticles={priorityArticles}
            focus={focus}
            locale={locale}
            ui={ui}
            onOpen={setSelectedArticle}
          />
        ) : null}
      </main>

      {selectedArticle ? (
        <StoryPanel
          article={selectedArticle}
          saved={savedIds.has(selectedArticle.id)}
          reviewed={reviewedIds.has(selectedArticle.id)}
          locale={locale}
          ui={ui}
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
  resultCount,
  hasMore,
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
  onLoadMore,
  articleProps,
  ui,
}: {
  data: DashboardData | null;
  articles: Article[];
  resultCount: number;
  hasMore: boolean;
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
  onLoadMore: () => void;
  ui: UIStrings;
  articleProps: (article: Article) => {
    article: Article;
    saved: boolean;
    reviewed: boolean;
    locale: Locale;
    ui: UIStrings;
    onOpen: () => void;
    onSave: () => void;
  };
}) {
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label={ui.recentCoverage}
          value={data?.stats.confirmed_in_lookback ?? "—"}
          note={ui.recentCoverageHelp}
          icon="coverage"
        />
        <MetricCard
          label={ui.readyReview}
          value={data?.stats.articles_with_body ?? "—"}
          note={ui.readyReviewHelp}
          icon="check"
        />
        <MetricCard
          label={ui.needsAttention}
          value={priorityCount}
          note={ui.attentionHelp}
          icon="alert"
        />
        <MetricCard label={ui.savedStories} value={savedCount} note={ui.shortlist} icon="bookmark" />
      </section>

      <div className={styles.tabs}>
        <button
          className={mode === "recent" ? styles.tabActive : ""}
          type="button"
          onClick={() => setMode("recent")}
        >
          {ui.recent} <span>{allFilteredCount}</span>
        </button>
        <button
          className={mode === "priority" ? styles.tabActive : ""}
          type="button"
          onClick={() => setMode("priority")}
        >
          {ui.needsAttention} <span>{priorityCount}</span>
        </button>
        <button
          className={mode === "saved" ? styles.tabActive : ""}
          type="button"
          onClick={() => setMode("saved")}
        >
          {ui.saved} <span>{savedCount}</span>
        </button>
      </div>

      <section className={styles.filterPanel}>
        <label className={styles.searchField}>
          <Icon name="search" size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={ui.searchPlaceholder}
          />
        </label>
        <select value={publisher} onChange={(event) => setPublisher(event.target.value)}>
          <option value="all">{ui.allPublications}</option>
          {(data?.publishers ?? []).map((item) => (
            <option value={item.code} key={item.code}>
              {ui === AR ? item.name_ar : item.name_en}
            </option>
          ))}
        </select>
        <select value={language} onChange={(event) => setLanguage(event.target.value)}>
          <option value="all">{ui.allLanguages}</option>
          <option value="ar">{ui.arabic}</option>
          <option value="en">{ui.english}</option>
        </select>
      </section>

      <div className={styles.resultHeader}>
        <h2>
          {mode === "priority"
            ? ui.priorityResults
            : mode === "saved"
              ? ui.savedResults
              : ui.latestStories}
        </h2>
        <span>{articles.length} / {resultCount} {ui.stories}</span>
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
        <EmptyCoverage mode={mode} ui={ui} onSync={onSync} />
      )}
      {hasMore ? (
        <button type="button" className={styles.loadMoreButton} onClick={onLoadMore}>
          {ui.loadMore}
        </button>
      ) : null}
    </>
  );
}

function Epaper({
  data,
  locale,
  ui,
}: {
  data: DashboardData | null;
  locale: Locale;
  ui: UIStrings;
}) {
  const searchable = data?.epaper_editions.filter((item) => item.status === "ocr_done").length;
  return (
    <>
      <section className={styles.metrics}>
        <MetricCard
          label={ui.recentEditions}
          value={data?.epaper_editions.length ?? "—"}
          note={ui.libraryHelp}
          icon="epaper"
        />
        <MetricCard
          label={ui.readySearch}
          value={searchable ?? "—"}
          note={ui.searchableHelp}
          icon="search"
        />
        <MetricCard
          label={ui.totalPages}
          value={data?.epaper_editions.reduce((sum, item) => sum + item.page_count, 0) ?? "—"}
          note={ui.pagesHelp}
          icon="coverage"
        />
        <MetricCard label={ui.savedCuttings} value="0" note={ui.selectedClippings} icon="bookmark" />
      </section>

      <div className={styles.resultHeader}>
        <h2>{ui.recentEditions}</h2>
        <span>{ui.newestFirst}</span>
      </div>
      <div className={styles.editionGrid}>
        {(data?.epaper_editions ?? []).map((edition) => (
          <article className={styles.editionCard} key={edition.id}>
            <div className={styles.paperCover}>
              <span className={styles.paperMasthead}>{edition.publisher_name_ar}</span>
              <strong>{edition.publisher_name_en}</strong>
              <div className={styles.paperRule} />
              <span>{formatDate(edition.edition_date, locale, ui)}</span>
              <div className={styles.paperLines}>
                <i />
                <i />
                <i />
                <i />
              </div>
              <small>{edition.page_count} {ui.pages}</small>
            </div>
            <div className={styles.editionBody}>
              <div>
                <h3>{locale === "ar" ? edition.publisher_name_ar : edition.publisher_name_en}</h3>
                <p>{formatDate(edition.edition_date, locale, ui)}</p>
              </div>
              <span className={styles.readyBadge}>{editionStatus(edition.status, ui)}</span>
              {edition.source_url ? (
                <a href={edition.source_url} target="_blank" rel="noreferrer">
                  {ui.openEdition} <Icon name="external" size={14} />
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
  priorityArticles,
  focus,
  locale,
  ui,
  onOpen,
}: {
  data: DashboardData | null;
  savedIds: Set<string>;
  reviewedIds: Set<string>;
  priorityArticles: Article[];
  focus: string;
  locale: Locale;
  ui: UIStrings;
  onOpen: (article: Article) => void;
}) {
  const enriched = (data?.articles ?? []).filter((article) => article.ai_summary);
  const priority = priorityArticles;
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
  const negativeCount = tones.negative ?? 0;
  const toneTotal = Math.max(enriched.length, 1);
  const tonePercentage = (tone: string) =>
    Math.round(((tones[tone] ?? 0) / toneTotal) * 100);
  const suggestedAction = (article: Article) => {
    if (focus && article.ai_sentiment === "negative") return ui.reviewClosely;
    if ((article.ai_importance ?? 0) >= 0.88) return ui.shareInternally;
    return ui.keepMonitoring;
  };

  return (
    <>
      <section className={styles.insightsHero}>
        <article className={styles.dailyBriefing}>
          <div className={styles.briefingTitle}>
            <span>
              <Icon name="insights" size={21} />
            </span>
            <div>
              <p>{ui.todaysBriefing}</p>
              <h2>
                {priority.length
                  ? `${priority.length} ${ui.closerLook}`
                  : ui.noUrgent}
              </h2>
            </div>
          </div>
          <p className={styles.briefingCopy}>
            {ui.reviewedPrefix} {data?.ai_status.deepseek.enriched_articles ?? enriched.length}{" "}
            {ui.recentStories}{focus ? ` “${focus}”` : ""}. {ui.overallTone}{" "}
            {toneLabel(dominantTone, ui)}
            {negativeCount
              ? `، ${negativeCount} ${ui.negativeCoverageSuffix}`
              : `، ${ui.noNegative}`}
          </p>
          <div className={styles.topicSection}>
            <span>{ui.trendingConversations}</span>
            <div className={styles.topicCloud}>
              {topTopics.length ? (
                topTopics.map(([topic, count]) => (
                  <span key={topic}>
                    {topic} <b>{count}</b>
                  </span>
                ))
              ) : (
                <span>{ui.topicsPending}</span>
              )}
            </div>
          </div>
        </article>

        <article className={styles.reputationPulse}>
          <div className={styles.pulseHeader}>
            <div>
              <p>{ui.reputationPulse}</p>
              <h2>{toneLabel(dominantTone, ui)}</h2>
            </div>
            <span className={styles.pulseTotal}>{enriched.length} {ui.stories}</span>
          </div>
          <div className={styles.toneBar} aria-label="Coverage tone distribution">
            <span
              className={styles.tonePositive}
              style={{ width: `${tonePercentage("positive")}%` }}
            />
            <span
              className={styles.toneNeutral}
              style={{ width: `${tonePercentage("neutral")}%` }}
            />
            <span
              className={styles.toneMixed}
              style={{ width: `${tonePercentage("mixed")}%` }}
            />
            <span
              className={styles.toneNegative}
              style={{ width: `${tonePercentage("negative")}%` }}
            />
          </div>
          <div className={styles.toneLegend}>
            <span>
              <i className={styles.legendPositive} />
              {ui.positive} <b>{tones.positive ?? 0}</b>
            </span>
            <span>
              <i className={styles.legendNeutral} />
              {ui.neutral} <b>{tones.neutral ?? 0}</b>
            </span>
            <span>
              <i className={styles.legendMixed} />
              {ui.mixed} <b>{tones.mixed ?? 0}</b>
            </span>
            <span>
              <i className={styles.legendNegative} />
              {ui.negative} <b>{negativeCount}</b>
            </span>
          </div>
          <p>
            {negativeCount
              ? ui.startNegative
              : ui.stableCoverage}
          </p>
        </article>
      </section>

      <div className={styles.priorityHeading}>
        <div>
          <span>{ui.priorityCoverage}</span>
          <h2>{ui.startStories}</h2>
        </div>
        <p>{ui.selectionReason}</p>
      </div>
      {priority.length ? (
        <div className={styles.priorityGrid}>
          {priority.map((article) => (
            <button
              type="button"
              onClick={() => onOpen(article)}
              key={article.id}
            >
              <div className={styles.priorityVisual}>
                <ArticleCover article={article} locale={locale} />
                <span
                  className={
                    article.ai_sentiment === "negative"
                      ? styles.negativeBadge
                      : styles.priorityBadge
                  }
                >
                  {article.ai_sentiment === "negative"
                    ? focus
                      ? ui.reputationWatch
                      : ui.negativeCoverage
                    : ui.priorityStory}
                </span>
              </div>
              <div className={styles.priorityBody}>
                <div className={styles.articleMeta}>
                  <span>
                    {locale === "ar" ? article.publisher_name_ar : article.publisher_name_en}
                  </span>
                  <span>·</span>
                  <span>{toneLabel(article.ai_sentiment, ui)}</span>
                  {savedIds.has(article.id) ? (
                    <>
                      <span>·</span>
                      <span>{ui.saved}</span>
                    </>
                  ) : null}
                  {reviewedIds.has(article.id) ? (
                    <>
                      <span>·</span>
                      <span className={styles.reviewedLabel}>{ui.reviewed}</span>
                    </>
                  ) : null}
                </div>
                <h3 dir={article.language === "ar" ? "rtl" : "ltr"}>{article.title}</h3>
                <p dir={article.language === "ar" ? "rtl" : "ltr"}>{article.ai_summary}</p>
                <div className={styles.priorityFooter}>
                  <span>
                    {ui.suggestedNext}: <b>{suggestedAction(article)}</b>
                  </span>
                  <Icon name="arrow" size={15} />
                </div>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <span className={styles.emptyIcon}>
            <Icon name="insights" size={22} />
          </span>
          <h3>{ui.noPriorityNow}</h3>
          <p>{ui.noPriorityNowHelp}</p>
        </div>
      )}
    </>
  );
}
