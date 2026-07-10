"use client";

import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { TextStyle, Color } from "@tiptap/extension-text-style";
import TextAlign from "@tiptap/extension-text-align";
import Placeholder from "@tiptap/extension-placeholder";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  Link as LinkIcon,
  Image as ImageIcon,
  List,
  ListOrdered,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Undo,
  Redo,
  Loader2,
} from "lucide-react";

export interface HtmlEditorProps {
  /** Controlled HTML value. */
  value: string;
  /** Called with the new HTML string on every content change. */
  onChange: (html: string) => void;
  /** Uploads an image file and resolves to a publicly-fetchable URL to embed as <img src>. */
  onImageUpload: (file: File) => Promise<string>;
  placeholder?: string;
  minHeightPx?: number;
  disabled?: boolean;
  className?: string;
}

function ToolbarButton({
  active,
  disabled,
  onClick,
  title,
  children,
}: {
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Button
      type="button"
      variant={active ? "secondary" : "ghost"}
      size="icon-sm"
      title={title}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()} // keep editor selection/focus intact
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

function EditorToolbar({
  editor,
  onImagePick,
  uploading,
}: {
  editor: Editor | null;
  onImagePick: (file: File) => void;
  uploading: boolean;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!editor) return null;

  const setLink = () => {
    const previous = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("链接地址", previous || "https://");
    if (url === null) return;
    if (!url.trim()) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: url.trim() }).run();
  };

  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b bg-muted/30 p-1">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onImagePick(file);
          e.target.value = "";
        }}
      />
      <ToolbarButton title="加粗" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}>
        <Bold className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="斜体" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}>
        <Italic className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="下划线" active={editor.isActive("underline")} onClick={() => editor.chain().focus().toggleUnderline().run()}>
        <UnderlineIcon className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="删除线" active={editor.isActive("strike")} onClick={() => editor.chain().focus().toggleStrike().run()}>
        <Strikethrough className="h-3.5 w-3.5" />
      </ToolbarButton>
      <input
        type="color"
        title="文字颜色"
        className="h-7 w-7 cursor-pointer rounded border-0 bg-transparent p-0.5"
        onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
      />
      <div className="mx-1 h-5 w-px bg-border" />
      <ToolbarButton title="链接" active={editor.isActive("link")} onClick={setLink}>
        <LinkIcon className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="插入图片" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
        {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5" />}
      </ToolbarButton>
      <div className="mx-1 h-5 w-px bg-border" />
      <ToolbarButton title="无序列表" active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()}>
        <List className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="有序列表" active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
        <ListOrdered className="h-3.5 w-3.5" />
      </ToolbarButton>
      <div className="mx-1 h-5 w-px bg-border" />
      <ToolbarButton title="左对齐" active={editor.isActive({ textAlign: "left" })} onClick={() => editor.chain().focus().setTextAlign("left").run()}>
        <AlignLeft className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="居中" active={editor.isActive({ textAlign: "center" })} onClick={() => editor.chain().focus().setTextAlign("center").run()}>
        <AlignCenter className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="右对齐" active={editor.isActive({ textAlign: "right" })} onClick={() => editor.chain().focus().setTextAlign("right").run()}>
        <AlignRight className="h-3.5 w-3.5" />
      </ToolbarButton>
      <div className="mx-1 h-5 w-px bg-border" />
      <ToolbarButton title="撤销" onClick={() => editor.chain().focus().undo().run()}>
        <Undo className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton title="重做" onClick={() => editor.chain().focus().redo().run()}>
        <Redo className="h-3.5 w-3.5" />
      </ToolbarButton>
    </div>
  );
}

export function HtmlEditor({
  value,
  onChange,
  onImageUpload,
  placeholder,
  minHeightPx = 200,
  disabled,
  className,
}: HtmlEditorProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        link: { openOnClick: false, autolink: true },
      }),
      Image,
      TextStyle,
      Color,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({ placeholder: placeholder || "" }),
    ],
    content: value,
    editable: !disabled,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
    editorProps: {
      attributes: {
        class: "prose prose-sm max-w-none focus:outline-none px-3 py-2",
      },
    },
    // Required for Next.js App Router: defers the first render to the client
    // to avoid an SSR/CSR hydration mismatch warning.
    immediatelyRender: false,
  });

  // Keep the editor in sync when `value` changes from outside (e.g. loading
  // a different template, or a reset after save) without fighting the
  // editor's own onUpdate-driven changes.
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value || "", { emitUpdate: false });
    }
  }, [value, editor]);

  useEffect(() => {
    editor?.setEditable(!disabled);
  }, [disabled, editor]);

  const handleImagePick = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const url = await onImageUpload(file);
      editor?.chain().focus().setImage({ src: url }).run();
    } catch (error) {
      console.error(error);
      setUploadError("图片上传失败，请检查文件大小/类型后重试");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className={cn("overflow-hidden rounded-lg border", className)}>
      <EditorToolbar editor={editor} onImagePick={handleImagePick} uploading={uploading} />
      {uploadError && (
        <p className="border-b bg-destructive/5 px-3 py-1.5 text-xs text-destructive">
          {uploadError}
        </p>
      )}
      <div style={{ minHeight: minHeightPx }}>
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
