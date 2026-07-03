"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import api from "@/lib/api";
import { INFLUENCER_STATUS_MAP, SUPPLEMENT_NICHES, getFollowerTier } from "@/lib/constants";
import type { EmailMessage, Influencer, InfluencerPlatform, WotoAudienceItem } from "@/types";
import { ArrowLeft, ExternalLink, Mail, MapPin, Trash2 } from "lucide-react";

function formatFollowers(n: number | null | undefined): string {
  if (!n) return "–";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function DetailSkeleton() {
  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-8 w-16 rounded" />
          <div className="space-y-2">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="p-6">
            <div className="flex flex-col items-center gap-3">
              <Skeleton className="h-20 w-20 rounded-full" />
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-6 w-20 rounded-full" />
            </div>
            <div className="mt-6 space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <Skeleton className="h-3.5 w-16" />
                  <Skeleton className="h-4 w-full" />
                </div>
              ))}
            </div>
          </Card>
          <div className="space-y-6 lg:col-span-2">
            <Card className="p-6">
              <Skeleton className="mb-4 h-5 w-20" />
              <div className="grid gap-4 md:grid-cols-2">
                {[1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
              </div>
            </Card>
            <Card className="p-6">
              <Skeleton className="mb-4 h-5 w-20" />
              <div className="space-y-3">
                {[1, 2].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

export default function InfluencerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const influencerId = String(params.id);
  const [influencer, setInfluencer] = useState<Influencer | null>(null);
  const [emails, setEmails] = useState<EmailMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const loadInfluencer = useCallback(async () => {
    setLoading(true);
    try {
      const [infRes, emailRes] = await Promise.all([
        api.get(`/influencers/${influencerId}`),
        api.get(`/influencers/${influencerId}/emails`).catch(() => ({ data: [] })),
      ]);
      setInfluencer(infRes.data);
      setEmails(emailRes.data);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [influencerId]);

  useEffect(() => {
    if (params.id) void loadInfluencer();
  }, [params.id, loadInfluencer]);

  const handleStatusChange = async (status: string) => {
    if (!influencer) return;
    try {
      const res = await api.put(`/influencers/${influencer.id}`, { status });
      setInfluencer(res.data);
    } catch {
      alert("更新状态失败");
    }
  };

  const handleDelete = async () => {
    if (!influencer || !confirm(`确定删除达人 ${influencer.name} 吗？`)) return;
    try {
      await api.delete(`/influencers/${influencer.id}`);
      router.push("/influencers");
    } catch {
      alert("删除达人失败");
    }
  };

  if (loading) return <DetailSkeleton />;

  if (notFound || !influencer) {
    return (
      <AppLayout>
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <p className="text-destructive">达人不存在或已被删除。</p>
          <Link href="/influencers" className={buttonVariants({ variant: "outline" })}>
            返回达人列表
          </Link>
        </div>
      </AppLayout>
    );
  }

  const nicheName = SUPPLEMENT_NICHES.find((n) => n.value === influencer.niche)?.label
    ?? influencer.niche?.replace(/_/g, " ")
    ?? "–";
  const initials = influencer.name.split(" ").slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");

  return (
    <AppLayout>
      <div className="space-y-6 fade-in">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => router.push("/influencers")}>
              <ArrowLeft className="mr-1 h-4 w-4" />
              返回
            </Button>
            <div>
              <h2 className="text-2xl font-bold">{influencer.name}</h2>
              <p className="text-sm text-muted-foreground">
                来源：<span className="font-medium">{influencer.source || "manual"}</span>
                {influencer.country && (
                  <> · <MapPin className="inline h-3 w-3" /> {influencer.country}</>
                )}
                · 创建于 {new Date(influencer.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
              </p>
            </div>
          </div>
          <Button variant="destructive" size="sm" onClick={handleDelete}>
            <Trash2 className="mr-1.5 h-4 w-4" />
            删除
          </Button>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Profile sidebar */}
          <Card className="space-y-5 p-6 lg:col-span-1">
            {/* Avatar */}
            <div className="flex flex-col items-center gap-3">
              {influencer.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={influencer.avatar_url}
                  alt={influencer.name}
                  className="h-20 w-20 rounded-full object-cover ring-2 ring-border"
                />
              ) : (
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10 text-2xl font-bold text-primary ring-2 ring-border">
                  {initials || "?"}
                </div>
              )}
              <div className="text-center">
                <p className="text-lg font-semibold">{influencer.name}</p>
                {influencer.email && (
                  <p className="flex items-center justify-center gap-1 text-sm text-muted-foreground">
                    <Mail className="h-3 w-3" />
                    {influencer.email}
                  </p>
                )}
              </div>
              <Badge variant={INFLUENCER_STATUS_MAP[influencer.status]?.variant ?? "secondary"}>
                {INFLUENCER_STATUS_MAP[influencer.status]?.label ?? influencer.status}
              </Badge>
            </div>

            <div className="border-t pt-4">
              <LabelText>更新状态</LabelText>
              <Select value={influencer.status} onValueChange={(v) => v && handleStatusChange(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">新建</SelectItem>
                  <SelectItem value="contacted">已联系</SelectItem>
                  <SelectItem value="replied">已回复</SelectItem>
                  <SelectItem value="negotiating">谈判中</SelectItem>
                  <SelectItem value="signed">已签约</SelectItem>
                  <SelectItem value="rejected">已拒绝</SelectItem>
                  <SelectItem value="blacklisted">黑名单</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <LabelText>细分领域</LabelText>
              <p className="text-sm capitalize">{nicheName}</p>
            </div>

            <div>
              <LabelText>标签</LabelText>
              <div className="flex flex-wrap gap-1">
                {influencer.tags.length === 0 ? (
                  <span className="text-sm text-muted-foreground">暂无标签</span>
                ) : (
                  influencer.tags.map((tag) => (
                    <Badge key={tag.id} variant="outline" style={{ borderColor: tag.color ?? undefined }}>
                      {tag.name}
                    </Badge>
                  ))
                )}
              </div>
            </div>

            {influencer.notes && (
              <div>
                <LabelText>备注</LabelText>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">{influencer.notes}</p>
              </div>
            )}
          </Card>

          {/* Main content */}
          <div className="space-y-6 lg:col-span-2">
            {/* Platforms */}
            <Card className="space-y-4 p-6">
              <h3 className="text-lg font-semibold">社交平台</h3>
              {influencer.platforms.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无平台数据</p>
              ) : (
                <div className="space-y-4">
                  {influencer.platforms.map((platform) => (
                    <PlatformCard key={platform.id} platform={platform} />
                  ))}
                </div>
              )}
            </Card>

            {/* Email history */}
            <Card className="space-y-4 p-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">邮件历史</h3>
                <Badge variant="outline">{emails.length} 封</Badge>
              </div>
              {emails.length === 0 ? (
                <p className="py-4 text-sm text-muted-foreground">还没有邮件记录。</p>
              ) : (
                <div className="space-y-3">
                  {emails.map((email) => (
                    <div key={email.id} className="rounded-xl border p-4 transition-colors hover:bg-muted/30">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-medium">{email.subject}</p>
                          <p className="text-sm text-muted-foreground">
                            {email.direction === "outbound" ? "发出" : "收到"} ·{" "}
                            {new Date(email.created_at).toLocaleString("en-US", {
                              month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                            })}
                          </p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1">
                          <Badge variant={email.direction === "outbound" ? "outline" : "default"} className="text-xs">
                            {email.direction === "outbound" ? "发出" : "收到"}
                          </Badge>
                          <Badge variant="secondary" className="text-xs capitalize">
                            {email.status}
                          </Badge>
                        </div>
                      </div>
                      {(email.body_text || email.body_html) && (
                        <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                          {email.body_text || email.body_html?.replace(/<[^>]+>/g, " ").trim()}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

function LabelText({ children }: { children: React.ReactNode }) {
  return <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{children}</p>;
}

function MetricCell({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <span className="text-xs text-muted-foreground">{label}</span>
      <p className="font-semibold text-sm">{value}</p>
    </div>
  );
}

function DistributionBar({ label, value, pct }: { label: string; value?: string; pct: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 shrink-0 text-muted-foreground truncate">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className="h-full rounded-full bg-primary/70" style={{ width: `${Math.round(pct * 100)}%` }} />
      </div>
      <span className="w-9 text-right font-medium">{value ?? `${Math.round(pct * 100)}%`}</span>
    </div>
  );
}

function AudienceSection({ raw }: { raw: NonNullable<InfluencerPlatform["raw_data"]> }) {
  const hasDemographics = raw.fans_age?.length || raw.fans_sex?.length || raw.fans_region?.length;
  if (!hasDemographics) return null;

  const topAge = [...(raw.fans_age ?? [])].sort((a, b) => b.distributionValue - a.distributionValue).slice(0, 5);
  const topRegion = [...(raw.fans_region ?? [])].sort((a, b) => b.distributionValue - a.distributionValue).slice(0, 5);
  const female = raw.fans_sex?.find((s: WotoAudienceItem) => s.sex === "F")?.distributionValue;
  const male = raw.fans_sex?.find((s: WotoAudienceItem) => s.sex === "M")?.distributionValue;

  return (
    <div className="border-t pt-3 space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">受众画像</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {(female != null || male != null) && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground font-medium">性别</p>
            {female != null && <DistributionBar label="女" pct={female} />}
            {male != null && <DistributionBar label="男" pct={male} />}
          </div>
        )}
        {topAge.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground font-medium">年龄段</p>
            {topAge.map((item: WotoAudienceItem) => (
              <DistributionBar key={item.ageGroup} label={item.ageGroup ?? "–"} pct={item.distributionValue} />
            ))}
          </div>
        )}
        {topRegion.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground font-medium">地区</p>
            {topRegion.map((item: WotoAudienceItem) => (
              <DistributionBar
                key={item.regionCode}
                label={item.regionName ?? item.regionNameEn ?? item.regionCode ?? "–"}
                pct={item.distributionValue}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PlatformCard({ platform }: { platform: InfluencerPlatform }) {
  const tier = getFollowerTier(platform.followers);
  const raw = platform.raw_data;
  const cateNames = platform.content_topics?.cate_names ?? raw?.cate_names ?? [];

  return (
    <Card className="p-4 space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge className="uppercase">{platform.platform}</Badge>
          {raw?.is_tk_union && (
            <Badge variant="secondary" className="text-xs bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300">
              TikTok Union
            </Badge>
          )}
          {raw?.has_amazon_tag && (
            <Badge variant="secondary" className="text-xs bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300">
              Amazon
            </Badge>
          )}
        </div>
        {platform.profile_url && (
          <a
            href={platform.profile_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            访问主页 <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      <p className="font-medium text-sm">@{platform.username}</p>

      {/* Core metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
        <MetricCell label="粉丝数" value={formatFollowers(platform.followers)} />
        <MetricCell
          label="互动率"
          value={platform.engagement_rate ? `${platform.engagement_rate.toFixed(2)}%` : "–"}
        />
        <MetricCell label="均播放" value={platform.avg_views ? formatFollowers(platform.avg_views) : "–"} />
        {tier ? (
          <MetricCell
            label="层级"
            value={
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tier.color}`}>
                {tier.value.charAt(0).toUpperCase() + tier.value.slice(1)}
              </span>
            }
          />
        ) : null}
      </div>

      {raw && (
        <>
          {/* Extended performance metrics */}
          {(raw.view_avg_15d != null || raw.view_avg_30d != null || raw.view_avg_60d != null ||
            raw.interactive_rate_60d != null || raw.interactive_rate_30n_all != null ||
            raw.interactive_rate_90d_post != null || raw.like_avg != null || raw.total_star != null ||
            raw.content_num != null || raw.latest_publish_date || raw.gmv_30d != null || raw.biz_count != null) && (
            <div className="border-t pt-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">详细数据</p>
              <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                {raw.view_avg_15d != null && <MetricCell label="均播 15d" value={formatFollowers(raw.view_avg_15d)} />}
                {raw.view_avg_30d != null && <MetricCell label="均播 30d" value={formatFollowers(raw.view_avg_30d)} />}
                {raw.view_avg_60d != null && <MetricCell label="均播 60d" value={formatFollowers(raw.view_avg_60d)} />}
                {raw.view_avg_15n != null && <MetricCell label="均播 15n" value={formatFollowers(raw.view_avg_15n)} />}
                {raw.view_avg_30n != null && <MetricCell label="均播 30n" value={formatFollowers(raw.view_avg_30n)} />}
                {raw.interactive_rate_60d != null && (
                  <MetricCell label="互动率 60d" value={`${Number(raw.interactive_rate_60d).toFixed(2)}%`} />
                )}
                {raw.interactive_rate_30n_all != null && (
                  <MetricCell label="互动率 30n" value={`${Number(raw.interactive_rate_30n_all).toFixed(2)}%`} />
                )}
                {raw.interactive_rate_90d_post != null && (
                  <MetricCell label="互动率 90d" value={`${Number(raw.interactive_rate_90d_post).toFixed(2)}%`} />
                )}
                {raw.like_avg != null && <MetricCell label="均点赞" value={formatFollowers(raw.like_avg)} />}
                {raw.like_avg_60d != null && <MetricCell label="均点赞 60d" value={formatFollowers(raw.like_avg_60d)} />}
                {raw.total_star != null && <MetricCell label="Woto 评分" value={String(raw.total_star)} />}
                {raw.content_num != null && <MetricCell label="内容数" value={String(raw.content_num)} />}
                {raw.latest_publish_date && (
                  <MetricCell label="最近发布" value={raw.latest_publish_date} />
                )}
                {raw.gmv_30d != null && (
                  <MetricCell label="GMV 30d" value={`¥${Number(raw.gmv_30d).toLocaleString()}`} />
                )}
                {raw.biz_count != null && <MetricCell label="品牌合作数" value={String(raw.biz_count)} />}
              </div>
            </div>
          )}

          {/* Audience demographics */}
          <AudienceSection raw={raw} />
        </>
      )}

      {/* Categories */}
      {cateNames.length > 0 && (
        <div className="border-t pt-3">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">内容分类</p>
          <div className="flex flex-wrap gap-1">
            {cateNames.map((name: string) => (
              <Badge key={name} variant="outline" className="text-xs">
                {name}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Last synced */}
      {platform.last_synced_at && (
        <p className="text-xs text-muted-foreground">
          同步于 {new Date(platform.last_synced_at).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" })}
        </p>
      )}
    </Card>
  );
}
