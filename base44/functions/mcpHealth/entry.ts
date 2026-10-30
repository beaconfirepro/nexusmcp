import { secrets } from 'base44:runtime';
import { requireAdmin } from '../../shared/requireAdmin.ts';

export default async function (req) {
  try {
    const auth = await requireAdmin(req);
    if (auth.error) return auth.error;

    const baseUrl = (secrets.get('MCP_BASE_URL') || '').replace(/\/+$/, '');
    if (!baseUrl) {
      return Response.json({
        healthy: false,
        message: 'MCP_BASE_URL is not configured.',
        checked_at: new Date().toISOString(),
      });
    }

    try {
      const resp = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(8000) });
      const data = await resp.json().catch(() => ({}));
      return Response.json({
        healthy: resp.ok,
        server: data,
        checked_at: new Date().toISOString(),
      });
    } catch (fetchErr) {
      return Response.json({
        healthy: false,
        message: fetchErr.message,
        checked_at: new Date().toISOString(),
      });
    }
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}