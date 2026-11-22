import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const apiBase = (process.env.CLOUD_RUN_API_URL || "").replace(/\/$/, "");
    if (!apiBase) {
      return NextResponse.json({ detail: "CLOUD_RUN_API_URL tanımlı değil." }, { status: 500 });
    }

    const payload: Record<string, unknown> = { ...body };
    // DB'de account_ids kullanılmıyorsa env fallback tokenları ekle
    if (!payload.account_ids && process.env.YT_ACCESS_TOKEN) {
      payload.yt_access_token = process.env.YT_ACCESS_TOKEN;
      payload.yt_refresh_token = process.env.YT_REFRESH_TOKEN;
      payload.yt_client_id = process.env.YT_CLIENT_ID;
      payload.yt_client_secret = process.env.YT_CLIENT_SECRET;
    }
    if (!payload.account_ids && process.env.IG_USER_ID && process.env.IG_ACCESS_TOKEN) {
      payload.ig_user_id = process.env.IG_USER_ID;
      payload.ig_access_token = process.env.IG_ACCESS_TOKEN;
    }

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (process.env.CROSSPOST_API_KEY) headers["X-API-Key"] = process.env.CROSSPOST_API_KEY;

    const cloudRunRes = await fetch(`${apiBase}/api/publish`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    const data = await cloudRunRes.json();
    return NextResponse.json(data, { status: cloudRunRes.status });
  } catch {
    return NextResponse.json({ detail: "Cloud Run sunucu bağlantı hatası" }, { status: 500 });
  }
}
