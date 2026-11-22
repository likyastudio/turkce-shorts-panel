import { NextResponse } from "next/server";

export async function GET(request: Request) {
  try {
    const apiBase = (process.env.CLOUD_RUN_API_URL || "").replace(/\/$/, "");
    if (!apiBase) return NextResponse.json({ by_video: {}, logs: [] });
    const { searchParams } = new URL(request.url);
    const vid = searchParams.get("video_id");
    const qs = vid ? `?video_id=${encodeURIComponent(vid)}` : "";
    const headers: Record<string, string> = {};
    if (process.env.CROSSPOST_API_KEY) headers["X-API-Key"] = process.env.CROSSPOST_API_KEY;
    const res = await fetch(`${apiBase}/api/publish/status${qs}`, { headers, cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ by_video: {}, logs: [] }, { status: 200 });
  }
}
