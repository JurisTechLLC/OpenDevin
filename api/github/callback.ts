import type { VercelRequest, VercelResponse } from '@vercel/node';
import * as jose from 'jose';

const GITHUB_CLIENT_ID = process.env.GITHUB_APP_CLIENT_ID || '';
const GITHUB_CLIENT_SECRET = process.env.GITHUB_APP_CLIENT_SECRET || '';
const JWT_SECRET = process.env.JWT_SECRET || process.env.NEXTAUTH_SECRET || 'openhands-default-secret';
const COOKIE_NAME = 'openhands-auth-token';

interface GitHubTokenResponse {
  access_token: string;
  token_type: string;
  scope: string;
  error?: string;
  error_description?: string;
}

interface GitHubUser {
  id: number;
  login: string;
  name: string | null;
  email: string | null;
  avatar_url: string;
}

interface OAuthState {
  original_redirect_uri?: string;
  original_state?: string;
}

/**
 * Vercel serverless function to handle GitHub OAuth callback.
 * Exchanges the authorization code for an access token, fetches user info,
 * creates a JWT, and redirects to the app.
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Allow-Credentials', 'true');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // Handle both GET (redirect from GitHub) and POST (from frontend)
  const code = req.method === 'GET' ? req.query.code : req.body?.code;
  const stateParam = req.method === 'GET' ? req.query.state : req.body?.state;
  
  if (!code || typeof code !== 'string') {
    return res.status(400).json({ 
      error: 'Missing authorization code',
      message: 'No code parameter provided'
    });
  }

  if (!GITHUB_CLIENT_ID || !GITHUB_CLIENT_SECRET) {
    return res.status(500).json({ 
      error: 'Server configuration error',
      message: 'GitHub OAuth credentials not configured'
    });
  }

  // Parse the state parameter to get original redirect info
  let oauthState: OAuthState = {};
  if (stateParam && typeof stateParam === 'string') {
    try {
      oauthState = JSON.parse(Buffer.from(stateParam, 'base64').toString('utf-8'));
    } catch {
      // State might not be base64 encoded, ignore
    }
  }

  try {
    // Exchange code for access token
    const tokenResponse = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        client_id: GITHUB_CLIENT_ID,
        client_secret: GITHUB_CLIENT_SECRET,
        code: code,
      }),
    });

    const tokenData: GitHubTokenResponse = await tokenResponse.json();

    if (tokenData.error) {
      return res.status(400).json({ 
        error: 'GitHub OAuth error',
        message: tokenData.error_description || tokenData.error
      });
    }

    if (!tokenData.access_token) {
      return res.status(400).json({ 
        error: 'No access token',
        message: 'GitHub did not return an access token'
      });
    }

    // Fetch user info from GitHub
    const userResponse = await fetch('https://api.github.com/user', {
      headers: {
        'Authorization': `Bearer ${tokenData.access_token}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'OpenHands-Vercel',
      },
    });

    if (!userResponse.ok) {
      return res.status(400).json({ 
        error: 'Failed to fetch user info',
        message: 'Could not retrieve user information from GitHub'
      });
    }

    const userData: GitHubUser = await userResponse.json();

    // Fetch user's primary email if not public
    let email = userData.email;
    if (!email) {
      const emailsResponse = await fetch('https://api.github.com/user/emails', {
        headers: {
          'Authorization': `Bearer ${tokenData.access_token}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'OpenHands-Vercel',
        },
      });

      if (emailsResponse.ok) {
        const emails = await emailsResponse.json();
        const primaryEmail = emails.find((e: { primary: boolean; verified: boolean; email: string }) => 
          e.primary && e.verified
        );
        if (primaryEmail) {
          email = primaryEmail.email;
        }
      }
    }

    // Create JWT token
    const secret = new TextEncoder().encode(JWT_SECRET);
    const token = await new jose.SignJWT({
      sub: userData.id.toString(),
      email: email,
      name: userData.name || userData.login,
      avatar_url: userData.avatar_url,
      github_id: userData.id,
      github_login: userData.login,
      github_access_token: tokenData.access_token,
    })
      .setProtectedHeader({ alg: 'HS256' })
      .setIssuedAt()
      .setIssuer('openhands-vercel')
      .setAudience('openhands-users')
      .setExpirationTime('24h')
      .sign(secret);

    // For GET requests (redirect from GitHub), set cookie and redirect
    if (req.method === 'GET') {
      // Set the auth cookie
      res.setHeader('Set-Cookie', [
        `${COOKIE_NAME}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${24 * 60 * 60}${process.env.NODE_ENV === 'production' ? '; Secure' : ''}`
      ]);

      // Get the host for redirect
      const host = req.headers.host || 'localhost:3000';
      const protocol = host.includes('localhost') ? 'http' : 'https';
      
      // If we have original state from the auth redirect, use it to construct the redirect URL
      // The original_state contains the URL with login_method parameter
      if (oauthState.original_state) {
        // The original_state is the full URL with login_method, e.g., "https://host/?login_method=github"
        // We need to redirect there so the frontend can pick up the login_method
        return res.redirect(302, oauthState.original_state);
      }
      
      // Default redirect to home with login_method
      const redirectUrl = `${protocol}://${host}/?login_method=github`;
      return res.redirect(302, redirectUrl);
    }

    // For POST requests (from frontend), return the token
    return res.status(200).json({
      success: true,
      token: token,
      user: {
        id: userData.id.toString(),
        email: email,
        name: userData.name || userData.login,
        avatar_url: userData.avatar_url,
        github_login: userData.login,
      },
      github_access_token: tokenData.access_token,
    });
  } catch (error) {
    console.error('GitHub OAuth error:', error);
    return res.status(500).json({ 
      error: 'Authentication failed',
      message: error instanceof Error ? error.message : 'Unknown error occurred'
    });
  }
}
