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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import api from "@/lib/api";
import { downloadExport } from "@/lib/download";
import type {
  Client,
  ClientCampaign,
  ClientCampaignEnrollment,
  PaginatedResponse,
} from "@/types";
import {
  ArrowLeft,
  Download,
  Pause,
  Play,
  Plus,
  Search,
  Square,
  Trash2,
} from "lucide-react";

const ENROLLMENT_STATUS_MAP: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  queued: { label: "待发送", variant: "secondary" },
  in_progress: { label: "发送中", variant: "default" },
  replied: { label: "已回复", variant: "outline" },
  completed: { label: "已完成", variant: "secondary" },
  unsubscribed: { label: "已退订", variant: "destructive" },
  bounced: { label: "已退信", variant: "destructive" },
};

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

export default function ClientCampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [campaign, setCampaign] = useState<ClientCampaign | null>(null);
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [enrollments, setEnrollments] = useState<ClientCampaignEnrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [allClients, setAllClients] = useState<Client[]>([]);
  const [clientSearch, setClientSearch] = useState("");
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>([]);
  const [progress, setProgress] = useState<SendProgress | null>(null);

  const campaignId = useMemo(() => String(params.id), [params.id]);

  const loadCampaign = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [campaignResponse, statsResponse, enrollmentsResponse] = await Promise.all([
        api.get(`/client-campaigns/${campaignId}`),
        api.get(`/client-campaigns/${campaignId}/stats`).catch(() => ({ data: null })),
        api.get(`/client-campaigns/${campaignId}/enrollments`).catch(() => ({ data: [] })),
      ]);
      setCampaign(campaignResponse.data);
      setStats(statsResponse.data);
      setEnrollments(enrollmentsResponse.data);
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
      const res = await api.get(`/client-campaigns/${campaignId}/send-progress`);
      setProgress(res.data);
    } catch {
      // progress is best-effort; ignore transient errors
    }
  }, [campaignId]);

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
      const response = await api.post(`/client-campaigns/${campaignId}/${action}`);
      setCampaign(response.data);
      await loadCampaign();
    } catch (requestError) {
      console.error(requestError);
      alert("活动操作失败");
    }
  };

  const removeEnrollment = async (enrollmentId: string) => {
    if (!confirm("确定移除此客户吗？")) return;

    try {
      await api.delete(`/client-campaigns/${campaignId}/enrollments/${enrollmentId}`);
      await loadCampaign();
    } catch (requestError) {
      console.error(requestError);
      alert("移除失败");
    }
  };

  const openAddClients = async () => {
    try {
      const response = await api.get<PaginatedResponse<Client>>("/clients", {
        params: { page: 1, per_page: 100 },
      });
      setAllClients(response.data.items);
      setSelectedClientIds([]);
      setClientSearch("");
      setAddOpen(true);
    } catch (requestError) {
      console.error(requestError);
      alert("加载客户列表失败");
    }
  };

  const submitAddClients = async () => {
    if (selectedClientIds.length === 0) {
      setAddOpen(false);
      return;
    }

    try {
      await api.post(`/client-campaigns/${campaignId}/enroll`, {
        client_ids: selectedClientIds,
      });
      setAddOpen(false);
      await loadCampaign();
    } catch (requestError) {
      console.error(requestError);
      alert("添加客户失败");
    }
  };

  const visibleClients = allClients.filter((client) => {
    if (enrollments.some((enrollment) => enrollment.client_id === client.id)) {
      return false;
    }
    if (!clientSearch.trim()) return true;
    const keyword = clientSearch.trim().toLowerCase();
    return (
      client.company_name.toLowerCase().includes(keyword) ||
      client.email?.toLowerCase().includes(keyword)
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
            <Button variant="ghost" size="sm" onClick={() => router.push("/client-campaigns")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回
            </Button>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold">{campaign.name}</h2>
                <Badge>{campaign.status}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                支持多步自动跟进序列；客户回复、退信或退订后自动停止后续步骤。
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
                    {step.condition?.ab_subject_b && (
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

        <Card className="p-0">
          <div className="border-b p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h3 className="text-lg font-semibold">入组客户</h3>
                <p className="text-sm text-muted-foreground">
                  可以查看每家客户的投递状态、最近一次邮件状态和失败原因。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  disabled={enrollments.length === 0}
                  onClick={() =>
                    downloadExport(
                      `/client-campaigns/${campaignId}/enrollments/export`,
                      { format: "xlsx" },
                      `client_campaign_${campaignId}_enrollments.xlsx`,
                    ).catch(() => alert("导出失败"))
                  }
                >
                  <Download className="mr-2 h-4 w-4" />
                  导出结果 (Excel)
                </Button>
                {(campaign.status === "draft" || campaign.status === "paused") && (
                  <Button variant="outline" onClick={openAddClients}>
                    <Plus className="mr-2 h-4 w-4" />
                    添加客户
                  </Button>
                )}
              </div>
            </div>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>客户</TableHead>
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
                    还没有入组客户。可以回到创建页重新创建，或点击“添加客户”补充。
                  </TableCell>
                </TableRow>
              ) : (
                enrollments.map((enrollment) => (
                  <TableRow key={enrollment.id}>
                    <TableCell>{enrollment.client_company_name}</TableCell>
                    <TableCell>{enrollment.client_email || "-"}</TableCell>
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
              <DialogTitle>添加入组客户</DialogTitle>
            </DialogHeader>

            <div className="max-h-[75vh] overflow-y-auto space-y-4 pr-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={clientSearch}
                  onChange={(event) => setClientSearch(event.target.value)}
                  className="pl-10"
                  placeholder="搜索公司名称或邮箱..."
                />
              </div>

              <div className="max-h-[360px] space-y-2 overflow-auto rounded-xl border p-3">
                {visibleClients.length === 0 ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    没有可添加的客户。
                  </p>
                ) : (
                  visibleClients.map((client) => (
                    <label
                      key={client.id}
                      className="flex items-start gap-3 rounded-lg border p-3"
                    >
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={selectedClientIds.includes(client.id)}
                        onChange={(event) => {
                          setSelectedClientIds((current) =>
                            event.target.checked
                              ? [...current, client.id]
                              : current.filter((id) => id !== client.id)
                          );
                        }}
                      />
                      <div>
                        <div className="font-medium">{client.company_name}</div>
                        <div className="text-sm text-muted-foreground">
                          {client.email || "暂无邮箱"}
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
                <Button onClick={submitAddClients}>确认添加</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
