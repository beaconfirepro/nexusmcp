import { requireAdmin } from '../../shared/requireAdmin.ts';

export default async function (req) {
  try {
    const auth = await requireAdmin(req);
    if (auth.error) return auth.error;
    const { base44 } = auth;

    const body = await req.json().catch(() => ({}));
    const id = body.id;
    if (!id) return Response.json({ error: 'id is required' }, { status: 400 });

    const conn = await base44.entities.ApiConnection.get(id).catch((e) => (e.status === 404 ? null : Promise.reject(e)));
    if (!conn) return Response.json({ error: 'Not found' }, { status: 404 });

    const base = (conn.base_url || '').replace(/\/+$/, '');
    if (!base) return Response.json({ error: 'Connection has no base_url' }, { status: 400 });

    let path = typeof body.path === 'string' && body.path.trim() ? body.path.trim() : '/';
    if (!path.startsWith('/')) path = '/' + path;

    const headers = {};
    if (conn.auth_type === 'bearer' && conn.secret) {
      headers['Authorization'] = `Bearer ${conn.secret}`;
    } else if (conn.auth_type === 'header' && conn.header_name && conn.secret) {
      headers[conn.header_name] = conn.secret;
    }

    try {
      const resp = await fetch(`${base}${path}`, {
        method: 'GET',
        headers,
        signal: AbortSignal.timeout(15000),
      });
      const text = await resp.text();
      return Response.json({ status: resp.status, body: text.slice(0, 500) });
    } catch (fetchErr) {
      return Response.json({ status: null, error: fetchErr.message });
    }
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}