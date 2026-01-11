import type { VercelRequest, VercelResponse } from '@vercel/node';

/**
 * Vercel serverless function to serve available security analyzers.
 * Returns a list of supported security analyzers.
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

  // Return empty list - security analyzers are optional
  const analyzers: string[] = [];

  return res.status(200).json(analyzers);
}
