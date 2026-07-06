export function getProxyBaseUrl() {
  const configured = (import.meta.env.VITE_CUTCTX_PROXY_URL || '').replace(/\/$/, '');
  if (!configured || typeof window === 'undefined') {
    return configured;
  }

  try {
    const target = new URL(configured);
    const current = new URL(window.location.href);
    const localhostNames = new Set(['127.0.0.1', 'localhost', '::1']);

    if (
      localhostNames.has(target.hostname) &&
      localhostNames.has(current.hostname) &&
      target.origin !== current.origin
    ) {
      return '';
    }
  } catch {
    return configured;
  }

  return configured;
}

export function getProxyUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const baseUrl = getProxyBaseUrl();
  return baseUrl ? `${baseUrl}${normalizedPath}` : normalizedPath;
}
