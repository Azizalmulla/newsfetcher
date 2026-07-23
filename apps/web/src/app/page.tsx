const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getHealth(): Promise<{ status?: string; phase?: string } | null> {
  try {
    const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export default async function HomePage() {
  const health = await getHealth();

  return (
    <main
      style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: "4rem 1.5rem",
      }}
    >
      <p style={{ letterSpacing: "0.08em", textTransform: "uppercase", opacity: 0.7 }}>
        Phase {health?.phase ?? "…"} platform
      </p>
      <h1 style={{ fontSize: "clamp(2.5rem, 6vw, 4rem)", margin: "0.4rem 0" }}>NewsFetcher</h1>
      <p style={{ fontSize: "1.15rem", lineHeight: 1.6, maxWidth: "36rem" }}>
        Kuwait media intelligence and digital press-clipping platform. Matching and semantic review
        feed draft reports; approval freezes an immutable PDF version.
      </p>
      <p style={{ marginTop: "2rem" }}>
        API health:{" "}
        <strong>
          {health ? `${health.status} (phase ${health.phase})` : "unreachable — start Compose"}
        </strong>
      </p>
      <p style={{ marginTop: "1rem" }}>
        <a href="/reports">Open report review →</a>
      </p>
      <p dir="rtl" style={{ marginTop: "1.5rem", fontSize: "1.1rem" }}>
        منصة مراقبة إعلامية كويتية — المرحلة صفر
      </p>
    </main>
  );
}
