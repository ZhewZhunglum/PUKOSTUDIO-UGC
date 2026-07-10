"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { INFLUENCER_STATUS_MAP } from "@/lib/constants";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  Campaign,
  Influencer,
  InfluencerCRMAction,
  InfluencerCRMSummary,
  PaginatedResponse,
  Tag,
  WotoQuota,
  WotoSyncJob,
  WotoSyncRequest,
} from "@/types";
import {
  AlertCircle,
  Archive,
  Ban,
  Copy,
  Database,
  Heart,
  Loader2,
  Mail,
  MessageSquareText,
  RefreshCcw,
  Search,
  Send,
  Settings,
  Sparkles,
  Star,
  Trash2,
  Unlock,
  UserCheck,
  Zap,
} from "lucide-react";

type PlatformFilter = "all" | "tiktok" | "instagram" | "youtube";
type FolderKey =
  | "archives"
  | "to_invite"
  | "contacted"
  | "recommended"
  | "platform_recommend"
  | "blacklist"
  | "unlocked"
  | "collected"
  | "special_focus";

type SyncForm = {
  platform: WotoSyncRequest["platform"];
  keyword: string;
  limit: string;
  hasEmail: "any" | "true" | "false";
  campaignId: string;
  enrichContacts: boolean;
};

const EMPTY_PAGE: PaginatedResponse<Influencer> = {
  items: [],
  total: 0,
  page: 1,
  per_page: 20,
  pages: 0,
};

const PLATFORM_LABELS: Record<string, string> = {
  tiktok: "TikTok",
  instagram: "Instagram",
  youtube: "YouTube",
};

const STATUS_LABELS = INFLUENCER_STATUS_MAP;

const FOLDERS: Array<{
  key: FolderKey;
  label: string;
  description: string;
  icon: typeof Archive;
}> = [
  { key: "archives", label: "红人档案", description: "全部本地达人", icon: Archive },
  { key: "to_invite", label: "待邀约", description: "新入库未联系", icon: Send },
  { key: "contacted", label: "已联系红人", description: "已发送或沟通过", icon: Mail },
  { key: "recommended", label: "推荐红人", description: "团队标记推荐", icon: Sparkles },
  { key: "platform_recommend", label: "平台推荐", description: "Woto API 来源", icon: Database },
  { key: "blacklist", label: "拉黑红人", description: "不再触达", icon: Ban },
  { key: "unlocked", label: "已解锁红人", description: "已有邮箱", icon: Unlock },
  { key: "collected", label: "已收藏红人", description: "收藏夹候选", icon: Heart },
  { key: "special_focus", label: "特别关注", description: "重点跟进对象", icon: Star },
];

const TAG_FOLDER_NAMES: Partial<Record<FolderKey, string>> = {
  recommended: "推荐红人",
  collected: "已收藏",
  special_focus: "特别关注",
};

const STATUS_FOLDER_FILTERS: Partial<Record<FolderKey, Influencer["status"]>> = {
  to_invite: "new",
  contacted: "contacted",
  blacklist: "blacklisted",
};

const ACTION_LABELS: Record<InfluencerCRMAction, string> = {
  mark_contacted: "标记已联系",
  mark_replied: "标记已回复",
  mark_negotiating: "标记议价中",
  mark_signed: "标记已签约",
  mark_rejected: "标记已拒绝",
  special_attention: "特别关注",
  favorite: "收藏",
  recommend: "推荐",
  blacklist: "拉黑",
  restore: "恢复待邀约",
  append_note: "添加备注",
};

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

function normalizeRate(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  return value <= 1 ? value * 100 : value;
}

function formatRate(value: number | null | undefined): string {
  const normalized = normalizeRate(value);
  return normalized === null ? "-" : `${normalized.toFixed(1)}%`;
}

function formatDate(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString("zh-CN") : "-";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function rawValue(influencer: Influencer, keys: string[]): unknown {
  const platform = influencer.platforms[0];
  if (!platform?.raw_data) return null;
  const raw = platform.raw_data;
  const pools = [
    raw,
    isRecord(raw.search) ? raw.search : null,
    isRecord(raw.detail) ? raw.detail : null,
  ].filter(Boolean) as Record<string, unknown>[];

  for (const pool of pools) {
    for (const key of keys) {
      const value = pool[key];
      if (value !== undefined && value !== null && value !== "") {
        return value;
      }
    }
  }
  return null;
}

function formatRawNumber(influencer: Influencer, keys: string[]): string {
  const value = rawValue(influencer, keys);
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "string" && value.trim()) {
    const number = Number(value.replace(/,/g, ""));
    return Number.isFinite(number) ? formatNumber(number) : value;
  }
  return "未接入";
}

function firstPlatform(influencer: Influencer) {
  return influencer.platforms[0];
}

function folderCount(folder: FolderKey, summary: InfluencerCRMSummary | null): number {
  if (!summary) return 0;
  if (folder === "archives") return summary.total;
  if (folder === "to_invite") return summary.by_status.new ?? 0;
  if (folder === "contacted") {
    return (
      (summary.by_status.contacted ?? 0) +
      (summary.by_status.replied ?? 0) +
      (summary.by_status.negotiating ?? 0) +
      (summary.by_status.signed ?? 0)
    );
  }
  if (folder === "platform_recommend") return summary.woto;
  if (folder === "blacklist") return summary.by_status.blacklisted ?? 0;
  if (folder === "unlocked") return summary.has_email;
  const tagName = TAG_FOLDER_NAMES[folder];
  return tagName ? summary.by_tag[tagName] ?? 0 : 0;
}

function buildSyncPayload(form: SyncForm): WotoSyncRequest {
  return {
    platform: form.platform,
    search_type: "KEYWORD",
    keyword: form.keyword.trim() || null,
    blogger_name: null,
    exclude_keywords: [],
    region_ids: [],
    category_ids: [],
    min_followers: null,
    max_followers: null,
    min_engagement_rate: null,
    max_engagement_rate: null,
    has_email: form.hasEmail === "any" ? null : form.hasEmail === "true",
    min_avg_views: null,
    max_avg_views: null,
    sort: "FANS_NUM",
    sort_order: "desc",
    limit: Number(form.limit || 50),
    fetch_detail: true,
    enrich_contacts: form.enrichContacts,
    campaign_id: form.campaignId || null,
  };
}

function tagByName(tags: Tag[], name: string): Tag | undefined {
  return tags.find((tag) => tag.name === name);
}

export default function BlogerManagerPage() {
  const [activeFolder, setActiveFolder] = useState<FolderKey>("archives");
  const [data, setData] = useState<PaginatedResponse<Influencer>>(EMPTY_PAGE);
  const [summary, setSummary] = useState<InfluencerCRMSummary | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [quota, setQuota] = useState<WotoQuota | null>(null);
  const [wotoUnconfigured, setWotoUnconfigured] = useState(false);
  const [jobs, setJobs] = useState<WotoSyncJob[]>([]);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const reqIdRef = useRef(0);
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");
  const [hasEmailFilter, setHasEmailFilter] = useState<"all" | "true" | "false">("all");
  const [sortBy, setSortBy] = useState("fans_num");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [metaLoading, setMetaLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [noteTarget, setNoteTarget] = useState<Influencer | null>(null);
  const [noteText, setNoteText] = useState("");
  const [syncSubmitting, setSyncSubmitting] = useState(false);
  const [syncForm, setSyncForm] = useState<SyncForm>({
    platform: "tiktok",
    keyword: "",
    limit: "50",
    hasEmail: "true",
    campaignId: "",
    enrichContacts: true,
  });

  const fetchSummary = useCallback(async () => {
    const response = await api.get<InfluencerCRMSummary>("/influencers/crm-summary");
    setSummary(response.data);
  }, []);

  const fetchInfluencers = useCallback(async () => {
    const reqId = ++reqIdRef.current;
    setLoading(true);
    setErrorMsg(null);
    try {
      const params: Record<string, string | number | boolean> = {
        page,
        per_page: 20,
        sort_by: sortBy,
        sort_order: "desc",
      };
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (platformFilter !== "all") params.platform = platformFilter;
      if (hasEmailFilter !== "all") params.has_email = hasEmailFilter;

      const statusFilter = STATUS_FOLDER_FILTERS[activeFolder];
      if (statusFilter) params.status = statusFilter;
      if (activeFolder === "contacted") {
        params.status = "contacted";
      }
      if (activeFolder === "platform_recommend") {
        params.source = "woto";
      }
      if (activeFolder === "unlocked") {
        params.has_email = true;
      }

      const tagName = TAG_FOLDER_NAMES[activeFolder];
      if (tagName) {
        const tag = tagByName(tags, tagName);
        if (!tag) {
          setData({ ...EMPTY_PAGE, page });
          return;
        }
        params.tag_id = tag.id;
      }

      const response = await api.get<PaginatedResponse<Influencer>>("/influencers", {
        params,
      });
      if (reqId === reqIdRef.current) setData(response.data);
    } catch (error: unknown) {
      if (reqId !== reqIdRef.current) return;
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "红人管理列表加载失败";
      setErrorMsg(detail);
    } finally {
      // Only the latest in-flight request applies results / clears the spinner.
      if (reqId === reqIdRef.current) setLoading(false);
    }
  }, [activeFolder, hasEmailFilter, page, platformFilter, debouncedSearch, sortBy, tags]);

  const fetchMeta = useCallback(async () => {
    setMetaLoading(true);
    setWotoUnconfigured(false);
    try {
      const [summaryResponse, tagsResponse, campaignResponse, jobResponse, quotaResponse] =
        await Promise.all([
          api.get<InfluencerCRMSummary>("/influencers/crm-summary"),
          api.get<Tag[]>("/influencers/tags/list"),
          api.get<Campaign[]>("/campaigns"),
          api.get<WotoSyncJob[]>("/discovery/woto/sync-jobs", { params: { limit: 8 } }),
          api.get<WotoQuota>("/discovery/woto/quota").catch((err: unknown) => {
            const msg: string =
              (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "";
            if (msg.includes("API Key") || msg.includes("WOTO_API_KEY")) {
              setWotoUnconfigured(true);
            }
            return { data: null };
          }),
        ]);
      setSummary(summaryResponse.data);
      setTags(tagsResponse.data);
      setCampaigns(
        campaignResponse.data.filter((campaign) =>
          ["draft", "paused"].includes(campaign.status)
        )
      );
      setJobs(jobResponse.data);
      setQuota(quotaResponse.data);
    } catch {
      setErrorMsg("红人管理台初始化失败，请确认后端已启动");
    } finally {
      setMetaLoading(false);
    }
  }, []);

  useEffect(() => {
    const queryCampaignId =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("campaign_id")
        : null;
    if (queryCampaignId) {
      setSyncForm((current) => ({ ...current, campaignId: queryCampaignId }));
    }
    void fetchMeta();
  }, [fetchMeta]);

  useEffect(() => {
    void fetchInfluencers();
  }, [fetchInfluencers]);

  // A new (debounced) search term resets to the first page of results.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
  }, [activeFolder, platformFilter, hasEmailFilter, search, sortBy]);

  useEffect(() => {
    const hasActiveJobs = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!hasActiveJobs) return;
    const timer = window.setInterval(async () => {
      const response = await api.get<WotoSyncJob[]>("/discovery/woto/sync-jobs", {
        params: { limit: 8 },
      });
      setJobs(response.data);
      if (response.data.every((job) => job.status !== "queued" && job.status !== "running")) {
        await fetchSummary();
        await fetchInfluencers();
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [fetchInfluencers, fetchSummary, jobs]);

  const updateSyncForm = (patch: Partial<SyncForm>) => {
    setSyncForm((current) => ({ ...current, ...patch }));
  };

  const replaceInfluencer = (updated: Influencer) => {
    setData((current) => ({
      ...current,
      items: current.items.map((item) => (item.id === updated.id ? updated : item)),
    }));
  };

  const handleCRMAction = async (
    influencer: Influencer,
    action: InfluencerCRMAction,
    note?: string
  ) => {
    setBusyId(influencer.id);
    setErrorMsg(null);
    try {
      const response = await api.post<Influencer>(`/influencers/${influencer.id}/crm-action`, {
        action,
        note,
      });
      replaceInfluencer(response.data);
      await fetchSummary();
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        `${ACTION_LABELS[action]}失败`;
      setErrorMsg(detail);
    } finally {
      setBusyId(null);
    }
  };

  const handleWotoRefresh = async (influencer: Influencer) => {
    if (wotoUnconfigured) {
      setErrorMsg("Woto API Key 未配置，请前往「系统设置 → Woto API」配置后再使用。");
      return;
    }
    setBusyId(influencer.id);
    setErrorMsg(null);
    try {
      const response = await api.post<Influencer>(`/influencers/${influencer.id}/woto-refresh`);
      replaceInfluencer(response.data);
      await fetchSummary();
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Woto 刷新失败";
      setErrorMsg(detail);
    } finally {
      setBusyId(null);
    }
  };

  const handleEnroll = async (influencer: Influencer) => {
    if (!syncForm.campaignId) {
      setErrorMsg("请先在右侧选择一个草稿或暂停中的 Campaign");
      return;
    }
    setBusyId(influencer.id);
    try {
      await api.post(`/campaigns/${syncForm.campaignId}/enroll`, {
        influencer_ids: [influencer.id],
      });
      await handleCRMAction(influencer, "mark_contacted");
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "加入 Campaign 失败";
      setErrorMsg(detail);
      setBusyId(null);
    }
  };

  const handleDelete = async (influencer: Influencer) => {
    if (!confirm(`确定从本地达人库移除 ${influencer.name} 吗？`)) return;
    setBusyId(influencer.id);
    try {
      await api.delete(`/influencers/${influencer.id}`);
      await fetchInfluencers();
      await fetchSummary();
    } catch {
      setErrorMsg("移除达人失败");
    } finally {
      setBusyId(null);
    }
  };

  const handleCopy = async (influencer: Influencer) => {
    const platform = firstPlatform(influencer);
    const value = platform?.profile_url || influencer.email || influencer.name;
    await copyText(value);
  };

  const handleStartSync = async () => {
    if (wotoUnconfigured) {
      setErrorMsg("Woto API Key 未配置，请前往「系统设置 → Woto API」配置后再使用。");
      return;
    }
    if (!syncForm.keyword.trim()) {
      setErrorMsg("请填写 Woto 搜索关键词");
      return;
    }
    setSyncSubmitting(true);
    setErrorMsg(null);
    try {
      const response = await api.post<WotoSyncJob>(
        "/discovery/woto/sync-jobs",
        buildSyncPayload(syncForm)
      );
      setJobs((current) => [response.data, ...current].slice(0, 8));
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "创建 Woto 自动建联任务失败";
      setErrorMsg(detail);
    } finally {
      setSyncSubmitting(false);
    }
  };

  const handleBulkAction = async (action: InfluencerCRMAction) => {
    const selected = data.items.filter((item) => selectedIds.has(item.id));
    for (const influencer of selected) {
      await handleCRMAction(influencer, action);
    }
    setSelectedIds(new Set());
  };

  const handleSaveNote = async () => {
    if (!noteTarget) return;
    await handleCRMAction(noteTarget, "append_note", noteText);
    setNoteTarget(null);
    setNoteText("");
  };

  const latestJob = jobs[0];
  const selectedCampaign = campaigns.find((campaign) => campaign.id === syncForm.campaignId);

  return (
    <AppLayout>
      <div className="space-y-6 fade-in">
        <div className="overflow-hidden rounded-[2rem] border bg-[radial-gradient(circle_at_top_left,_rgba(20,184,166,0.20),_transparent_32%),linear-gradient(135deg,_#06131c,_#0f172a_52%,_#111827)] p-6 text-white shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="border-white/20 bg-white/10 text-white hover:bg-white/10">
                  Woto CRM
                </Badge>
                <Badge className="border-emerald-300/40 bg-emerald-300/15 text-emerald-100 hover:bg-emerald-300/15">
                  API 已接入
                </Badge>
              </div>
              <h2 className="mt-4 text-3xl font-bold tracking-tight">红人管理</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                对齐 WotoHub 红人管理的信息架构：红人档案、待邀约、已联系、收藏、推荐、特别关注、拉黑和已解锁邮箱。
                这里使用本地达人库作为主数据源，并通过 Woto API 自动搜索、补联系方式、同步数据和加入 Campaign。
              </p>
            </div>
            <div className="grid min-w-[280px] grid-cols-2 gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">本地红人</p>
                <p className="mt-1 text-2xl font-bold">{summary?.total ?? "..."}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">Woto 额度</p>
                {wotoUnconfigured ? (
                  <Link href="/settings?tab=woto" className="mt-1 flex items-center gap-1.5 text-amber-300 hover:text-amber-200">
                    <Settings className="h-4 w-4" />
                    <span className="text-sm font-medium">去配置</span>
                  </Link>
                ) : (
                  <p className="mt-1 text-2xl font-bold">{quota?.remain_quota ?? "—"}</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {wotoUnconfigured && (
          <Card className="border-amber-300/50 bg-amber-50/80 p-4 text-sm dark:border-amber-700/40 dark:bg-amber-900/20">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-start gap-2 text-amber-800 dark:text-amber-200">
                <Settings className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Woto API Key 未配置，请先在设置页填写，Woto 相关功能（搜索、解锁邮箱）暂不可用。</span>
              </div>
              <Link href="/settings?tab=woto" className="shrink-0">
                <Button size="sm" variant="outline" className="border-amber-400 text-amber-800 hover:bg-amber-100 dark:border-amber-600 dark:text-amber-200">
                  去配置
                </Button>
              </Link>
            </div>
          </Card>
        )}
        {errorMsg && (
          <Card className="border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4" />
              <span>{errorMsg}</span>
              {(errorMsg.includes("API Key") || errorMsg.includes("WOTO_API_KEY") || errorMsg.includes("未配置")) && (
                <Link href="/settings?tab=woto" className="ml-auto shrink-0 underline">
                  去配置
                </Link>
              )}
            </div>
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">待邀约</p>
              <Send className="h-4 w-4 text-blue-500" />
            </div>
            <p className="mt-2 text-2xl font-bold">{summary?.by_status.new ?? 0}</p>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">已联系/沟通中</p>
              <MessageSquareText className="h-4 w-4 text-emerald-500" />
            </div>
            <p className="mt-2 text-2xl font-bold">{folderCount("contacted", summary)}</p>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">已解锁邮箱</p>
              <Unlock className="h-4 w-4 text-amber-500" />
            </div>
            <p className="mt-2 text-2xl font-bold">{summary?.has_email ?? 0}</p>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Woto 来源</p>
              <Zap className="h-4 w-4 text-primary" />
            </div>
            <p className="mt-2 text-2xl font-bold">{summary?.woto ?? 0}</p>
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-[280px_1fr_320px]">
          <div className="space-y-4">
            <Card className="p-3">
              <div className="mb-3 px-2">
                <p className="text-sm font-semibold">红人分组</p>
                <p className="text-xs text-muted-foreground">复刻 WotoHub 的红人管理栏目</p>
              </div>
              <div className="space-y-1">
                {FOLDERS.map((folder) => {
                  const Icon = folder.icon;
                  const active = activeFolder === folder.key;
                  return (
                    <button
                      key={folder.key}
                      onClick={() => setActiveFolder(folder.key)}
                      className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-colors ${
                        active
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "hover:bg-muted"
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium">{folder.label}</span>
                        <span
                          className={`block truncate text-xs ${
                            active ? "text-primary-foreground/70" : "text-muted-foreground"
                          }`}
                        >
                          {folder.description}
                        </span>
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          active ? "bg-white/15" : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {folderCount(folder.key, summary)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </Card>

            <Card className="space-y-3 p-4">
              <div>
                <p className="font-semibold">快速自动建联</p>
                <p className="text-xs text-muted-foreground">
                  调 Woto 搜索、补邮箱、保存本地，可选加入 Campaign。
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {(["tiktok", "instagram", "youtube"] as const).map((platform) => (
                  <button
                    key={platform}
                    onClick={() => updateSyncForm({ platform })}
                    className={`rounded-xl border px-2 py-2 text-xs font-medium ${
                      syncForm.platform === platform
                        ? "border-primary bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    {PLATFORM_LABELS[platform]}
                  </button>
                ))}
              </div>
              <div>
                <Label>关键词</Label>
                <Input
                  value={syncForm.keyword}
                  onChange={(event) => updateSyncForm({ keyword: event.target.value })}
                  placeholder="skincare / collagen"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label>数量</Label>
                  <Select
                    value={syncForm.limit}
                    onValueChange={(value) => value && updateSyncForm({ limit: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="20">20 位</SelectItem>
                      <SelectItem value="50">50 位</SelectItem>
                      <SelectItem value="100">100 位</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>邮箱</Label>
                  <Select
                    value={syncForm.hasEmail}
                    onValueChange={(value) =>
                      value && updateSyncForm({ hasEmail: value as SyncForm["hasEmail"] })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">优先有邮箱</SelectItem>
                      <SelectItem value="any">不限</SelectItem>
                      <SelectItem value="false">可无邮箱</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>同步后加入 Campaign</Label>
                <select
                  value={syncForm.campaignId}
                  onChange={(event) => updateSyncForm({ campaignId: event.target.value })}
                  className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                >
                  <option value="">仅保存本地</option>
                  {campaigns.map((campaign) => (
                    <option key={campaign.id} value={campaign.id}>
                      {campaign.name}
                    </option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 rounded-xl border p-2 text-xs">
                <input
                  type="checkbox"
                  checked={syncForm.enrichContacts}
                  onChange={(event) => updateSyncForm({ enrichContacts: event.target.checked })}
                />
                自动解锁/补充邮箱
              </label>
              <Button className="w-full" onClick={handleStartSync} disabled={syncSubmitting}>
                {syncSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    创建任务中
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4" />
                    从 Woto 自动建联
                  </>
                )}
              </Button>
            </Card>
          </div>

          <Card className="overflow-hidden">
            <div className="border-b p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="font-semibold">
                    {FOLDERS.find((folder) => folder.key === activeFolder)?.label}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    当前显示 {data.total} 位达人，支持 Woto 数据刷新、邮箱解锁和 Campaign 入组。
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={fetchMeta} disabled={metaLoading}>
                    <RefreshCcw className={`h-4 w-4 ${metaLoading ? "animate-spin" : ""}`} />
                    刷新概览
                  </Button>
                  <Link href="/discovery">
                    <Button variant="outline" size="sm">
                      <Sparkles className="h-4 w-4" />
                      高级发现
                    </Button>
                  </Link>
                </div>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_150px_150px_180px]">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="搜索达人名称或邮箱"
                    className="pl-10"
                  />
                </div>
                <Select
                  value={platformFilter}
                  onValueChange={(value) => setPlatformFilter(value as PlatformFilter)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部平台</SelectItem>
                    <SelectItem value="tiktok">TikTok</SelectItem>
                    <SelectItem value="instagram">Instagram</SelectItem>
                    <SelectItem value="youtube">YouTube</SelectItem>
                  </SelectContent>
                </Select>
                <Select
                  value={hasEmailFilter}
                  onValueChange={(value) =>
                    setHasEmailFilter(value as "all" | "true" | "false")
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部邮箱</SelectItem>
                    <SelectItem value="true">已解锁邮箱</SelectItem>
                    <SelectItem value="false">缺邮箱</SelectItem>
                  </SelectContent>
                </Select>
                <Select
                  value={sortBy}
                  onValueChange={(value) => value && setSortBy(value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fans_num">粉丝数排序</SelectItem>
                    <SelectItem value="view_volume_avg_60d">平均观看排序</SelectItem>
                    <SelectItem value="interactive_rate_60d">互动率排序</SelectItem>
                    <SelectItem value="gmt_modify">最近更新排序</SelectItem>
                    <SelectItem value="gmt_create">创建时间排序</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {selectedIds.size > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-2xl border bg-muted/40 p-3 text-sm">
                  <span className="font-medium">已选 {selectedIds.size} 位</span>
                  <Button size="sm" variant="outline" onClick={() => handleBulkAction("favorite")}>
                    批量收藏
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleBulkAction("special_attention")}
                  >
                    批量特别关注
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleBulkAction("recommend")}>
                    批量推荐
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => handleBulkAction("blacklist")}>
                    批量拉黑
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
                    取消选择
                  </Button>
                </div>
              )}
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">
                    <input
                      type="checkbox"
                      checked={data.items.length > 0 && selectedIds.size === data.items.length}
                      onChange={(event) => {
                        setSelectedIds(
                          event.target.checked
                            ? new Set(data.items.map((influencer) => influencer.id))
                            : new Set()
                        );
                      }}
                    />
                  </TableHead>
                  <TableHead>达人</TableHead>
                  <TableHead>类型/标签</TableHead>
                  <TableHead>粉丝</TableHead>
                  <TableHead>30日GMV</TableHead>
                  <TableHead>平均观看</TableHead>
                  <TableHead>平均点赞</TableHead>
                  <TableHead>互动率</TableHead>
                  <TableHead>合作状态</TableHead>
                  <TableHead>来源/同步</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, index) => (
                    <TableRow key={index}>
                      {Array.from({ length: 11 }).map((__, cellIndex) => (
                        <TableCell key={cellIndex}>
                          <Skeleton className="h-5 w-20" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : data.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={11} className="py-16 text-center text-muted-foreground">
                      这个分组暂时没有达人。可以从左侧“快速自动建联”开始导入 Woto 达人。
                    </TableCell>
                  </TableRow>
                ) : (
                  data.items.map((influencer) => {
                    const platform = firstPlatform(influencer);
                    const isBusy = busyId === influencer.id;
                    const selected = selectedIds.has(influencer.id);
                    return (
                      <TableRow key={influencer.id} className="group">
                        <TableCell>
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={(event) => {
                              setSelectedIds((current) => {
                                const next = new Set(current);
                                if (event.target.checked) {
                                  next.add(influencer.id);
                                } else {
                                  next.delete(influencer.id);
                                }
                                return next;
                              });
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <div className="flex min-w-[220px] items-center gap-3">
                            <Avatar size="lg">
                              {influencer.avatar_url && (
                                <AvatarImage src={influencer.avatar_url} alt={influencer.name} />
                              )}
                              <AvatarFallback>{influencer.name.slice(0, 1)}</AvatarFallback>
                            </Avatar>
                            <div className="min-w-0">
                              <Link
                                href={`/influencers/${influencer.id}`}
                                className="font-medium hover:underline"
                              >
                                {influencer.name}
                              </Link>
                              <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                                {platform && (
                                  <Badge variant="outline" className="text-[10px]">
                                    {PLATFORM_LABELS[platform.platform] || platform.platform}
                                  </Badge>
                                )}
                                <span>{platform?.username ? `@${platform.username}` : "未录入账号"}</span>
                              </div>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {influencer.email || "未解锁邮箱"}
                              </p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex max-w-[180px] flex-wrap gap-1">
                            {influencer.niche && (
                              <Badge variant="secondary" className="text-[10px]">
                                {influencer.niche}
                              </Badge>
                            )}
                            {influencer.tags.slice(0, 3).map((tag) => (
                              <Badge key={tag.id} variant="outline" className="text-[10px]">
                                {tag.name}
                              </Badge>
                            ))}
                            {!influencer.niche && influencer.tags.length === 0 && (
                              <span className="text-xs text-muted-foreground">未打标</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-medium">
                          {formatNumber(platform?.followers)}
                        </TableCell>
                        <TableCell>{formatRawNumber(influencer, ["gmv30d", "gmv30D"])}</TableCell>
                        <TableCell>
                          {formatNumber(platform?.avg_views) !== "-"
                            ? formatNumber(platform?.avg_views)
                            : formatRawNumber(influencer, ["viewVolumeAvg60d", "viewAvg"])}
                        </TableCell>
                        <TableCell>
                          {formatRawNumber(influencer, ["likeVolumeAvg60d", "likeAvg"])}
                        </TableCell>
                        <TableCell>{formatRate(platform?.engagement_rate)}</TableCell>
                        <TableCell>
                          <Badge
                            variant={STATUS_LABELS[influencer.status]?.variant || "secondary"}
                          >
                            {STATUS_LABELS[influencer.status]?.label || influencer.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            <Badge
                              variant={influencer.source === "woto" ? "default" : "outline"}
                              className="text-[10px]"
                            >
                              {influencer.source === "woto" ? "Woto" : influencer.source || "manual"}
                            </Badge>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(platform?.last_synced_at || influencer.updated_at)}
                            </p>
                            {platform?.external_id && (
                              <p className="max-w-[120px] truncate font-mono text-[10px] text-muted-foreground">
                                {platform.external_id}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex min-w-[280px] flex-wrap gap-1">
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => handleEnroll(influencer)}
                              disabled={isBusy}
                            >
                              <UserCheck className="h-3 w-3" />
                              入组
                            </Button>
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => handleWotoRefresh(influencer)}
                              disabled={isBusy}
                            >
                              {isBusy ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <Unlock className="h-3 w-3" />
                              )}
                              解锁
                            </Button>
                            <Button
                              size="xs"
                              variant="ghost"
                              onClick={() => handleCRMAction(influencer, "special_attention")}
                              disabled={isBusy}
                            >
                              <Star className="h-3 w-3" />
                              关注
                            </Button>
                            <Button
                              size="xs"
                              variant="ghost"
                              onClick={() => handleCRMAction(influencer, "favorite")}
                              disabled={isBusy}
                            >
                              <Heart className="h-3 w-3" />
                              收藏
                            </Button>
                            <Button
                              size="xs"
                              variant="ghost"
                              onClick={() => handleCRMAction(influencer, "recommend")}
                              disabled={isBusy}
                            >
                              推荐
                            </Button>
                            <Button
                              size="xs"
                              variant="ghost"
                              onClick={() => {
                                setNoteTarget(influencer);
                                setNoteText("");
                              }}
                            >
                              备注
                            </Button>
                            <Button
                              size="xs"
                              variant="ghost"
                              onClick={() => handleCopy(influencer)}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                            {influencer.status === "blacklisted" ? (
                              <Button
                                size="xs"
                                variant="outline"
                                onClick={() => handleCRMAction(influencer, "restore")}
                                disabled={isBusy}
                              >
                                恢复
                              </Button>
                            ) : (
                              <Button
                                size="xs"
                                variant="destructive"
                                onClick={() => handleCRMAction(influencer, "blacklist")}
                                disabled={isBusy}
                              >
                                拉黑
                              </Button>
                            )}
                            <Button
                              size="xs"
                              variant="ghost"
                              onClick={() => handleDelete(influencer)}
                              disabled={isBusy}
                            >
                              <Trash2 className="h-3 w-3 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>

            {data.pages > 1 && (
              <div className="flex items-center justify-between border-t px-4 py-3">
                <span className="text-sm text-muted-foreground">
                  共 {data.total} 条，第 {data.page}/{data.pages} 页
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((current) => current - 1)}
                  >
                    上一页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= data.pages}
                    onClick={() => setPage((current) => current + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            )}
          </Card>

          <div className="space-y-4">
            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold">当前建联目标</p>
                  <p className="text-xs text-muted-foreground">用于单个达人入组动作</p>
                </div>
                <Mail className="h-4 w-4 text-primary" />
              </div>
              <p className="mt-3 rounded-2xl border bg-muted/30 p-3 text-sm">
                {selectedCampaign ? selectedCampaign.name : "未选择 Campaign，仅做达人库维护"}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                如果要一键同步并入组，请在左侧快速自动建联里选择 Campaign。
              </p>
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold">最近 Woto 任务</p>
                  <p className="text-xs text-muted-foreground">同步任务由 Celery 后台执行</p>
                </div>
                <Database className="h-4 w-4 text-muted-foreground" />
              </div>
              {!latestJob ? (
                <div className="mt-4 rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">
                  暂无同步任务。
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {jobs.slice(0, 5).map((job) => (
                    <div key={job.id} className="rounded-2xl border p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium">
                            {PLATFORM_LABELS[job.platform] || job.platform} ·{" "}
                            {job.query && "keyword" in job.query
                              ? String(job.query.keyword || "Woto 搜索")
                              : "Woto 搜索"}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            发现 {job.discovered}，新增 {job.created_count}，更新{" "}
                            {job.updated_count}，入组 {job.enrolled_count}
                          </p>
                        </div>
                        <Badge
                          variant={
                            job.status === "failed"
                              ? "destructive"
                              : job.status === "completed"
                                ? "outline"
                                : "default"
                          }
                        >
                          {job.status === "queued"
                            ? "排队中"
                            : job.status === "running"
                              ? "同步中"
                              : job.status === "completed"
                                ? "已完成"
                                : "失败"}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card className="p-4">
              <p className="font-semibold">WotoHub 对齐说明</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                原页面需要登录，系统根据公开路由和前端资源中可观察到的栏目复刻为功能等价版本：
                红人档案、进度状态、收藏夹、已联系、推荐、平台推荐、拉黑、已解锁、特别关注和手动录入。
              </p>
            </Card>
          </div>
        </div>

        <Dialog open={Boolean(noteTarget)} onOpenChange={(open) => !open && setNoteTarget(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加合作备注</DialogTitle>
              <DialogDescription>
                备注会追加到达人档案中，用于记录报价、样品、沟通进度或风险点。
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <Textarea
                value={noteText}
                onChange={(event) => setNoteText(event.target.value)}
                placeholder="例如：报价 $150，愿意收样，等待确认交付物..."
                rows={5}
              />
              <Button className="w-full" onClick={handleSaveNote} disabled={!noteText.trim()}>
                保存备注
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
