/** Trigger a browser download for in-memory content. */
export function downloadContent(content: string, filename: string, type = "application/json;charset=utf-8"): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadJson(value: unknown, filename: string): void {
  downloadContent(JSON.stringify(value, null, 2), filename);
}
