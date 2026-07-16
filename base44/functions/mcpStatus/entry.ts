Deno.serve(async (req) => {
  try {
    const body = await req.json();
    const { url } = body;
    if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
      return Response.json({ error: 'Missing or invalid url' }, { status: 400 });
    }

    const baseUrl = url.replace(/\/+$/, '');

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);

    try {
      const resp = await fetch(`${baseUrl}/status`, {
        signal: controller.signal,
      });
      clearTimeout(timeout);
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
      clearTimeout(timeout);
      return Response.json({
        ok: false,
        error: fetchErr.message || 'Failed to reach MCP server /status endpoint.',
        checked_at: new Date().toISOString(),
      });
    }
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});