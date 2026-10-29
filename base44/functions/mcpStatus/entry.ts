import { secrets } from 'base44:runtime';
import { requireAdmin } from '../../shared/requireAdmin.ts';

export default async function (req) {
  try {
    const auth = await requireAdmin(req);
    if (auth.error) return auth.error;

    const baseUrl = (secrets.get('MCP_BASE_URL') || '').replace(/\/+$/, '');
    if (!baseUrl) {
      return Response.json({
        ok: false,
        error: 'MCP_BASE_URL is not configured.',
        checked_at: new Date().toISOString(),
      });
    }

    const statusToken = secrets.get('STATUS_TOKEN');
    if (!statusToken) {
      return Response.json({
        ok: false,
        error: 'STATUS_TOKEN is not configured on the server.',
        checked_at: new Date().toISOString(),
      });
    }

    try {
      const resp = await fetch(`${baseUrl}/status`, {
        headers: { 'Authorization': `Bearer ${statusToken}` },
        signal: AbortSignal.timeout(30000),
      });
      const data = await resp.json().catch(() => ({}));

      if (!resp.ok) {
        return Response.json({
          ok: false,
          status: resp.status,
          error: data.error || data.message || `Server returned ${resp.status}`,
          checked_at: new Date().toISOString(),
        });
      }

      return Response.json({
        ok: true,
        status: 200,
        ...data,
        checked_at: data.checked_at || new Date().toISOString(),
      });
    } catch (fetchErr) {
      return Response.json({
        ok: false,
        error: fetchErr.message || 'Failed to reach MCP server /status endpoint.',
        checked_at: new Date().toISOString(),
      });
    }
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}