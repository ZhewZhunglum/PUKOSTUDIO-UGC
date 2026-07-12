"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import api from "@/lib/api";
import { CAMPAIGN_STATUS_MAP } from "@/lib/constants";
import type { Campaign } from "@/types";
import { Plus, ArrowRight } from "lucide-react";

const TYPE_MAP: Record<string, string> = {
  ugc: "UGC内容",
  brand_promo: "品牌推广",
  tiktok_shop: "TikTok Shop",
};

const STATUS_DOT: Record<string, string> = {
  active: "ds-dot-ok",
  paused: "ds-dot-warn",
  draft: "",
  completed: "ds-dot-info",
};

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "ds-tag-ok", paused: "ds-tag-warn",
    draft: "", completed: "ds-tag-info", archived: "",
  };
  const label = CAMPAIGN_STATUS_MAP[status]?.label ?? status;
  return <span className={`ds-tag ${map[status] ?? ""}`}>{label}</span>;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("active");
  const [selected, setSelected] = useState<Campaign | null>(null);

  useEffect(() => {
    api.get("/campaigns")
      .then((res) => {
        const list: Campaign[] = res.data;
        setCampaigns(list);
        if (list.length > 0) setSelected(list[0]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const tabs = [
    ["active", "进行中"],
    ["draft", "草稿"],
    ["paused", "已暂停"],
    ["completed", "已完成"],
    ["all", "全部"],
  ] as const;

  const filtered = tab === "all" ? campaigns : campaigns.filter((c) => c.status === tab);

  return (
    <AppLayout>
      <div className="fade-in">
        {/* Header */}
        <div className="ds-between" style={{ marginBottom: 20 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>工作流</div>
            <h1 className="ds-h1">建联活动</h1>
            <p className="ds-body" style={{ marginTop: 4, color: "var(--ink-3)" }}>
              按市场 / SKU / 时间窗组织外联节奏 · 当前在跑{" "}
              <b className="ds-primary ds-num">{campaigns.filter((c) => c.status === "active").length}</b> 个活动
            </p>
          </div>
          <div className="ds-row" style={{ gap: 8 }}>
            <Link href="/campaigns/new" className="ds-btn ds-btn-primary ds-btn-sm">
              <Plus className="h-[14px] w-[14px]" />新建活动
            </Link>
          </div>
        </div>

        {/* Tabs */}
        <div className="ds-row" style={{ gap: 24, borderBottom: "1px solid var(--hairline)", marginBottom: 16 }}>
          {tabs.map(([id, label]) => {
            const count = id === "all" ? campaigns.length : campaigns.filter((c) => c.status === id).length;
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                style={{
                  padding: "10px 0", fontSize: 13, fontWeight: 600,
                  color: tab === id ? "var(--ink)" : "var(--ink-3)",
                  borderBottom: tab === id ? "2px solid var(--ink)" : "2px solid transparent",
                  marginBottom: -1, background: "none", border: "none",
                  borderBottomWidth: 2,
                  borderBottomStyle: "solid",
                  borderBottomColor: tab === id ? "var(--ink)" : "transparent",
                  cursor: "pointer",
                }}
              >
                {label} <span className="ds-num" style={{ fontWeight: 500, color: "var(--ink-4)" }}>{count}</span>
              </button>
            );
          })}
        </div>

        {/* Master / detail */}
        {loading ? (
          <div style={{ padding: "48px 0", textAlign: "center", color: "var(--ink-3)" }}>加载中…</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1.05fr 1.4fr", gap: 16, alignItems: "start" }}>
            {/* Master list */}
            <div className="ds-card" style={{ overflow: "hidden" }}>
              {filtered.length === 0 ? (
                <div style={{ padding: "48px 20px", textAlign: "center", color: "var(--ink-3)", fontSize: 13 }}>
                  暂无活动 ·{" "}
                  <Link href="/campaigns/new" style={{ color: "var(--da-accent)", fontWeight: 600 }}>新建活动</Link>
                </div>
              ) : (
                filtered.map((c, idx) => {
                  const active = selected?.id === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => setSelected(c)}
                      style={{
                        padding: "16px 18px",
                        paddingLeft: active ? 15 : 18,
                        cursor: "pointer",
                        borderBottom: idx < filtered.length - 1 ? "1px solid var(--hairline-soft)" : 0,
                        background: active ? "var(--surface-2)" : "transparent",
                        borderLeft: active ? "3px solid var(--ink)" : "3px solid transparent",
                      }}
                    >
                      <div className="ds-between" style={{ marginBottom: 8 }}>
                        <div className="ds-row" style={{ gap: 8, minWidth: 0 }}>
                          <span className={`ds-dot ${STATUS_DOT[c.status] ?? ""}`} />
                          <span className="ds-primary" style={{ fontSize: 13.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 280 }}>
                            {c.name}
                          </span>
                        </div>
                        <StatusBadge status={c.status} />
                      </div>
                      <div className="ds-row ds-caption" style={{ gap: 10, marginBottom: 8, color: "var(--ink-3)" }}>
                        <span>{TYPE_MAP[c.campaign_type] ?? c.campaign_type}</span>
                        <span style={{ color: "var(--ink-4)" }}>·</span>
                        <span>{new Date(c.created_at).toLocaleDateString("zh-CN")}</span>
                      </div>
                      <div className="ds-progress">
                        <span style={{ width: `${Math.min(100, (c.steps?.length ?? 0) * 20)}%` }} />
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Detail */}
            {selected ? (
              <div className="ds-col" style={{ gap: 16 }}>
                <div className="ds-card">
                  <div className="ds-card-section ds-between">
                    <div>
                      <div className="ds-row" style={{ gap: 8, marginBottom: 4 }}>
                        <span className="ds-tag" style={{ fontFamily: "var(--f-mono)", fontSize: 10 }}>{selected.id.slice(0, 8)}</span>
                        <span className="ds-tag">{TYPE_MAP[selected.campaign_type] ?? selected.campaign_type}</span>
                        <StatusBadge status={selected.status} />
                      </div>
                      <h2 className="ds-h2">{selected.name}</h2>
                      <div className="ds-caption" style={{ marginTop: 4, color: "var(--ink-3)" }}>
                        {selected.steps?.length ?? 0} 个发送步骤 · 创建于 {new Date(selected.created_at).toLocaleDateString("zh-CN")}
                      </div>
                    </div>
                    <div className="ds-row" style={{ gap: 6 }}>
                      <Link href={`/campaigns/${selected.id}`} className="ds-btn ds-btn-outline ds-btn-sm">
                        详情 <ArrowRight className="h-[13px] w-[13px]" />
                      </Link>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)" }}>
                    {[
                      { label: "发送步骤", value: selected.steps?.length ?? 0 },
                      { label: "状态",     value: CAMPAIGN_STATUS_MAP[selected.status]?.label ?? selected.status },
                      { label: "创建时间", value: new Date(selected.created_at).toLocaleDateString("zh-CN") },
                    ].map((m, i, a) => (
                      <div key={m.label} style={{
                        padding: "16px 18px",
                        borderRight: i < a.length - 1 ? "1px solid var(--hairline)" : 0,
                        borderTop: "1px solid var(--hairline)",
                      }}>
                        <div className="ds-caption" style={{ textTransform: "uppercase", letterSpacing: "0.04em", fontSize: 10.5, marginBottom: 4, color: "var(--ink-3)" }}>{m.label}</div>
                        <div className="ds-num ds-primary" style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em" }}>{m.value}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {selected.description && (
                  <div className="ds-card ds-card-pad">
                    <div className="ds-h3" style={{ marginBottom: 10 }}>活动描述</div>
                    <p className="ds-body">{selected.description}</p>
                  </div>
                )}

                <div className="ds-card">
                  <div className="ds-card-section ds-between">
                    <div className="ds-h3">发送步骤</div>
                    <Link href={`/campaigns/${selected.id}`} className="ds-btn ds-btn-ghost ds-btn-sm">
                      编辑步骤 <ArrowRight className="h-[13px] w-[13px]" />
                    </Link>
                  </div>
                  {(selected.steps ?? []).length === 0 ? (
                    <div style={{ padding: "24px 20px", textAlign: "center", color: "var(--ink-3)", fontSize: 13 }}>
                      暂无步骤，<Link href={`/campaigns/${selected.id}`} style={{ color: "var(--da-accent)", fontWeight: 600 }}>前往配置</Link>
                    </div>
                  ) : (
                    selected.steps.map((step, idx) => (
                      <div key={step.id} style={{
                        padding: "14px 20px",
                        borderBottom: idx < selected.steps.length - 1 ? "1px solid var(--hairline-soft)" : 0,
                      }}>
                        <div className="ds-row" style={{ gap: 10 }}>
                          <div style={{ width: 24, height: 24, borderRadius: 99, background: "var(--surface-2)", border: "1.5px solid var(--hairline)", display: "grid", placeItems: "center", fontSize: 11.5, fontWeight: 700, flexShrink: 0, color: "var(--ink-4)" }}>
                            {idx + 1}
                          </div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>{`步骤 ${idx + 1} · ${step.step_type === "initial" ? "首封" : "跟进"}`}</div>
                            <div className="ds-caption" style={{ color: "var(--ink-3)", marginTop: 2 }}>
                              延迟 {step.delay_days ?? 0} 天
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <div className="ds-card" style={{ padding: "48px 20px", textAlign: "center", color: "var(--ink-3)" }}>
                从左侧选择一个活动查看详情
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
