"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import api from "@/lib/api";
import { INFLUENCER_STATUS_MAP } from "@/lib/constants";
import type { Client, ClientRelationshipType, ClientStatus } from "@/types";
import { ArrowLeft, Building2, Mail, Phone, Trash2 } from "lucide-react";

const RELATIONSHIP_LABELS: Record<ClientRelationshipType, string> = {
  buyer: "批发/零售采购商",
  agency_prospect: "代理服务客户",
  partner: "品牌合作伙伴",
};

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const clientId = String(params.id);

  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingStatus, setSavingStatus] = useState(false);

  const loadClient = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<Client>(`/clients/${clientId}`);
      setClient(res.data);
    } catch {
      setError("客户不存在或加载失败");
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    if (clientId) void loadClient();
  }, [clientId, loadClient]);

  const updateStatus = async (status: ClientStatus) => {
    if (!client) return;
    setSavingStatus(true);
    try {
      const res = await api.put<Client>(`/clients/${client.id}`, { status });
      setClient(res.data);
    } catch {
      alert("更新状态失败");
    } finally {
      setSavingStatus(false);
    }
  };

  const handleDelete = async () => {
    if (!client || !confirm(`确定删除客户 ${client.company_name} 吗？`)) return;
    try {
      await api.delete(`/clients/${client.id}`);
      router.push("/clients");
    } catch {
      alert("删除失败");
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="space-y-4">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-48 w-full" />
        </div>
      </AppLayout>
    );
  }

  if (!client) {
    return (
      <AppLayout>
        <p className="text-destructive">{error || "客户不存在"}</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push("/clients")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回
          </Button>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold">{client.company_name}</h2>
            <Badge variant="outline">{RELATIONSHIP_LABELS[client.relationship_type]}</Badge>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="space-y-4 p-6 lg:col-span-2">
            <h3 className="text-lg font-semibold">基本信息</h3>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-muted-foreground">联系人</dt>
                <dd>{client.contact_name || "-"}{client.title ? ` · ${client.title}` : ""}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">行业</dt>
                <dd>{client.industry || "-"}</dd>
              </div>
              <div>
                <dt className="flex items-center gap-1 text-muted-foreground"><Mail className="h-3.5 w-3.5" />邮箱</dt>
                <dd>{client.email || "-"}</dd>
              </div>
              <div>
                <dt className="flex items-center gap-1 text-muted-foreground"><Phone className="h-3.5 w-3.5" />电话</dt>
                <dd>{client.phone || "-"}</dd>
              </div>
              <div>
                <dt className="flex items-center gap-1 text-muted-foreground"><Building2 className="h-3.5 w-3.5" />网站</dt>
                <dd className="truncate">{client.website || "-"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">来源</dt>
                <dd>{client.source === "csv_import" ? "CSV/Excel 导入" : "手动创建"}</dd>
              </div>
            </dl>
            {client.notes && (
              <div>
                <dt className="text-sm text-muted-foreground">备注</dt>
                <dd className="mt-1 whitespace-pre-wrap text-sm">{client.notes}</dd>
              </div>
            )}
          </Card>

          <Card className="space-y-4 p-6">
            <h3 className="text-lg font-semibold">状态</h3>
            <Select value={client.status} onValueChange={(v) => v && updateStatus(v as ClientStatus)}>
              <SelectTrigger disabled={savingStatus}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(INFLUENCER_STATUS_MAP).map(([value, meta]) => (
                  <SelectItem key={value} value={value}>{meta.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="destructive" className="w-full" onClick={handleDelete}>
              <Trash2 className="mr-2 h-4 w-4" />
              删除客户
            </Button>
          </Card>
        </div>

        <Card className="p-6">
          <h3 className="mb-2 text-lg font-semibold">建联记录</h3>
          <p className="text-sm text-muted-foreground">
            B端客户建联活动与收件箱即将上线，届时该客户的邮件往来记录将显示在这里。
          </p>
        </Card>
      </div>
    </AppLayout>
  );
}
