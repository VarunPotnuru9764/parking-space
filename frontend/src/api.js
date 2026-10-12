const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "parking_access_token";

export const authStore = {
  getToken() {
    return sessionStorage.getItem(TOKEN_KEY);
  },
  setToken(token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    sessionStorage.removeItem(TOKEN_KEY);
  },
};

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = authStore.getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && options.body instanceof Blob) {
    if (options.body.type) headers.set("Content-Type", options.body.type);
  } else if (options.body && !(options.body instanceof FormData) && !(options.body instanceof ArrayBuffer)) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach the ParkingSpace API at ${API_BASE}. Check that the backend is running.`);
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    if (response.status === 401) {
      authStore.clear();
      window.dispatchEvent(new Event("parking:unauthorized"));
    }
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return payload;
}

export async function apiBlob(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = authStore.getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach the ParkingSpace API at ${API_BASE}. Check that the backend is running.`);
  }
  if (!response.ok) {
    if (response.status === 401) {
      authStore.clear();
      window.dispatchEvent(new Event("parking:unauthorized"));
    }
    let detail = "";
    try { detail = (await response.json())?.detail || ""; } catch { /* response may not be JSON */ }
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return response.blob();
}

export { API_BASE };
