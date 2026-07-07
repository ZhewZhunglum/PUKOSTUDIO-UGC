"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";
import { downloadExport } from "@/lib/download";
import type { EmailTemplate } from "@/types";
import { ChevronDown, ChevronUp, Copy, Download, Edit, Eye, Loader2, Plus, Sparkles, Trash2, Upload, Wand2 } from "lucide-react";

type ConvertResult = {
  subject: string;
  body_html: string;
  variables: string[];
  method: string;
};

const CATEGORY_MAP: Record<string, string> = {
  initial_outreach: "初始建联",
  followup_1: "第一次跟进",
  followup_2: "第二次跟进",
  reply: "回复模板",
  custom: "自定义",
};

const LANGUAGE_MAP: Record<string, string> = {
  en: "English",
  zh: "中文",
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [libraryTemplates, setLibraryTemplates] = useState<EmailTemplate[]>([]);
  const [languageFilter, setLanguageFilter] = useState("en");
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [selected, setSelected] = useState<EmailTemplate | null>(null);

  // Form
  const [formName, setFormName] = useState("");
  const [formSubject, setFormSubject] = useState("");
  const [formBody, setFormBody] = useState("");
  const [formCategory, setFormCategory] = useState("initial_outreach");
  const [formLanguage, setFormLanguage] = useState("en");

  // Converter panel
  const [converterOpen, setConverterOpen] = useState(false);
  const [rawSubject, setRawSubject] = useState("");
  const [rawBody, setRawBody] = useState("");
  const [converting, setConverting] = useState<"rule" | "ai" | null>(null);
  const [convertResult, setConvertResult] = useState<ConvertResult | null>(null);

  const [ioMessage, setIoMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchTemplates = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get("/templates"),
      api.get("/templates/library", { params: { language: languageFilter } }),
    ])
      .then(([owned, library]) => {
        setTemplates(owned.data);
        setLibraryTemplates(library.data);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [languageFilter]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleExport = async (fmt: "csv" | "xlsx") => {
    try {
      await downloadExport("/templates/export", { format: fmt }, `templates.${fmt}`);
    } catch {
      setIoMessage("导出失败，请稍后重试");
    }
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIoMessage(null);
    const name = file.name.toLowerCase();
    if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) {
      setIoMessage("导入仅支持 CSV 或 Excel(.xlsx)");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/templates/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setIoMessage(`导入完成：${res.data.imported} 成功，${res.data.skipped} 跳过`);
      fetchTemplates();
    } catch {
      setIoMessage("导入失败，请确认表头包含 name/subject/body_html");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const resetConverter = () => {
    setRawSubject("");
    setRawBody("");
    setConvertResult(null);
    setConverterOpen(false);
  };

  const openCreate = () => {
    setSelected(null);
    setFormName("");
    setFormSubject("");
    setFormBody("");
    setFormCategory("initial_outreach");
    setFormLanguage(languageFilter);
    resetConverter();
    setEditOpen(true);
  };

  const openEdit = (t: EmailTemplate) => {
    setSelected(t);
    setFormName(t.name);
    setFormSubject(t.subject);
    setFormBody(t.body_html);
    setFormCategory(t.category);
    setFormLanguage(t.language);
    resetConverter();
    setEditOpen(true);
  };

  const handleConvert = async (mode: "rule" | "ai") => {
    if (!rawBody.trim()) return;
    setConverting(mode);
    setConvertResult(null);
    try {
      const res = await api.post<ConvertResult>("/templates/convert", {
        raw_subject: rawSubject,
        raw_body: rawBody,
        use_ai: mode === "ai",
      });
      setConvertResult(res.data);
    } catch {
      setConvertResult(null);
      alert("转换失败，请检查后端服务或 AI 配置");
    } finally {
      setConverting(null);
    }
  };

  const applyConvertResult = () => {
    if (!convertResult) return;
    if (convertResult.subject) setFormSubject(convertResult.subject);
    setFormBody(convertResult.body_html);
    setConvertResult(null);
    setConverterOpen(false);
  };

  const handleSave = async () => {
    try {
      if (selected) {
        await api.put(`/templates/${selected.id}`, {
          name: formName,
          subject: formSubject,
          body_html: formBody,
          category: formCategory,
          language: formLanguage,
        });
      } else {
        await api.post("/templates", {
          name: formName,
          subject: formSubject,
          body_html: formBody,
          category: formCategory,
          language: formLanguage,
        });
      }
      setEditOpen(false);
      fetchTemplates();
    } catch {
      alert("保存失败");
    }
  };

  const handleClone = async (id: string) => {
    try {
      await api.post(`/templates/${id}/clone`);
      fetchTemplates();
    } catch {
      alert("克隆失败");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除此模板？")) return;
    try {
      await api.delete(`/templates/${id}`);
      fetchTemplates();
    } catch {
      alert("删除失败");
    }
  };

  return (
    <AppLayout>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="ds-between" style={{ marginBottom: 4 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>系统</div>
            <h1 className="h-1">邮件模板</h1>
            <p className="ds-body" style={{ marginTop: 4, color: "var(--ink-3)" }}>
              使用 {"{{"} name {"}}"},  {"{{"} first_name {"}}"}  等变量实现个性化。
            </p>
          </div>
          <div className="ds-row" style={{ gap: 8 }}>
            <Select value={languageFilter} onValueChange={(v) => v && setLanguageFilter(v)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="zh">中文</SelectItem>
              </SelectContent>
            </Select>
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
            <button className="ds-btn ds-btn-primary" onClick={openCreate}>
              <Plus className="h-[14px] w-[14px]" />新建模板
            </button>
          </div>
        </div>

        {ioMessage && (
          <p className="text-sm text-muted-foreground">{ioMessage}</p>
        )}

        <div className="text-sm text-muted-foreground">
          使用 {"{{name}}"}, {"{{first_name}}"} 等变量实现个性化。系统会自动替换为达人的真实信息。
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">模板库</h3>
            <Badge variant="outline">{LANGUAGE_MAP[languageFilter] || languageFilter}</Badge>
          </div>
          {loading ? (
            <p className="text-muted-foreground">加载中...</p>
          ) : libraryTemplates.length === 0 ? (
            <Card className="p-6 text-center text-muted-foreground">
              暂无可克隆的预制模板，请先运行 seed_library_templates.py
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {libraryTemplates.map((t) => (
                <Card key={t.id} className="p-4 space-y-3">
                  <div className="space-y-1">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-semibold leading-tight">{t.name}</h4>
                      <Badge variant="secondary">{CATEGORY_MAP[t.category] || t.category}</Badge>
                    </div>
                    <p className="line-clamp-2 text-sm text-muted-foreground">{t.subject}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelected(t);
                        setPreviewOpen(true);
                      }}
                    >
                      <Eye className="mr-1.5 h-4 w-4" />
                      预览
                    </Button>
                    <Button size="sm" onClick={() => handleClone(t.id)}>
                      <Copy className="mr-1.5 h-4 w-4" />
                      克隆
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-2">
          <h3 className="text-lg font-semibold">我的模板</h3>
        </div>

        {loading ? (
          <p className="text-muted-foreground">加载中...</p>
        ) : templates.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">
            暂无模板，点击“新建模板”开始创建
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {templates.map((t) => (
              <Card key={t.id} className="p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold">{t.name}</h3>
                    <Badge variant="outline" className="mt-1">
                      {CATEGORY_MAP[t.category] || t.category}
                    </Badge>
                    <Badge variant="secondary" className="ml-1 mt-1">
                      {LANGUAGE_MAP[t.language] || t.language}
                    </Badge>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSelected(t);
                        setPreviewOpen(true);
                      }}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openEdit(t)}>
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(t.id)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  主题: {t.subject}
                </p>
                <p className="text-xs text-muted-foreground">
                  更新: {new Date(t.updated_at).toLocaleDateString("zh-CN")}
                </p>
              </Card>
            ))}
          </div>
        )}

        {/* Edit Dialog */}
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{selected ? "编辑模板" : "新建模板"}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[75vh] overflow-y-auto space-y-4 pr-1">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>模板名称 *</Label>
                  <Input value={formName} onChange={(e) => setFormName(e.target.value)} />
                </div>
                <div>
                  <Label>分类</Label>
                  <Select value={formCategory} onValueChange={(v) => v && setFormCategory(v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="initial_outreach">初始建联</SelectItem>
                      <SelectItem value="followup_1">第一次跟进</SelectItem>
                      <SelectItem value="followup_2">第二次跟进</SelectItem>
                      <SelectItem value="reply">回复模板</SelectItem>
                      <SelectItem value="custom">自定义</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>语言</Label>
                  <Select value={formLanguage} onValueChange={(v) => v && setFormLanguage(v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="zh">中文</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>邮件主题 *</Label>
                <Input
                  value={formSubject}
                  onChange={(e) => setFormSubject(e.target.value)}
                  placeholder="Hi {{name}}, collaboration opportunity!"
                />
              </div>
              {/* ── Converter panel ── */}
              <div className="rounded-xl border bg-muted/20">
                <button
                  type="button"
                  onClick={() => setConverterOpen((v) => !v)}
                  className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/40 transition-colors rounded-xl"
                >
                  <span className="flex items-center gap-2">
                    <Wand2 className="h-4 w-4 text-primary" />
                    从原稿转换变量
                  </span>
                  {converterOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>

                {converterOpen && (
                  <div className="space-y-3 border-t px-4 pb-4 pt-3">
                    <p className="text-xs text-muted-foreground">
                      粘贴原始邮件文本，系统将自动识别姓名、垂类等个人化内容并替换为
                      <code className="mx-1 rounded bg-muted px-1">{"{{变量}}"}</code>格式。
                    </p>

                    <div>
                      <Label className="text-xs">原稿主题（选填）</Label>
                      <Input
                        value={rawSubject}
                        onChange={(e) => setRawSubject(e.target.value)}
                        placeholder="Hi [Name], we'd love to work with you!"
                        className="mt-1 text-sm"
                      />
                    </div>

                    <div>
                      <Label className="text-xs">原稿正文 *</Label>
                      <Textarea
                        value={rawBody}
                        onChange={(e) => { setRawBody(e.target.value); setConvertResult(null); }}
                        rows={6}
                        placeholder={"Hi Jane,\n\nI came across your skincare content and loved it!\nWe'd love to collaborate with you...\n\nBest,\nBrand Team"}
                        className="mt-1 font-mono text-xs"
                      />
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => handleConvert("rule")}
                        disabled={!rawBody.trim() || converting !== null}
                      >
                        {converting === "rule" ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Wand2 className="mr-1.5 h-3.5 w-3.5" />}
                        规则转换
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => handleConvert("ai")}
                        disabled={!rawBody.trim() || converting !== null}
                      >
                        {converting === "ai" ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-1.5 h-3.5 w-3.5 text-primary" />}
                        AI 转换
                      </Button>
                    </div>

                    {convertResult && (
                      <div className="space-y-3 rounded-xl border bg-background p-3">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-medium text-muted-foreground">
                            转换结果
                            <Badge variant="outline" className="ml-2 text-xs">
                              {convertResult.method === "ai" ? "AI" : "规则"}
                            </Badge>
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {convertResult.variables.map((v) => (
                              <Badge key={v} variant="secondary" className="font-mono text-xs">
                                {`{{${v}}}`}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        {convertResult.subject && (
                          <p className="truncate rounded bg-muted px-2 py-1 text-xs">
                            <span className="text-muted-foreground">主题：</span>{convertResult.subject}
                          </p>
                        )}
                        <div
                          className="max-h-40 overflow-y-auto rounded bg-muted px-2 py-1 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all"
                        >
                          {convertResult.body_html}
                        </div>
                        <Button type="button" size="sm" className="w-full" onClick={applyConvertResult}>
                          应用到模板
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div>
                <Label>邮件正文 (HTML) *</Label>
                <Textarea
                  value={formBody}
                  onChange={(e) => setFormBody(e.target.value)}
                  rows={10}
                  placeholder={`<p>Hi {{first_name}},</p>\n<p>I came across your content and loved it!</p>\n<p>We'd love to collaborate with you on...</p>`}
                />
              </div>
              <Button onClick={handleSave} disabled={!formName || !formSubject || !formBody}>
                {selected ? "保存修改" : "创建模板"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Preview Dialog */}
        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>模板预览: {selected?.name}</DialogTitle>
            </DialogHeader>
            {selected && (
              <div className="max-h-[75vh] overflow-y-auto space-y-4 pr-1">
                <div>
                  <Label>主题</Label>
                  <p className="mt-1 rounded bg-muted p-2 text-sm">{selected.subject}</p>
                </div>
                <div>
                  <Label>正文</Label>
                  <div
                    className="mt-1 rounded border p-4 text-sm"
                    dangerouslySetInnerHTML={{ __html: selected.body_html }}
                  />
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
