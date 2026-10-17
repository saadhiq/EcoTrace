const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`API ${status}: ${detail}`);
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  /** Firebase ID token; sent as `Authorization: Bearer`. */
  token?: string;
  body?: unknown;
  /** Multipart upload (e.g. photos). The browser sets the Content-Type boundary. */
  form?: FormData;
  /** Extra headers (e.g. the partner API's X-API-Key). */
  headers?: Record<string, string>;
};

export async function apiFetch<T>(path: string, options: Options = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { ...options.headers };
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  let body: string | FormData | undefined;
  if (options.form) {
    body = options.form;
  } else if (method !== "GET") {
    // Always send a body: Google's front end rejects POSTs without Content-Length.
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body ?? {});
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body });
  } catch {
    throw new ApiError(0, "network_error");
  }

  if (!res.ok) {
    let detail = res.statusText || "error";
    try {
      const data: unknown = await res.json();
      if (data && typeof data === "object" && "detail" in data) {
        detail = String((data as { detail: unknown }).detail);
      }
    } catch {
      // Non-JSON error body; keep statusText.
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}
