"use client";

import { useCallback, useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { HtmlEditor } from "@/components/editor/HtmlEditor";
import api from "@/lib/api";
import { uploadInlineImage } from "@/lib/uploads";
import type { ClientConversation, ClientConversationDetail } from "@/types";
import { Inbox, Send } from "lucide-react";

type Bucket = "all" | "needs_review" | "replied";

const BUCKET_LABELS: Record<Bucket, string> = {
  all: "全部",
  needs_review: "待审核",
  replied: "已回复",
};

export default function ClientInboxPage() {
  const [bucket, setBucket] = useState<Bucket>("all");
  const [conversations, setConversations] = useState<ClientConversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<ClientConversationDetail | null>(null);
  const [manualSubject, setManualSubject] = useState("");
  const [manualBody, setManualBody] = useState("");
  const [needsReview, setNeedsReview] = useState(true);
  const [assignedTo, setAssignedTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadConversations = useCallback(async (nextBucket: Bucket) => {
    setLoading(true);
    try {
      const response = await api.get("/client-conversations", {
        params: { bucket: nextBucket },
      });
      const items: ClientConversation[] = response.data;
      setConversations(items);
      setSelectedId((currentSelectedId) =>
        currentSelectedId && items.some((item) => item.id === currentSelectedId)
          ? currentSelectedId
          : items[0]?.id ?? null
      );
    } catch (requestError) {
      console.error(requestError);
      setMessage("会话列表加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadConversationDetail = useCallback(async (conversationId: string) => {
    try {
      const response = await api.get(`/client-conversations/${conversationId}`);
      const detail: ClientConversationDetail = response.data;
      setSelectedConversation(detail);
      setNeedsReview(detail.needs_review);
      setAssignedTo(detail.assigned_to || "");
      setManualSubject("");
      setManualBody("");
    } catch (requestError) {
      console.error(requestError);
      setMessage("会话详情加载失败");
    }
  }, []);

  useEffect(() => {
    void loadConversations(bucket);
  }, [bucket, loadConversations]);

  useEffect(() => {
    if (selectedId) {
      void loadConversationDetail(selectedId);
    } else {
      setSelectedConversation(null);
    }
  }, [selectedId, loadConversationDetail]);

  const refreshSelected = async () => {
    if (!selectedId) return;
    await Promise.all([loadConversationDetail(selectedId), loadConversations(bucket)]);
  };

  const saveConversationReview = async () => {
    if (!selectedConversation) return;
    setWorking(true);
    try {
      await api.patch(`/client-conversations/${selectedConversation.id}`, {
        needs_review: needsReview,
        assigned_to: assignedTo || null,
      });
      await refreshSelected();
      setMessage("会话审核结果已保存");
    } catch (requestError) {
      console.error(requestError);
      setMessage("保存会话审核结果失败");
    } finally {
      setWorking(false);
    }
  };

  const sendManualReply = async () => {
    if (!selectedConversation || !manualBody.trim()) return;
    setWorking(true);
    try {
      await api.post(`/client-conversations/${selectedConversation.id}/send-reply`, {
        subject: manualSubject || null,
        body_html: manualBody,
      });
      await refreshSelected();
      setManualBody("");
      setMessage("人工回复已发送");
    } catch (requestError) {
      console.error(requestError);
      setMessage("发送人工回复失败");
    } finally {
      setWorking(false);
    }
  };

  return (
    <AppLayout>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="ds-between" style={{ marginBottom: 4 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>B端客户</div>
            <h1 className="h-1">客户收件箱</h1>
            <p className="ds-body" style={{ marginTop: 4, color: "var(--ink-3)" }}>
              B 端客户往来邮件的人工回复入口，不含 AI 草稿辅助。
            </p>
          </div>
          {message && <p className="ds-caption" style={{ color: "var(--ink-3)" }}>{message}</p>}
        </div>

        <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)_320px]">
          <Card className="overflow-hidden p-0">
            <div className="border-b p-4">
              <div className="flex flex-wrap gap-2">
                {(Object.keys(BUCKET_LABELS) as Bucket[]).map((item) => (
                  <Button
                    key={item}
                    variant={bucket === item ? "default" : "outline"}
                    size="sm"
                    onClick={() => setBucket(item)}
                  >
                    {BUCKET_LABELS[item]}
                  </Button>
                ))}
              </div>
            </div>

            <div className="max-h-[76vh] overflow-auto">
              {loading ? (
                <div className="p-6 text-sm text-muted-foreground">加载中...</div>
              ) : conversations.length === 0 ? (
                <div className="flex flex-col items-center gap-3 p-10 text-center text-muted-foreground">
                  <Inbox className="h-10 w-10" />
                  <p className="text-sm">当前筛选条件下还没有会话。</p>
                </div>
              ) : (
                conversations.map((conversation) => (
                  <button
                    type="button"
                    key={conversation.id}
                    onClick={() => setSelectedId(conversation.id)}
                    className={`w-full border-b p-4 text-left transition-colors ${
                      selectedId === conversation.id ? "bg-muted/60" : "hover:bg-muted/30"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="truncate font-medium">{conversation.client_company_name}</div>
                      {conversation.unread_count > 0 && (
                        <Badge variant="destructive">{conversation.unread_count}</Badge>
                      )}
                    </div>
                    <div className="mt-1 truncate text-sm text-muted-foreground">
                      {conversation.client_email || "暂无邮箱"}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {conversation.needs_review && <Badge variant="outline">待审核</Badge>}
                    </div>
                    <div className="mt-3 line-clamp-2 text-sm text-muted-foreground">
                      {conversation.last_message_preview || conversation.latest_subject || "暂无摘要"}
                    </div>
                  </button>
                ))
              )}
            </div>
          </Card>

          <Card className="space-y-5 p-5">
            {!selectedConversation ? (
              <div className="flex min-h-[520px] items-center justify-center text-sm text-muted-foreground">
                请选择一个会话查看详情。
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">
                      {selectedConversation.client_company_name}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {selectedConversation.client_email || "暂无邮箱"}
                    </p>
                  </div>
                  {selectedConversation.needs_review && <Badge variant="outline">待审核</Badge>}
                </div>

                <div className="max-h-[58vh] space-y-3 overflow-auto pr-1">
                  {selectedConversation.messages.map((messageItem) => (
                    <div
                      key={messageItem.id}
                      className={`rounded-lg border p-4 ${
                        messageItem.direction === "outbound" ? "bg-muted/30" : "bg-background"
                      }`}
                    >
                      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div className="font-medium">{messageItem.subject}</div>
                        <Badge variant={messageItem.direction === "outbound" ? "outline" : "default"}>
                          {messageItem.direction === "outbound" ? "Outbound" : "Inbound"}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {new Date(messageItem.created_at).toLocaleString("zh-CN")}
                      </div>
                      <div className="mt-3 whitespace-pre-wrap text-sm text-muted-foreground">
                        {messageItem.body_text ||
                          messageItem.body_html?.replace(/<[^>]+>/g, " ").trim() ||
                          "(无正文)"}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="rounded-lg border p-4">
                  <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                    <div className="grid gap-3 md:grid-cols-2">
                      <Input
                        value={assignedTo}
                        onChange={(event) => setAssignedTo(event.target.value)}
                        placeholder="负责人 UUID（可选）"
                      />
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={needsReview}
                          onChange={(event) => setNeedsReview(event.target.checked)}
                        />
                        仍需审核
                      </label>
                    </div>
                    <Button variant="outline" onClick={saveConversationReview} disabled={working}>
                      保存审核
                    </Button>
                  </div>
                </div>
              </>
            )}
          </Card>

          <Card className="space-y-3 p-5">
            <h3 className="font-semibold">人工直接回复</h3>
            <Input
              value={manualSubject}
              onChange={(event) => setManualSubject(event.target.value)}
              placeholder="回复主题"
            />
            <HtmlEditor
              value={manualBody}
              onChange={setManualBody}
              onImageUpload={(file) => uploadInlineImage(file, "snippet_asset")}
              minHeightPx={200}
              placeholder="Hi..."
            />
            <Button
              className="w-full"
              variant="outline"
              onClick={sendManualReply}
              disabled={!selectedConversation || working || !manualBody.trim()}
            >
              <Send className="h-4 w-4" />
              发送人工回复
            </Button>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
