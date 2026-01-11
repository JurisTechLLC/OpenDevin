import type { VercelRequest, VercelResponse } from '@vercel/node';

/**
 * Vercel serverless function to serve the OpenHands configuration.
 * This provides the necessary config for the frontend to enable GitHub OAuth login.
 */
export default function handler(req: VercelRequest, res: VercelResponse) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Get the host to construct the AUTH_URL dynamically
  const host = req.headers.host || 'localhost:3000';
  const protocol = host.includes('localhost') ? 'http' : 'https';
  
  // If AUTH_URL is not explicitly set, use our custom auth endpoint
  // The frontend's generateAuthUrl expects a Keycloak-style URL, so we provide
  // a custom endpoint that mimics the Keycloak auth path structure
  const authUrl = process.env.AUTH_URL || `${protocol}://${host}/api/auth`;

  // Build the config response from environment variables
  const config = {
    APP_MODE: process.env.APP_MODE || 'saas',
    APP_SLUG: process.env.APP_SLUG || undefined,
    GITHUB_CLIENT_ID: process.env.GITHUB_APP_CLIENT_ID || '',
    POSTHOG_CLIENT_KEY: process.env.POSTHOG_CLIENT_KEY || 'phc_3ESMmY9SgqEAGBB6sMGK5ayYHkeUuknH2vP6FmWH9RA',
    PROVIDERS_CONFIGURED: process.env.GITHUB_APP_CLIENT_ID ? ['github'] : [],
    AUTH_URL: authUrl,
    RECAPTCHA_SITE_KEY: process.env.RECAPTCHA_SITE_KEY || undefined,
    FEATURE_FLAGS: {
      ENABLE_BILLING: process.env.ENABLE_BILLING === 'true',
      HIDE_LLM_SETTINGS: process.env.HIDE_LLM_SETTINGS === 'true',
      ENABLE_JIRA: process.env.ENABLE_JIRA === 'true',
      ENABLE_JIRA_DC: process.env.ENABLE_JIRA_DC === 'true',
      ENABLE_LINEAR: process.env.ENABLE_LINEAR === 'true',
    },
    MAINTENANCE: process.env.MAINTENANCE_START_TIME
      ? { startTime: process.env.MAINTENANCE_START_TIME }
      : undefined,
  };

  return res.status(200).json(config);
}
