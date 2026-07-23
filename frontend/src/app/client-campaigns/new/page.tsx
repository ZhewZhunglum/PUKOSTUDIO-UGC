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
import { AttachmentField, uploadAttachmentFiles } from "@/components/shared/AttachmentField";
import api from "@/lib/api";
import type {
  Attachment,
  Client,
  ClientRelationshipType,
  EmailTemplate,
  PaginatedResponse,
} from "@/types";
import { ArrowLeft, CheckSquare, Search, Square } from "lucide-react";

const RELATIONSHIP_LABELS: Record<ClientRelationshipType, string> = {
  buyer: "批发/零售采购商",
  agency_prospect: "代理服务客户",
  partner: "品牌合作伙伴",
};

export default function NewClientCampaignPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [relationshipFilter, setRelationshipFilter] = useState("");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>([]);

  const [abSubjectB, setAbSubjectB] = useState("");
  const [initialAttachments, setInitialAttachments] = useState<Attachment[]>([]);
  const [followUps, setFollowUps] = useState<
    { template_id: string; delay_days: number; attachments: Attachment[] }[]
  >([]);
  const [uploadingKey, setUploadingKey] = useState<"initial" | number | null>(null);

  const [windowEnabled, setWindowEnabled] = useState(false);
  const [windowStart, setWindowStart] = useState("9");
  const [windowEnd, setWindowEnd] = useState("17");
  const [windowTz, setWindowTz] = useState("America/Los_Angeles");

  const TIMEZONES = [
    { value: "America/Los_Angeles", label: "美西 (Los Angeles)" },
    { value: "America/New_York", label: "美东 (New York)" },
    { value: "Europe/London", label: "英国 (London)" },
    { value: "Asia/Shanghai", label: "中国 (Shanghai)" },
    { value: "UTC", label: "UTC" },
  ];

  useEffect(() => {
    Promise.all([
      api.get("/templates"),
      api.get<PaginatedResponse<Client>>("/clients", {
        params: { page: 1, per_page: 500 },
      }),
    ])
      .then(([templatesRes, clientsRes]) => {
        setTemplates(templatesRes.data);
        setClients(clientsRes.data.items);
      })
      .catch(() => setError("加载模板或客户列表失败"));
  }, []);

  const filteredClients = useMemo(() => {
    let list = clients;
    if (relationshipFilter) {
      list = list.filter((c) => c.relationship_type === relationshipFilter);
    }
    if (search.trim()) {
      const kw = search.trim().toLowerCase();
      list = list.filter(
        (c) =>
          c.company_name.toLowerCase().includes(kw) ||
          c.contact_name?.toLowerCase().includes(kw) ||
          c.email?.toLowerCase().includes(kw)
      );
    }
    return list;
  }, [clients, search, relationshipFilter]);

  const toggleClient = (id: string) => {
    setSelectedClientIds((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]
    );
  };

  const selectAll = () => {
    const ids = filteredClients.map((c) => c.id);
    setSelectedClientIds((cur) => [...new Set([...cur, ...ids])]);
  };

  const deselectAll = () => {
    const ids = new Set(filteredClients.map((c) => c.id));
    setSelectedClientIds((cur) => cur.filter((id) => !ids.has(id)));
  };

  const updateFollowUp = (
    index: number,
    patch: Partial<{ template_id: string; delay_days: number; attachments: Attachment[] }>
  ) => {
    setFollowUps((cur) => cur.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  };

  const addAttachments = async (key: "initial" | number, files: FileList) => {
    setUploadingKey(key);
    try {
      const uploaded = await uploadAttachmentFiles(files);
      if (key === "initial") {
        setInitialAttachments((cur) => [...cur, ...uploaded]);
      } else {
        updateFollowUp(key, {
          attachments: [...(followUps[key]?.attachments ?? []), ...uploaded],
        });
      }
    } catch {
      setError("附件上传失败（请检查文件类型与大小）");
    } finally {
      setUploadingKey(null);
    }
  };

  const removeAttachment = (key: "initial" | number, id: string) => {
    if (key === "initial") {
      setInitialAttachments((cur) => cur.filter((a) => a.id !== id));
    } else {
      updateFollowUp(key, {
        attachments: (followUps[key]?.attachments ?? []).filter((a) => a.id !== id),
      });
    }
  };

  const handleCreate = async () => {
    if (!name || !templateId) {
      setError("请填写活动名称并选择首封模板");
      return;
    }
    if (followUps.some((f) => !f.template_id)) {
      setError("每个跟进步骤都需要选择模板");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const campaignRes = await api.post("/client-campaigns", {
        name,
        description: description || null,
        schedule_config: windowEnabled
          ? {
              send_window: {
                start_hour: Number(windowStart),
                end_hour: Number(windowEnd),
                timezone: windowTz,
              },
            }
          : null,
        steps: [
          {
            step_order: 1,
            step_type: "initial",
            template_id: templateId,
            delay_days: 0,
            condition: abSubjectB.trim() ? { ab_subject_b: abSubjectB.trim() } : null,
            attachment_ids: initialAttachments.map((a) => a.id),
          },
          ...followUps.map((f, i) => ({
            step_order: i + 2,
            step_type: "followup",
            template_id: f.template_id,
            delay_days: Math.max(1, f.delay_days),
            attachment_ids: f.attachments.map((a) => a.id),
          })),
        ],
      });
      if (selectedClientIds.length > 0) {
        await api.post(`/client-campaigns/${campaignRes.data.id}/enroll`, {
          client_ids: selectedClientIds,
        });
      }
      router.push(`/client-campaigns/${campaignRes.data.id}`);
    } catch {
      setError("创建活动失败");
    } finally {
      setLoading(false);
    }
  };

  const stepLabels = ["基本信息", "邮件序列", "入组客户"];

  return (
    <AppLayout>
      <div className="mx-auto max-w-5xl space-y-6 fade-in">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push("/client-campaigns")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回
          </Button>
          <div>
            <h2 className="text-2xl font-bold">创建客户建联活动</h2>
            <p className="text-sm text-muted-foreground">共 3 步完成活动配置</p>
          </div>
        </div>

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

        {step === 1 && (
          <Card className="space-y-5 p-6">
            <h3 className="text-lg font-semibold">基本信息</h3>
            <div>
              <Label>活动名称 *</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="如：批发采购商 Q2 建联"
                className="mt-1.5"
              />
            </div>
            <div>
              <Label>活动描述</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="说明这次建联的目标、产品和合作方式..."
                rows={4}
                className="mt-1.5"
              />
            </div>
            <div className="space-y-3 rounded-xl border bg-muted/20 p-4">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={windowEnabled}
                  onChange={(e) => setWindowEnabled(e.target.checked)}
                />
                启用发送时间窗口（按收件人时区，只在指定时段发信）
              </label>
              {windowEnabled && (
                <div className="grid gap-3 sm:grid-cols-3">
                  <div>
                    <Label>开始（点）</Label>
                    <Input
                      type="number"
                      min={0}
                      max={23}
                      value={windowStart}
                      onChange={(e) => setWindowStart(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>结束（点）</Label>
                    <Input
                      type="number"
                      min={1}
                      max={24}
                      value={windowEnd}
                      onChange={(e) => setWindowEnd(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>时区</Label>
                    <Select value={windowTz} onValueChange={(v) => v && setWindowTz(v)}>
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TIMEZONES.map((tz) => (
                          <SelectItem key={tz.value} value={tz.value}>{tz.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>
            <Button onClick={() => setStep(2)} disabled={!name.trim()}>
              下一步：配置邮件序列
            </Button>
          </Card>
        )}

        {step === 2 && (
          <Card className="space-y-4 p-6">
            <h3 className="text-lg font-semibold">配置邮件序列：首封模板</h3>
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
            {templateId && (
              <div className="space-y-3 rounded-xl border bg-muted/20 p-4">
                <div>
                  <Label>A/B 主题测试（可选）</Label>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    填写 B 版主题后，50% 客户收到模板原主题（A 版），50% 收到 B 版；活动详情可对比两版打开率。支持 {"{{first_name}}"} 等变量。
                  </p>
                  <Input
                    className="mt-1.5"
                    value={abSubjectB}
                    onChange={(e) => setAbSubjectB(e.target.value)}
                    placeholder="B 版主题，留空则不做 A/B 测试"
                  />
                </div>
                <div>
                  <Label>附件（可选）</Label>
                  <div className="mt-1.5">
                    <AttachmentField
                      attachments={initialAttachments}
                      uploading={uploadingKey === "initial"}
                      inputId="attachments-initial"
                      onAdd={(files) => addAttachments("initial", files)}
                      onRemove={(id) => removeAttachment("initial", id)}
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-3 rounded-xl border bg-muted/20 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>自动跟进序列（可选）</Label>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    未回复的客户将按延迟自动收到跟进邮件；一旦回复/退信/退订即停止。
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={followUps.length >= 4}
                  onClick={() =>
                    setFollowUps((cur) => [...cur, { template_id: "", delay_days: 3, attachments: [] }])
                  }
                >
                  + 添加跟进
                </Button>
              </div>
              {followUps.length === 0 ? (
                <p className="text-sm text-muted-foreground">未配置跟进，仅发送首封邮件。</p>
              ) : (
                followUps.map((f, i) => (
                  <div key={i} className="space-y-2 rounded-lg border bg-background p-3">
                    <div className="flex flex-wrap items-end gap-2">
                      <span className="pb-2 text-sm font-medium">第 {i + 2} 封</span>
                      <div className="w-28">
                        <Label className="text-xs">延迟（天）</Label>
                        <Input
                          type="number"
                          min={1}
                          value={String(f.delay_days)}
                          onChange={(e) => updateFollowUp(i, { delay_days: Number(e.target.value) || 1 })}
                          className="mt-1"
                        />
                      </div>
                      <div className="min-w-[220px] flex-1">
                        <Label className="text-xs">模板</Label>
                        <Select
                          value={f.template_id || undefined}
                          onValueChange={(v) => v && updateFollowUp(i, { template_id: v })}
                        >
                          <SelectTrigger className="mt-1">
                            <SelectValue placeholder="选择跟进模板" />
                          </SelectTrigger>
                          <SelectContent>
                            {templates.map((tmpl) => (
                              <SelectItem key={tmpl.id} value={tmpl.id}>{tmpl.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setFollowUps((cur) => cur.filter((_, x) => x !== i))}
                      >
                        移除
                      </Button>
                    </div>
                    <AttachmentField
                      attachments={f.attachments}
                      uploading={uploadingKey === i}
                      inputId={`attachments-followup-${i}`}
                      onAdd={(files) => addAttachments(i, files)}
                      onRemove={(id) => removeAttachment(i, id)}
                    />
                  </div>
                ))
              )}
            </div>

            <div className="flex gap-2 pt-2">
              <Button variant="outline" onClick={() => setStep(1)}>上一步</Button>
              <Button onClick={() => setStep(3)} disabled={!templateId}>下一步：入组客户</Button>
            </div>
          </Card>
        )}

        {step === 3 && (
          <Card className="space-y-4 p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-semibold">选择入组客户</h3>
                <p className="text-sm text-muted-foreground">
                  这一步可选。可先创建活动，再到详情页补充客户。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">
                  已选 <span className="text-primary">{selectedClientIds.length}</span> 家
                </span>
                <Button variant="outline" size="sm" onClick={selectAll}>全选当前</Button>
                <Button variant="ghost" size="sm" onClick={deselectAll}>清空</Button>
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索公司名称、联系人或邮箱..."
                  className="pl-10"
                />
              </div>
              <Select value={relationshipFilter || "all"} onValueChange={(v) => setRelationshipFilter(!v || v === "all" ? "" : v)}>
                <SelectTrigger className="w-full sm:w-48">
                  <SelectValue placeholder="全部关系类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部关系类型</SelectItem>
                  {(Object.keys(RELATIONSHIP_LABELS) as ClientRelationshipType[]).map((rt) => (
                    <SelectItem key={rt} value={rt}>{RELATIONSHIP_LABELS[rt]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="max-h-[420px] space-y-2 overflow-y-auto rounded-xl border p-3">
              {filteredClients.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  没有匹配的客户
                </p>
              ) : (
                filteredClients.map((client) => {
                  const checked = selectedClientIds.includes(client.id);
                  return (
                    <label
                      key={client.id}
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
                        onChange={() => toggleClient(client.id)}
                        readOnly
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{client.company_name}</span>
                          <Badge variant="outline" className="text-xs">
                            {RELATIONSHIP_LABELS[client.relationship_type]}
                          </Badge>
                        </div>
                        <div className="truncate text-sm text-muted-foreground">
                          {client.email || "暂无邮箱"}
                          {client.contact_name && <> · {client.contact_name}</>}
                        </div>
                      </div>
                    </label>
                  );
                })
              )}
            </div>

            <div className="flex gap-2 pt-2">
              <Button variant="outline" onClick={() => setStep(2)}>上一步</Button>
              <Button onClick={handleCreate} disabled={loading}>
                {loading ? "创建中..." : `创建活动${selectedClientIds.length > 0 ? `（含 ${selectedClientIds.length} 家客户）` : ""}`}
              </Button>
            </div>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
