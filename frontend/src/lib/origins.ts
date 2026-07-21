/**
 * URL allowlists for API / WebSocket bases (OWASP A10 / SSRF-ish misconfig).
 * Browser only talks to configured origins — never arbitrary user URLs.
 */

const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost"]);

function isAllowedHttpBase(raw: string): boolean {
  if (raw.startsWith("/")) return true; // same-origin relative
  try {
    const u = new URL(raw);
    if (u.protocol !== "http:" && u.protocol !== "https:") return false;
    if (LOCAL_HOSTS.has(u.hostname)) return true;
    // Production: same host as the page, or explicit https host from env
    if (typeof window !== "undefined" && u.hostname === window.location.hostname) {
      return true;
    }
    return u.protocol === "https:";
  } catch {
    return false;
  }
}

function isAllowedWsUrl(raw: string): boolean {
  try {
    const u = new URL(raw);
    if (u.protocol !== "ws:" && u.protocol !== "wss:") return false;
    if (LOCAL_HOSTS.has(u.hostname)) return true;
    if (typeof window !== "undefined" && u.hostname === window.location.hostname) {
      return u.protocol === (window.location.protocol === "https:" ? "wss:" : "ws:");
    }
    return u.protocol === "wss:";
  } catch {
    return false;
  }
}

export function resolveApiBase(configured: string | undefined, isDev: boolean): string {
  const fallback = isDev ? "http://127.0.0.1:8000" : "/api";
  const candidate = (configured || fallback).trim().replace(/\/$/, "");
  if (!isAllowedHttpBase(candidate)) {
    console.warn("[urban-twin] rejected VITE_API_BASE; using fallback");
    return fallback;
  }
  return candidate;
}

export function resolveWsUrl(configured: string | undefined, isDev: boolean): string {
  const fallback = isDev
    ? "ws://127.0.0.1:8001/ws/live"
    : defaultSameOriginWs("/ws/live");
  const candidate = (configured || fallback).trim();
  if (!isAllowedWsUrl(candidate)) {
    console.warn("[urban-twin] rejected VITE_WS_URL; using fallback");
    return fallback;
  }
  return candidate;
}

export function resolveDroneWsUrl(
  configured: string | undefined,
  configuredLive: string | undefined,
  isDev: boolean,
): string {
  const fallback = isDev
    ? "ws://127.0.0.1:8001/ws/drone"
    : defaultSameOriginWs("/ws/drone");
  let derived = fallback;
  if (configuredLive) {
    try {
      const live = new URL(configuredLive);
      live.pathname = live.pathname.replace(/\/ws\/live\/?$/, "/ws/drone");
      derived = live.toString();
    } catch {
      derived = fallback;
    }
  }
  const candidate = (configured || derived).trim();
  if (!isAllowedWsUrl(candidate)) {
    console.warn("[urban-twin] rejected VITE_DRONE_WS_URL; using fallback");
    return fallback;
  }
  return candidate;
}

function defaultSameOriginWs(path: string): string {
  if (typeof window === "undefined") return `ws://127.0.0.1:8001${path}`;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}
