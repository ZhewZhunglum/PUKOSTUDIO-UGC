"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
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
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";
import { SUPPLEMENT_NICHES, getFollowerTier } from "@/lib/constants";
import type { EmailTemplate, Influencer, PaginatedResponse } from "@/types";
import { ArrowLeft, CheckSquare, Search, Square } from "lucide-react";

function formatFollowers(n: number | null | undefined): string {
  if (!n) return "";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

export default function NewCampaignPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [nicheFilter, setNicheFilter] = useState("");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [campaignType, setCampaignType] = useState("ugc");
  const [templateId, setTemplateId] = useState("");
  const [selectedInfluencerIds, setSelectedInfluencerIds] = useState<string[]>([]);

  useEffect(() => {
    Promise.all([
      api.get("/templates"),
      api.get<PaginatedResponse<Influencer>>("/influencers", {
        params: { page: 1, per_page: 500 },
      }),
    ])
      .then(([templatesRes, infRes]) => {
        setTemplates(templatesRes.data);
        setInfluencers(infRes.data.items);
      })
      .catch(() => setError("加载模板或达人列表失败"));
  }, []);

  const filteredInfluencers = useMemo(() => {
    let list = influencers;
    if (nicheFilter) {
      list = list.filter((i) => i.niche === nicheFilter);
    }
    if (search.trim()) {
      const kw = search.trim().toLowerCase();
      list = list.filter(
        (i) =>
          i.name.toLowerCase().includes(kw) ||
          i.email?.toLowerCase().includes(kw) ||
          i.platforms.some((p) => p.username.toLowerCase().includes(kw))
      );
    }
    return list;
  }, [influencers, search, nicheFilter]);

  const toggleInfluencer = (id: string) => {
    setSelectedInfluencerIds((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]
    );
  };

  const selectAll = () => {
    const ids = filteredInfluencers.map((i) => i.id);
    setSelectedInfluencerIds((cur) => [...new Set([...cur, ...ids])]);
  };

  const deselectAll = () => {
    const ids = new Set(filteredInfluencers.map((i) => i.id));
    setSelectedInfluencerIds((cur) => cur.filter((id) => !ids.has(id)));
  };

  const handleCreate = async () => {
    if (!name || !templateId) {
      setError("请填写活动名称并选择首封模板");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const campaignRes = await api.post("/campaigns", {
        name,
        description: description || null,
        campaign_type: campaignType,
        steps: [
          { step_order: 1, step_type: "initial", template_id: templateId, delay_days: 0 },
        ],
      });
      if (selectedInfluencerIds.length > 0) {
        await api.post(`/campaigns/${campaignRes.data.id}/enroll`, {
          influencer_ids: selectedInfluencerIds,
        });
      }
      router.push(`/campaigns/${campaignRes.data.id}`);
    } catch {
      setError("创建活动失败");
    } finally {
      setLoading(false);
    }
  };

  const stepLabels = ["基本信息", "首封模板", "入组达人"];

  return (
    <AppLayout>
      <div className="mx-auto max-w-5xl space-y-6 fade-in">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push("/campaigns")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回
          </Button>
          <div>
            <h2 className="text-2xl font-bold">创建外联活动</h2>
            <p className="text-sm text-muted-foreground">共 3 步完成活动配置</p>
          </div>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2">
          {stepLabels.map((label, i) => {
            const n = i + 1;
            const active = step === n;
            const done = step > n;
            return (
              <div key={n} className="flex items-center gap-2">
                <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                  done ? "bg-green-600 text-white" :
                  active ? "bg-primary text-primary-foreground" :
                  "bg-muted text-muted-foreground"
                }`}>
                  {done ? "✓" : n}
                </div>
                <span className={`text-sm font-medium ${active ? "text-foreground" : "text-muted-foreground"}`}>
                  {label}
                </span>
                {i < stepLabels.length - 1 && (
                  <div className="mx-1 h-px w-8 bg-border" />
                )}
              </div>
            );
          })}
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {/* Step 1: Basic info */}
        {step === 1 && (
          <Card className="space-y-5 p-6">
            <h3 className="text-lg font-semibold">基本信息</h3>
            <div>
              <Label>活动名称 *</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="如：Supplement Collagen UGC – Q2 2026"
                className="mt-1.5"
              />
            </div>
            <div>
              <Label>活动类型</Label>
              <Select value={campaignType} onValueChange={(v) => v && setCampaignType(v)}>
                <SelectTrigger className="mt-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ugc">UGC 内容合作</SelectItem>
                  <SelectItem value="brand_promo">品牌推广合作</SelectItem>
                  <SelectItem value="tiktok_shop">TikTok Shop 带货</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>活动描述</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="说明这次外联的目标、产品和合作方式..."
                rows={4}
                className="mt-1.5"
              />
            </div>
            <Button onClick={() => setStep(2)} disabled={!name.trim()}>
              下一步：选择首封模板
            </Button>
          </Card>
        )}

        {/* Step 2: Template */}
        {step === 2 && (
          <Card className="space-y-4 p-6">
            <h3 className="text-lg font-semibold">选择首封邮件模板</h3>
            {templates.length === 0 ? (
              <div className="rounded-lg border border-dashed p-8 text-center">
                <p className="text-sm text-muted-foreground">暂无模板，请先创建模板。</p>
                <Button variant="outline" className="mt-4" onClick={() => router.push("/templates")}>
                  去模板中心
                </Button>
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {templates.map((tmpl) => (
                  <button
                    key={tmpl.id}
                    onClick={() => setTemplateId(tmpl.id)}
                    className={`rounded-xl border p-4 text-left transition-colors ${
                      templateId === tmpl.id
                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                        : "hover:border-muted-foreground/40"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-medium">{tmpl.name}</div>
                      <Badge variant="outline" className="shrink-0 text-xs">
                        {tmpl.category}
                      </Badge>
                    </div>
                    <div className="mt-1 truncate text-sm text-muted-foreground">
                      {tmpl.subject}
                    </div>
                  </button>
                ))}
              </div>
            )}
            <div className="flex gap-2 pt-2">
              <Button variant="outline" onClick={() => setStep(1)}>上一步</Button>
              <Button onClick={() => setStep(3)} disabled={!templateId}>下一步：入组达人</Button>
            </div>
          </Card>
        )}

        {/* Step 3: Influencer selection */}
        {step === 3 && (
          <Card className="space-y-4 p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-semibold">选择入组达人</h3>
                <p className="text-sm text-muted-foreground">
                  这一步可选。可先创建活动，再到详情页补充达人。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">
                  已选 <span className="text-primary">{selectedInfluencerIds.length}</span> 位
                </span>
                <Button variant="outline" size="sm" onClick={selectAll}>全选当前</Button>
                <Button variant="ghost" size="sm" onClick={deselectAll}>清空</Button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索名称、邮箱或账号..."
                  className="pl-10"
                />
              </div>
              <Select value={nicheFilter || "all"} onValueChange={(v) => setNicheFilter(!v || v === "all" ? "" : v)}>
                <SelectTrigger className="w-full sm:w-48">
                  <SelectValue placeholder="全部类目" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部类目</SelectItem>
                  {SUPPLEMENT_NICHES.map((n) => (
                    <SelectItem key={n.value} value={n.value}>{n.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Influencer list */}
            <div className="max-h-[420px] space-y-2 overflow-y-auto rounded-xl border p-3">
              {filteredInfluencers.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  没有匹配的达人
                </p>
              ) : (
                filteredInfluencers.map((inf) => {
                  const checked = selectedInfluencerIds.includes(inf.id);
                  const firstPlatform = inf.platforms[0];
                  const tier = firstPlatform ? getFollowerTier(firstPlatform.followers) : null;
                  return (
                    <label
                      key={inf.id}
                      className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors ${
                        checked ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                      }`}
                    >
                      <div className="shrink-0 text-muted-foreground">
                        {checked
                          ? <CheckSquare className="h-4 w-4 text-primary" />
                          : <Square className="h-4 w-4" />
                        }
                      </div>
                      <input
                        type="checkbox"
                        className="hidden"
                        checked={checked}
                        onChange={() => toggleInfluencer(inf.id)}
                        readOnly
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{inf.name}</span>
                          {inf.niche && (
                            <Badge variant="outline" className="text-xs capitalize">
                              {inf.niche.replace(/_/g, " ")}
                            </Badge>
                          )}
                        </div>
                        <div className="truncate text-sm text-muted-foreground">
                          {inf.email || "暂无邮箱"}
                          {firstPlatform && (
                            <> · @{firstPlatform.username} · {formatFollowers(firstPlatform.followers)} 粉</>
                          )}
                        </div>
                      </div>
                      {tier && (
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${tier.color}`}>
                          {tier.value.charAt(0).toUpperCase() + tier.value.slice(1)}
                        </span>
                      )}
                    </label>
                  );
                })
              )}
            </div>

            <div className="flex gap-2 pt-2">
              <Button variant="outline" onClick={() => setStep(2)}>上一步</Button>
              <Button onClick={handleCreate} disabled={loading}>
                {loading ? "创建中..." : `创建活动${selectedInfluencerIds.length > 0 ? `（含 ${selectedInfluencerIds.length} 位达人）` : ""}`}
              </Button>
            </div>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
