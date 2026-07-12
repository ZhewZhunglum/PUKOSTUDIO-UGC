"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { downloadExport } from "@/lib/download";
import { useDebouncedValue } from "@/lib/hooks";
import { INFLUENCER_STATUS_MAP } from "@/lib/constants";
import type { Client, ClientRelationshipType, PaginatedResponse } from "@/types";
import { Download, Pencil, Plus, Search, Trash2, Upload } from "lucide-react";

const RELATIONSHIP_LABELS: Record<ClientRelationshipType, string> = {
  buyer: "批发/零售采购商",
  agency_prospect: "代理服务客户",
  partner: "品牌合作伙伴",
};

type FormState = {
  company_name: string;
  contact_name: string;
  title: string;
  email: string;
  phone: string;
  industry: string;
  website: string;
  relationship_type: ClientRelationshipType;
  notes: string;
};

const EMPTY_FORM: FormState = {
  company_name: "",
  contact_name: "",
  title: "",
  email: "",
  phone: "",
  industry: "",
  website: "",
  relationship_type: "buyer",
  notes: "",
};

export default function ClientsPage() {
  const [data, setData] = useState<PaginatedResponse<Client> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [statusFilter, setStatusFilter] = useState("");
  const [relationshipFilter, setRelationshipFilter] = useState("");
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<Client | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reqIdRef = useRef(0);

  const fetchClients = useCallback(async () => {
    const reqId = ++reqIdRef.current;
    setLoading(true);
    const params: Record<string, string | number> = { page, per_page: 20 };
    if (debouncedSearch) params.search = debouncedSearch;
    if (statusFilter) params.status = statusFilter;
    if (relationshipFilter) params.relationship_type = relationshipFilter;

    try {
      const res = await api.get("/clients", { params });
      if (reqId === reqIdRef.current) setData(res.data);
    } catch {
      if (reqId === reqIdRef.current) setErrorMsg("客户列表加载失败，请稍后重试");
    } finally {
      if (reqId === reqIdRef.current) setLoading(false);
    }
  }, [page, debouncedSearch, statusFilter, relationshipFilter]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  const updateForm = (patch: Partial<FormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const openCreate = () => {
    setSelected(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (client: Client) => {
    setSelected(client);
    setForm({
      company_name: client.company_name,
      contact_name: client.contact_name ?? "",
      title: client.title ?? "",
      email: client.email ?? "",
      phone: client.phone ?? "",
      industry: client.industry ?? "",
      website: client.website ?? "",
      relationship_type: client.relationship_type,
      notes: client.notes ?? "",
    });
    setDialogOpen(true);
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setErrorMsg(null);

    const name = file.name.toLowerCase();
    if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) {
      setErrorMsg("导入仅支持 CSV 或 Excel(.xlsx)");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/clients/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setErrorMsg(`导入完成：${res.data.imported} 成功，${res.data.skipped} 跳过`);
      await fetchClients();
    } catch {
      setErrorMsg("导入失败，请确认文件格式正确");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleExport = async (fmt: "csv" | "xlsx") => {
    try {
      await downloadExport(
        "/clients/export",
        {
          format: fmt,
          search: search || undefined,
          status: statusFilter || undefined,
          relationship_type: relationshipFilter || undefined,
        },
        `clients.${fmt}`,
      );
    } catch {
      setErrorMsg("导出失败，请稍后重试");
    }
  };

  const handleSave = async () => {
    if (!form.company_name.trim()) {
      setErrorMsg("请填写公司名称");
      return;
    }
    setSaving(true);
    setErrorMsg(null);
    const payload = {
      company_name: form.company_name.trim(),
      contact_name: form.contact_name.trim() || null,
      title: form.title.trim() || null,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      industry: form.industry.trim() || null,
      website: form.website.trim() || null,
      relationship_type: form.relationship_type,
      notes: form.notes.trim() || null,
    };
    try {
      if (selected) {
        await api.put(`/clients/${selected.id}`, payload);
      } else {
        await api.post("/clients", payload);
      }
      setDialogOpen(false);
      setSelected(null);
      setForm(EMPTY_FORM);
      await fetchClients();
    } catch {
      setErrorMsg(selected ? "更新客户失败" : "添加客户失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (client: Client) => {
    if (!confirm(`确定删除客户 ${client.company_name} 吗？`)) return;
    try {
      await api.delete(`/clients/${client.id}`);
      await fetchClients();
    } catch {
      setErrorMsg("删除客户失败");
    }
  };

  return (
    <AppLayout>
      <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="ds-between" style={{ marginBottom: 4 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>资产 · B端客户</div>
            <h1 className="ds-h1">客户管理</h1>
            <p className="ds-body" style={{ marginTop: 4, color: "var(--ink-3)" }}>
              共 <b className="ds-primary ds-num">{data?.total ?? 0}</b> 位客户 · 批发/零售采购商、代理服务客户、品牌合作伙伴
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
              <button className="ds-btn ds-btn-outline ds-btn-sm" onClick={() => fileInputRef.current?.click()}>
                <Upload className="h-[14px] w-[14px]" />导入 CSV/Excel
              </button>
              <button className="ds-btn ds-btn-primary ds-btn-sm" onClick={openCreate}>
                <Plus className="h-[14px] w-[14px]" />添加客户
              </button>
            </div>
          </div>
        </div>

        <div className="ds-card ds-card-pad-sm">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索公司名称、联系人或邮箱..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select
              value={relationshipFilter || "all"}
              onValueChange={(v) => { setRelationshipFilter(!v || v === "all" ? "" : v); setPage(1); }}
            >
              <SelectTrigger className="w-full md:w-44">
                <SelectValue placeholder="关系类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部类型</SelectItem>
                {(Object.keys(RELATIONSHIP_LABELS) as ClientRelationshipType[]).map((rt) => (
                  <SelectItem key={rt} value={rt}>{RELATIONSHIP_LABELS[rt]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusFilter || "all"}
              onValueChange={(v) => { setStatusFilter(!v || v === "all" ? "" : v); setPage(1); }}
            >
              <SelectTrigger className="w-full md:w-40">
                <SelectValue placeholder="状态筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                {Object.entries(INFLUENCER_STATUS_MAP).map(([value, meta]) => (
                  <SelectItem key={value} value={value}>{meta.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="ds-card" style={{ overflow: "hidden" }}>
          <table className="ds-table">
            <thead>
              <tr>
                <th>公司</th>
                <th>联系人</th>
                <th>邮箱</th>
                <th>关系类型</th>
                <th>行业</th>
                <th>来源</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    <td><Skeleton className="h-4 w-28" /></td>
                    <td><Skeleton className="h-4 w-24" /></td>
                    <td><Skeleton className="h-4 w-36" /></td>
                    <td><Skeleton className="h-5 w-20 rounded-full" /></td>
                    <td><Skeleton className="h-4 w-16" /></td>
                    <td><Skeleton className="h-4 w-14" /></td>
                    <td><Skeleton className="h-5 w-16 rounded-full" /></td>
                    <td><Skeleton className="h-6 w-14 rounded" /></td>
                  </tr>
                ))
              ) : !data || data.items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-muted-foreground">
                    暂无客户数据，点击&quot;添加客户&quot;或&quot;导入&quot;开始。
                  </td>
                </tr>
              ) : (
                data.items.map((client) => (
                  <tr key={client.id} className="group">
                    <td>
                      <Link href={`/clients/${client.id}`} className="font-medium hover:underline">
                        {client.company_name}
                      </Link>
                    </td>
                    <td className="text-sm text-muted-foreground">
                      {client.contact_name || "–"}{client.title ? ` · ${client.title}` : ""}
                    </td>
                    <td className="text-sm text-muted-foreground">{client.email || "–"}</td>
                    <td>
                      <Badge variant="outline" className="text-xs">
                        {RELATIONSHIP_LABELS[client.relationship_type]}
                      </Badge>
                    </td>
                    <td className="text-sm">{client.industry || "–"}</td>
                    <td className="text-sm text-muted-foreground">
                      {client.source === "csv_import" ? "CSV" : "手动"}
                    </td>
                    <td>
                      <Badge variant={INFLUENCER_STATUS_MAP[client.status]?.variant || "secondary"}>
                        {INFLUENCER_STATUS_MAP[client.status]?.label || client.status}
                      </Badge>
                    </td>
                    <td>
                      <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <Button variant="ghost" size="sm" onClick={() => openEdit(client)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(client)}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {data && data.pages > 1 && (
            <div className="flex items-center justify-between border-t px-4 py-3">
              <span className="text-sm text-muted-foreground">
                共 {data.total} 条，第 {data.page}/{data.pages} 页
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  上一页
                </Button>
                <Button variant="outline" size="sm" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>
                  下一页
                </Button>
              </div>
            </div>
          )}
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{selected ? "编辑客户" : "添加客户"}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[75vh] overflow-y-auto space-y-4 pr-1">
              <div>
                <Label>公司名称 *</Label>
                <Input
                  value={form.company_name}
                  onChange={(e) => updateForm({ company_name: e.target.value })}
                  placeholder="达人所在公司或品牌名称"
                />
              </div>
              <div>
                <Label>关系类型</Label>
                <select
                  value={form.relationship_type}
                  onChange={(e) => updateForm({ relationship_type: e.target.value as ClientRelationshipType })}
                  className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                >
                  {(Object.keys(RELATIONSHIP_LABELS) as ClientRelationshipType[]).map((rt) => (
                    <option key={rt} value={rt}>{RELATIONSHIP_LABELS[rt]}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>联系人</Label>
                  <Input
                    value={form.contact_name}
                    onChange={(e) => updateForm({ contact_name: e.target.value })}
                  />
                </div>
                <div>
                  <Label>职位</Label>
                  <Input
                    value={form.title}
                    onChange={(e) => updateForm({ title: e.target.value })}
                    placeholder="采购经理"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>邮箱</Label>
                  <Input
                    type="email"
                    value={form.email}
                    onChange={(e) => updateForm({ email: e.target.value })}
                  />
                </div>
                <div>
                  <Label>电话</Label>
                  <Input
                    value={form.phone}
                    onChange={(e) => updateForm({ phone: e.target.value })}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>行业</Label>
                  <Input
                    value={form.industry}
                    onChange={(e) => updateForm({ industry: e.target.value })}
                    placeholder="健身/零售/电商..."
                  />
                </div>
                <div>
                  <Label>网站</Label>
                  <Input
                    value={form.website}
                    onChange={(e) => updateForm({ website: e.target.value })}
                    placeholder="https://..."
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
                {saving ? "保存中..." : selected ? "保存修改" : "创建客户"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
