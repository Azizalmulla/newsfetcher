import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const KUNA_HOST = "www.kuna.net.kw";
const ALLOWED_PATHS = new Set(["/Default.aspx", "/ArticleDetails.aspx"]);

export async function GET(request: NextRequest) {
  const rawUrl = request.nextUrl.searchParams.get("url");
  if (!rawUrl) {
    return NextResponse.json({ error: "url_required" }, { status: 400 });
  }

  let target: URL;
  try {
    target = new URL(rawUrl);
  } catch {
    return NextResponse.json({ error: "invalid_url" }, { status: 400 });
  }
  if (
    target.protocol !== "https:" ||
    target.hostname !== KUNA_HOST ||
    !ALLOWED_PATHS.has(target.pathname)
  ) {
    return NextResponse.json({ error: "target_not_allowed" }, { status: 403 });
  }

  try {
    const response = await fetch(target, {
      cache: "no-store",
      headers: {
        Accept: "text/html,application/xhtml+xml",
        "User-Agent":
          "NewsFetcherBot/0.1 (+https://newsfetcher-two.vercel.app; media-monitoring)",
      },
      signal: AbortSignal.timeout(25_000),
    });
    const body = await response.arrayBuffer();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "text/html; charset=utf-8",
        "Cache-Control": target.pathname === "/Default.aspx"
          ? "public, s-maxage=60, stale-while-revalidate=300"
          : "public, s-maxage=1800, stale-while-revalidate=86400",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 504 });
  }
}
