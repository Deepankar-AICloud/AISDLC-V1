import { msalInstance, apiScope, authConfigured } from './auth';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export type RequestCategory =
  | 'GitHubAccess' | 'AzureAccess' | 'VpnAccess' | 'ApplicationAccess'
  | 'DatabaseAccess' | 'ProductionAccess' | 'SoftwareInstallation'
  | 'LaptopRequest' | 'HardwareRequest' | 'PasswordSupport' | 'GeneralSupport';

export type RequestStatus =
  | 'Draft' | 'Submitted' | 'ManagerApproval' | 'SecurityApproval'
  | 'ItProcessing' | 'Provisioned' | 'AwaitingConfirmation' | 'Closed' | 'Rejected';

export interface AccessRequest {
  id: string;
  title: string;
  description: string;
  category: RequestCategory;
  status: RequestStatus;
  requesterId: string;
  assignedToId?: string | null;
  requiresSecurityReview: boolean;
  createdAt: string;
  updatedAt?: string | null;
}

async function authHeader(): Promise<Record<string, string>> {
  if (!authConfigured) return {};
  const account = msalInstance.getAllAccounts()[0];
  if (!account) return {};
  const result = await msalInstance.acquireTokenSilent({
    scopes: [apiScope],
    account
  });
  return { Authorization: `Bearer ${result.accessToken}` };
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

export const api = {
  list: () => request<AccessRequest[]>('/api/requests'),
  get: (id: string) => request<AccessRequest>(`/api/requests/${id}`),
  create: (body: { title: string; description: string; category: RequestCategory }) =>
    request<AccessRequest>('/api/requests', {
      method: 'POST',
      body: JSON.stringify(body)
    }),
  decide: (id: string, approved: boolean, notes?: string) =>
    request<AccessRequest>(`/api/requests/${id}/decision`, {
      method: 'POST',
      body: JSON.stringify({ approved, notes })
    }),
  confirm: (id: string) =>
    request<AccessRequest>(`/api/requests/${id}/confirm`, { method: 'POST' }),
  comment: (id: string, bodyText: string) =>
    request<void>(`/api/requests/${id}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body: bodyText })
    })
};
