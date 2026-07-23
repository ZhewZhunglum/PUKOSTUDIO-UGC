"use client";

import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import type { Attachment } from "@/types";
import { Loader2, Paperclip, X } from "lucide-react";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Upload each file to /uploads (purpose="email") and return the created
 * Attachment rows. Shared by any screen that lets the user attach files to
 * an outbound email (inbox replies, AI drafts, campaign step editors). */
export async function uploadAttachmentFiles(files: FileList): Promise<Attachment[]> {
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
  return uploaded;
}

interface AttachmentFieldProps {
  attachments: Attachment[];
  uploading: boolean;
  disabled?: boolean;
  inputId: string;
  onAdd: (files: FileList) => void;
  onRemove: (id: string) => void;
}

export function AttachmentField({
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
