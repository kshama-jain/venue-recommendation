export function apiUrl(path: string): string {
  const base = process.env.REACT_APP_API_BASE || "";
  if (!base) return path;
  return base.replace(/\/+$/, "") + path;
}

