"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/app-layout";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";
import { downloadExport } from "@/lib/download";
import type {
  Campaign,
  CampaignAIPlaybook,
  CampaignEnrollment,
  Influencer,
  PaginatedResponse,
} from "@/types";
import {
  ArrowLeft,
  Download,
  Pause,
  Play,
  Plus,
  Search,
  Sparkles,
  Square,
  Trash2,
  WandSparkles,
} from "lucide-react";

const ENROLLMENT_STATUS_MAP: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  queued: { label: "待发送", variant: "secondary" },
  in_progress: { label: "发送中", variant: "default" },
  replied: { label: "已回复", variant: "outline" },
  completed: { label: "已完成", variant: "secondary" },
  unsubscribed: { label: "已退订", variant: "destructive" },
  bounced: { label: "已退信", variant: "destructive" },
};

const EMPTY_PLAYBOOK: Omit<
  CampaignAIPlaybook,
  "id" | "campaign_id" | "created_at" | "updated_at"
> = {
  enabled: false,
  product_name: "",
  product_description: "",
  offer_summary: "",
  deliverables: "",
  sample_policy: "",
  pricing_rules: "",
  negotiation_limits: "",
  prohibited_claims: "",
  tone: "friendly and concise",
  language: "English",
  signature: "",
  reply_guidelines: "",
  campaign_objectives: "",
  target_audience: "",
  key_messages: "",
  content_dos: "",
  content_donts: "",
  required_hashtags: "",
  disclosure_requirements: "",
  payment_terms: "",
  usage_rights: "",
  approval_process: "",
  contract_required: false,
  content_review_checklist: "",
  posting_guidance: "",
  performance_kpis: "",
  competitor_notes: "",
};

const PLAYBOOK_TEXT_FIELDS: Array<{
  key: keyof typeof EMPTY_PLAYBOOK;
  label: string;
  placeholder: string;
  rows?: number;
}> = [
  {
    key: "product_description",
    label: "产品说明",
    placeholder: "产品定位、核心卖点、适用人群。避免写未经验证的功效承诺。",
    rows: 4,
  },
  {
    key: "offer_summary",
    label: "合作方案",
    placeholder: "例如：免费样品 + 固定 UGC fee；或样品 + 佣金。",
  },
  {
    key: "deliverables",
    label: "交付物",
    placeholder: "例如：1 条 TikTok 视频 + 3 张素材图，授权 30 天投放。",
  },
  {
    key: "sample_policy",
    label: "样品政策",
    placeholder: "样品是否免费、是否包邮、是否需要归还。",
  },
  {
    key: "pricing_rules",
    label: "报价规则",
    placeholder: "可接受报价范围、不同粉丝量级的建议报价。",
  },
  {
    key: "negotiation_limits",
    label: "谈判边界",
    placeholder: "哪些条件可以让步，哪些必须人工确认。",
  },
  {
    key: "prohibited_claims",
    label: "禁用承诺",
    placeholder: "例如：不承诺治疗、减重结果，不使用 FDA approved 等表达。",
  },
  {
    key: "reply_guidelines",
    label: "回复指南",
    placeholder: "例如：先回答问题，再推进下一步；报价超过上限时请保持礼貌并请求更多信息。",
    rows: 4,
  },
  {
    key: "signature",
    label: "邮件签名",
    placeholder: "团队署名、品牌名、联系方式。",
  },
];

const SOP_BRIEF_FIELDS: Array<{
  key: keyof typeof EMPTY_PLAYBOOK;
  label: string;
  placeholder: string;
  rows?: number;
}> = [
  {
    key: "campaign_objectives",
    label: "Campaign 目标",
    placeholder: "最多 3 个目标：曝光、素材、转化、Affiliate 销售等。",
  },
  {
    key: "target_audience",
    label: "目标受众",
    placeholder: "年龄、性别、地域、兴趣、痛点、决策触发。",
  },
  {
    key: "key_messages",
    label: "核心卖点",
    placeholder: "最多 3 个必须传达的差异化卖点。",
  },
  {
    key: "competitor_notes",
    label: "竞品洞察",
    placeholder: "3 个竞品、爆款内容钩子、竞品弱点、可借鉴内容方向。",
  },
  {
    key: "content_dos",
    label: "Do's",
    placeholder: "自然植入、真实使用场景、黄金前 3 秒、明确 CTA。",
  },
  {
    key: "content_donts",
    label: "Don'ts",
    placeholder: "禁竞品出镜、禁不实功效、禁缺少广告披露、禁偏离品牌调性。",
  },
];

const SOP_GOVERNANCE_FIELDS: Array<{
  key: keyof typeof EMPTY_PLAYBOOK;
  label: string;
  placeholder: string;
  rows?: number;
}> = [
  {
    key: "required_hashtags",
    label: "必填标签",
    placeholder: "#ad / #sponsored / 品牌账号 / 活动话题。",
  },
  {
    key: "disclosure_requirements",
    label: "合规披露",
    placeholder: "FTC/ASA：付费、寄样、affiliate 都要显眼披露。",
  },
  {
    key: "payment_terms",
    label: "付款条款",
    placeholder: "金额、币种、付款节点、付款渠道。",
  },
  {
    key: "usage_rights",
    label: "版权/授权",
    placeholder: "使用期限、广告投放授权、Spark Ads/Whitelist、是否可剪辑。",
  },
  {
    key: "approval_process",
    label: "审核流程",
    placeholder: "R1 初审 -> R2 复审 -> R3 终审；可修改几轮。",
  },
  {
    key: "content_review_checklist",
    label: "内容审核清单",
    placeholder: "卖点、品牌露出、#ad、CTA、画面音频、竞品、时长。",
    rows: 4,
  },
  {
    key: "posting_guidance",
    label: "发布时间/放量",
    placeholder: "TikTok/IG/YT 推荐时间，Spark Ads 小额测试与放量规则。",
    rows: 4,
  },
  {
    key: "performance_kpis",
    label: "复盘指标",
    placeholder: "曝光、互动率、CTR、加购、ROI/ROAS、CPE、达人配合度。",
    rows: 4,
  },
];

type ABVariantStats = { sent: number; opened: number; open_rate: number };

type CampaignStats = {
  total_enrolled?: number;
  emails_sent?: number;
  open_rate?: number;
  reply_rate?: number;
  ab_test?: Record<string, ABVariantStats> | null;
};

type SendProgress = {
  campaign_status: string;
  is_active: boolean;
  total: number;
  pending: number;
  sent: number;
  failed: number;
  progress_pct: number;
};

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [enrollments, setEnrollments] = useState<CampaignEnrollment[]>([]);
  const [playbookForm, setPlaybookForm] = useState(EMPTY_PLAYBOOK);
  const [savingPlaybook, setSavingPlaybook] = useState(false);
  const [playbookMessage, setPlaybookMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [allInfluencers, setAllInfluencers] = useState<Influencer[]>([]);
  const [influencerSearch, setInfluencerSearch] = useState("");
  const [selectedInfluencerIds, setSelectedInfluencerIds] = useState<string[]>([]);
  const [progress, setProgress] = useState<SendProgress | null>(null);

  const campaignId = useMemo(() => String(params.id), [params.id]);

  const loadCampaign = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [campaignResponse, statsResponse, enrollmentsResponse] = await Promise.all([
        api.get(`/campaigns/${campaignId}`),
        api.get(`/campaigns/${campaignId}/stats`).catch(() => ({ data: null })),
        api.get(`/campaigns/${campaignId}/enrollments`).catch(() => ({ data: [] })),
      ]);
      setCampaign(campaignResponse.data);
      setStats(statsResponse.data);
      setEnrollments(enrollmentsResponse.data);
      const playbookResponse = await api
        .get<CampaignAIPlaybook>(`/campaigns/${campaignId}/ai-playbook`)
        .catch(() => ({ data: null }));
      if (playbookResponse.data) {
        setPlaybookForm({
          enabled: playbookResponse.data.enabled,
          product_name: playbookResponse.data.product_name || "",
          product_description: playbookResponse.data.product_description || "",
          offer_summary: playbookResponse.data.offer_summary || "",
          deliverables: playbookResponse.data.deliverables || "",
          sample_policy: playbookResponse.data.sample_policy || "",
          pricing_rules: playbookResponse.data.pricing_rules || "",
          negotiation_limits: playbookResponse.data.negotiation_limits || "",
          prohibited_claims: playbookResponse.data.prohibited_claims || "",
          tone: playbookResponse.data.tone || "friendly and concise",
          language: playbookResponse.data.language || "English",
          signature: playbookResponse.data.signature || "",
          reply_guidelines: playbookResponse.data.reply_guidelines || "",
          campaign_objectives: playbookResponse.data.campaign_objectives || "",
          target_audience: playbookResponse.data.target_audience || "",
          key_messages: playbookResponse.data.key_messages || "",
          content_dos: playbookResponse.data.content_dos || "",
          content_donts: playbookResponse.data.content_donts || "",
          required_hashtags: playbookResponse.data.required_hashtags || "",
          disclosure_requirements: playbookResponse.data.disclosure_requirements || "",
          payment_terms: playbookResponse.data.payment_terms || "",
          usage_rights: playbookResponse.data.usage_rights || "",
          approval_process: playbookResponse.data.approval_process || "",
          contract_required: playbookResponse.data.contract_required,
          content_review_checklist: playbookResponse.data.content_review_checklist || "",
          posting_guidance: playbookResponse.data.posting_guidance || "",
          performance_kpis: playbookResponse.data.performance_kpis || "",
          competitor_notes: playbookResponse.data.competitor_notes || "",
        });
      }
    } catch (requestError) {
      console.error(requestError);
      setError("活动详情加载失败");
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    if (campaignId) {
      void loadCampaign();
    }
  }, [campaignId, loadCampaign]);

  const loadProgress = useCallback(async () => {
    try {
      const res = await api.get(`/campaigns/${campaignId}/send-progress`);
      setProgress(res.data);
    } catch {
      // progress is best-effort; ignore transient errors
    }
  }, [campaignId]);

  // Poll send progress live while the campaign is actively sending; otherwise
  // fetch once. The interval is cleared on unmount / status change.
  useEffect(() => {
    if (!campaign) return;
    void loadProgress();
    if (campaign.status !== "active") return;
    const timer = window.setInterval(() => {
      void loadProgress();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [campaign, loadProgress]);

  const handleAction = async (action: string) => {
    try {
      const response = await api.post(`/campaigns/${campaignId}/${action}`);
      setCampaign(response.data);
      await loadCampaign();
    } catch (requestError) {
      console.error(requestError);
      alert("活动操作失败");
    }
  };

  const updatePlaybookField = (
    key: keyof typeof EMPTY_PLAYBOOK,
    value: string | boolean
  ) => {
    setPlaybookForm((current) => ({ ...current, [key]: value }));
  };

  const savePlaybook = async () => {
    setSavingPlaybook(true);
    setPlaybookMessage(null);
    try {
      await api.put(`/campaigns/${campaignId}/ai-playbook`, playbookForm);
      setPlaybookMessage("AI 沟通设置已保存");
    } catch (requestError) {
      console.error(requestError);
      setPlaybookMessage("AI 沟通设置保存失败");
    } finally {
      setSavingPlaybook(false);
    }
  };

  const applySopDefaults = async () => {
    setSavingPlaybook(true);
    setPlaybookMessage(null);
    try {
      const response = await api.post<CampaignAIPlaybook>(
        `/campaigns/${campaignId}/ai-playbook/apply-sop`
      );
      setPlaybookForm({
        enabled: response.data.enabled,
        product_name: response.data.product_name || "",
        product_description: response.data.product_description || "",
        offer_summary: response.data.offer_summary || "",
        deliverables: response.data.deliverables || "",
        sample_policy: response.data.sample_policy || "",
        pricing_rules: response.data.pricing_rules || "",
        negotiation_limits: response.data.negotiation_limits || "",
        prohibited_claims: response.data.prohibited_claims || "",
        tone: response.data.tone || "friendly and concise",
        language: response.data.language || "English",
        signature: response.data.signature || "",
        reply_guidelines: response.data.reply_guidelines || "",
        campaign_objectives: response.data.campaign_objectives || "",
        target_audience: response.data.target_audience || "",
        key_messages: response.data.key_messages || "",
        content_dos: response.data.content_dos || "",
        content_donts: response.data.content_donts || "",
        required_hashtags: response.data.required_hashtags || "",
        disclosure_requirements: response.data.disclosure_requirements || "",
        payment_terms: response.data.payment_terms || "",
        usage_rights: response.data.usage_rights || "",
        approval_process: response.data.approval_process || "",
        contract_required: response.data.contract_required,
        content_review_checklist: response.data.content_review_checklist || "",
        posting_guidance: response.data.posting_guidance || "",
        performance_kpis: response.data.performance_kpis || "",
        competitor_notes: response.data.competitor_notes || "",
      });
      setPlaybookMessage("已套用 SOP 默认规则，你可以继续按产品细化。");
    } catch (requestError) {
      console.error(requestError);
      setPlaybookMessage("套用 SOP 默认规则失败");
    } finally {
      setSavingPlaybook(false);
    }
  };

  const removeEnrollment = async (enrollmentId: string) => {
    if (!confirm("确定移除此达人吗？")) return;

    try {
      await api.delete(`/campaigns/${campaignId}/enrollments/${enrollmentId}`);
      await loadCampaign();
    } catch (requestError) {
      console.error(requestError);
      alert("移除失败");
    }
  };

  const openAddInfluencers = async () => {
    try {
      const response = await api.get<PaginatedResponse<Influencer>>("/influencers", {
        params: { page: 1, per_page: 100 },
      });
      setAllInfluencers(response.data.items);
      setSelectedInfluencerIds([]);
      setInfluencerSearch("");
      setAddOpen(true);
    } catch (requestError) {
      console.error(requestError);
      alert("加载达人列表失败");
    }
  };

  const submitAddInfluencers = async () => {
    if (selectedInfluencerIds.length === 0) {
      setAddOpen(false);
      return;
    }

    try {
      await api.post(`/campaigns/${campaignId}/enroll`, {
        influencer_ids: selectedInfluencerIds,
      });
      setAddOpen(false);
      await loadCampaign();
    } catch (requestError) {
      console.error(requestError);
      alert("添加达人失败");
    }
  };

  const visibleInfluencers = allInfluencers.filter((influencer) => {
    if (enrollments.some((enrollment) => enrollment.influencer_id === influencer.id)) {
      return false;
    }
    if (!influencerSearch.trim()) return true;
    const keyword = influencerSearch.trim().toLowerCase();
    return (
      influencer.name.toLowerCase().includes(keyword) ||
      influencer.email?.toLowerCase().includes(keyword)
    );
  });

  if (loading) {
    return (
      <AppLayout>
        <p className="text-muted-foreground">加载中...</p>
      </AppLayout>
    );
  }

  if (!campaign) {
    return (
      <AppLayout>
        <p className="text-destructive">{error || "活动不存在"}</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.push("/campaigns")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回
            </Button>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold">{campaign.name}</h2>
                <Badge>{campaign.status}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                支持多步自动跟进序列；达人回复、退信或退订后自动停止后续步骤。
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            {campaign.status === "draft" && (
              <Button onClick={() => handleAction("start")}>
                <Play className="mr-2 h-4 w-4" />
                启动活动
              </Button>
            )}
            {campaign.status === "active" && (
              <>
                <Button variant="outline" onClick={() => handleAction("pause")}>
                  <Pause className="mr-2 h-4 w-4" />
                  暂停
                </Button>
                <Button variant="destructive" onClick={() => handleAction("stop")}>
                  <Square className="mr-2 h-4 w-4" />
                  停止
                </Button>
              </>
            )}
            {campaign.status === "paused" && (
              <Button onClick={() => handleAction("start")}>
                <Play className="mr-2 h-4 w-4" />
                恢复
              </Button>
            )}
          </div>
        </div>

        {stats && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">已入组</p>
              <p className="text-2xl font-bold">{stats.total_enrolled || 0}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">已发送</p>
              <p className="text-2xl font-bold">{stats.emails_sent || 0}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">打开率</p>
              <p className="text-2xl font-bold">{Number(stats.open_rate || 0).toFixed(1)}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">回复率</p>
              <p className="text-2xl font-bold">{Number(stats.reply_rate || 0).toFixed(1)}%</p>
            </Card>
          </div>
        )}

        {progress && progress.total > 0 && (
          <Card className="space-y-3 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">发送进度</h3>
              <span className="text-sm text-muted-foreground">
                {progress.is_active ? "发送中 · 每 3 秒自动刷新" : "当前未在发送"}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${progress.progress_pct}%` }}
              />
            </div>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-muted-foreground">总数</div>
                <div className="text-2xl font-bold">{progress.total}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">已发送</div>
                <div className="text-2xl font-bold text-green-600">{progress.sent}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">待发送</div>
                <div className="text-2xl font-bold">{progress.pending}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">失败</div>
                <div className="text-2xl font-bold text-red-500">{progress.failed}</div>
              </div>
            </div>
          </Card>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="space-y-4 p-6 lg:col-span-1">
            <h3 className="text-lg font-semibold">活动信息</h3>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-muted-foreground">类型</dt>
                <dd>{campaign.campaign_type}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">描述</dt>
                <dd>{campaign.description || "-"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">创建时间</dt>
                <dd>{new Date(campaign.created_at).toLocaleString("zh-CN")}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">启动时间</dt>
                <dd>{campaign.started_at ? new Date(campaign.started_at).toLocaleString("zh-CN") : "-"}</dd>
              </div>
            </dl>
          </Card>

          <Card className="space-y-4 p-6 lg:col-span-2">
            <h3 className="text-lg font-semibold">邮件序列（{campaign.steps.length} 步）</h3>
            {campaign.steps.length === 0 ? (
              <p className="text-muted-foreground">当前没有配置发送步骤。</p>
            ) : (
              campaign.steps.map((step) => (
                <div key={step.id} className="rounded-xl border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">
                      第 {step.step_order} 封 · {step.step_order === 1 ? "首发" : `延迟 ${step.delay_days} 天跟进`}
                    </span>
                    {(step.condition as Record<string, string> | null)?.ab_subject_b && (
                      <Badge variant="outline">A/B 主题测试</Badge>
                    )}
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    模板 ID：{step.template_id}
                    {step.attachment_ids.length > 0 && (
                      <> · 附件 {step.attachment_ids.length} 个</>
                    )}
                  </div>
                </div>
              ))
            )}
            {stats?.ab_test && (
              <div className="rounded-xl border bg-muted/20 p-4">
                <div className="mb-2 font-medium">A/B 主题测试结果</div>
                <div className="grid grid-cols-2 gap-4">
                  {(["A", "B"] as const).map((v) => {
                    const data = stats.ab_test![v];
                    return (
                      <div key={v} className="rounded-lg border bg-background p-3">
                        <div className="text-sm text-muted-foreground">{v} 版主题</div>
                        <div className="text-xl font-bold">{data.open_rate}% 打开率</div>
                        <div className="text-xs text-muted-foreground">
                          发送 {data.sent} · 打开 {data.opened}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Card>
        </div>

        <Card className="space-y-5 p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h3 className="text-lg font-semibold">AI 沟通设置</h3>
              <p className="text-sm text-muted-foreground">
                入站回复会引用这里的产品、报价、Brief、合规和审核规则生成待审核草稿。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" onClick={applySopDefaults} disabled={savingPlaybook}>
                <WandSparkles className="mr-2 h-4 w-4" />
                套用 SOP
              </Button>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={playbookForm.enabled}
                  onChange={(event) => updatePlaybookField("enabled", event.target.checked)}
                />
                启用 AI 草稿
              </label>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <Label>产品名称</Label>
              <Input
                value={playbookForm.product_name || ""}
                onChange={(event) => updatePlaybookField("product_name", event.target.value)}
                placeholder="例如：Collagen Gummies"
              />
            </div>
            <div>
              <Label>回复语气</Label>
              <Input
                value={playbookForm.tone || ""}
                onChange={(event) => updatePlaybookField("tone", event.target.value)}
                placeholder="friendly and concise"
              />
            </div>
            <div>
              <Label>回复语言</Label>
              <Input
                value={playbookForm.language || ""}
                onChange={(event) => updatePlaybookField("language", event.target.value)}
                placeholder="English"
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {PLAYBOOK_TEXT_FIELDS.map((field) => (
              <div key={field.key} className="space-y-1.5">
                <Label>{field.label}</Label>
                <Textarea
                  value={String(playbookForm[field.key] || "")}
                  onChange={(event) => updatePlaybookField(field.key, event.target.value)}
                  placeholder={field.placeholder}
                  rows={field.rows || 3}
                />
              </div>
            ))}
          </div>

          <div className="rounded-2xl border bg-muted/20 p-4">
            <div className="mb-4 flex flex-col gap-1">
              <h4 className="font-semibold">SOP Brief 字段</h4>
              <p className="text-sm text-muted-foreground">
                对齐 SOP 的 Campaign Brief：目标、受众、卖点、竞品洞察和内容边界。
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {SOP_BRIEF_FIELDS.map((field) => (
                <div key={field.key} className="space-y-1.5">
                  <Label>{field.label}</Label>
                  <Textarea
                    value={String(playbookForm[field.key] || "")}
                    onChange={(event) => updatePlaybookField(field.key, event.target.value)}
                    placeholder={field.placeholder}
                    rows={field.rows || 3}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border bg-muted/20 p-4">
            <div className="mb-4 flex flex-col gap-1">
              <h4 className="font-semibold">合规、合同、审核与复盘</h4>
              <p className="text-sm text-muted-foreground">
                把合同检查、FTC 披露、三轮审核和发布复盘写进活动规则，AI 才不会替你乱承诺。
              </p>
            </div>
            <label className="mb-4 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={playbookForm.contract_required}
                onChange={(event) => updatePlaybookField("contract_required", event.target.checked)}
              />
              付费或高风险合作需要合同确认
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              {SOP_GOVERNANCE_FIELDS.map((field) => (
                <div key={field.key} className="space-y-1.5">
                  <Label>{field.label}</Label>
                  <Textarea
                    value={String(playbookForm[field.key] || "")}
                    onChange={(event) => updatePlaybookField(field.key, event.target.value)}
                    placeholder={field.placeholder}
                    rows={field.rows || 3}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-muted-foreground">
              {playbookMessage || "未配置或未启用时，AI 仍可识别意图，但不会生成可发送草稿。"}
            </p>
            <Button onClick={savePlaybook} disabled={savingPlaybook}>
              {savingPlaybook ? "保存中..." : "保存 AI 设置"}
            </Button>
          </div>
        </Card>

        <Card className="p-0">
          <div className="border-b p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h3 className="text-lg font-semibold">入组达人</h3>
                <p className="text-sm text-muted-foreground">
                  可以查看每位达人的投递状态、最近一次邮件状态和失败原因。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  disabled={enrollments.length === 0}
                  onClick={() =>
                    downloadExport(
                      `/campaigns/${campaignId}/enrollments/export`,
                      { format: "xlsx" },
                      `campaign_${campaignId}_enrollments.xlsx`,
                    ).catch(() => alert("导出失败"))
                  }
                >
                  <Download className="mr-2 h-4 w-4" />
                  导出结果 (Excel)
                </Button>
                {(campaign.status === "draft" || campaign.status === "paused") && (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => router.push(`/discovery?campaign_id=${campaignId}`)}
                    >
                      <Sparkles className="mr-2 h-4 w-4" />
                      从 Woto 自动建联
                    </Button>
                    <Button variant="outline" onClick={openAddInfluencers}>
                      <Plus className="mr-2 h-4 w-4" />
                      添加达人
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>达人</TableHead>
                <TableHead>邮箱</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>最近发送</TableHead>
                <TableHead>邮件状态</TableHead>
                <TableHead>失败原因</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {enrollments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                    还没有入组达人。可以回到创建页重新创建，或后续补充入组接口。
                  </TableCell>
                </TableRow>
              ) : (
                enrollments.map((enrollment) => (
                  <TableRow key={enrollment.id}>
                    <TableCell>{enrollment.influencer_name}</TableCell>
                    <TableCell>{enrollment.influencer_email || "-"}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          ENROLLMENT_STATUS_MAP[enrollment.status]?.variant || "secondary"
                        }
                      >
                        {ENROLLMENT_STATUS_MAP[enrollment.status]?.label || enrollment.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {enrollment.last_sent_at
                        ? new Date(enrollment.last_sent_at).toLocaleString("zh-CN")
                        : "-"}
                    </TableCell>
                    <TableCell>{enrollment.last_email_status || "-"}</TableCell>
                    <TableCell className="max-w-[260px] whitespace-normal text-sm text-muted-foreground">
                      {enrollment.failure_reason || "-"}
                    </TableCell>
                    <TableCell>
                      {(campaign.status === "draft" || campaign.status === "paused") && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeEnrollment(enrollment.id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>

        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>添加入组达人</DialogTitle>
            </DialogHeader>

            <div className="max-h-[75vh] overflow-y-auto space-y-4 pr-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={influencerSearch}
                  onChange={(event) => setInfluencerSearch(event.target.value)}
                  className="pl-10"
                  placeholder="搜索达人名称或邮箱..."
                />
              </div>

              <div className="max-h-[360px] space-y-2 overflow-auto rounded-xl border p-3">
                {visibleInfluencers.length === 0 ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    没有可添加的达人。
                  </p>
                ) : (
                  visibleInfluencers.map((influencer) => (
                    <label
                      key={influencer.id}
                      className="flex items-start gap-3 rounded-lg border p-3"
                    >
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={selectedInfluencerIds.includes(influencer.id)}
                        onChange={(event) => {
                          setSelectedInfluencerIds((current) =>
                            event.target.checked
                              ? [...current, influencer.id]
                              : current.filter((id) => id !== influencer.id)
                          );
                        }}
                      />
                      <div>
                        <div className="font-medium">{influencer.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {influencer.email || "暂无邮箱"}
                        </div>
                      </div>
                    </label>
                  ))
                )}
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setAddOpen(false)}>
                  取消
                </Button>
                <Button onClick={submitAddInfluencers}>确认添加</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
