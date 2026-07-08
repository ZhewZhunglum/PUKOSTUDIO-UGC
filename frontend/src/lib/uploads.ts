import api from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8917";

export type InlineImagePurpose = "signature_logo" | "snippet_asset";

/**
 * Upload an image for inline embedding (signature logo or rich-text editor
 * image) and return its publicly-fetchable URL (GET /uploads/public/{id}) —
 * recipient mail clients must load it without auth, so we never inline it as
 * a base64 data URI.
 */
export async function uploadInlineImage(
  file: File,
  purpose: InlineImagePurpose,
): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("purpose", purpose);
  const res = await api.post("/uploads", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return `${API_URL}/api/v1/uploads/public/${res.data.id}`;
}
