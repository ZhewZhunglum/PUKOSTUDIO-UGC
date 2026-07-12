"use client";

import { useCallback, useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { HtmlEditor } from "@/components/editor/HtmlEditor";
import api from "@/lib/api";
import {
  AI_DRAFT_STATUS_MAP,
  AI_RISK_LEVEL_MAP,
  CONVERSATION_INTENT_MAP,
} from "@/lib/constants";
import { uploadInlineImage } from "@/lib/uploads";
import type {
  AIActionLog,
  AIMessageDraft,
  Attachment,
  Conversation,
  ConversationDetail,
} from "@/types";
import {
  CheckCircle2,
  FileWarning,
  Inbox,
  Loader2,
  Paperclip,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

interface AttachmentFieldProps {
  attachments: Attachment[];
  uploading: boolean;
  disabled?: boolean;
  inputId: string;
  onAdd: (files: FileList) => void;
  onRemove: (id: string) => void;
}

function AttachmentField({
  attachments,
  uploading,
  disabled,
  inputId,
  onAdd,
  onRemove,
}: AttachmentFieldProps) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <input
          id={inputId}
          type="file"
          multiple
          className="hidden"
          onChange={(event) => {
            if (event.target.files?.length) onAdd(event.target.files);
            event.target.value = "";
          }}
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={disabled || uploading}
          onClick={() => document.getElementById(inputId)?.click()}
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Paperclip className="h-4 w-4" />
          )}
          添加附件
        </Button>
      </div>
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachments.map((attachment) => (
            <span
              key={attachment.id}
              className="inline-flex items-center gap-1.5 rounded-full border bg-muted/40 px-2.5 py-1 text-xs"
            >
              <Paperclip className="h-3 w-3" />
              <span className="max-w-[160px] truncate">{attachment.filename}</span>
              <span className="text-muted-foreground">{formatBytes(attachment.size_bytes)}</span>
              <button
                type="button"
                className="text-muted-foreground hover:text-destructive"
                onClick={() => onRemove(attachment.id)}
                aria-label={`移除 ${attachment.filename}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

type Bucket = "all" | "needs_review" | "has_draft" | "negotiation" | "replied" | "blacklisted";

const BUCKET_LABELS: Record<Bucket, string> = {
  all: "全部",
  needs_review: "待审核",
  has_draft: "有 AI 草稿",
  negotiation: "议价中",
  replied: "已回复",
  blacklisted: "黑名单",
};

const AI_INTENT_OPTIONS = [
  { value: "interested", label: "感兴趣" },
  { value: "question", label: "提问中" },
  { value: "negotiation", label: "议价中" },
  { value: "not_interested", label: "不感兴趣" },
  { value: "spam", label: "垃圾回复" },
  { value: "unknown", label: "待识别" },
];

function statusBadge(status: string | null) {
  if (!status) return null;
  const meta = AI_DRAFT_STATUS_MAP[status] || { label: status, variant: "secondary" as const };
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}

function riskBadge(risk: string | null) {
  if (!risk) return null;
  const meta = AI_RISK_LEVEL_MAP[risk] || { label: risk, variant: "secondary" as const };
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}

export default function InboxPage() {
  const [bucket, setBucket] = useState<Bucket>("all");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<ConversationDetail | null>(null);
  const [drafts, setDrafts] = useState<AIMessageDraft[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<AIMessageDraft | null>(null);
  const [actionLogs, setActionLogs] = useState<AIActionLog[]>([]);
  const [guidelines, setGuidelines] = useState("");
  const [replySubject, setReplySubject] = useState("");
  const [replyBody, setReplyBody] = useState("");
  const [manualSubject, setManualSubject] = useState("");
  const [manualBody, setManualBody] = useState("");
  const [draftAttachments, setDraftAttachments] = useState<Attachment[]>([]);
  const [manualAttachments, setManualAttachments] = useState<Attachment[]>([]);
  const [uploadingTarget, setUploadingTarget] = useState<"draft" | "manual" | null>(null);
  const [intent, setIntent] = useState<string>("unknown");
  const [needsReview, setNeedsReview] = useState(true);
  const [assignedTo, setAssignedTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadConversations = useCallback(async (nextBucket: Bucket) => {
    setLoading(true);
    try {
      const response = await api.get("/conversations", {
        params: { bucket: nextBucket },
      });
      const items: Conversation[] = response.data;
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
      const [detailResponse, draftsResponse, logsResponse] = await Promise.all([
        api.get(`/conversations/${conversationId}`),
        api.get(`/conversations/${conversationId}/ai-drafts`).catch(() => ({ data: [] })),
        api.get("/ai-action-logs", { params: { conversation_id: conversationId } }).catch(() => ({
          data: [],
        })),
      ]);
      const detail: ConversationDetail = detailResponse.data;
      const nextDrafts: AIMessageDraft[] = draftsResponse.data;
      const preferredDraft =
        nextDrafts.find((draft) => draft.status === "pending_review") || nextDrafts[0] || null;

      setSelectedConversation(detail);
      setDrafts(nextDrafts);
      setSelectedDraft(preferredDraft);
      setActionLogs(logsResponse.data);
      setIntent(detail.ai_intent || "unknown");
      setNeedsReview(detail.needs_review);
      setAssignedTo(detail.assigned_to || "");
      setReplySubject(preferredDraft?.subject || "");
      setReplyBody(preferredDraft?.body_html || "");
      setManualSubject("");
      setManualBody("");
      setDraftAttachments([]);
      setManualAttachments([]);
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
      setDrafts([]);
      setSelectedDraft(null);
      setActionLogs([]);
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
      await api.patch(`/conversations/${selectedConversation.id}`, {
        ai_intent: intent,
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

  const classifyConversation = async () => {
    if (!selectedConversation) return;
    setWorking(true);
    try {
      await api.post(`/conversations/${selectedConversation.id}/classify`);
      await refreshSelected();
      setMessage("AI 已重新识别意图");
    } catch (requestError) {
      console.error(requestError);
      setMessage("AI 识别失败");
    } finally {
      setWorking(false);
    }
  };

  const generateDraft = async () => {
    if (!selectedConversation) return;
    setWorking(true);
    try {
      const response = await api.post(`/conversations/${selectedConversation.id}/ai-drafts`, {
        guidelines,
      });
      const draft: AIMessageDraft = response.data;
      await refreshSelected();
      setSelectedDraft(draft);
      setReplySubject(draft.subject);
      setReplyBody(draft.body_html);
      setMessage(draft.status === "failed" ? draft.failure_reason || "AI 草稿生成失败" : "AI 草稿已生成，等待审核");
    } catch (requestError) {
      console.error(requestError);
      setMessage("生成 AI 草稿失败");
    } finally {
      setWorking(false);
    }
  };

  const uploadFiles = async (files: FileList, target: "draft" | "manual") => {
    setUploadingTarget(target);
    try {
      const uploaded: Attachment[] = [];
      for (const file of Array.from(files)) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("purpose", "email");
        const response = await api.post("/uploads", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        uploaded.push(response.data as Attachment);
      }
      if (target === "draft") {
        setDraftAttachments((current) => [...current, ...uploaded]);
      } else {
        setManualAttachments((current) => [...current, ...uploaded]);
      }
    } catch (requestError) {
      console.error(requestError);
      setMessage("附件上传失败（请检查文件类型与大小）");
    } finally {
      setUploadingTarget(null);
    }
  };

  const saveDraftEdits = async () => {
    if (!selectedDraft) return null;
    const response = await api.patch(`/ai-drafts/${selectedDraft.id}`, {
      subject: replySubject,
      body_html: replyBody,
    });
    return response.data as AIMessageDraft;
  };

  const approveAndSendDraft = async () => {
    if (!selectedDraft || !replyBody.trim()) return;
    setWorking(true);
    try {
      const updatedDraft = await saveDraftEdits();
      const response = await api.post(
        `/ai-drafts/${updatedDraft?.id || selectedDraft.id}/approve-send`,
        { attachment_ids: draftAttachments.map((attachment) => attachment.id) }
      );
      const sentDraft: AIMessageDraft = response.data;
      await refreshSelected();
      setMessage(sentDraft.status === "sent" ? "AI 草稿已批准并发送" : sentDraft.failure_reason || "发送失败");
    } catch (requestError) {
      console.error(requestError);
      setMessage("批准发送失败");
    } finally {
      setWorking(false);
    }
  };

  const discardDraft = async () => {
    if (!selectedDraft) return;
    setWorking(true);
    try {
      await api.post(`/ai-drafts/${selectedDraft.id}/discard`);
      await refreshSelected();
      setMessage("AI 草稿已废弃");
    } catch (requestError) {
      console.error(requestError);
      setMessage("废弃草稿失败");
    } finally {
      setWorking(false);
    }
  };

  const sendManualReply = async () => {
    if (!selectedConversation || !manualBody.trim()) return;
    setWorking(true);
    try {
      await api.post(`/conversations/${selectedConversation.id}/send-reply`, {
        subject: manualSubject || null,
        body_html: manualBody,
        attachment_ids: manualAttachments.map((attachment) => attachment.id),
      });
      await refreshSelected();
      setManualBody("");
      setManualAttachments([]);
      setMessage("人工回复已发送");
    } catch (requestError) {
      console.error(requestError);
      setMessage("发送人工回复失败");
    } finally {
      setWorking(false);
    }
  };

  const selectDraft = (draft: AIMessageDraft) => {
    setSelectedDraft(draft);
    setReplySubject(draft.subject);
    setReplyBody(draft.body_html);
  };

  return (
    <AppLayout>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="ds-between" style={{ marginBottom: 4 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>工作流</div>
            <h1 className="ds-h1">收件箱</h1>
            <p className="ds-body" style={{ marginTop: 4, color: "var(--ink-3)" }}>
              入站回复会自动识别意图并生成待审核草稿，确认后再发给达人。
            </p>
          </div>
          {message && <p className="ds-caption" style={{ color: "var(--ink-3)" }}>{message}</p>}
        </div>

        <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)_360px]">
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
                      <div className="truncate font-medium">{conversation.influencer_name}</div>
                      {conversation.unread_count > 0 && (
                        <Badge variant="destructive">{conversation.unread_count}</Badge>
                      )}
                    </div>
                    <div className="mt-1 truncate text-sm text-muted-foreground">
                      {conversation.influencer_email || "暂无邮箱"}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {conversation.ai_intent && (
                        <Badge
                          variant={
                            CONVERSATION_INTENT_MAP[conversation.ai_intent]?.variant || "secondary"
                          }
                        >
                          {CONVERSATION_INTENT_MAP[conversation.ai_intent]?.label ||
                            conversation.ai_intent}
                        </Badge>
                      )}
                      {statusBadge(conversation.latest_draft_status)}
                      {riskBadge(conversation.risk_level)}
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
                      {selectedConversation.influencer_name}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {selectedConversation.influencer_email || "暂无邮箱"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedConversation.ai_intent && (
                      <Badge
                        variant={
                          CONVERSATION_INTENT_MAP[selectedConversation.ai_intent]?.variant ||
                          "secondary"
                        }
                      >
                        {CONVERSATION_INTENT_MAP[selectedConversation.ai_intent]?.label ||
                          selectedConversation.ai_intent}
                      </Badge>
                    )}
                    {riskBadge(selectedConversation.risk_level)}
                    {selectedConversation.needs_review && <Badge variant="outline">待审核</Badge>}
                  </div>
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
                    <div className="grid gap-3 md:grid-cols-3">
                      <select
                        value={intent}
                        onChange={(event) => setIntent(event.target.value)}
                        className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm"
                      >
                        {AI_INTENT_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
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
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" onClick={classifyConversation} disabled={working}>
                        <Sparkles className="h-4 w-4" />
                        重新识别
                      </Button>
                      <Button variant="outline" onClick={saveConversationReview} disabled={working}>
                        保存审核
                      </Button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </Card>

          <div className="space-y-4">
            <Card className="space-y-4 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold">AI 草稿审核</h3>
                  <p className="text-sm text-muted-foreground">编辑后批准发送，或废弃重新生成。</p>
                </div>
                {working && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
              </div>

              <div className="space-y-2">
                <Input
                  value={guidelines}
                  onChange={(event) => setGuidelines(event.target.value)}
                  placeholder="补充起草要求，例如：先回答报价问题"
                />
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={generateDraft}
                  disabled={!selectedConversation || working}
                >
                  <Sparkles className="h-4 w-4" />
                  生成 AI 草稿
                </Button>
              </div>

              {drafts.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {drafts.slice(0, 5).map((draft) => (
                    <Button
                      key={draft.id}
                      size="sm"
                      variant={selectedDraft?.id === draft.id ? "default" : "outline"}
                      onClick={() => selectDraft(draft)}
                    >
                      {AI_DRAFT_STATUS_MAP[draft.status]?.label || draft.status}
                    </Button>
                  ))}
                </div>
              )}

              {selectedDraft ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {statusBadge(selectedDraft.status)}
                    {riskBadge(selectedDraft.risk_level)}
                    {selectedDraft.intent && (
                      <Badge variant="outline">
                        {CONVERSATION_INTENT_MAP[selectedDraft.intent]?.label ||
                          selectedDraft.intent}
                      </Badge>
                    )}
                  </div>
                  {selectedDraft.failure_reason && (
                    <div className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                      <FileWarning className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{selectedDraft.failure_reason}</span>
                    </div>
                  )}
                  <Input
                    value={replySubject}
                    onChange={(event) => setReplySubject(event.target.value)}
                    placeholder="回复主题"
                  />
                  <HtmlEditor
                    value={replyBody}
                    onChange={setReplyBody}
                    onImageUpload={(file) => uploadInlineImage(file, "snippet_asset")}
                    minHeightPx={200}
                    placeholder="Hi..."
                  />
                  {selectedDraft.rationale && (
                    <p className="text-xs leading-5 text-muted-foreground">
                      AI 理由：{selectedDraft.rationale}
                    </p>
                  )}
                  {selectedDraft.missing_context && (
                    <p className="text-xs leading-5 text-muted-foreground">
                      需人工确认：{selectedDraft.missing_context}
                    </p>
                  )}
                  <AttachmentField
                    attachments={draftAttachments}
                    uploading={uploadingTarget === "draft"}
                    disabled={selectedDraft.status === "sent"}
                    inputId="draft-attachment-input"
                    onAdd={(files) => uploadFiles(files, "draft")}
                    onRemove={(id) =>
                      setDraftAttachments((current) =>
                        current.filter((attachment) => attachment.id !== id)
                      )
                    }
                  />
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Button
                      onClick={approveAndSendDraft}
                      disabled={working || selectedDraft.status === "sent" || !replyBody.trim()}
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      批准发送
                    </Button>
                    <Button
                      variant="outline"
                      onClick={discardDraft}
                      disabled={working || selectedDraft.status === "sent"}
                    >
                      <Trash2 className="h-4 w-4" />
                      废弃草稿
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  当前会话还没有 AI 草稿。若活动未配置 AI 沟通设置，系统会提示补齐规则。
                </p>
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
                minHeightPx={140}
                placeholder="Hi..."
              />
              <AttachmentField
                attachments={manualAttachments}
                uploading={uploadingTarget === "manual"}
                disabled={!selectedConversation}
                inputId="manual-attachment-input"
                onAdd={(files) => uploadFiles(files, "manual")}
                onRemove={(id) =>
                  setManualAttachments((current) =>
                    current.filter((attachment) => attachment.id !== id)
                  )
                }
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

            <Card className="space-y-3 p-5">
              <h3 className="font-semibold">AI 操作记录</h3>
              {actionLogs.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无记录。</p>
              ) : (
                <div className="max-h-56 space-y-2 overflow-auto">
                  {actionLogs.slice(0, 8).map((log) => (
                    <div key={log.id} className="rounded-lg border p-3 text-sm">
                      <div className="font-medium">{log.action_type}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(log.created_at).toLocaleString("zh-CN")}
                      </div>
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
