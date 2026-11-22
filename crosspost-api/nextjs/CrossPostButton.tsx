"use client";

import React, { useEffect, useState } from "react";

export interface PlatformLog {
  id: number;
  platform: "YT" | "IG";
  account_name?: string;
  status: "Bekliyor" | "Yükleniyor" | "Yayında" | "Hata";
  platform_post_url?: string | null;
  error_message?: string | null;
}

interface CrossPostButtonProps {
  videoId: string;
  videoUrl?: string;
  localFilePath?: string;
  title: string;
  description: string;
  igCaption?: string;
  accountIds?: number[];
  thumbOffsetMs?: number;
}

const BADGE_STYLE: Record<string, string> = {
  Bekliyor: "bg-slate-700/60 text-slate-200 border-slate-500/40",
  Yükleniyor: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  Yayında: "bg-emerald-600/20 text-emerald-300 border-emerald-500/40",
  Hata: "bg-red-600/20 text-red-300 border-red-500/40",
};

export function CrossPostButton({
  videoId,
  videoUrl,
  localFilePath,
  title,
  description,
  igCaption,
  accountIds,
  thumbOffsetMs,
}: CrossPostButtonProps) {
  const [logs, setLogs] = useState<PlatformLog[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPolling = logs.some((l) => l.status === "Bekliyor" || l.status === "Yükleniyor");

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/social/status?video_id=${encodeURIComponent(videoId)}`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      setLogs(data.by_video?.[videoId] || []);
    } catch {}
  };

  useEffect(() => { fetchStatus(); }, [videoId]);
  useEffect(() => {
    if (!isPolling) return;
    const t = setInterval(fetchStatus, 3000);
    return () => clearInterval(t);
  }, [isPolling, videoId]);

  const handlePublish = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/social/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: videoId,
          video_url: videoUrl,
          local_file_path: localFilePath,
          title,
          description,
          ig_caption: igCaption,
          account_ids: accountIds,
          thumb_offset_ms: thumbOffsetMs,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Paylaşım başlatılamadı.");
      if (data.logs) setLogs(data.logs);
      setTimeout(fetchStatus, 1500);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={handlePublish}
        disabled={busy || isPolling}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 px-4 py-2 text-sm font-medium text-white transition-all"
      >
        {busy || isPolling ? (
          <>
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            <span>Yükleniyor...</span>
          </>
        ) : (
          <span>🚀 YT &amp; IG Paylaş</span>
        )}
      </button>

      {logs.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {logs.map((l) => (
            <span
              key={`${l.platform}-${l.id}`}
              title={l.error_message || ""}
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLE[l.status] || BADGE_STYLE.Bekliyor}`}
            >
              <span>{l.platform === "YT" ? "▶️ YT" : "📸 IG"}</span>
              {l.account_name ? <span className="opacity-80">({l.account_name})</span> : null}
              <span>· {l.status}</span>
              {l.platform_post_url && (
                <a href={l.platform_post_url} target="_blank" rel="noreferrer" className="underline ml-1">Aç</a>
              )}
            </span>
          ))}
        </div>
      )}

      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
