import { secrets } from 'base44:runtime';
import { requireAdmin } from '../../shared/requireAdmin.ts';

function base64url(bytes) {
  let bin = '';
  const arr = new Uint8Array(bytes);
  for (let i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export default async function (req) {
  try {
    const auth = await requireAdmin(req);
    if (auth.error) return auth.error;
    const { user } = auth;

    const body = await req.json().catch(() => ({}));
    const request = body.request;
    if (!request || typeof request !== 'string') {
      return Response.json({ error: 'request is required' }, { status: 400 });
    }

    const signingSecret = secrets.get('NEXUS_BRIDGE_SECRET') || '';
    const baseUrl = (secrets.get('MCP_BASE_URL') || '').replace(/\/+$/, '');
    if (!signingSecret || !baseUrl) {
      return Response.json({ error: 'Server is not configured.' }, { status: 500 });
    }

    const now = Math.floor(Date.now() / 1000);
    const payload = {
      sub: user.email,
      name: user.full_name || '',
      req: request,
      iat: now,
      exp: now + 120,
    };
    const payloadBytes = new TextEncoder().encode(JSON.stringify(payload));

    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(signingSecret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign'],
    );
    const signature = new Uint8Array(await crypto.subtle.sign('HMAC', key, payloadBytes));

    const assertion = `${base64url(payloadBytes)}.${base64url(signature)}`;
    return Response.json({
      redirect_url: `${baseUrl}/authorize/bridge?assertion=${encodeURIComponent(assertion)}`,
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}