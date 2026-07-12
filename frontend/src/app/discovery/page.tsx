"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import api from "@/lib/api";
import type {
  Campaign,
  WotoCostEstimate,
  WotoDictionaryItem,
  WotoPricingTable,
  WotoQuota,
  WotoSyncJob,
  WotoSyncRequest,
} from "@/types";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Database,
  Loader2,
  Mail,
  RefreshCcw,
  Search,
  Sparkles,
  Users,
  XCircle,
  Zap,
} from "lucide-react";

type WotoPlatform = "tiktok" | "instagram" | "youtube";

type FormState = {
  platform: WotoPlatform;
  searchType: "KEYWORD" | "NAME";
  keyword: string;
  bloggerName: string;
  excludeKeywords: string;
  regionId: string;
  categoryId: string;
  minFollowers: string;
  maxFollowers: string;
  minEngagementRate: string;
  maxEngagementRate: string;
  minAvgViews: string;
  maxAvgViews: string;
  hasEmail: "any" | "true" | "false";
  sort: WotoSyncRequest["sort"];
  sortOrder: WotoSyncRequest["sort_order"];
  limit: string;
  fetchDetail: boolean;
  enrichContacts: boolean;
  campaignId: string;
};

const EMPTY_FORM: FormState = {
  platform: "tiktok",
  searchType: "KEYWORD",
  keyword: "",
  bloggerName: "",
  excludeKeywords: "",
  regionId: "",
  categoryId: "",
  minFollowers: "",
  maxFollowers: "",
  minEngagementRate: "",
  maxEngagementRate: "",
  minAvgViews: "",
  maxAvgViews: "",
  hasEmail: "true",
  sort: "FANS_NUM",
  sortOrder: "desc",
  limit: "1",
  fetchDetail: true,
  enrichContacts: true,
  campaignId: "",
};

const PLATFORM_LABELS: Record<WotoPlatform, string> = {
  tiktok: "TikTok",
  instagram: "Instagram",
  youtube: "YouTube",
};

const STATUS_META: Record<
  WotoSyncJob["status"],
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  queued: { label: "排队中", variant: "secondary" },
  running: { label: "同步中", variant: "default" },
  completed: { label: "已完成", variant: "outline" },
  failed: { label: "失败", variant: "destructive" },
};

function toOptionalNumber(value: string): number | null {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : null;
}

function splitKeywords(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString("zh-CN") : "-";
}

function moneyNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined) return 0;
  return typeof value === "number" ? value : Number(value);
}

function formatCny(value: number | string | null | undefined): string {
  return `¥${moneyNumber(value).toFixed(2)}`;
}

function formatDiscount(value: number | string | null | undefined): string {
  return `${(moneyNumber(value) * 10).toFixed(1)} 折`;
}

function buildSyncPayload(form: FormState): WotoSyncRequest {
  const keyword = form.keyword.trim();
  const bloggerName = form.bloggerName.trim();
  return {
    platform: form.platform,
    search_type: form.searchType,
    keyword: keyword || null,
    blogger_name: bloggerName || null,
    exclude_keywords: splitKeywords(form.excludeKeywords),
    region_ids: form.regionId ? [form.regionId] : [],
    category_ids: form.categoryId ? [form.categoryId] : [],
    min_followers: toOptionalNumber(form.minFollowers),
    max_followers: toOptionalNumber(form.maxFollowers),
    min_engagement_rate: toOptionalNumber(form.minEngagementRate),
    max_engagement_rate: toOptionalNumber(form.maxEngagementRate),
    has_email: form.hasEmail === "any" ? null : form.hasEmail === "true",
    min_avg_views: toOptionalNumber(form.minAvgViews),
    max_avg_views: toOptionalNumber(form.maxAvgViews),
    sort: form.sort,
    sort_order: form.sortOrder,
    limit: Math.min(500, Math.max(1, Number(form.limit || 1))),
    fetch_detail: form.fetchDetail,
    enrich_contacts: form.fetchDetail && form.enrichContacts,
    campaign_id: form.campaignId || null,
  };
}

type PresetInputProps = {
  value: string;
  onChange: (v: string) => void;
  presets: Array<{ label: string; value: string }>;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
};

function PresetInput({ value, onChange, presets, placeholder, min, max, step }: PresetInputProps) {
  return (
    <div>
      <Input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        max={max}
        step={step}
      />
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {presets.map((p) => (
          <button
            key={p.value}
            type="button"
            onClick={() => onChange(value === p.value ? "" : p.value)}
            className={`rounded-md border px-2 py-0.5 text-xs transition-colors ${
              value === p.value
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border hover:border-primary/50 hover:bg-muted"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const FOLLOWER_PRESETS = [
  { label: "5k", value: "5000" },
  { label: "1万", value: "10000" },
  { label: "5万", value: "50000" },
  { label: "10万", value: "100000" },
  { label: "50万", value: "500000" },
  { label: "100万", value: "1000000" },
];

const ENGAGEMENT_PRESETS = [
  { label: "1%", value: "1" },
  { label: "3%", value: "3" },
  { label: "5%", value: "5" },
  { label: "10%", value: "10" },
  { label: "20%", value: "20" },
  { label: "30%", value: "30" },
];

const AVG_VIEWS_PRESETS = [
  { label: "1k", value: "1000" },
  { label: "5k", value: "5000" },
  { label: "1万", value: "10000" },
  { label: "5万", value: "50000" },
  { label: "10万", value: "100000" },
  { label: "50万", value: "500000" },
];

const LIMIT_PRESETS = [
  { label: "1", value: "1" },
  { label: "5", value: "5" },
  { label: "10", value: "10" },
  { label: "20", value: "20" },
  { label: "50", value: "50" },
  { label: "100", value: "100" },
];

function JobStatusBadge({ status }: { status: WotoSyncJob["status"] }) {
  const meta = STATUS_META[status] ?? STATUS_META.queued;
  const Icon =
    status === "completed"
      ? CheckCircle2
      : status === "failed"
        ? XCircle
        : status === "running"
          ? Loader2
          : Clock;
  return (
    <Badge variant={meta.variant} className="gap-1">
      <Icon className={`h-3 w-3 ${status === "running" ? "animate-spin" : ""}`} />
      {meta.label}
    </Badge>
  );
}

export default function DiscoveryPage() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [quota, setQuota] = useState<WotoQuota | null>(null);
  const [pricing, setPricing] = useState<WotoPricingTable | null>(null);
  const [estimate, setEstimate] = useState<WotoCostEstimate | null>(null);
  const [jobs, setJobs] = useState<WotoSyncJob[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [regions, setRegions] = useState<WotoDictionaryItem[]>([]);
  const [categories, setCategories] = useState<WotoDictionaryItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const updateForm = (patch: Partial<FormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const loadJobs = useCallback(async () => {
    const response = await api.get<WotoSyncJob[]>("/discovery/woto/sync-jobs", {
      params: { limit: 20 },
    });
    setJobs(response.data);
  }, []);

  const loadMeta = useCallback(async () => {
    setLoadingMeta(true);
    setErrorMsg(null);
    try {
      const [
        quotaResponse,
        pricingResponse,
        jobResponse,
        campaignResponse,
        regionResponse,
        categoryResponse,
      ] = await Promise.all([
          api.get<WotoQuota>("/discovery/woto/quota").catch((error) => {
            setErrorMsg(
              error.response?.data?.detail ||
                "Woto quota 查询失败，请确认后端已配置 WOTO_API_KEY"
            );
            return { data: null };
          }),
          api.get<WotoPricingTable>("/discovery/woto/pricing"),
          api.get<WotoSyncJob[]>("/discovery/woto/sync-jobs", { params: { limit: 20 } }),
          api.get<Campaign[]>("/campaigns"),
          api
            .get<WotoDictionaryItem[]>("/discovery/woto/dictionaries", {
              params: { dict_type_code: "dim_region" },
            })
            .catch(() => ({ data: [] })),
          api
            .get<WotoDictionaryItem[]>("/discovery/woto/dictionaries", {
              params: { dict_type_code: "blog_cate_new" },
            })
            .catch(() => ({ data: [] })),
        ]);

      setQuota(quotaResponse.data);
      setPricing(pricingResponse.data);
      setJobs(jobResponse.data);
      setCampaigns(
        campaignResponse.data.filter((campaign) =>
          ["draft", "paused"].includes(campaign.status)
        )
      );
      setRegions(regionResponse.data.slice(0, 200));
      setCategories(categoryResponse.data.slice(0, 200));
    } catch (error) {
      console.error(error);
      setErrorMsg("Woto 发现中心加载失败，请检查后端服务");
    } finally {
      setLoadingMeta(false);
    }
  }, []);

  useEffect(() => {
    const queryCampaignId =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("campaign_id")
        : null;
    if (queryCampaignId) {
      setForm((current) => ({ ...current, campaignId: queryCampaignId }));
    }
    void loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    const hasActiveJobs = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => {
      void loadJobs().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobs, loadJobs]);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const response = await api.post<WotoCostEstimate>(
          "/discovery/woto/pricing/estimate",
          buildSyncPayload(form)
        );
        setEstimate(response.data);
      } catch {
        setEstimate(null);
      }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [form]);

  const handleStartSync = async () => {
    const keyword = form.keyword.trim();
    const bloggerName = form.bloggerName.trim();
    if (form.searchType === "KEYWORD" && !keyword) {
      setErrorMsg("请填写搜索关键词");
      return;
    }
    if (form.searchType === "NAME" && !bloggerName && !keyword) {
      setErrorMsg("请填写达人名");
      return;
    }

    const payload = buildSyncPayload(form);

    setSubmitting(true);
    setErrorMsg(null);
    try {
      const response = await api.post<WotoSyncJob>("/discovery/woto/sync-jobs", payload);
      setJobs((current) => [response.data, ...current]);
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "创建 Woto 同步任务失败";
      setErrorMsg(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const selectedCampaign = campaigns.find((campaign) => campaign.id === form.campaignId);

  return (
    <AppLayout>
      <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div className="ds-between">
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>工作流</div>
            <div className="ds-row" style={{ gap: 8, marginBottom: 6 }}>
              <h1 className="ds-h1">发现达人</h1>
              <span className="ds-tag ds-tag-accent"><Sparkles className="h-3 w-3" />API 自动建联</span>
            </div>
            <p className="ds-body" style={{ color: "var(--ink-3)", maxWidth: 560 }}>
              从 WotoHub 搜索 TikTok、Instagram、YouTube 达人，自动补联系方式，保存到本地达人库。
            </p>
          </div>
          <div className="ds-row" style={{ gap: 8 }}>
            <button className="ds-btn ds-btn-outline ds-btn-sm" onClick={loadMeta} disabled={loadingMeta}>
              <RefreshCcw className={`h-[14px] w-[14px] ${loadingMeta ? "animate-spin" : ""}`} />刷新
            </button>
            <Link href="/influencers?source=woto" className="ds-btn ds-btn-outline ds-btn-sm">
              <Database className="h-[14px] w-[14px]" />查看 Woto 达人
            </Link>
          </div>
        </div>

        {errorMsg && (
          <Card className="border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4" />
              <span>{errorMsg}</span>
            </div>
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Woto 剩余额度</p>
              <Zap className="h-4 w-4 text-amber-500" />
            </div>
            <p className="mt-2 text-2xl font-bold">
              {quota?.remain_quota ?? (loadingMeta ? "..." : "未知")}
            </p>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">本次入组目标</p>
              <Users className="h-4 w-4 text-primary" />
            </div>
            <p className="mt-2 truncate text-lg font-semibold">
              {selectedCampaign ? selectedCampaign.name : "仅保存到达人库"}
            </p>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">本次预估成本</p>
              <Mail className="h-4 w-4 text-green-600" />
            </div>
            <p className="mt-2 text-2xl font-bold">
              {estimate ? formatCny(estimate.estimated_total_cny) : "..."}
            </p>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">本月 Woto 成本</p>
              <Database className="h-4 w-4 text-blue-600" />
            </div>
            <p className="mt-2 text-lg font-semibold">
              {pricing ? formatCny(pricing.current_month_spend_cny) : "..."}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {pricing
                ? `${pricing.current_month_billable_calls} 次，${formatDiscount(pricing.current_discount_rate)}`
                : "读取中"}
            </p>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-5">
          <Card className="space-y-5 p-5 lg:col-span-2">
            <div>
              <h3 className="font-semibold">同步条件</h3>
              <p className="text-sm text-muted-foreground">
                建议先勾选“有邮箱”，这样入库后可以直接进入 Campaign 待发送。
              </p>
            </div>

            <div>
              <Label className="mb-2 block">平台</Label>
              <div className="grid grid-cols-3 gap-2">
                {(["tiktok", "instagram", "youtube"] as WotoPlatform[]).map((platform) => (
                  <button
                    key={platform}
                    onClick={() => updateForm({ platform })}
                    className={`rounded-xl border px-3 py-2 text-sm font-medium transition-colors ${
                      form.platform === platform
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border hover:border-primary/50 hover:bg-muted"
                    }`}
                  >
                    {PLATFORM_LABELS[platform]}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>搜索类型</Label>
                <Select
                  value={form.searchType}
                  onValueChange={(value) =>
                    value &&
                    updateForm({ searchType: value as FormState["searchType"] })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="KEYWORD">关键词搜索</SelectItem>
                    <SelectItem value="NAME">达人名搜索</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>同步数量（1–500）</Label>
                <PresetInput
                  value={form.limit}
                  onChange={(v) => updateForm({ limit: v })}
                  presets={LIMIT_PRESETS}
                  placeholder="1"
                  min={1}
                  max={500}
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>关键词</Label>
                <Input
                  value={form.keyword}
                  onChange={(event) => updateForm({ keyword: event.target.value })}
                  placeholder="supplements / collagen / skincare"
                />
              </div>
              <div>
                <Label>达人名</Label>
                <Input
                  value={form.bloggerName}
                  onChange={(event) => updateForm({ bloggerName: event.target.value })}
                  placeholder="按名称搜索时填写"
                />
              </div>
            </div>

            <div>
              <Label>排除关键词（逗号分隔）</Label>
              <Input
                value={form.excludeKeywords}
                onChange={(event) => updateForm({ excludeKeywords: event.target.value })}
                placeholder="giveaway, fake, repost"
              />
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>国家/地区</Label>
                <select
                  value={form.regionId}
                  onChange={(event) => updateForm({ regionId: event.target.value })}
                  className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                >
                  <option value="">全部地区</option>
                  {regions.map((region) => (
                    <option key={String(region.id ?? region.dict_code)} value={String(region.id)}>
                      {region.dict_value || region.dict_code || region.id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label>达人分类</Label>
                <select
                  value={form.categoryId}
                  onChange={(event) => updateForm({ categoryId: event.target.value })}
                  className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                >
                  <option value="">全部分类</option>
                  {categories.map((category) => (
                    <option key={String(category.id ?? category.dict_code)} value={String(category.id)}>
                      {category.dict_value || category.dict_code || category.id}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>粉丝下限</Label>
                <PresetInput
                  value={form.minFollowers}
                  onChange={(v) => updateForm({ minFollowers: v })}
                  presets={FOLLOWER_PRESETS}
                  placeholder="不限"
                  min={0}
                />
              </div>
              <div>
                <Label>粉丝上限</Label>
                <PresetInput
                  value={form.maxFollowers}
                  onChange={(v) => updateForm({ maxFollowers: v })}
                  presets={FOLLOWER_PRESETS}
                  placeholder="不限"
                  min={0}
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>互动率下限 %</Label>
                <PresetInput
                  value={form.minEngagementRate}
                  onChange={(v) => updateForm({ minEngagementRate: v })}
                  presets={ENGAGEMENT_PRESETS}
                  placeholder="不限"
                  min={0}
                  max={100}
                  step={0.1}
                />
              </div>
              <div>
                <Label>互动率上限 %</Label>
                <PresetInput
                  value={form.maxEngagementRate}
                  onChange={(v) => updateForm({ maxEngagementRate: v })}
                  presets={ENGAGEMENT_PRESETS}
                  placeholder="不限"
                  min={0}
                  max={100}
                  step={0.1}
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>平均观看下限</Label>
                <PresetInput
                  value={form.minAvgViews}
                  onChange={(v) => updateForm({ minAvgViews: v })}
                  presets={AVG_VIEWS_PRESETS}
                  placeholder="不限"
                  min={0}
                />
              </div>
              <div>
                <Label>平均观看上限</Label>
                <PresetInput
                  value={form.maxAvgViews}
                  onChange={(v) => updateForm({ maxAvgViews: v })}
                  presets={AVG_VIEWS_PRESETS}
                  placeholder="不限"
                  min={0}
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>邮箱筛选</Label>
                <Select
                  value={form.hasEmail}
                  onValueChange={(value) =>
                    value &&
                    updateForm({ hasEmail: value as FormState["hasEmail"] })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">优先有邮箱</SelectItem>
                    <SelectItem value="any">不限</SelectItem>
                    <SelectItem value="false">无邮箱也同步</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>排序</Label>
                <Select
                  value={form.sort}
                  onValueChange={(value) =>
                    value && updateForm({ sort: value as FormState["sort"] })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="FANS_NUM">粉丝数</SelectItem>
                    <SelectItem value="VIEW_AVG">平均观看</SelectItem>
                    <SelectItem value="INTERACTIVE_RATE">互动率</SelectItem>
                    <SelectItem value="TOTAL_STAR">Woto 评分</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label>同步后加入活动</Label>
              <select
                value={form.campaignId}
                onChange={(event) => updateForm({ campaignId: event.target.value })}
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
              >
                <option value="">不入组，仅保存本地</option>
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>
                    {campaign.name}（{campaign.status}）
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                按需付费功能
              </Label>
              <label
                className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm transition-colors ${
                  form.fetchDetail ? "border-primary/40 bg-primary/5" : "hover:bg-muted/50"
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 shrink-0"
                  checked={form.fetchDetail}
                  onChange={(event) => updateForm({ fetchDetail: event.target.checked })}
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">获取基础数据</span>
                    <span className="shrink-0 font-mono text-xs text-amber-600">
                      ¥0.75–1.50/个
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    频道信息、粉丝画像、互动率、Woto 评分等。关闭后仅保存搜索列表字段。
                  </p>
                </div>
              </label>
              <label
                className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm transition-colors ${
                  !form.fetchDetail
                    ? "cursor-not-allowed opacity-40"
                    : form.enrichContacts
                      ? "border-primary/40 bg-primary/5"
                      : "hover:bg-muted/50"
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 shrink-0"
                  checked={form.enrichContacts}
                  disabled={!form.fetchDetail}
                  onChange={(event) => updateForm({ enrichContacts: event.target.checked })}
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">获取联系邮箱</span>
                    <span className="shrink-0 font-mono text-xs text-amber-600">¥1.50/个</span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    已验证商务邮箱；无邮箱返回时不计费。需先开启「获取基础数据」。
                  </p>
                </div>
              </label>
            </div>

            {estimate && (
              <div className="rounded-2xl border bg-muted/30 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">成本预估</p>
                    <p className="text-xs text-muted-foreground">
                      {estimate.estimated_billable_calls} 次预估调用，当前阶梯{" "}
                      {formatDiscount(estimate.discount_rate)}
                    </p>
                  </div>
                  <p className="text-xl font-bold">{formatCny(estimate.estimated_total_cny)}</p>
                </div>
                <div className="mt-3 space-y-2">
                  {estimate.lines.map((line) => (
                    <div
                      key={`${line.operation}-${line.platform}`}
                      className="flex items-center justify-between gap-3 text-sm"
                    >
                      <span className="text-muted-foreground">
                        {line.label} × {line.units}
                      </span>
                      <span className="font-medium">{formatCny(line.discounted_subtotal_cny)}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  实际成本会按 Woto 返回数量、是否返回邮箱、本地重复 external_id 去重后结算。
                </p>
              </div>
            )}

            <Button className="w-full gap-2" onClick={handleStartSync} disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  创建任务中...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4" />
                  开始 Woto 同步
                </>
              )}
            </Button>
          </Card>

          <div className="space-y-4 lg:col-span-3">
            {pricing && (
              <Card className="p-4">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h3 className="font-semibold">Woto API 资费表</h3>
                    <p className="text-sm text-muted-foreground">
                      有效期 {pricing.valid_from} 至 {pricing.valid_to}，限速{" "}
                      {pricing.rate_limit_per_minute} 次/分钟。
                    </p>
                  </div>
                  <Badge variant="outline">{formatDiscount(pricing.current_discount_rate)}</Badge>
                </div>
                <div className="mt-4 grid gap-2 md:grid-cols-2">
                  {pricing.items.map((item) => (
                    <div
                      key={`${item.operation}-${item.platform}-${item.label}`}
                      className="rounded-xl border p-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium">{item.label}</p>
                          <p className="text-xs text-muted-foreground">
                            {item.platform === "all" ? "全平台" : PLATFORM_LABELS[item.platform as WotoPlatform] || item.platform}
                            {item.return_count ? ` · 每次返回 ${item.return_count}` : ""}
                          </p>
                        </div>
                        <p className="whitespace-nowrap text-sm font-bold">
                          {formatCny(item.unit_price_cny)}/{item.unit}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">{pricing.duplicate_policy}</p>
              </Card>
            )}

            <div className="flex items-center justify-between">
              <h3 className="font-semibold">同步任务</h3>
              <p className="text-sm text-muted-foreground">Celery 后台执行，可安全离开页面</p>
            </div>

            {jobs.length === 0 ? (
              <Card className="flex flex-col items-center justify-center gap-4 py-16 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
                  <Database className="h-6 w-6 text-muted-foreground" />
                </div>
                <div>
                  <p className="font-medium">还没有 Woto 同步任务</p>
                  <p className="text-sm text-muted-foreground">
                    配好搜索条件后，点击“开始 Woto 同步”。
                  </p>
                </div>
              </Card>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => (
                  <Card key={job.id} className="p-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {PLATFORM_LABELS[job.platform as WotoPlatform] || job.platform}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            {formatDate(job.created_at)}
                          </span>
                          {job.campaign_id && (
                            <Badge variant="outline" className="text-xs">
                              自动入组
                            </Badge>
                          )}
                        </div>
                        <p className="mt-1 font-mono text-xs text-muted-foreground">
                          {job.id}
                        </p>
                      </div>
                      <JobStatusBadge status={job.status} />
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-3 border-t pt-4 sm:grid-cols-5">
                      <div>
                        <p className="text-lg font-bold">{job.discovered}</p>
                        <p className="text-xs text-muted-foreground">发现</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-green-600">{job.created_count}</p>
                        <p className="text-xs text-muted-foreground">新增</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-blue-600">{job.updated_count}</p>
                        <p className="text-xs text-muted-foreground">更新</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-primary">{job.enrolled_count}</p>
                        <p className="text-xs text-muted-foreground">入组</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-muted-foreground">{job.skipped_count}</p>
                        <p className="text-xs text-muted-foreground">跳过</p>
                      </div>
                    </div>

                    <div className="mt-3 grid gap-2 rounded-xl bg-muted/30 p-3 text-sm md:grid-cols-3">
                      <div>
                        <p className="text-xs text-muted-foreground">预估成本</p>
                        <p className="font-semibold">{formatCny(job.estimated_cost_cny)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">实际计费</p>
                        <p className="font-semibold">{formatCny(job.actual_cost_cny)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">计费调用</p>
                        <p className="font-semibold">
                          搜索 {job.billable_search_calls} / 基础 {job.billable_detail_calls} / 邮箱{" "}
                          {job.billable_contact_calls}
                        </p>
                      </div>
                    </div>

                    {job.status === "running" && (
                      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                        <div className="h-full w-2/3 animate-pulse rounded-full bg-primary" />
                      </div>
                    )}

                    {job.error_message && (
                      <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                        {job.error_message}
                      </p>
                    )}

                    {job.warning_messages && job.warning_messages.length > 0 && (
                      <div className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-700">
                        {job.warning_messages.slice(0, 2).join("；")}
                        {job.warning_messages.length > 2 ? " ..." : ""}
                      </div>
                    )}

                    {job.status === "completed" && (
                      <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
                        <Link href="/influencers?source=woto">
                          <Button variant="outline" size="sm">
                            查看入库达人
                          </Button>
                        </Link>
                        {job.campaign_id && (
                          <Link href={`/campaigns/${job.campaign_id}`}>
                            <Button variant="outline" size="sm">
                              查看活动入组
                            </Button>
                          </Link>
                        )}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
