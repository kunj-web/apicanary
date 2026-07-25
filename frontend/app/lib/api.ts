const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let legacyMigration: Promise<boolean> | null = null;

export function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);

  if (MUTATING_METHODS.has(method)) {
    headers.set("X-Requested-With", "APICanary");
  }

  return fetch(input, {
    ...init,
    credentials: "include",
    headers,
  });
}

export function migrateLegacySession(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (legacyMigration) return legacyMigration;

  const legacyToken = localStorage.getItem("token");
  if (!legacyToken) return Promise.resolve(false);

  legacyMigration = apiFetch("/api/auth/session", {
    method: "POST",
    headers: { Authorization: `Bearer ${legacyToken}` },
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      localStorage.removeItem("token");
      legacyMigration = null;
    });

  return legacyMigration;
}

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  let response = await apiFetch(input, init);
  if (response.status === 401 && (await migrateLegacySession())) {
    response = await apiFetch(input, init);
  }
  return response;
}

export function clearLegacyToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
  }
}
