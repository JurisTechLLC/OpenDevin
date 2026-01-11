import type { VercelRequest, VercelResponse } from '@vercel/node';

const GITHUB_CLIENT_ID = process.env.GITHUB_APP_CLIENT_ID || '';

/**
 * Vercel serverless function that mimics the Keycloak auth endpoint.
 * This endpoint redirects to GitHub OAuth when kc_idp_hint=github.
 * 
 * The OpenHands frontend's generateAuthUrl creates URLs like:
 * ${authUrl}/realms/allhands/protocol/openid-connect/auth?
 *   client_id=allhands&
 *   kc_idp_hint=github&
 *   response_type=code&
 *   redirect_uri=${redirectUri}&
 *   scope=${scope}&
 *   state=${state}
 * 
 * This endpoint intercepts that request and redirects to GitHub OAuth directly.
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { kc_idp_hint, redirect_uri, state } = req.query;

  // Only support GitHub for now
  if (kc_idp_hint !== 'github') {
    return res.status(400).json({ 
      error: 'Unsupported identity provider',
      message: `Provider "${kc_idp_hint}" is not supported. Only "github" is available.`
    });
  }

  if (!GITHUB_CLIENT_ID) {
    return res.status(500).json({ 
      error: 'Server configuration error',
      message: 'GitHub OAuth client ID not configured'
    });
  }

  // Build GitHub OAuth URL
  const host = req.headers.host || 'localhost:3000';
  const protocol = host.includes('localhost') ? 'http' : 'https';
  
  // Our callback URL - GitHub will redirect here after auth
  const callbackUrl = `${protocol}://${host}/api/github/callback`;
  
  // Encode the original redirect_uri and state so we can use them after GitHub callback
  // The state from the frontend contains the return URL with login_method
  const oauthState = JSON.stringify({
    original_redirect_uri: redirect_uri,
    original_state: state,
  });

  const githubAuthUrl = new URL('https://github.com/login/oauth/authorize');
  githubAuthUrl.searchParams.set('client_id', GITHUB_CLIENT_ID);
  githubAuthUrl.searchParams.set('redirect_uri', callbackUrl);
  githubAuthUrl.searchParams.set('scope', 'user:email read:user');
  githubAuthUrl.searchParams.set('state', Buffer.from(oauthState).toString('base64'));

  return res.redirect(302, githubAuthUrl.toString());
}
