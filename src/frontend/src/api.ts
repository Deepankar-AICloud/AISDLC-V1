import { InteractionRequiredAuthError } from '@azure/msal-browser';
import { msalInstance, apiScope, authConfigured } from './auth';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export type RequestKind = 'Access' | 'Service';

export type RequestStatus = 'Submitted' | 'UnderReview' | 'Approved' | 'Rejected' | 'Fulfilled';

export interface PortalRequest {
  id: string;
  kind: RequestKind;
  requestTypeId: string;
  requestTypeName: string;
  title: string;
  description: string;
  status: RequestStatus;
  requesterId: string;
  managerId?: string | null;
  createdAt: string;
  updatedAt?: string | null;
}

export interface RequestType {
  id: string;
  kind: RequestKind;
  name: string;
  description?: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt?: string | null;
  deactivatedAt?: string | null;
}

export interface PagedResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  totalCount: number;
}

const REQUEST_KINDS: readonly RequestKind[] = ['Access', 'Service'];
const REQUEST_STATUSES: readonly RequestStatus[] = ['Submitted', 'UnderReview', 'Approved', 'Rejected', 'Fulfilled'];

// Type guard/parser for the API's PortalRequest shape; also used by the apiFixture.test.ts fixture test.
export function isPortalRequest(value: unknown): value is PortalRequest {
  if (typeof value !== 'object' || value === null) return false;
  const r = value as Record<string, unknown>;
  return (
    typeof r.id === 'string' &&
    typeof r.kind === 'string' && REQUEST_KINDS.includes(r.kind as RequestKind) &&
    typeof r.requestTypeId === 'string' &&
    typeof r.requestTypeName === 'string' &&
    typeof r.title === 'string' &&
    typeof r.description === 'string' &&
    typeof r.status === 'string' && REQUEST_STATUSES.includes(r.status as RequestStatus) &&
    typeof r.requesterId === 'string' &&
    typeof r.createdAt === 'string'
  );
}

export function parsePortalRequest(json: string): PortalRequest {
  const parsed: unknown = JSON.parse(json);
  if (!isPortalRequest(parsed)) {
    throw new Error('Response does not match the expected PortalRequest shape.');
  }
  return parsed;
}

async function authHeader(): Promise<Record<string, string>> {
  if (!authConfigured) return {};
  const account = msalInstance.getAllAccounts()[0];
  if (!account) return {};
  const request = { scopes: [apiScope], account };
  try {
    const result = await msalInstance.acquireTokenSilent(request);
    return { Authorization: `Bearer ${result.accessToken}` };
  } catch (e) {
    if (e instanceof InteractionRequiredAuthError) {
      await msalInstance.acquireTokenRedirect(request);
    }
    throw e;
  }
}

function correlationId(): string {
  return crypto.randomUUID();
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'x-correlation-id': correlationId(),
    ...(await authHeader()),
    ...(init.headers as Record<string, string> | undefined)
  };
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText} ${text}`.trim());
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function assertPortalRequest(value: unknown): PortalRequest {
  if (!isPortalRequest(value)) throw new Error('Response does not match the expected PortalRequest shape.');
  return value;
}

export const api = {
  list: () => request<PortalRequest[]>('/api/requests').then((items) => items.map(assertPortalRequest)),
  get: (id: string) => request<PortalRequest>(`/api/requests/${id}`).then(assertPortalRequest),
  create: (body: { kind: RequestKind; requestTypeId: string; title: string; description: string }) =>
    request<PortalRequest>('/api/requests', { method: 'POST', body: JSON.stringify(body) }),
  decide: (id: string, approved: boolean, notes?: string) =>
    request<PortalRequest>(`/api/requests/${id}/decision`, {
      method: 'POST',
      body: JSON.stringify({ approved, notes })
    }),
  fulfil: (id: string) =>
    request<PortalRequest>(`/api/requests/${id}/fulfil`, { method: 'POST' }),
  retryRouting: (id: string) =>
    request<PortalRequest>(`/api/requests/${id}/retry-routing`, { method: 'POST' }),

  auditAllRequests: (page = 1, pageSize = 50) =>
    request<PagedResult<PortalRequest>>(`/api/audit/requests?page=${page}&pageSize=${pageSize}`),
  auditHistory: (id: string, page = 1, pageSize = 50) =>
    request<PagedResult<unknown>>(`/api/audit/requests/${id}/history?page=${page}&pageSize=${pageSize}`),

  securityAccessRequests: (page = 1, pageSize = 50) =>
    request<PagedResult<PortalRequest>>(`/api/security/access-requests?page=${page}&pageSize=${pageSize}`),

  requestTypes: {
    list: () => request<RequestType[]>('/api/request-types'),
    create: (body: { kind: RequestKind; name: string; description?: string }) =>
      request<RequestType>('/api/request-types', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: { name: string; description?: string }) =>
      request<RequestType>(`/api/request-types/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
    deactivate: (id: string) =>
      request<RequestType>(`/api/request-types/${id}/deactivate`, { method: 'POST' })
  }
};
