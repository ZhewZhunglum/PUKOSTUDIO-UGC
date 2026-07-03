"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import api from "@/lib/api";
import type { SOPPlaybook } from "@/types";
import {
  ArrowRight,
  BookOpen,
  Calculator,
  CheckCircle2,
  FileSpreadsheet,
  MailCheck,
  Rocket,
  ShieldCheck,
  Sparkles,
  Target,
  Trophy,
  Users,
} from "lucide-react";

const setupSteps = [
  {
    title: "配置活动 SOP Brief",
    description: "在活动详情里套用 SOP，补齐目标、受众、卖点、报价、审核和合规边界。",
    href: "/campaigns",
    cta: "去活动",
    icon: BookOpen,
  },
  {
    title: "导入达人并初筛",
    description: "CSV 导入达人后，用粉丝量、互动率、平台数据判断是否进入建联池。",
    href: "/influencers",
    cta: "管达人",
    icon: Users,
  },
  {
    title: "准备首封建联模板",
    description: "首封邮件明确产品、合作形式、CTA，并保持具体、自然、不过度承诺。",
    href: "/templates",
    cta: "建模板",
    icon: MailCheck,
  },
  {
    title: "启动活动",
    description: "选择达人入组并启动首封外联，后续回复进入 AI 沟通台待审核。",
    href: "/campaigns/new",
    cta: "建活动",
    icon: Rocket,
  },
  {
    title: "审核 AI 草稿",
    description: "AI 先分类、再引用活动规则生成回复，你确认后才发送。",
    href: "/inbox",
    cta: "看收件箱",
    icon: Sparkles,
  },
];

const csvColumns = [
  { name: "name", required: true, note: "达人名称" },
  { name: "email", required: false, note: "发信需要邮箱，强烈建议填写" },
  { name: "niche", required: false, note: "垂类，例如 beauty、fitness" },
  { name: "country", required: false, note: "国家或地区，例如 US" },
  { name: "platform", required: false, note: "tiktok、instagram、youtube" },
  { name: "username", required: false, note: "平台用户名" },
  { name: "followers", required: false, note: "粉丝数，数字格式" },
  { name: "engagement_rate", required: false, note: "互动率，建议填百分比数字，如 5.8" },
];

const fallbackSop: SOPPlaybook = {
  source_title: "NF工作室-海外达人合作 SOP手册",
  source_updated_at: "2026-04-30",
  operating_principle: "找对博主 -> 说清需求 -> 管好过程 -> 拿到结果",
  modules: [],
  pricing_benchmarks: [],
  platform_guides: [],
  screening_rules: [],
  compliance_rules: [],
  negotiation_scripts: [],
  review_checklist: [],
  performance_metrics: [],
};

export default function GuidePage() {
  const [sop, setSop] = useState<SOPPlaybook>(fallbackSop);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<SOPPlaybook>("/sop/playbook")
      .then((response) => {
        setSop(response.data);
        setLoadError(null);
      })
      .catch(() => {
        setLoadError("SOP 规则接口暂不可用，当前展示基础使用指南。");
      });
  }, []);

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-8">
        <section className="overflow-hidden rounded-3xl border bg-background">
          <div className="relative grid gap-8 p-8 md:p-10 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-emerald-200/50 blur-3xl" />
            <div className="absolute bottom-0 right-24 h-32 w-32 rounded-full bg-amber-200/40 blur-3xl" />
            <div className="relative max-w-3xl space-y-4">
              <Badge variant="outline">SOP 工作台</Badge>
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
                把海外达人合作 SOP 变成系统动作
              </h2>
              <p className="text-base leading-7 text-muted-foreground">
                当前系统已按「{sop.operating_principle}」重组使用路径：先用 SOP 写好活动
                Brief，再筛选达人、启动建联、处理 AI 草稿、跟踪内容和复盘结果。
              </p>
              {loadError && <p className="text-sm text-amber-600">{loadError}</p>}
              <div className="flex flex-wrap gap-3">
                <Link href="/campaigns/new" className={buttonVariants()}>
                  创建活动
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/inbox" className={buttonVariants({ variant: "outline" })}>
                  进入 AI 沟通台
                </Link>
              </div>
            </div>

            <Card className="relative space-y-4 p-6">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                <h3 className="font-semibold">SOP 来源</h3>
              </div>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>{sop.source_title}</p>
                <p>最后更新：{sop.source_updated_at}</p>
                <p>已结构化为规则中心、活动 AI Playbook、达人 SOP 初筛和前端操作指南。</p>
              </div>
            </Card>
          </div>
        </section>

        <section className="space-y-4">
          <div>
            <h3 className="text-xl font-semibold">推荐执行流程</h3>
            <p className="text-sm text-muted-foreground">
              这 5 步对应 SOP 的「Brief -&gt; 筛选 -&gt; 建联 -&gt; 沟通 -&gt; 复盘」主链路。
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {setupSteps.map((step, index) => {
              const Icon = step.icon;
              return (
                <Card key={step.title} className="flex flex-col gap-4 p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-muted">
                      <Icon className="h-5 w-5" />
                    </div>
                    <Badge variant="outline">Step {index + 1}</Badge>
                  </div>
                  <div className="space-y-2">
                    <h4 className="font-semibold">{step.title}</h4>
                    <p className="text-sm leading-6 text-muted-foreground">{step.description}</p>
                  </div>
                  <Link href={step.href} className={cn(buttonVariants({ variant: "outline" }), "mt-auto")}>
                    {step.cta}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Card>
              );
            })}
          </div>
        </section>

        {sop.modules.length > 0 && (
          <section className="space-y-4">
            <div>
              <h3 className="text-xl font-semibold">SOP 模块映射</h3>
              <p className="text-sm text-muted-foreground">
                每个 SOP 模块都对应一个系统区域，避免工作流散落在脑子和表格里。
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {sop.modules.map((module) => (
                <Card key={module.id} className="p-4">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h4 className="font-semibold">{module.title}</h4>
                    <Badge variant="secondary">{module.system_area}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{module.output}</p>
                </Card>
              ))}
            </div>
          </section>
        )}

        <section className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
          <Card className="p-6">
            <div className="mb-4 flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5" />
              <h3 className="text-lg font-semibold">CSV 导入格式</h3>
            </div>
            <div className="overflow-hidden rounded-xl border">
              <table className="w-full text-sm">
                <thead className="bg-muted/60 text-left">
                  <tr>
                    <th className="px-4 py-3 font-medium">字段</th>
                    <th className="px-4 py-3 font-medium">是否必填</th>
                    <th className="px-4 py-3 font-medium">SOP 用途</th>
                  </tr>
                </thead>
                <tbody>
                  {csvColumns.map((column) => (
                    <tr key={column.name} className="border-t">
                      <td className="px-4 py-3 font-mono text-xs">{column.name}</td>
                      <td className="px-4 py-3">
                        {column.required ? (
                          <Badge>必填</Badge>
                        ) : (
                          <Badge variant="outline">可选</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{column.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <pre className="mt-4 overflow-auto rounded-xl bg-muted p-4 text-xs leading-6">
              <code>{`name,email,niche,country,platform,username,followers,engagement_rate
Jane Creator,jane@example.com,beauty,US,tiktok,janeugc,12000,5.8`}</code>
            </pre>
          </Card>

          <div className="space-y-4">
            <Card className="p-6">
              <div className="mb-4 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5" />
                <h3 className="text-lg font-semibold">达人初筛硬规则</h3>
              </div>
              <div className="space-y-3">
                {sop.screening_rules.slice(0, 5).map((rule) => (
                  <div key={rule.title} className="rounded-xl border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="font-medium">{rule.title}</h4>
                      {rule.severity && <Badge variant="outline">{rule.severity}</Badge>}
                    </div>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {rule.description}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </section>

        {sop.pricing_benchmarks.length > 0 && (
          <section className="space-y-4">
            <div className="flex items-center gap-2">
              <Calculator className="h-5 w-5" />
              <h3 className="text-xl font-semibold">报价基准</h3>
            </div>
            <Card className="overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/60 text-left">
                  <tr>
                    <th className="px-4 py-3">层级</th>
                    <th className="px-4 py-3">粉丝</th>
                    <th className="px-4 py-3">TikTok</th>
                    <th className="px-4 py-3">Instagram Reels</th>
                    <th className="px-4 py-3">YouTube</th>
                    <th className="px-4 py-3">建议模式</th>
                  </tr>
                </thead>
                <tbody>
                  {sop.pricing_benchmarks.map((row) => (
                    <tr key={row.tier} className="border-t">
                      <td className="px-4 py-3 font-medium">{row.tier}</td>
                      <td className="px-4 py-3">{row.follower_range}</td>
                      <td className="px-4 py-3">{row.tiktok}</td>
                      <td className="px-4 py-3">{row.instagram_reels}</td>
                      <td className="px-4 py-3">{row.youtube}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {row.collaboration_model}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </section>
        )}

        <section className="grid gap-4 lg:grid-cols-3">
          {sop.platform_guides.map((platform) => (
            <Card key={platform.platform} className="p-6">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-lg font-semibold">{platform.platform}</h3>
                <Badge variant="outline">{platform.best_posting_window_utc}</Badge>
              </div>
              <div className="space-y-3 text-sm text-muted-foreground">
                <p>形式：{platform.content_formats}</p>
                <p>优势：{platform.strength}</p>
                <p>适合达人：{platform.ideal_creators}</p>
                <p>{platform.amplification_note}</p>
              </div>
            </Card>
          ))}
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          <Card className="p-6">
            <div className="mb-4 flex items-center gap-2">
              <Sparkles className="h-5 w-5" />
              <h3 className="text-lg font-semibold">谈判话术</h3>
            </div>
            <div className="space-y-3">
              {sop.negotiation_scripts.map((script) => (
                <div key={script.title} className="rounded-xl border p-3">
                  <h4 className="font-medium">{script.title}</h4>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {script.description}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6">
            <div className="mb-4 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" />
              <h3 className="text-lg font-semibold">合规红线</h3>
            </div>
            <div className="space-y-3">
              {sop.compliance_rules.map((rule) => (
                <div key={rule.title} className="rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="font-medium">{rule.title}</h4>
                    {rule.severity && <Badge variant="destructive">{rule.severity}</Badge>}
                  </div>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {rule.description}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6">
            <div className="mb-4 flex items-center gap-2">
              <Trophy className="h-5 w-5" />
              <h3 className="text-lg font-semibold">内容审核与复盘</h3>
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              {sop.review_checklist.slice(0, 7).map((item) => (
                <div key={item} className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Card>
        </section>
      </div>
    </AppLayout>
  );
}
