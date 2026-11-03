import { PublicClientApplication, Configuration } from '@azure/msal-browser';

// Microsoft Entra ID (MSAL) config from build-time environment; no secrets embedded (public client / PKCE).
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

// Without Entra config (local demo), the UI skips auth; the API is the real authorization authority.
export const authConfigured = clientId.length > 0;
