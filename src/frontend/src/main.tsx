import React from 'react';
import ReactDOM from 'react-dom/client';
import { InteractionType } from '@azure/msal-browser';
import { MsalAuthenticationTemplate, MsalProvider } from '@azure/msal-react';
import { apiScope, authConfigured, msalInstance } from './auth';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MsalProvider instance={msalInstance}>
      {authConfigured ? (
        <MsalAuthenticationTemplate
          interactionType={InteractionType.Redirect}
          authenticationRequest={{ scopes: [apiScope] }}
        >
          <App />
        </MsalAuthenticationTemplate>
      ) : (
        <App />
      )}
    </MsalProvider>
  </React.StrictMode>
);
