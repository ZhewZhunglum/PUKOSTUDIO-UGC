"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import api from "@/lib/api";
import type { EmailAccount } from "@/types";
import { CheckCircle2, ChevronDown, Loader2, Plus, TestTube, Trash2, ShieldCheck, Sparkles, XCircle } from "lucide-react";

const WOTO_PROD_URL = "https://api.wotohub.com/api-gateway";

type WotoSettings = {
  has_api_key: boolean;
  api_key_preview: string | null;
  use_sandbox: boolean;
  sandbox_base_url: string;
  production_base_url: string;
  effective_base_url: string;
};

type WotoForm = {
  api_key: string;
  use_sandbox: boolean;
  sandbox_base_url: string;
  production_base_url: string;
};

type WotoTestResult = {
  success: boolean;
  environment: string;
  base_url: string;
  remain_quota: number | null;
  error: string | null;
} | null;

// ── AI settings types ──────────────────────────────────────────────────────
type ProviderCatalogEntry = {
  id: string;
  name: string;
  auth_type: "api_key" | "azure" | "aws";
  base_url: string | null;
  models: string[];
  region: string;
  docs: string;
  note?: string;
  extra_fields?: { key: string; label: string; placeholder?: string; default?: string; type?: string; required?: boolean }[];
};

type AISettings = {
  provider: string;
  model: string;
  base_url: string | null;
  has_api_key: boolean;
  api_key_preview: string | null;
  catalog: ProviderCatalogEntry[];
  extra: Record<string, string | boolean>;
};

type AIForm = {
  provider: string;
  api_key: string;
  model: string;
  base_url: string;
  // Azure
  azure_endpoint: string;
  api_version: string;
  // AWS Bedrock
  aws_region: string;
  aws_access_key_id: string;
  aws_secret_access_key: string;
};

type AITestResult = {
  success: boolean;
  provider: string;
  model: string;
  ping_response: string | null;
  error: string | null;
} | null;

// ── Suppression list types ─────────────────────────────────────────────────
type Suppression = {
  id: string;
  email: string;
  reason: "bounced" | "complained" | "unsubscribed" | "manual";
  created_at: string;
};

const SUPPRESSION_REASON_MAP: Record<Suppression["reason"], string> = {
  bounced: "退信",
  complained: "投诉",
  unsubscribed: "退订",
  manual: "手动",
};

// ── Email account types ────────────────────────────────────────────────────
type ProviderType = "ses" | "sendgrid" | "smtp";

type FormState = {
  email_address: string;
  display_name: string;
  provider_type: ProviderType;
  daily_limit: string;
  ses_region: string;
  ses_access_key_id: string;
  ses_secret_access_key: string;
  sendgrid_api_key: string;
  smtp_host: string;
  smtp_port: string;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
};

const INITIAL_FORM: FormState = {
  email_address: "",
  display_name: "",
  provider_type: "ses",
  daily_limit: "50",
  ses_region: "us-east-1",
  ses_access_key_id: "",
  ses_secret_access_key: "",
  sendgrid_api_key: "",
  smtp_host: "",
  smtp_port: "587",
  smtp_username: "",
  smtp_password: "",
  smtp_use_tls: true,
};

const HEALTH_MAP: Record<string, { label: string; variant: "default" | "secondary" | "destructive" }> = {
  healthy: { label: "正常", variant: "default" },
  degraded: { label: "异常", variant: "secondary" },
  suspended: { label: "暂停", variant: "destructive" },
};

function SettingsPageContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") ?? "email";
  const [activeTab, setActiveTab] = useState<string>(
    ["email", "woto", "ai", "suppression", "team"].includes(initialTab) ? initialTab : "email"
  );

  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [message, setMessage] = useState<string | null>(null);

  // Woto settings state
  const [wotoSettings, setWotoSettings] = useState<WotoSettings | null>(null);
  const [wotoForm, setWotoForm] = useState<WotoForm>({
    api_key: "",
    use_sandbox: false,
    sandbox_base_url: "",
    production_base_url: WOTO_PROD_URL,
  });
  const [wotoSaving, setWotoSaving] = useState(false);
  const [wotoTesting, setWotoTesting] = useState<"sandbox" | "production" | null>(null);
  const [wotoTestResult, setWotoTestResult] = useState<WotoTestResult>(null);
  const [wotoMessage, setWotoMessage] = useState<string | null>(null);

  // Suppression list state
  const [suppressions, setSuppressions] = useState<Suppression[]>([]);
  const [suppressionEmail, setSuppressionEmail] = useState("");
  const [suppressionBusy, setSuppressionBusy] = useState(false);
  const [suppressionMessage, setSuppressionMessage] = useState<string | null>(null);

  // AI settings state
  const [aiSettings, setAISettings] = useState<AISettings | null>(null);
  const [aiForm, setAIForm] = useState<AIForm>({
    provider: "claude", api_key: "", model: "", base_url: "",
    azure_endpoint: "", api_version: "2024-02-01",
    aws_region: "us-east-1", aws_access_key_id: "", aws_secret_access_key: "",
  });
  const [aiSaving, setAISaving] = useState(false);
  const [aiTesting, setAITesting] = useState(false);
  const [aiTestResult, setAITestResult] = useState<AITestResult>(null);
  const [aiMessage, setAIMessage] = useState<string | null>(null);

  const selectedProviderEntry = aiSettings?.catalog.find((p) => p.id === aiForm.provider);
  const authType = selectedProviderEntry?.auth_type ?? "api_key";
  const providerHasPresetModels = (selectedProviderEntry?.models.length ?? 0) > 0;
  const showBaseUrl = authType === "api_key" && aiForm.provider !== "claude";
  const savedAzureEndpoint =
    typeof aiSettings?.extra?.azure_endpoint === "string"
      ? aiSettings.extra.azure_endpoint
      : "";

  const providerType = form.provider_type;

  const providerConfig = useMemo(() => {
    if (providerType === "ses") {
      return {
        region: form.ses_region.trim(),
        access_key_id: form.ses_access_key_id.trim(),
        secret_access_key: form.ses_secret_access_key.trim(),
      };
    }
    if (providerType === "sendgrid") {
      return {
        api_key: form.sendgrid_api_key.trim(),
      };
    }
    return {
      host: form.smtp_host.trim(),
      port: Number(form.smtp_port || "587"),
      username: form.smtp_username.trim(),
      password: form.smtp_password.trim(),
      use_tls: form.smtp_use_tls,
    };
  }, [form, providerType]);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const response = await api.get("/email-accounts");
      setAccounts(response.data);
    } catch (requestError) {
      console.error(requestError);
      setMessage("邮箱账号加载失败");
    } finally {
      setLoading(false);
    }
  };

  const fetchWotoSettings = async () => {
    try {
      const response = await api.get<WotoSettings>("/settings/woto");
      setWotoSettings(response.data);
      setWotoForm((current) => ({
        ...current,
        use_sandbox: response.data.use_sandbox,
        sandbox_base_url: response.data.sandbox_base_url,
        production_base_url: response.data.production_base_url || WOTO_PROD_URL,
      }));
    } catch {
      // Woto settings load failure is non-critical
    }
  };

  const fetchAISettings = async () => {
    try {
      const response = await api.get<AISettings>("/settings/ai");
      setAISettings(response.data);
      const extra = response.data.extra ?? {};
      setAIForm((current) => ({
        ...current,
        provider: response.data.provider || "claude",
        model: response.data.model || "",
        base_url: response.data.base_url || "",
        azure_endpoint: (extra.azure_endpoint as string) || "",
        api_version: (extra.api_version as string) || "2024-02-01",
        aws_region: (extra.aws_region as string) || "us-east-1",
      }));
    } catch {
      // non-critical
    }
  };

  const buildAIPayload = () => ({
    provider: aiForm.provider,
    api_key: aiForm.api_key || null,
    model: aiForm.model,
    base_url: aiForm.base_url || null,
    azure_endpoint: aiForm.azure_endpoint || null,
    api_version: aiForm.api_version || null,
    aws_region: aiForm.aws_region || null,
    aws_access_key_id: aiForm.aws_access_key_id || null,
    aws_secret_access_key: aiForm.aws_secret_access_key || null,
  });

  const handleSaveAI = async () => {
    setAISaving(true);
    setAIMessage(null);
    setAITestResult(null);
    try {
      await api.put("/settings/ai", buildAIPayload());
      setAIForm((current) => ({ ...current, api_key: "", aws_access_key_id: "", aws_secret_access_key: "" }));
      await fetchAISettings();
      setAIMessage("AI 配置已保存");
    } catch {
      setAIMessage("保存 AI 配置失败");
    } finally {
      setAISaving(false);
    }
  };

  const handleTestAI = async () => {
    setAITesting(true);
    setAITestResult(null);
    try {
      const response = await api.post<NonNullable<AITestResult>>("/settings/ai/test", buildAIPayload());
      setAITestResult(response.data);
    } catch {
      setAITestResult({ success: false, provider: aiForm.provider, model: aiForm.model, ping_response: null, error: "请求失败，请检查后端服务" });
    } finally {
      setAITesting(false);
    }
  };

  const fetchSuppressions = async () => {
    try {
      const response = await api.get<Suppression[]>("/suppressions");
      setSuppressions(response.data);
    } catch {
      // non-critical
    }
  };

  const handleAddSuppression = async () => {
    const email = suppressionEmail.trim();
    if (!email) return;
    setSuppressionBusy(true);
    setSuppressionMessage(null);
    try {
      const response = await api.post<Suppression[]>("/suppressions", { email });
      setSuppressions(response.data);
      setSuppressionEmail("");
      setSuppressionMessage("已加入抑制名单");
    } catch {
      setSuppressionMessage("添加失败，请确认邮箱格式正确");
    } finally {
      setSuppressionBusy(false);
    }
  };

  const handleRemoveSuppression = async (id: string) => {
    if (!confirm("移出抑制名单后，该地址将重新可以接收邮件。确定吗？")) return;
    try {
      await api.delete(`/suppressions/${id}`);
      await fetchSuppressions();
    } catch {
      setSuppressionMessage("移除失败，请稍后重试");
    }
  };

  useEffect(() => {
    void fetchAccounts();
    void fetchWotoSettings();
    void fetchAISettings();
    void fetchSuppressions();
  }, []);

  const updateForm = (patch: Partial<FormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const updateWotoForm = (patch: Partial<WotoForm>) => {
    setWotoForm((current) => ({ ...current, ...patch }));
  };

  const handleSaveWoto = async () => {
    setWotoSaving(true);
    setWotoMessage(null);
    setWotoTestResult(null);
    try {
      await api.put("/settings/woto", {
        api_key: wotoForm.api_key || null,
        use_sandbox: wotoForm.use_sandbox,
        sandbox_base_url: wotoForm.sandbox_base_url || null,
        production_base_url: wotoForm.production_base_url || null,
      });
      setWotoForm((current) => ({ ...current, api_key: "" }));
      await fetchWotoSettings();
      setWotoMessage("Woto 配置已保存");
    } catch {
      setWotoMessage("保存 Woto 配置失败");
    } finally {
      setWotoSaving(false);
    }
  };

  const handleTestWoto = async (environment: "sandbox" | "production") => {
    setWotoTesting(environment);
    setWotoTestResult(null);
    try {
      const response = await api.post<NonNullable<WotoTestResult>>("/settings/woto/test", {
        environment,
        api_key: wotoForm.api_key || null,
        base_url:
          environment === "sandbox"
            ? wotoForm.sandbox_base_url || null
            : wotoForm.production_base_url || null,
      });
      setWotoTestResult(response.data);
    } catch {
      setWotoTestResult({
        success: false,
        environment,
        base_url: "",
        remain_quota: null,
        error: "请求失败，请检查后端服务",
      });
    } finally {
      setWotoTesting(null);
    }
  };

  const resetForm = () => {
    setForm(INITIAL_FORM);
  };

  const handleAddAccount = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await api.post("/email-accounts", {
        email_address: form.email_address.trim(),
        display_name: form.display_name.trim() || null,
        provider_type: form.provider_type,
        provider_config: providerConfig,
        daily_limit: Number(form.daily_limit || "50"),
      });
      setAddOpen(false);
      resetForm();
      await fetchAccounts();
      setMessage("邮箱账号已创建");
    } catch (requestError) {
      console.error(requestError);
      setMessage("创建邮箱账号失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (accountId: string) => {
    if (!confirm("确定删除这个邮箱账号吗？")) return;
    try {
      await api.delete(`/email-accounts/${accountId}`);
      await fetchAccounts();
    } catch (requestError) {
      console.error(requestError);
      setMessage("删除邮箱账号失败");
    }
  };

  const handleVerify = async (accountId: string) => {
    try {
      const response = await api.post(`/email-accounts/${accountId}/verify`);
      if (response.data.success) {
        setMessage("连接验证成功");
      } else {
        setMessage(`连接验证失败：${response.data.error || "未知错误"}`);
      }
      await fetchAccounts();
    } catch (requestError) {
      console.error(requestError);
      setMessage("验证邮箱连接失败");
    }
  };

  const handleTest = async (accountId: string) => {
    const targetAddress = prompt("请输入测试收件邮箱：");
    if (!targetAddress) return;

    try {
      const response = await api.post(`/email-accounts/${accountId}/test`, {
        to_address: targetAddress,
      });
      if (response.data.success) {
        setMessage("测试邮件发送成功");
      } else {
        setMessage(`测试邮件发送失败：${response.data.error || "未知错误"}`);
      }
      await fetchAccounts();
    } catch (requestError) {
      console.error(requestError);
      setMessage("测试邮件发送失败");
    }
  };

  return (
    <AppLayout>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>系统</div>
          <h1 className="h-1">设置</h1>
          <p className="ds-body" style={{ marginTop: 4, color: "var(--ink-3)" }}>
            管理品牌身份、发送策略、AI 协作规则与团队权限。
          </p>
        </div>

        {message && <p className="text-sm text-muted-foreground">{message}</p>}

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="email">邮箱账号</TabsTrigger>
            <TabsTrigger value="woto">Woto API</TabsTrigger>
            <TabsTrigger value="ai">AI 配置</TabsTrigger>
            <TabsTrigger value="suppression">抑制名单</TabsTrigger>
            <TabsTrigger value="team">团队</TabsTrigger>
          </TabsList>

          <TabsContent value="email" className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-muted-foreground">
                当前支持 Amazon SES、SendGrid 和 SMTP。新账号创建后建议先做“验证连接”和“发送测试”。
              </p>
              <Button onClick={() => setAddOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                添加账号
              </Button>
            </div>

            {loading ? (
              <p className="text-muted-foreground">加载中...</p>
            ) : accounts.length === 0 ? (
              <Card className="p-8 text-center text-muted-foreground">
                暂无邮箱账号，请先添加至少一个可用发信账号。
              </Card>
            ) : (
              <div className="space-y-3">
                {accounts.map((account) => (
                  <Card key={account.id} className="flex flex-col gap-4 p-4 md:flex-row md:items-center md:justify-between">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{account.email_address}</span>
                        <Badge variant="outline">{account.provider_type.toUpperCase()}</Badge>
                        <Badge variant={HEALTH_MAP[account.health_status]?.variant || "secondary"}>
                          {HEALTH_MAP[account.health_status]?.label || account.health_status}
                        </Badge>
                        {!account.is_active && <Badge variant="destructive">已禁用</Badge>}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        今日已发 {account.sent_today}/{account.daily_limit}，预热阶段 {account.warmup_stage}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="ghost" size="sm" onClick={() => handleVerify(account.id)}>
                        <ShieldCheck className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleTest(account.id)}>
                        <TestTube className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(account.id)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            <Dialog open={addOpen} onOpenChange={setAddOpen}>
              <DialogContent className="max-w-xl">
                <DialogHeader>
                  <DialogTitle>添加邮箱账号</DialogTitle>
                </DialogHeader>

                <div className="max-h-[75vh] overflow-y-auto space-y-4 pr-1">
                  <div>
                    <Label>邮箱地址</Label>
                    <Input
                      value={form.email_address}
                      onChange={(event) => updateForm({ email_address: event.target.value })}
                      type="email"
                    />
                  </div>

                  <div>
                    <Label>显示名称</Label>
                    <Input
                      value={form.display_name}
                      onChange={(event) => updateForm({ display_name: event.target.value })}
                      placeholder="如：Brand Team"
                    />
                  </div>

                  <div>
                    <Label>服务商</Label>
                    <select
                      value={form.provider_type}
                      onChange={(event) =>
                        updateForm({ provider_type: event.target.value as ProviderType })
                      }
                      className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                    >
                      <option value="ses">Amazon SES</option>
                      <option value="sendgrid">SendGrid</option>
                      <option value="smtp">SMTP</option>
                    </select>
                  </div>

                  <div>
                    <Label>每日发送上限</Label>
                    <Input
                      value={form.daily_limit}
                      onChange={(event) => updateForm({ daily_limit: event.target.value })}
                      type="number"
                    />
                  </div>

                  {providerType === "ses" && (
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="md:col-span-2">
                        <Label>Region</Label>
                        <Input
                          value={form.ses_region}
                          onChange={(event) => updateForm({ ses_region: event.target.value })}
                        />
                      </div>
                      <div>
                        <Label>Access Key ID</Label>
                        <Input
                          value={form.ses_access_key_id}
                          onChange={(event) =>
                            updateForm({ ses_access_key_id: event.target.value })
                          }
                        />
                      </div>
                      <div>
                        <Label>Secret Access Key</Label>
                        <Input
                          value={form.ses_secret_access_key}
                          onChange={(event) =>
                            updateForm({ ses_secret_access_key: event.target.value })
                          }
                          type="password"
                        />
                      </div>
                    </div>
                  )}

                  {providerType === "sendgrid" && (
                    <div>
                      <Label>API Key</Label>
                      <Input
                        value={form.sendgrid_api_key}
                        onChange={(event) => updateForm({ sendgrid_api_key: event.target.value })}
                        type="password"
                      />
                    </div>
                  )}

                  {providerType === "smtp" && (
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="md:col-span-2">
                        <Label>Host</Label>
                        <Input
                          value={form.smtp_host}
                          onChange={(event) => updateForm({ smtp_host: event.target.value })}
                        />
                      </div>
                      <div>
                        <Label>Port</Label>
                        <Input
                          value={form.smtp_port}
                          onChange={(event) => updateForm({ smtp_port: event.target.value })}
                          type="number"
                        />
                      </div>
                      <div>
                        <Label>Username</Label>
                        <Input
                          value={form.smtp_username}
                          onChange={(event) => updateForm({ smtp_username: event.target.value })}
                        />
                      </div>
                      <div>
                        <Label>Password</Label>
                        <Input
                          value={form.smtp_password}
                          onChange={(event) => updateForm({ smtp_password: event.target.value })}
                          type="password"
                        />
                      </div>
                      <label className="flex items-center gap-2 text-sm md:col-span-2">
                        <input
                          type="checkbox"
                          checked={form.smtp_use_tls}
                          onChange={(event) =>
                            updateForm({ smtp_use_tls: event.target.checked })
                          }
                        />
                        使用 TLS / STARTTLS
                      </label>
                    </div>
                  )}

                  <Button onClick={handleAddAccount} className="w-full" disabled={saving}>
                    {saving ? "保存中..." : "创建邮箱账号"}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </TabsContent>

          <TabsContent value="woto" className="space-y-4">
            <Card className="space-y-5 p-6">
              <div>
                <h3 className="text-lg font-semibold">Woto API 配置</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  配置 WotoHub API Key 和运行环境。沙箱环境用于测试，不消耗真实额度。
                </p>
              </div>

              {wotoSettings && (
                <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-muted/30 p-3 text-sm">
                  <span className="text-muted-foreground">当前 Key：</span>
                  <span className="font-mono font-medium">
                    {wotoSettings.has_api_key ? wotoSettings.api_key_preview : "未配置"}
                  </span>
                  <Badge variant={wotoSettings.use_sandbox ? "secondary" : "outline"}>
                    {wotoSettings.use_sandbox ? "沙箱模式" : "生产模式"}
                  </Badge>
                  <span className="text-xs text-muted-foreground break-all">
                    当前请求地址：{wotoSettings.effective_base_url}
                  </span>
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <Label>API Key</Label>
                  <Input
                    type="password"
                    value={wotoForm.api_key}
                    onChange={(e) => updateWotoForm({ api_key: e.target.value })}
                    placeholder={wotoSettings?.has_api_key ? "留空保持不变，输入新值则替换" : "输入 Woto API Key"}
                  />
                </div>

                <div>
                  <Label>生产环境 Base URL</Label>
                  <Input
                    value={wotoForm.production_base_url}
                    onChange={(e) => updateWotoForm({ production_base_url: e.target.value })}
                    placeholder={WOTO_PROD_URL}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    默认：{WOTO_PROD_URL}
                  </p>
                </div>

                <div>
                  <Label>沙箱环境 Base URL</Label>
                  <Input
                    value={wotoForm.sandbox_base_url}
                    onChange={(e) => updateWotoForm({ sandbox_base_url: e.target.value })}
                    placeholder="https://sandbox-api.wotohub.com/api-gateway"
                  />
                </div>

                <label className="flex items-center gap-3 rounded-xl border p-3 text-sm cursor-pointer hover:bg-muted/30 transition-colors">
                  <input
                    type="checkbox"
                    checked={wotoForm.use_sandbox}
                    onChange={(e) => updateWotoForm({ use_sandbox: e.target.checked })}
                    className="h-4 w-4 rounded"
                  />
                  <div>
                    <p className="font-medium">启用沙箱模式</p>
                    <p className="text-xs text-muted-foreground">
                      开启后，所有 Woto API 请求（包括达人发现同步）将发往沙箱 URL
                    </p>
                  </div>
                </label>
              </div>

              {wotoMessage && (
                <p className="text-sm text-muted-foreground">{wotoMessage}</p>
              )}

              <Button onClick={handleSaveWoto} disabled={wotoSaving} className="w-full">
                {wotoSaving ? "保存中..." : "保存 Woto 配置"}
              </Button>
            </Card>

            <Card className="space-y-4 p-6">
              <div>
                <h3 className="font-semibold">连接测试</h3>
                <p className="text-sm text-muted-foreground">
                  向指定环境发送真实 POST 请求，验证 API Key 是否有效。
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button
                  variant="outline"
                  onClick={() => handleTestWoto("production")}
                  disabled={wotoTesting !== null}
                >
                  <TestTube className="mr-2 h-4 w-4" />
                  {wotoTesting === "production" ? "测试中..." : "测试生产环境"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleTestWoto("sandbox")}
                  disabled={wotoTesting !== null || !wotoForm.sandbox_base_url}
                >
                  <TestTube className="mr-2 h-4 w-4" />
                  {wotoTesting === "sandbox" ? "测试中..." : "测试沙箱环境"}
                </Button>
              </div>

              {!wotoForm.sandbox_base_url && (
                <p className="text-xs text-muted-foreground">
                  填写沙箱 Base URL 后才能测试沙箱环境
                </p>
              )}

              {wotoTestResult && (
                <div
                  className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${
                    wotoTestResult.success
                      ? "border-green-200 bg-green-50 text-green-800"
                      : "border-red-200 bg-red-50 text-red-800"
                  }`}
                >
                  {wotoTestResult.success ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  ) : (
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  )}
                  <div className="space-y-1">
                    <p className="font-medium">
                      {wotoTestResult.success ? "连接成功" : "连接失败"} ·{" "}
                      {wotoTestResult.environment === "sandbox" ? "沙箱" : "生产"}环境
                    </p>
                    {wotoTestResult.success && wotoTestResult.remain_quota !== null && (
                      <p>剩余额度：{wotoTestResult.remain_quota}</p>
                    )}
                    {wotoTestResult.base_url && (
                      <p className="font-mono text-xs break-all opacity-70">
                        {wotoTestResult.base_url}
                      </p>
                    )}
                    {wotoTestResult.error && <p>{wotoTestResult.error}</p>}
                  </div>
                </div>
              )}
            </Card>
          </TabsContent>

          <TabsContent value="ai" className="space-y-4">
            {/* Status bar */}
            {aiSettings && (
              <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-muted/30 px-4 py-3 text-sm">
                <Sparkles className="h-4 w-4 text-primary shrink-0" />
                <span className="font-medium">
                  {aiSettings.catalog.find((p) => p.id === aiSettings.provider)?.name ?? aiSettings.provider}
                </span>
                {aiSettings.model && (
                  <Badge variant="outline" className="font-mono text-xs">{aiSettings.model}</Badge>
                )}
                <Badge variant={aiSettings.has_api_key ? "default" : "destructive"}>
                  {aiSettings.has_api_key ? `Key: ${aiSettings.api_key_preview}` : "未配置 Key"}
                </Badge>
              </div>
            )}

            <Card className="space-y-5 p-6">
              <div>
                <h3 className="text-base font-semibold">AI 服务商配置</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  选择任意 LLM 服务商。团队配置优先于 .env 环境变量，用于邮件分类、起草回复和模板转换。
                </p>
              </div>

              <div className="space-y-4">
                {/* Provider selector */}
                <div>
                  <Label>服务商</Label>
                  <div className="relative mt-1">
                    <select
                      value={aiForm.provider}
                      onChange={(e) => {
                        const id = e.target.value;
                        const entry = aiSettings?.catalog.find((p) => p.id === id);
                        setAIForm((f) => ({
                          ...f,
                          provider: id,
                          model: entry?.models[0] ?? "",
                          base_url: entry?.base_url ?? "",
                          azure_endpoint: "",
                          api_version: "2024-02-01",
                          aws_region: "us-east-1",
                          aws_access_key_id: "",
                          aws_secret_access_key: "",
                        }));
                        setAITestResult(null);
                      }}
                      className="h-9 w-full appearance-none rounded-lg border border-input bg-transparent pl-3 pr-8 text-sm"
                    >
                      {(aiSettings?.catalog ?? [])
                        .reduce<{ label: string; entries: ProviderCatalogEntry[] }[]>((groups, p) => {
                          const regionLabel = p.region === "domestic" ? "国内" : p.region === "international" ? "国际" : p.region === "local" ? "本地" : "其他";
                          const g = groups.find((x) => x.label === regionLabel);
                          if (g) g.entries.push(p);
                          else groups.push({ label: regionLabel, entries: [p] });
                          return groups;
                        }, [])
                        .map((group) => (
                          <optgroup key={group.label} label={group.label}>
                            {group.entries.map((p) => (
                              <option key={p.id} value={p.id}>{p.name}</option>
                            ))}
                          </optgroup>
                        ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  </div>
                  {selectedProviderEntry?.note && (
                    <p className="mt-1 text-xs text-amber-600">{selectedProviderEntry.note}</p>
                  )}
                </div>

                {/* Model */}
                <div>
                  <Label>模型</Label>
                  {providerHasPresetModels ? (
                    <div className="relative mt-1">
                      <select
                        value={aiForm.model}
                        onChange={(e) => setAIForm((f) => ({ ...f, model: e.target.value }))}
                        className="h-9 w-full appearance-none rounded-lg border border-input bg-transparent pl-3 pr-8 text-sm"
                      >
                        {selectedProviderEntry?.models.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    </div>
                  ) : (
                    <Input
                      className="mt-1"
                      value={aiForm.model}
                      onChange={(e) => setAIForm((f) => ({ ...f, model: e.target.value }))}
                      placeholder="输入模型名称，例如 llama3.2、deepseek-chat"
                    />
                  )}
                </div>

                {/* ── api_key auth ─────────────────────────────────────── */}
                {authType === "api_key" && (
                  <div>
                    <Label>API Key</Label>
                    <Input
                      className="mt-1"
                      type="password"
                      value={aiForm.api_key}
                      onChange={(e) => setAIForm((f) => ({ ...f, api_key: e.target.value }))}
                      placeholder={aiSettings?.has_api_key ? "留空保持不变，输入新值则替换" : "输入 API Key"}
                    />
                  </div>
                )}

                {/* Base URL (api_key providers except claude) */}
                {showBaseUrl && (
                  <div>
                    <Label>
                      Base URL
                      <span className="ml-1 text-xs text-muted-foreground">
                        {aiForm.provider === "custom" || aiForm.provider === "ollama" || aiForm.provider === "vertex"
                          ? "（必填）"
                          : "（可选，留空使用默认值）"}
                      </span>
                    </Label>
                    <Input
                      className="mt-1 font-mono text-xs"
                      value={aiForm.base_url}
                      onChange={(e) => setAIForm((f) => ({ ...f, base_url: e.target.value }))}
                      placeholder={selectedProviderEntry?.base_url || "https://api.example.com/v1"}
                    />
                    {selectedProviderEntry?.base_url && (
                      <p className="mt-1 text-xs text-muted-foreground">默认：{selectedProviderEntry.base_url}</p>
                    )}
                  </div>
                )}

                {/* ── Azure auth ────────────────────────────────────────── */}
                {authType === "azure" && (
                  <>
                    <div>
                      <Label>Azure Endpoint <span className="text-destructive">*</span></Label>
                      <Input
                        className="mt-1 font-mono text-xs"
                        value={aiForm.azure_endpoint}
                        onChange={(e) => setAIForm((f) => ({ ...f, azure_endpoint: e.target.value }))}
                        placeholder="https://myresource.openai.azure.com"
                      />
                      {savedAzureEndpoint && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          已保存：{savedAzureEndpoint}
                        </p>
                      )}
                    </div>
                    <div>
                      <Label>API Key <span className="text-destructive">*</span></Label>
                      <Input
                        className="mt-1"
                        type="password"
                        value={aiForm.api_key}
                        onChange={(e) => setAIForm((f) => ({ ...f, api_key: e.target.value }))}
                        placeholder={aiSettings?.has_api_key ? "留空保持不变" : "Azure API Key"}
                      />
                    </div>
                    <div>
                      <Label>API Version</Label>
                      <Input
                        className="mt-1"
                        value={aiForm.api_version}
                        onChange={(e) => setAIForm((f) => ({ ...f, api_version: e.target.value }))}
                        placeholder="2024-02-01"
                      />
                    </div>
                  </>
                )}

                {/* ── AWS Bedrock auth ──────────────────────────────────── */}
                {authType === "aws" && (
                  <>
                    <div>
                      <Label>AWS Region <span className="text-destructive">*</span></Label>
                      <Input
                        className="mt-1"
                        value={aiForm.aws_region}
                        onChange={(e) => setAIForm((f) => ({ ...f, aws_region: e.target.value }))}
                        placeholder="us-east-1"
                      />
                    </div>
                    <div>
                      <Label>Access Key ID <span className="text-destructive">*</span></Label>
                      <Input
                        className="mt-1"
                        value={aiForm.aws_access_key_id}
                        onChange={(e) => setAIForm((f) => ({ ...f, aws_access_key_id: e.target.value }))}
                        placeholder={aiSettings?.extra?.has_aws_access_key_id ? "留空保持不变" : "AKIAIOSFODNN7EXAMPLE"}
                      />
                    </div>
                    <div>
                      <Label>Secret Access Key <span className="text-destructive">*</span></Label>
                      <Input
                        className="mt-1"
                        type="password"
                        value={aiForm.aws_secret_access_key}
                        onChange={(e) => setAIForm((f) => ({ ...f, aws_secret_access_key: e.target.value }))}
                        placeholder={aiSettings?.extra?.has_aws_secret_access_key ? "留空保持不变" : "wJalrXUtnFEMI/K7MDENG/..."}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      需要先在 AWS IAM 授权 <code className="rounded bg-muted px-1">bedrock:InvokeModel</code> 权限，并在 Bedrock 控制台开启目标模型的访问权限。
                    </p>
                  </>
                )}
              </div>

              {aiMessage && (
                <p className="text-sm text-muted-foreground">{aiMessage}</p>
              )}

              <div className="flex flex-wrap gap-3">
                <Button onClick={handleSaveAI} disabled={aiSaving}>
                  {aiSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />保存中...</> : "保存配置"}
                </Button>
                <Button variant="outline" onClick={handleTestAI} disabled={aiTesting || !aiForm.model}>
                  {aiTesting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />测试中...</> : <><TestTube className="mr-2 h-4 w-4" />测试连接</>}
                </Button>
                {selectedProviderEntry?.docs && (
                  <a
                    href={selectedProviderEntry.docs}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-primary hover:underline self-center"
                  >
                    查看官方文档 ↗
                  </a>
                )}
              </div>

              {aiTestResult && (
                <div className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${
                  aiTestResult.success
                    ? "border-green-200 bg-green-50 text-green-800"
                    : "border-red-200 bg-red-50 text-red-800"
                }`}>
                  {aiTestResult.success
                    ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                    : <XCircle className="mt-0.5 h-4 w-4 shrink-0" />}
                  <div className="space-y-1 min-w-0">
                    <p className="font-medium">
                      {aiTestResult.success ? "✅ 连接成功" : "❌ 连接失败"} · {aiTestResult.provider} / {aiTestResult.model}
                    </p>
                    {aiTestResult.ping_response && (
                      <p className="font-mono text-xs opacity-80">模型回复：{aiTestResult.ping_response}</p>
                    )}
                    {aiTestResult.error && <p className="break-all">{aiTestResult.error}</p>}
                  </div>
                </div>
              )}
            </Card>

            {/* Provider catalog grid */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold text-sm">全部支持的服务商（{aiSettings?.catalog.length ?? 0} 个）</h3>
              {(["international", "domestic", "local", "custom"] as const).map((region) => {
                const entries = (aiSettings?.catalog ?? []).filter((p) => p.region === region);
                if (entries.length === 0) return null;
                const label = { international: "🌐 国际", domestic: "🇨🇳 国内", local: "💻 本地", custom: "⚙️ 其他" }[region];
                return (
                  <div key={region} className="mb-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
                    <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                      {entries.map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => {
                            setAIForm((f) => ({ ...f, provider: p.id, model: p.models[0] ?? "", base_url: p.base_url ?? "" }));
                            setAITestResult(null);
                          }}
                          className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50 ${aiForm.provider === p.id ? "border-primary bg-primary/5" : ""}`}
                        >
                          <p className="font-medium leading-tight">{p.name}</p>
                          <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
                            {p.base_url || (p.id === "claude" ? "Anthropic SDK" : "—")}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </Card>
          </TabsContent>

          <TabsContent value="suppression" className="space-y-4">
            <Card className="space-y-4 p-6">
              <div>
                <h3 className="text-lg font-semibold">抑制名单</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  退信、被投诉、退订的地址会自动加入，系统不会再向这些地址发送任何邮件。
                  这是保护发信域名信誉、提高送达率的核心机制。
                </p>
              </div>

              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-[260px] flex-1">
                  <Label>手动添加邮箱</Label>
                  <Input
                    type="email"
                    value={suppressionEmail}
                    onChange={(e) => setSuppressionEmail(e.target.value)}
                    placeholder="do-not-email@example.com"
                  />
                </div>
                <Button onClick={handleAddSuppression} disabled={suppressionBusy || !suppressionEmail.trim()}>
                  <Plus className="mr-2 h-4 w-4" />
                  加入名单
                </Button>
              </div>

              {suppressionMessage && (
                <p className="text-sm text-muted-foreground">{suppressionMessage}</p>
              )}

              {suppressions.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  名单为空。退信/投诉/退订发生时会自动写入。
                </p>
              ) : (
                <div className="space-y-2">
                  {suppressions.map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"
                    >
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-mono text-sm">{item.email}</span>
                        <Badge variant={item.reason === "manual" ? "outline" : "destructive"}>
                          {SUPPRESSION_REASON_MAP[item.reason] || item.reason}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {new Date(item.created_at).toLocaleString("zh-CN")}
                        </span>
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => handleRemoveSuppression(item.id)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </TabsContent>

          <TabsContent value="team">
            <Card className="space-y-3 p-6">
              <h3 className="text-lg font-semibold">团队</h3>
              <p className="text-sm text-muted-foreground">
                当前版本已经支持会话分配字段，但团队成员管理 UI 还未开放。
              </p>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}

export default function SettingsPage() {
  return (
    <Suspense
      fallback={
        <AppLayout>
          <p className="text-sm text-muted-foreground">加载中...</p>
        </AppLayout>
      }
    >
      <SettingsPageContent />
    </Suspense>
  );
}
