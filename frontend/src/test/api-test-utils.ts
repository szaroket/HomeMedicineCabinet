const BASE = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1`;

export function jsonResponse(
  body: unknown,
  { status = 200 }: { status?: number } = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function stripBase(url: string): string {
  return url.startsWith(BASE) ? url.slice(BASE.length) : url;
}

export function callInfo(call: unknown[]): {
  path: string;
  init?: RequestInit;
} {
  const [url, init] = call as [string, RequestInit | undefined];
  return { path: stripBase(url), init };
}
