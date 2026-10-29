import { secrets } from 'base44:runtime';
import { requireAdmin } from '../../shared/requireAdmin.ts';

export default async function (req) {
  try {
    const auth = await requireAdmin(req);
    if (auth.error) return auth.error;

    const baseUrl = (secrets.get('MCP_BASE_URL') || '').replace(/\/+$/, '');
    return Response.json({ mcp_base_url: baseUrl });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}