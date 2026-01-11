import type { VercelRequest, VercelResponse } from '@vercel/node';

/**
 * Vercel serverless function to serve available models.
 * Returns a list of supported LLM models.
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

  // Return a list of commonly available models
  // In a full deployment, this would query the actual backend
  const models = [
    'anthropic/claude-sonnet-4-20250514',
    'anthropic/claude-opus-4-20250514',
    'anthropic/claude-3-5-sonnet-20241022',
    'anthropic/claude-3-5-haiku-20241022',
    'openai/gpt-4o',
    'openai/gpt-4o-mini',
    'openai/gpt-4-turbo',
    'openai/o1-preview',
    'openai/o1-mini',
  ];

  return res.status(200).json(models);
}
