import { PublicClientApplication, Configuration } from '@azure/msal-browser';

// Microsoft Entra ID (MSAL) configuration. Values come from environment at
// build time; no secrets are embedded (public client / PKCE).
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID ?? '';
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID ?? 'common';

export const apiScope =
  import.meta.env.VITE_API_SCOPE ?? 'api://smartserve-api/access_as_user';

const config: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin
  },
  cache: { cacheLocation: 'sessionStorage' }
};

export const msalInstance = new PublicClientApplication(config);

// When Entra is not configured (local demo), auth is effectively disabled and
// the API runs in its own dev mode. UI still enforces nothing security-critical;
// the backend is the authority.
export const authConfigured = clientId.length > 0;
