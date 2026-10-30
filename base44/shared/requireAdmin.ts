import { createClientFromRequest } from 'npm:@base44/sdk@0.8.54';

/**
 * Returns { base44, user } for a signed-in admin, or { error: Response } to return directly.
 */
export async function requireAdmin(req: Request) {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me().catch((e: any) => (e.status === 401 ? null : Promise.reject(e)));
  if (!user) {
    return { error: Response.json({ error: 'Unauthorized' }, { status: 401 }) };
  }
  if (user.role !== 'admin') {
    return { error: Response.json({ error: 'Forbidden' }, { status: 403 }) };
  }
  return { base44, user };
}