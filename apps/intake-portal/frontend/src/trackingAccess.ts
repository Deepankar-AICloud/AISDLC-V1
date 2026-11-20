import type { TrackingAccess } from "./types";

const STORAGE_KEY = "aisdlc-request-tracking";

export function readTrackingAccess(): TrackingAccess[] {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  const parsed: unknown = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("Saved request tracking data is invalid.");
  }
  return Object.entries(parsed).map(([id, token]) => {
    if (!id.startsWith("req_") || typeof token !== "string" || token.length < 32) {
      throw new Error("Saved request tracking data is invalid.");
    }
    return { id, token };
  });
}

export function saveTrackingAccess(id: string, token: string): void {
  const records = readTrackingAccess();
  const next = Object.fromEntries(records.map((record) => [record.id, record.token]));
  next[id] = token;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function getTrackingToken(id: string): string {
  return readTrackingAccess().find((record) => record.id === id)?.token ?? "";
}
