import { createClientFromRequest } from 'npm:@base44/sdk@0.8.54';
import { secrets } from 'base44:runtime';

function timingSafeEqual(a, b) {
  const ab = new TextEncoder().encode(a);
  const bb = new TextEncoder().encode(b);
  const len = Math.max(ab.length, bb.length);
  let diff = ab.length ^ bb.length;
  for (let i = 0; i < len; i++) {
    diff |= (ab[i] ?? 0) ^ (bb[i] ?? 0);
  }
  return diff === 0;
}

export default async function (req) {
  try {
    if (req.method !== 'GET') {
      return Response.json({ error: 'Method not allowed' }, { status: 405 });
    }

    const expected = secrets.get('NEXUS_BRIDGE_SECRET') || '';
    const header = req.headers.get('Authorization') || '';
    const provided = header.startsWith('Bearer ') ? header.slice(7) : '';

    if (!expected || !provided || !timingSafeEqual(provided, expected)) {
      return Response.json({ error: 'unauthorized' }, { status: 401 });
    }

    const base44 = createClientFromRequest(req);
    const res = await base44.asServiceRole.entities.ApiConnection.filter({ enabled: true });
    const rows = Array.isArray(res) ? res : (res?.items || []);

    const connections = rows.map((r) => ({
      slug: r.slug,
      name: r.name,
      base_url: r.base_url,
      auth_type: r.auth_type,
      header_name: r.header_name || '',
      secret: r.secret || '',
      description: r.description || '',
    }));

    return Response.json({ connections });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}