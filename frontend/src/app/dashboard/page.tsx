"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import api from "@/lib/api";
import { downloadExport } from "@/lib/download";
import type { Campaign, DashboardData } from "@/types";
import { ArrowRight, Download, Plus } from "lucide-react";

function fmtNum(n: number) {
  return n >= 1000 ? n.toLocaleString("zh-CN") : String(n);
}

function rate(numerator: number, denominator: number) {
  return denominator > 0 ? Math.round((numerator / denominator) * 1000) / 10 : 0;
}

function Sparkline({ values, width = 88, height = 28, color = "var(--ink-3)" }: {
  values: number[]; width?: number; height?: number; color?: string;
}) {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const span = Math.max(1, max - min);
  const step = width / (values.length - 1);
  const pts = values.map((v, i) => `${i * step},${height - 4 - ((v - min) / span) * (height - 8)}`).join(" ");
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TrendChart({ data }: { data: { date: string; emails_sent: number; emails_opened: number; emails_replied: number }[] }) {
  if (!data || data.length === 0) return (
    <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ink-4)", fontSize: 13 }}>暂无数据</div>
  );
  const w = 640, h = 220, pad = { l: 28, r: 12, t: 8, b: 24 };
  const cw = w - pad.l - pad.r, ch = h - pad.t - pad.b;
  const max = Math.max(...data.map((d) => d.emails_sent), 1);
  const step = cw / data.length;
  const barW = Math.min(12, step * 0.35);
  return (
    <div style={{ width: "100%", overflow: "hidden" }}>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display: "block" }}>
        {[0, Math.round(max / 2), max].map((v, i) => {
          const y = pad.t + ch - (v / max) * ch;
          return (
            <g key={i}>
              <line x1={pad.l} x2={w - pad.r} y1={y} y2={y} stroke="var(--hairline-soft)" strokeDasharray={i === 0 ? "" : "3 3"} />
              <text x={pad.l - 8} y={y + 3} fill="var(--ink-4)" fontSize="10" textAnchor="end">{v}</text>
            </g>
          );
        })}
        {data.map((d, i) => {
          const cx = pad.l + step * (i + 0.5);
          const bs = (v: number) => (v / max) * ch;
          return (
            <g key={i}>
              <rect x={cx - barW * 1.6} y={pad.t + ch - bs(d.emails_sent)} width={barW} height={bs(d.emails_sent)} fill="var(--ink)" rx="1" />
              <rect x={cx - barW * 0.5} y={pad.t + ch - bs(d.emails_opened)} width={barW} height={bs(d.emails_opened)} fill="var(--da-accent)" rx="1" />
              <rect x={cx + barW * 0.6} y={pad.t + ch - bs(d.emails_replied)} width={barW} height={bs(d.emails_replied)} fill="var(--ok)" rx="1" />
              <text x={cx} y={h - 8} fill="var(--ink-4)" fontSize="10" textAnchor="middle">{d.date?.slice(-5)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function FunnelChart({ rows }: { rows: { label: string; value: number; pct: number }[] }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="ds-col" style={{ gap: 14 }}>
      {rows.map((r, i) => (
        <div key={r.label}>
          <div className="ds-between" style={{ marginBottom: 6 }}>
            <span style={{ fontSize: 12.5, color: "var(--ink)" }}>{r.label}</span>
            <div className="ds-row" style={{ gap: 8 }}>
              <span className="ds-num ds-primary" style={{ fontSize: 13, fontWeight: 600 }}>{r.value}</span>
              <span className="ds-caption ds-num" style={{ minWidth: 42, textAlign: "right", color: "var(--ink-4)" }}>{r.pct}%</span>
            </div>
          </div>
          <div className="ds-progress">
            <span style={{
              width: (r.value / max * 100) + "%",
              background: i === 0 ? "var(--ink)" : i < 3 ? "oklch(0.40 0.025 250)" : i < 5 ? "var(--da-accent)" : "var(--ok)",
            }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function TierBars({ data }: { data: { name: string; value: number; pct: number }[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="ds-col" style={{ gap: 14 }}>
      {data.map((d) => (
        <div key={d.name}>
          <div className="ds-between" style={{ marginBottom: 5 }}>
            <span style={{ fontSize: 12.5, color: "var(--ink)" }}>{d.name}</span>
            <div className="ds-row" style={{ gap: 8 }}>
              <span className="ds-num ds-primary" style={{ fontSize: 13 }}>{fmtNum(d.value)}</span>
              <span className="ds-caption ds-num" style={{ minWidth: 32, textAlign: "right", color: "var(--ink-4)" }}>{d.pct}%</span>
            </div>
          </div>
          <div className="ds-progress">
            <span style={{ width: (d.value / max * 100) + "%" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function NicheList({ rows }: { rows: { name: string; value: number; pct: number }[] }) {
  const colors = ["var(--ink)", "oklch(0.35 0.03 250)", "var(--da-accent)", "oklch(0.55 0.06 200)", "oklch(0.55 0.05 165)", "oklch(0.65 0.05 60)"];
  return (
    <div className="ds-col" style={{ gap: 10 }}>
      {rows.map((r, i) => (
        <div key={r.name} className="ds-row" style={{ gap: 12 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: colors[i % colors.length], flexShrink: 0 }} />
          <span style={{ fontSize: 12.5, color: "var(--ink)", flex: 1 }}>{r.name}</span>
          <span className="ds-num ds-primary" style={{ fontSize: 13, fontWeight: 600 }}>{r.value}</span>
          <span className="ds-caption ds-num" style={{ width: 36, textAlign: "right", color: "var(--ink-4)" }}>{r.pct}%</span>
        </div>
      ))}
    </div>
  );
}

/** Sample-data tag shared by the four dashboard panels with no real backing
 * endpoint yet (funnel / tier / niche / activity feed) — makes it visually
 * unambiguous that these numbers are illustrative, not live. */
function SampleTag() {
  return <span className="ds-tag" title="尚无对应后端接口，展示示例数据">示例数据</span>;
}

// Illustrative only — no backend endpoint computes conversion funnel, follower
// tiers, niche distribution, or an activity feed yet. See SampleTag above.
const STATIC_FUNNEL = [
  { label: "已发送", value: 8423, pct: 100 },
  { label: "已送达", value: 7980, pct: 95 },
  { label: "已打开", value: 2314, pct: 29 },
  { label: "已回复", value: 634, pct: 8 },
  { label: "意向合作", value: 89, pct: 1 },
  { label: "已签约", value: 23, pct: 0 },
];

const STATIC_TIERS = [
  { name: "S · Macro (50W+)",  value: 84,   pct: 8 },
  { name: "A · Mid (10-50W)",  value: 312,  pct: 28 },
  { name: "B · Micro (1-10W)", value: 968,  pct: 42 },
  { name: "C · Nano (<1W)",    value: 1483, pct: 22 },
];

const STATIC_NICHES = [
  { name: "蛋白粉",       value: 642, pct: 23 },
  { name: "维生素矿物",   value: 488, pct: 17 },
  { name: "胶原美容",     value: 356, pct: 13 },
  { name: "运动前补剂",   value: 312, pct: 11 },
  { name: "益生菌肠道",   value: 268, pct: 9 },
  { name: "Omega-3 鱼油", value: 228, pct: 8 },
];

const SAMPLE_ACTIVITY = [
  { icon: "reply",   text: "Ava Carter 回复了 Protein-V3 活动",       time: "3 分钟前" },
  { icon: "send",    text: "Omega-3 EU 活动批量发送 86 封邮件",         time: "18 分钟前" },
  { icon: "sparkle", text: "AI 生成 12 封回复草稿等待审核",              time: "42 分钟前" },
  { icon: "check",   text: "Collagen-V2 与 Sarah Mitchell 签约成功",   time: "1 小时前" },
  { icon: "search",  text: "发现达人任务完成，新增 34 位达人",            time: "2 小时前" },
];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [activeCampaigns, setActiveCampaigns] = useState<Campaign[]>([]);
  const [campaignsLoading, setCampaignsLoading] = useState(true);

  useEffect(() => {
    api.get("/analytics/dashboard")
      .then((res) => setData(res.data))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    api.get("/campaigns")
      .then((res) => {
        const list: Campaign[] = res.data;
        setActiveCampaigns(list.filter((c) => c.status === "active"));
      })
      .catch(() => {})
      .finally(() => setCampaignsLoading(false));
  }, []);

  const handleExport = async (fmt: "csv" | "xlsx") => {
    try {
      await downloadExport("/analytics/export", { format: fmt }, `dashboard.${fmt}`);
    } catch {
      // export failure is non-critical; surface via console for now
      console.error("dashboard export failed");
    }
  };

  const stats = data?.stats;
  const recentDaily = (data?.daily ?? []).slice(-8);

  const metrics: { label: string; value: number | undefined; spark: number[]; suffix: string }[] = [
    { label: "已发送邮件", value: stats?.emails_sent, spark: recentDaily.map((d) => d.emails_sent), suffix: "" },
    { label: "打开率",     value: stats?.open_rate,   spark: recentDaily.map((d) => rate(d.emails_opened, d.emails_sent)),  suffix: "%" },
    { label: "回复率",     value: stats?.reply_rate,  spark: recentDaily.map((d) => rate(d.emails_replied, d.emails_sent)), suffix: "%" },
    { label: "退信率",     value: stats?.bounce_rate, spark: recentDaily.map((d) => rate(d.emails_bounced, d.emails_sent)), suffix: "%" },
  ];

  return (
    <AppLayout>
      <div className="fade-in" style={{ maxWidth: 1440 }}>
        {/* Header */}
        <div className="ds-between" style={{ marginBottom: 24 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              {new Date().toLocaleDateString("zh-CN", { weekday: "long", month: "long", day: "numeric" })} · GMT+8
            </div>
            <h1 className="h-display">早上好，欢迎回来。</h1>
            <p className="body-lg" style={{ marginTop: 6, maxWidth: 560, color: "var(--ink-2)" }}>
              {loading ? "数据加载中…" : `${stats?.active_campaigns ?? 0} 个进行中的活动，AI 草稿等待你的审核。`}
            </p>
          </div>
          <div className="ds-row" style={{ gap: 8 }}>
            <button className="ds-btn ds-btn-outline" onClick={() => handleExport("xlsx")}>
              <Download className="h-[14px] w-[14px]" />导出周报 (Excel)
            </button>
            <button className="ds-btn ds-btn-outline" onClick={() => handleExport("csv")}>
              <Download className="h-[14px] w-[14px]" />CSV
            </button>
            <Link href="/campaigns/new" className="ds-btn ds-btn-primary">
              <Plus className="h-[14px] w-[14px]" />新建活动
            </Link>
          </div>
        </div>

        {/* 4-metric stat card */}
        <div className="ds-card" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", marginBottom: 20 }}>
          {metrics.map((m, i, arr) => (
            <div key={m.label} className="ds-stat" style={{ borderRight: i < arr.length - 1 ? "1px solid var(--hairline)" : 0 }}>
              <div className="ds-stat-label">{m.label}</div>
              <div className="ds-row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginTop: 2 }}>
                <div className="ds-stat-value">
                  {loading || loadError || m.value == null ? (
                    <span style={{ color: "var(--ink-4)" }} title={loadError ? "数据加载失败" : undefined}>—</span>
                  ) : (
                    <>
                      {m.value >= 1000 ? fmtNum(m.value) : m.value}
                      {m.suffix && <span className="ds-stat-unit">{m.suffix}</span>}
                    </>
                  )}
                </div>
                <Sparkline values={m.spark} />
              </div>
              <div className="ds-row" style={{ marginTop: 6 }}>
                <span className="ds-caption" style={{ color: "var(--ink-4)" }}>近 30 天</span>
              </div>
            </div>
          ))}
        </div>

        {/* Trend + Funnel */}
        <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 20, marginBottom: 20 }}>
          <div className="ds-card">
            <div className="ds-card-section ds-between">
              <div>
                <div className="ds-h3">每日触达趋势</div>
                <div className="ds-caption" style={{ color: "var(--ink-3)" }}>最近天 · 发送 / 打开 / 回复</div>
              </div>
              <div className="ds-row" style={{ gap: 14 }}>
                {[["var(--ink)", "发送"], ["var(--da-accent)", "打开"], ["var(--ok)", "回复"]].map(([c, l]) => (
                  <span key={l} className="ds-row ds-caption" style={{ gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: c }} />{l}
                  </span>
                ))}
              </div>
            </div>
            <div style={{ padding: "20px 12px 16px" }}>
              <TrendChart data={data?.daily ?? []} />
            </div>
          </div>

          <div className="ds-card">
            <div className="ds-card-section ds-between">
              <div>
                <div className="ds-h3">转化漏斗</div>
                <div className="ds-caption" style={{ color: "var(--ink-3)" }}>累计 · 从发送到签约</div>
              </div>
              <SampleTag />
            </div>
            <div style={{ padding: "16px 20px 20px" }}>
              <FunnelChart rows={STATIC_FUNNEL} />
            </div>
          </div>
        </div>

        {/* Active campaigns + Quick links */}
        <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 20, marginBottom: 20 }}>
          <div className="ds-card">
            <div className="ds-card-section ds-between">
              <div>
                <div className="ds-h3">进行中的活动</div>
                <div className="ds-caption" style={{ color: "var(--ink-3)" }}>状态为「进行中」的活动</div>
              </div>
              <Link href="/campaigns" className="ds-btn ds-btn-ghost ds-btn-sm">
                查看全部 <ArrowRight className="h-[13px] w-[13px]" />
              </Link>
            </div>
            {campaignsLoading ? (
              <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--ink-3)", fontSize: 13 }}>
                加载中…
              </div>
            ) : activeCampaigns.length === 0 ? (
              <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--ink-3)", fontSize: 13 }}>
                暂无进行中的活动 ·{" "}
                <Link href="/campaigns/new" style={{ color: "var(--da-accent)", fontWeight: 600 }}>新建活动</Link>
              </div>
            ) : (
              activeCampaigns.slice(0, 3).map((c, i) => (
                <Link
                  key={c.id}
                  href={`/campaigns/${c.id}`}
                  style={{
                    padding: "16px 20px",
                    borderBottom: i < Math.min(activeCampaigns.length, 3) - 1 ? "1px solid var(--hairline-soft)" : 0,
                    display: "grid", gridTemplateColumns: "1fr 90px 90px",
                    gap: 16, alignItems: "center",
                    textDecoration: "none",
                  }}
                >
                  <div className="ds-row" style={{ gap: 8 }}>
                    <span className="ds-dot ds-dot-ok" />
                    <span className="ds-primary" style={{ fontSize: 13.5, fontWeight: 600 }}>{c.name}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="ds-caption" style={{ marginBottom: 2, color: "var(--ink-3)" }}>步骤</div>
                    <div className="ds-num ds-primary" style={{ fontSize: 14, fontWeight: 600 }}>{c.steps?.length ?? 0}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="ds-caption" style={{ marginBottom: 2, color: "var(--ink-3)" }}>开始于</div>
                    <div className="ds-num ds-primary" style={{ fontSize: 13 }}>
                      {c.started_at ? new Date(c.started_at).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }) : "—"}
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>

          <div className="ds-card">
            <div className="ds-card-section ds-between">
              <div className="ds-h3">最近动态</div>
              <SampleTag />
            </div>
            <div style={{ padding: "4px 0" }}>
              {SAMPLE_ACTIVITY.map((a, i) => (
                <div key={i} className="ds-row" style={{ padding: "12px 20px", alignItems: "flex-start", gap: 12 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: 7,
                    background: "var(--surface-2)", border: "1px solid var(--hairline)",
                    display: "grid", placeItems: "center", flexShrink: 0, color: "var(--ink-2)",
                  }}>
                    {a.icon === "reply" && <ArrowRight className="h-3 w-3" />}
                    {a.icon === "check" && <span style={{ fontSize: 12 }}>✓</span>}
                    {a.icon === "send" && <ArrowRight className="h-3 w-3" />}
                    {a.icon === "sparkle" && <span style={{ fontSize: 12 }}>✦</span>}
                    {a.icon === "search" && <span style={{ fontSize: 12 }}>⊙</span>}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: "var(--ink)", fontSize: 12.5 }}>{a.text}</div>
                    <div className="ds-caption" style={{ color: "var(--ink-4)", marginTop: 2 }}>{a.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Tier × Niche */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <div className="ds-card ds-card-pad">
            <div className="ds-between" style={{ marginBottom: 16 }}>
              <div>
                <div className="ds-h3">达人粉丝层级</div>
                <div className="ds-caption" style={{ color: "var(--ink-3)" }}>
                  共 {fmtNum(stats?.total_influencers ?? 0)} 位达人 · 层级分布为示例
                </div>
              </div>
              <SampleTag />
            </div>
            <TierBars data={STATIC_TIERS} />
          </div>
          <div className="ds-card ds-card-pad">
            <div className="ds-between" style={{ marginBottom: 16 }}>
              <div>
                <div className="ds-h3">类目分布</div>
                <div className="ds-caption" style={{ color: "var(--ink-3)" }}>保健品细分类目 · Top 6</div>
              </div>
              <SampleTag />
            </div>
            <NicheList rows={STATIC_NICHES} />
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
