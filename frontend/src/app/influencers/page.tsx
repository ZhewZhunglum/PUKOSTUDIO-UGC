"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { InfluencerCard } from "@/components/influencers/influencer-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
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
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";
import { INFLUENCER_STATUS_MAP, SUPPLEMENT_NICHES, getFollowerTier } from "@/lib/constants";
import { downloadExport } from "@/lib/download";
import { useDebouncedValue } from "@/lib/hooks";
import type { Campaign, Influencer, PaginatedResponse } from "@/types";
import {
  AtSign,
  Database,
  Download,
  FileDown,
  LayoutGrid,
  List,
  Loader2,
  MailPlus,
  Pencil,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";

const PLATFORM_LABELS: Record<string, string> = {
  tiktok: "TikTok",
  instagram: "Instagram",
  youtube: "YouTube",
};

type ViewMode = "table" | "grid";

type EmailDigJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  mode: "dig" | "woto";
  input_count: number;
  processed_count: number;
  found_count: number;
  phone_found_count: number;
  updated_count: number;
  created_count: number;
  error_message: string | null;
};

// A creator that was already dug but yielded nothing gets a visible mark so
// nobody wastes another run on them.
function DigOutcome({ influencer }: { influencer: Influencer }) {
  if (!influencer.email_dig_status || influencer.email_dig_status === "found") {
    return <span className="text-muted-foreground">–</span>;
  }
  const digDate = influencer.email_dig_at
    ? new Date(influencer.email_dig_at).toLocaleDateString("zh-CN")
    : "";
  return (
    <span
      className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
      title={`批量提取已跑过${digDate ? `（${digDate}）` : ""}，公开页面上没有找到`}
    >
      {influencer.email_dig_status === "unreachable" ? "已提取·未触达" : "已提取·未找到"}
    </span>
  );
}

// Tiny provenance tag so dig-found vs Woto-paid contacts are tellable apart at
// a glance (and countable via the export's *_source columns).
function SourceTag({ source }: { source: string | null }) {
  if (!source) return null;
  const isWoto = source === "woto";
  return (
    <span
      className={`ml-1 rounded px-1 py-px align-middle text-[10px] ${
        isWoto ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"
      }`}
      title={isWoto ? "通过 Woto 付费库补充" : "公开主页免费提取"}
    >
      {isWoto ? "Woto" : "提取"}
    </span>
  );
}

// Niche cells can hold long comma-separated lists (e.g. Woto tags). Render each
// as a chip in a fixed-width box that wraps between chips and scrolls when it
// overflows — never char-by-char vertical stacking.
function NicheCell({ niche }: { niche: string | null }) {
  if (!niche) return <span className="text-muted-foreground">–</span>;
  const parts = niche.split(/[,，、]/).map((s) => s.trim().replace(/_/g, " ")).filter(Boolean);
  return (
    <div
      className="flex flex-wrap gap-1 overflow-y-auto"
      style={{ minWidth: 120, maxWidth: 180, maxHeight: 56 }}
    >
      {parts.map((part, i) => (
        <span
          key={i}
          className="whitespace-nowrap rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
        >
          {part}
        </span>
      ))}
    </div>
  );
}

type InfluencerFormState = {
  name: string;
  email: string;
  niche: string;
  notes: string;
  platform: string;
  username: string;
  followers: string;
  engagement_rate: string;
};

const EMPTY_FORM: InfluencerFormState = {
  name: "",
  email: "",
  niche: "",
  notes: "",
  platform: "",
  username: "",
  followers: "",
  engagement_rate: "",
};

function formatFollowers(value: number | null | undefined): string {
  if (!value) return "–";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

function normalizeEngagementRate(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  return value <= 1 ? value * 100 : value;
}

function getSopRecommendation(platform: Influencer["platforms"][number] | undefined) {
  if (!platform) {
    return {
      label: "待补资料",
      detail: "缺平台数据",
      variant: "outline" as const,
    };
  }
  const engagementRate = normalizeEngagementRate(platform.engagement_rate);
  if (engagementRate === null) {
    return {
      label: "待验证",
      detail: "补互动率",
      variant: "outline" as const,
    };
  }
  if (engagementRate >= 5) {
    return {
      label: "可建联",
      detail: `互动 ${engagementRate.toFixed(1)}%`,
      variant: "default" as const,
    };
  }
  if (engagementRate >= 3) {
    return {
      label: "需复核",
      detail: `互动 ${engagementRate.toFixed(1)}%`,
      variant: "secondary" as const,
    };
  }
  return {
    label: "先冷藏",
    detail: `互动 ${engagementRate.toFixed(1)}%`,
    variant: "destructive" as const,
  };
}

function TableSkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i}>
          <td><Skeleton className="h-4 w-28" /></td>
          <td><Skeleton className="h-4 w-36" /></td>
          <td><Skeleton className="h-4 w-24" /></td>
          <td><Skeleton className="h-5 w-20 rounded-full" /></td>
          <td><Skeleton className="h-4 w-14" /></td>
          <td><Skeleton className="h-4 w-20" /></td>
          <td><Skeleton className="h-5 w-16 rounded-full" /></td>
          <td><Skeleton className="h-5 w-20 rounded-full" /></td>
          <td><Skeleton className="h-5 w-14 rounded-full" /></td>
          <td><Skeleton className="h-4 w-20" /></td>
          <td><Skeleton className="h-6 w-14 rounded" /></td>
        </tr>
      ))}
    </>
  );
}

function GridSkeletonCards() {
  return (
    <>
      {Array.from({ length: 12 }).map((_, i) => (
        <Card key={i} className="flex flex-col gap-3 p-4">
          <div className="flex items-start gap-3">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-1.5">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-44" />
            </div>
            <Skeleton className="h-5 w-14 rounded-full" />
          </div>
          <div className="flex gap-1.5">
            <Skeleton className="h-5 w-24 rounded-full" />
            <Skeleton className="h-5 w-20 rounded-full" />
          </div>
          <div className="flex gap-4">
            <div className="space-y-1">
              <Skeleton className="h-3 w-8" />
              <Skeleton className="h-4 w-12" />
            </div>
            <div className="space-y-1">
              <Skeleton className="h-3 w-10" />
              <Skeleton className="h-4 w-10" />
            </div>
          </div>
        </Card>
      ))}
    </>
  );
}

export default function InfluencersPage() {
  const [data, setData] = useState<PaginatedResponse<Influencer> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const reqIdRef = useRef(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [nicheFilter, setNicheFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [hasEmailFilter, setHasEmailFilter] = useState("");
  const [digStatusFilter, setDigStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [outreachOpen, setOutreachOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [selected, setSelected] = useState<Influencer | null>(null);
  // id → whether that influencer already has an email (outreach needs an
  // email; batch email extraction is for the ones without).
  const [selectedMap, setSelectedMap] = useState<Record<string, boolean>>({});
  const selectedIds = Object.keys(selectedMap);
  const selectedEmailIds = selectedIds.filter((id) => selectedMap[id]);
  const [digJob, setDigJob] = useState<EmailDigJob | null>(null);
  const [digStarting, setDigStarting] = useState(false);
  const digTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [startAfterEnroll, setStartAfterEnroll] = useState(false);
  const [form, setForm] = useState<InfluencerFormState>(EMPTY_FORM);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchInfluencers = useCallback(async () => {
    const reqId = ++reqIdRef.current;
    setLoading(true);
    const params: Record<string, string | number> = { page, per_page: viewMode === "grid" ? 24 : 20 };
    if (debouncedSearch) params.search = debouncedSearch;
    if (statusFilter) params.status = statusFilter;
    if (nicheFilter) params.niche = nicheFilter;
    if (sourceFilter) params.source = sourceFilter;
    if (hasEmailFilter) params.has_email = hasEmailFilter;
    if (digStatusFilter) params.dig_status = digStatusFilter;

    try {
      const res = await api.get("/influencers", { params });
      if (reqId === reqIdRef.current) setData(res.data);
    } catch {
      if (reqId === reqIdRef.current) setErrorMsg("达人列表加载失败，请稍后重试");
    } finally {
      // Only the latest in-flight request may clear the spinner / apply results,
      // so a slow earlier response can't overwrite a newer one.
      if (reqId === reqIdRef.current) setLoading(false);
    }
  }, [page, debouncedSearch, statusFilter, nicheFilter, sourceFilter, hasEmailFilter, digStatusFilter, viewMode]);

  useEffect(() => {
    fetchInfluencers();
  }, [fetchInfluencers]);

  // A new (debounced) search term resets to the first page of results.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  useEffect(() => {
    api
      .get<Campaign[]>("/campaigns")
      .then((res) => {
        const eligible = res.data.filter((campaign) =>
          campaign.status === "draft" || campaign.status === "paused"
        );
        setCampaigns(eligible);
        setSelectedCampaignId((current) => current || eligible[0]?.id || "");
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const source = params.get("source");
    if (source) {
      setSourceFilter(source);
      setPage(1);
    }
  }, []);

  const updateForm = (patch: Partial<InfluencerFormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const openCreate = () => {
    setSelected(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (influencer: Influencer) => {
    setSelected(influencer);
    setForm({
      name: influencer.name,
      email: influencer.email ?? "",
      niche: influencer.niche ?? "",
      notes: influencer.notes ?? "",
      platform: influencer.platforms[0]?.platform ?? "",
      username: influencer.platforms[0]?.username ?? "",
      followers: influencer.platforms[0]?.followers?.toString() ?? "",
      engagement_rate: influencer.platforms[0]?.engagement_rate?.toString() ?? "",
    });
    setDialogOpen(true);
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setErrorMsg(null);

    const name = file.name.toLowerCase();
    if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) {
      setErrorMsg("导入仅支持 CSV 或 Excel(.xlsx)，请另存为其中一种格式");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/influencers/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const importErrors: string[] = res.data.errors ?? [];
      setErrorMsg(
        `导入完成：${res.data.imported} 成功，${res.data.skipped} 跳过` +
          (importErrors.length ? `。原因示例：${importErrors.slice(0, 2).join("；")}` : ""),
      );
      await fetchInfluencers();
      const noEmailIds: string[] = res.data.imported_without_email_ids ?? [];
      if (
        noEmailIds.length > 0 &&
        confirm(`本次导入有 ${noEmailIds.length} 位达人没有邮箱，是否立即为他们批量提取邮箱？`)
      ) {
        await startEmailDig(noEmailIds);
      }
    } catch {
      setErrorMsg("导入失败，请确认文件格式正确");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDownloadTemplate = () => {
    // Canonical import template; other headers (creator-finder exports,
    // Chinese headers) are auto-mapped by the backend, this is the safe format.
    const csv = [
      "name,email,niche,country,platform,username,followers,engagement_rate,avg_views,profile_url",
      "Jane Creator,jane@example.com,beauty,US,tiktok,janeugc,12000,3.5,800,https://www.tiktok.com/@janeugc",
    ].join("\n");
    const url = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "influencer-import-template.csv";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  const handleExport = async (fmt: "csv" | "xlsx") => {
    try {
      await downloadExport(
        "/influencers/export",
        {
          format: fmt,
          search: search || undefined,
          status: statusFilter || undefined,
          niche: nicheFilter || undefined,
          source: sourceFilter || undefined,
        },
        `influencers.${fmt}`,
      );
    } catch {
      setErrorMsg("导出失败，请稍后重试");
    }
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      setErrorMsg("请填写达人姓名");
      return;
    }
    setSaving(true);
    setErrorMsg(null);
    const payload = {
      name: form.name.trim(),
      email: form.email.trim() || null,
      niche: form.niche.trim() || null,
      notes: form.notes.trim() || null,
      platforms:
        form.platform && form.username
          ? [
              {
                platform: form.platform,
                username: form.username.trim(),
                data_provider: selected?.platforms[0]?.data_provider ?? null,
                external_id: selected?.platforms[0]?.external_id ?? null,
                followers: form.followers.trim() ? Number(form.followers) : null,
                engagement_rate: form.engagement_rate.trim()
                  ? Number(form.engagement_rate)
                  : null,
              },
            ]
          : [],
    };
    try {
      if (selected) {
        await api.put(`/influencers/${selected.id}`, payload);
      } else {
        await api.post("/influencers", payload);
      }
      setDialogOpen(false);
      setSelected(null);
      setForm(EMPTY_FORM);
      await fetchInfluencers();
    } catch {
      setErrorMsg(selected ? "更新达人失败" : "添加达人失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (influencer: Influencer) => {
    if (!confirm(`确定删除达人 ${influencer.name} 吗？`)) return;
    try {
      await api.delete(`/influencers/${influencer.id}`);
      await fetchInfluencers();
    } catch {
      setErrorMsg("删除达人失败");
    }
  };

  const toggleSelected = (influencer: Influencer) => {
    setSelectedMap((current) => {
      const next = { ...current };
      if (influencer.id in next) {
        delete next[influencer.id];
      } else {
        next[influencer.id] = Boolean(influencer.email);
      }
      return next;
    });
  };

  const togglePageSelected = () => {
    if (!data) return;
    const pageIds = data.items.map((item) => item.id);
    const allSelected =
      pageIds.length > 0 && pageIds.every((id) => id in selectedMap);
    setSelectedMap((current) => {
      const next = { ...current };
      if (allSelected) {
        for (const id of pageIds) delete next[id];
      } else {
        for (const item of data.items) next[item.id] = Boolean(item.email);
      }
      return next;
    });
  };

  const handleOutreach = async () => {
    if (!selectedCampaignId || selectedEmailIds.length === 0) return;
    setEnrolling(true);
    setErrorMsg(null);
    try {
      const res = await api.post(`/campaigns/${selectedCampaignId}/enroll`, {
        influencer_ids: selectedEmailIds,
      });
      if (startAfterEnroll) {
        await api.post(`/campaigns/${selectedCampaignId}/start`);
      }
      setErrorMsg(`已加入外联：${res.data.enrolled} 位达人`);
      setSelectedMap({});
      setOutreachOpen(false);
    } catch {
      setErrorMsg("发起外联失败，请确认活动仍处于草稿或暂停状态");
    } finally {
      setEnrolling(false);
    }
  };

  const pollDigJob = useCallback((jobId: string) => {
    if (digTimerRef.current) clearTimeout(digTimerRef.current);
    digTimerRef.current = setTimeout(async () => {
      try {
        const res = await api.get<EmailDigJob>(`/discovery/email-dig/${jobId}`);
        setDigJob(res.data);
        if (res.data.status === "completed" || res.data.status === "failed") {
          await fetchInfluencers();
          // Selection stays visible during the run so the user can see which
          // rows are being processed; only a successful run clears it.
          if (res.data.status === "completed") setSelectedMap({});
        } else {
          pollDigJob(jobId);
        }
      } catch {
        pollDigJob(jobId);
      }
    }, 3000);
  }, [fetchInfluencers]);

  useEffect(() => {
    return () => {
      if (digTimerRef.current) clearTimeout(digTimerRef.current);
    };
  }, []);

  const startEmailDig = async (influencerIds: string[]) => {
    if (influencerIds.length === 0) return;
    setDigStarting(true);
    setErrorMsg(null);
    try {
      const res = await api.post<EmailDigJob>("/discovery/email-dig", {
        influencer_ids: influencerIds,
      });
      setDigJob(res.data);
      pollDigJob(res.data.id);
    } catch {
      setErrorMsg("批量提取邮箱任务创建失败，请稍后重试");
    } finally {
      setDigStarting(false);
    }
  };

  const startWotoBackfill = async (influencerIds: string[]) => {
    if (influencerIds.length === 0) return;
    if (
      !confirm(
        `将通过 Woto 付费接口为 ${influencerIds.length} 位达人补充邮箱/电话。\n` +
          "每位达人消耗：1 次搜索（已关联 Woto 的达人免搜索）+ 命中邮箱时 1 次联系方式解锁。\n" +
          "只回填空邮箱/电话，不覆盖已有数据。确定继续？",
      )
    ) {
      return;
    }
    setDigStarting(true);
    setErrorMsg(null);
    try {
      const res = await api.post<EmailDigJob>("/influencers/woto-backfill", {
        influencer_ids: influencerIds,
      });
      setDigJob(res.data);
      pollDigJob(res.data.id);
    } catch {
      setErrorMsg("Woto 补充任务创建失败，请确认已配置 Woto 密钥后重试");
    } finally {
      setDigStarting(false);
    }
  };

  return (
    <AppLayout>
      <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Header */}
        <div className="ds-between" style={{ marginBottom: 4 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>资产 · 全网达人池</div>
            <h1 className="ds-h1">达人管理</h1>
            <p className="ds-body" style={{ marginTop: 4, color: "var(--ink-3)" }}>
              共 <b className="ds-primary ds-num">{data?.total ?? 0}</b> 位达人 · 支持手动维护、CSV 批量导入和 SOP 初筛
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
            {errorMsg && <p style={{ fontSize: 12, color: "var(--destructive)", maxWidth: 280, textAlign: "right" }}>{errorMsg}</p>}
            <div className="ds-row" style={{ gap: 8 }}>
              <input ref={fileInputRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={handleImport} />
              <button className="ds-btn ds-btn-outline ds-btn-sm" onClick={() => handleExport("csv")}>
                <Download className="h-[14px] w-[14px]" />导出 CSV
              </button>
              <button className="ds-btn ds-btn-outline ds-btn-sm" onClick={() => handleExport("xlsx")}>
                <Download className="h-[14px] w-[14px]" />导出 Excel
              </button>
              <button className="ds-btn ds-btn-outline ds-btn-sm" onClick={handleDownloadTemplate}>
                <FileDown className="h-[14px] w-[14px]" />下载模板
              </button>
              <button className="ds-btn ds-btn-outline ds-btn-sm" onClick={() => fileInputRef.current?.click()}>
                <Upload className="h-[14px] w-[14px]" />导入 CSV/Excel
              </button>
              <button className="ds-btn ds-btn-primary ds-btn-sm" onClick={openCreate}>
                <Plus className="h-[14px] w-[14px]" />添加达人
              </button>
            </div>
          </div>
        </div>

        {/* Niche quick-filter chips */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          <button onClick={() => { setNicheFilter(""); setPage(1); }} className={`ds-chip ${nicheFilter === "" ? "active" : ""}`}>全部类目</button>
          {SUPPLEMENT_NICHES.map((niche) => (
            <button key={niche.value} onClick={() => { setNicheFilter(niche.value); setPage(1); }} className={`ds-chip ${nicheFilter === niche.value ? "active" : ""}`}>
              {niche.label}
            </button>
          ))}
        </div>

        {/* Filters + view toggle */}
        <div className="ds-card ds-card-pad-sm">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索达人名称或邮箱..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select
              value={statusFilter || "all"}
              onValueChange={(v) => { setStatusFilter(!v || v === "all" ? "" : v); setPage(1); }}
            >
              <SelectTrigger className="w-full md:w-40">
                <SelectValue placeholder="状态筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="new">新建</SelectItem>
                <SelectItem value="contacted">已联系</SelectItem>
                <SelectItem value="replied">已回复</SelectItem>
                <SelectItem value="negotiating">谈判中</SelectItem>
                <SelectItem value="signed">已签约</SelectItem>
                <SelectItem value="rejected">已拒绝</SelectItem>
                <SelectItem value="blacklisted">黑名单</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={sourceFilter || "all"}
              onValueChange={(v) => { setSourceFilter(!v || v === "all" ? "" : v); setPage(1); }}
            >
              <SelectTrigger className="w-full md:w-36">
                <SelectValue placeholder="来源" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部来源</SelectItem>
                <SelectItem value="woto">Woto</SelectItem>
                <SelectItem value="manual">手动</SelectItem>
                <SelectItem value="csv_import">CSV</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={hasEmailFilter || "all"}
              onValueChange={(v) => { setHasEmailFilter(!v || v === "all" ? "" : v); setPage(1); }}
            >
              <SelectTrigger className="w-full md:w-36">
                <SelectValue placeholder="邮箱" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部邮箱</SelectItem>
                <SelectItem value="true">有邮箱</SelectItem>
                <SelectItem value="false">缺邮箱</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={digStatusFilter || "all"}
              onValueChange={(v) => { setDigStatusFilter(!v || v === "all" ? "" : v); setPage(1); }}
            >
              <SelectTrigger className="w-full md:w-40">
                <SelectValue placeholder="提取状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部提取状态</SelectItem>
                <SelectItem value="none">未提取过</SelectItem>
                <SelectItem value="found">提取到联系方式</SelectItem>
                <SelectItem value="no-email">已提取·未找到</SelectItem>
                <SelectItem value="unreachable">已提取·未触达</SelectItem>
              </SelectContent>
            </Select>

            {/* View toggle */}
            <div className="flex rounded-md border">
              <button
                onClick={() => setViewMode("table")}
                className={`rounded-l-md px-3 py-2 transition-colors ${
                  viewMode === "table"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
                aria-label="列表视图"
              >
                <List className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode("grid")}
                className={`rounded-r-md border-l px-3 py-2 transition-colors ${
                  viewMode === "grid"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
                aria-label="网格视图"
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Results count */}
        {data && (
          <p className="text-sm text-muted-foreground">
            共找到 <span className="font-semibold text-foreground">{data.total}</span> 位达人
            {nicheFilter && (
              <> · 当前类目：<span className="font-medium text-foreground">
                {SUPPLEMENT_NICHES.find((n) => n.value === nicheFilter)?.label ?? nicheFilter}
              </span></>
            )}
          </p>
        )}

        {selectedIds.length > 0 && (
          <div className="ds-card ds-card-pad-sm ds-between">
            <div className="ds-body">
              已选择 <span className="ds-primary">{selectedIds.length}</span> 位达人
              （{selectedEmailIds.length} 位有邮箱）
            </div>
            <div className="ds-row" style={{ gap: 8 }}>
              <button className="ds-btn ds-btn-outline ds-btn-sm" onClick={() => setSelectedMap({})}>清空选择</button>
              <button
                className="ds-btn ds-btn-outline ds-btn-sm"
                disabled={digStarting || (digJob !== null && (digJob.status === "queued" || digJob.status === "running"))}
                onClick={() => startEmailDig(selectedIds)}
                title="从公开主页挖掘邮箱，只回填空邮箱，不覆盖已有邮箱"
              >
                {digStarting ? (
                  <Loader2 className="h-[14px] w-[14px] animate-spin" />
                ) : (
                  <AtSign className="h-[14px] w-[14px]" />
                )}
                批量提取邮箱
              </button>
              <button
                className="ds-btn ds-btn-outline ds-btn-sm"
                disabled={digStarting || (digJob !== null && (digJob.status === "queued" || digJob.status === "running"))}
                onClick={() => startWotoBackfill(selectedIds)}
                title="用 Woto 付费数据库补充公开主页找不到的邮箱/电话（只填空，不覆盖）"
              >
                <Database className="h-[14px] w-[14px]" />Woto 补邮箱/电话
              </button>
              <button
                className="ds-btn ds-btn-primary ds-btn-sm"
                disabled={selectedEmailIds.length === 0}
                onClick={() => setOutreachOpen(true)}
                title={
                  selectedEmailIds.length === 0
                    ? "所选达人都没有邮箱，无法发起外联。请先批量提取或用 Woto 补邮箱"
                    : `为 ${selectedEmailIds.length} 位有邮箱达人发起外联`
                }
              >
                <MailPlus className="h-[14px] w-[14px]" />发起外联
                {selectedEmailIds.length > 0 && ` (${selectedEmailIds.length})`}
              </button>
            </div>
          </div>
        )}

        {digJob && (
          <div className="ds-card ds-card-pad-sm ds-between">
            <div className="ds-body">
              {(() => {
                const label = digJob.mode === "woto" ? "Woto 补充" : "提取";
                if (digJob.status === "completed") {
                  return (
                    <>
                      {label}完成：邮箱 <span className="ds-primary">{digJob.found_count}</span> 个
                      · 电话 <span className="ds-primary">{digJob.phone_found_count}</span> 个
                      · 回填 <span className="ds-primary">{digJob.updated_count}</span> 位
                      {digJob.created_count > 0 && <> · 新建 {digJob.created_count} 位</>}
                      {digJob.found_count === 0 && digJob.phone_found_count === 0 && (
                        <> · 未找到的已在表格标记，不必重复{digJob.mode === "woto" ? "补充" : "提取"}</>
                      )}
                    </>
                  );
                }
                if (digJob.status === "failed") {
                  return <>{label}失败：{digJob.error_message || "未知错误"}</>;
                }
                return (
                  <>
                    <Loader2 className="mr-1.5 inline h-[14px] w-[14px] animate-spin" />
                    {digJob.mode === "woto" ? "正在通过 Woto 补充邮箱/电话" : "正在提取邮箱/电话"}：
                    {digJob.processed_count}/{digJob.input_count}
                    {digJob.found_count > 0 && <> · 已找到 {digJob.found_count}</>}
                  </>
                );
              })()}
            </div>
            {(digJob.status === "completed" || digJob.status === "failed") && (
              <button
                className="ds-btn ds-btn-outline ds-btn-sm"
                onClick={() => setDigJob(null)}
                aria-label="关闭提取结果"
              >
                <X className="h-[14px] w-[14px]" />
              </button>
            )}
          </div>
        )}

        {/* Grid view */}
        {viewMode === "grid" && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {loading ? (
              <GridSkeletonCards />
            ) : !data || data.items.length === 0 ? (
              <div className="col-span-full py-16 text-center text-muted-foreground">
                暂无达人数据，点击&quot;添加达人&quot;或&quot;导入&quot;开始。
              </div>
            ) : (
              data.items.map((influencer) => (
                <InfluencerCard
                  key={influencer.id}
                  influencer={influencer}
                  onEdit={openEdit}
                  onDelete={handleDelete}
                />
              ))
            )}
          </div>
        )}

        {/* Table view */}
        {viewMode === "table" && (
          <div className="ds-card" style={{ overflow: "hidden" }}>
            <table className="ds-table">
              <thead>
                <tr>
                  <th className="w-10">
                    <input
                      type="checkbox"
                      checked={
                        !!data?.items.length &&
                        data.items.every((item) => item.id in selectedMap)
                      }
                      onChange={togglePageSelected}
                      aria-label="选择当前页达人"
                    />
                  </th>
                  <th>达人</th>
                  <th>邮箱</th>
                  <th>电话/WhatsApp</th>
                  <th>平台</th>
                  <th>粉丝</th>
                  <th>层级</th>
                  <th>SOP建议</th>
                  <th>来源</th>
                  <th>领域</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <TableSkeletonRows />
                ) : !data || data.items.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="py-12 text-center text-muted-foreground">
                      暂无达人数据，点击&quot;添加达人&quot;或&quot;导入&quot;开始。
                    </td>
                  </tr>
                ) : (
                  data.items.map((influencer) => {
                    const firstPlatform = influencer.platforms[0];
                    const tier = firstPlatform ? getFollowerTier(firstPlatform.followers) : null;
                    const sopRecommendation = getSopRecommendation(firstPlatform);
                    return (
                      <tr key={influencer.id} className="group">
                        <td>
                          <input
                            type="checkbox"
                            checked={influencer.id in selectedMap}
                            onChange={() => toggleSelected(influencer)}
                            aria-label={`选择 ${influencer.name}`}
                          />
                        </td>
                        <td>
                          <Link
                            href={`/influencers/${influencer.id}`}
                            className="font-medium hover:underline"
                          >
                            {influencer.name}
                          </Link>
                        </td>
                        <td className="text-sm text-muted-foreground">
                          {influencer.email ? (
                            <>
                              {influencer.email}
                              <SourceTag source={influencer.email_source} />
                            </>
                          ) : (
                            <DigOutcome influencer={influencer} />
                          )}
                        </td>
                        <td className="text-sm text-muted-foreground">
                          {influencer.phone ? (
                            <>
                              {influencer.phone}
                              <SourceTag source={influencer.phone_source} />
                            </>
                          ) : (
                            <DigOutcome influencer={influencer} />
                          )}
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-1">
                            {influencer.platforms.length === 0 ? (
                              <span className="text-muted-foreground">–</span>
                            ) : (
                              influencer.platforms.map((p) => (
                                <Badge key={p.id} variant="outline" className="text-xs">
                                  {PLATFORM_LABELS[p.platform] || p.platform}
                                </Badge>
                              ))
                            )}
                          </div>
                        </td>
                        <td className="font-medium">
                          {firstPlatform ? formatFollowers(firstPlatform.followers) : "–"}
                        </td>
                        <td>
                          {tier ? (
                            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tier.color}`}>
                              {tier.label}
                            </span>
                          ) : "–"}
                        </td>
                        <td>
                          <div className="space-y-1">
                            <Badge variant={sopRecommendation.variant}>
                              {sopRecommendation.label}
                            </Badge>
                            <div className="text-xs text-muted-foreground">
                              {sopRecommendation.detail}
                            </div>
                          </div>
                        </td>
                        <td>
                          <div className="flex flex-col gap-1">
                            <Badge
                              variant={influencer.source === "woto" ? "default" : "outline"}
                              className="w-fit text-xs"
                            >
                              {influencer.source === "woto"
                                ? "Woto"
                                : influencer.source || "manual"}
                            </Badge>
                            {firstPlatform?.last_synced_at && (
                              <span className="text-xs text-muted-foreground">
                                {new Date(firstPlatform.last_synced_at).toLocaleDateString("zh-CN")}
                              </span>
                            )}
                            {firstPlatform?.external_id && (
                              <span className="max-w-[100px] truncate font-mono text-[10px] text-muted-foreground">
                                {firstPlatform.external_id}
                              </span>
                            )}
                          </div>
                        </td>
                        <td>
                          <NicheCell niche={influencer.niche} />
                        </td>
                        <td>
                          <Badge
                            variant={
                              INFLUENCER_STATUS_MAP[influencer.status]?.variant || "secondary"
                            }
                          >
                            {INFLUENCER_STATUS_MAP[influencer.status]?.label || influencer.status}
                          </Badge>
                        </td>
                        <td>
                          <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEdit(influencer)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(influencer)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>

            {data && data.pages > 1 && (
              <div className="flex items-center justify-between border-t px-4 py-3">
                <span className="text-sm text-muted-foreground">
                  共 {data.total} 条，第 {data.page}/{data.pages} 页
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    上一页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= data.pages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Grid pagination */}
        {viewMode === "grid" && data && data.pages > 1 && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              共 {data.total} 条，第 {data.page}/{data.pages} 页
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                下一页
              </Button>
            </div>
          </div>
        )}

        {/* Add / Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{selected ? "编辑达人" : "添加达人"}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[75vh] overflow-y-auto space-y-4 pr-1">
              <div>
                <Label>姓名 *</Label>
                <Input
                  value={form.name}
                  onChange={(e) => updateForm({ name: e.target.value })}
                  placeholder="达人真实姓名或账号名"
                />
              </div>
              <div>
                <Label>邮箱</Label>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => updateForm({ email: e.target.value })}
                />
              </div>
              <div>
                <Label>领域</Label>
                <select
                  value={form.niche}
                  onChange={(e) => updateForm({ niche: e.target.value })}
                  className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                >
                  <option value="">选择领域</option>
                  {SUPPLEMENT_NICHES.map((n) => (
                    <option key={n.value} value={n.value}>
                      {n.label}
                    </option>
                  ))}
                  <option value="other">其他</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>平台</Label>
                  <select
                    value={form.platform}
                    onChange={(e) => updateForm({ platform: e.target.value })}
                    className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                  >
                    <option value="">选择平台</option>
                    <option value="tiktok">TikTok</option>
                    <option value="instagram">Instagram</option>
                    <option value="youtube">YouTube</option>
                  </select>
                </div>
                <div>
                  <Label>用户名</Label>
                  <Input
                    value={form.username}
                    onChange={(e) => updateForm({ username: e.target.value })}
                    placeholder="@username"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>粉丝数</Label>
                  <Input
                    type="number"
                    value={form.followers}
                    onChange={(e) => updateForm({ followers: e.target.value })}
                    placeholder="12000"
                  />
                </div>
                <div>
                  <Label>互动率 %</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={form.engagement_rate}
                    onChange={(e) => updateForm({ engagement_rate: e.target.value })}
                    placeholder="5.8"
                  />
                </div>
              </div>
              <div>
                <Label>备注</Label>
                <Textarea
                  value={form.notes}
                  onChange={(e) => updateForm({ notes: e.target.value })}
                  rows={3}
                />
              </div>
              <Button onClick={handleSave} className="w-full" disabled={saving}>
                {saving ? "保存中..." : selected ? "保存修改" : "创建达人"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={outreachOpen} onOpenChange={setOutreachOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>发起外联</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>选择活动</Label>
                <Select
                  value={selectedCampaignId}
                  onValueChange={(v) => v && setSelectedCampaignId(v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择草稿或暂停活动" />
                  </SelectTrigger>
                  <SelectContent>
                    {campaigns.map((campaign) => (
                      <SelectItem key={campaign.id} value={campaign.id}>
                        {campaign.name} · {campaign.status === "draft" ? "草稿" : "暂停"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={startAfterEnroll}
                  onChange={(e) => setStartAfterEnroll(e.target.checked)}
                />
                加入后立即启动活动
              </label>
              <Button
                className="w-full"
                disabled={!selectedCampaignId || enrolling || campaigns.length === 0}
                onClick={handleOutreach}
              >
                {enrolling && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                加入 {selectedEmailIds.length} 位有邮箱达人
              </Button>
              {campaigns.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  暂无可加入的草稿或暂停活动，请先创建活动。
                </p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
