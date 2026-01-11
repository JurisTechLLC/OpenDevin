import type { VercelRequest, VercelResponse } from '@vercel/node';
import * as jose from 'jose';

const JWT_SECRET = process.env.JWT_SECRET || process.env.NEXTAUTH_SECRET || 'openhands-default-secret';
const COOKIE_NAME = 'openhands-auth-token';

/**
 * Vercel serverless function to check if user is authenticated.
 * Returns 200 if authenticated, 401 if not.
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Access-Control-Allow-Credentials', 'true');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST' && req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Get token from cookie or Authorization header
    let token: string | undefined;
    
    // Try cookie first
    const cookies = req.cookies;
    if (cookies && cookies[COOKIE_NAME]) {
      token = cookies[COOKIE_NAME];
    }
    
    // Fallback to Authorization header
    if (!token) {
      const authHeader = req.headers.authorization;
      if (authHeader?.startsWith('Bearer ')) {
        token = authHeader.substring(7);
      }
    }

    if (!token) {
      return res.status(401).json({ 
        error: 'Not authenticated',
        message: 'No authentication token found'
      });
    }

    // Verify JWT token
    const secret = new TextEncoder().encode(JWT_SECRET);
    const { payload } = await jose.jwtVerify(token, secret, {
      issuer: 'openhands-vercel',
      audience: 'openhands-users',
    });

    // Return user info
    return res.status(200).json({
      authenticated: true,
      user: {
        id: payload.sub,
        email: payload.email,
        name: payload.name,
        avatar_url: payload.avatar_url,
        github_id: payload.github_id,
      }
    });
  } catch (error) {
    // Token verification failed
    return res.status(401).json({ 
      error: 'Not authenticated',
      message: 'Invalid or expired token'
    });
  }
}
