import api from "@/lib/api";

/**
 * Download a file from an authenticated GET endpoint that returns a blob
 * (CSV/XLSX export). Uses the Content-Disposition filename when present,
 * otherwise falls back to `fallbackName`.
 */
export async function downloadExport(
  path: string,
  params: Record<string, string | number | undefined>,
  fallbackName: string,
): Promise<void> {
  const res = await api.get(path, { params, responseType: "blob" });

  const disposition = String(res.headers?.["content-disposition"] ?? "");
  const match = /filename\*?=(?:UTF-8'')?"?([^;"]+)"?/i.exec(disposition);
  const filename = match ? decodeURIComponent(match[1].trim()) : fallbackName;

  const url = URL.createObjectURL(res.data as Blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
