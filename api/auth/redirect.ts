import type { VercelRequest, VercelResponse } from '@vercel/node';

const GITHUB_CLIENT_ID = process.env.GITHUB_APP_CLIENT_ID || '';

/**
 * Vercel serverless function to redirect to GitHub OAuth.
 * This endpoint mimics the Keycloak auth endpoint that the OpenHands frontend expects.
 * 
 * Expected query params (from generateAuthUrl):
 * - kc_idp_hint: identity provider (e.g., "github")
 * - redirect_uri: where to redirect after auth (e.g., /oauth/keycloak/callback)
 * - state: original URL + login_method
 * - scope: OAuth scope
 * - client_id: client ID (ignored, we use our own)
 * - response_type: "code"
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { kc_idp_hint, redirect_uri, state, scope } = req.query;

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
  // We'll use our own callback URL that will then redirect to the frontend's expected callback
  const host = req.headers.host || 'localhost:3000';
  const protocol = host.includes('localhost') ? 'http' : 'https';
  
  // Store the original redirect_uri and state in our callback URL
  const callbackUrl = `${protocol}://${host}/api/github/callback`;
  
  // Encode the original redirect_uri and state so we can use them after GitHub callback
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
