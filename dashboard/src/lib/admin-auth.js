const STORAGE_KEY = 'cutctxAdminKey';
const WINDOW_MEMORY_KEY = '__cutctxAdminKey';

let inMemoryAdminKey = '';

function readWindowMemoryKey() {
  if (typeof window === 'undefined') {
    return '';
  }

  return typeof window[WINDOW_MEMORY_KEY] === 'string' ? window[WINDOW_MEMORY_KEY] : '';
}

function readStorageKey() {
  if (typeof window === 'undefined') {
    return '';
  }

  try {
    const ls = window.localStorage.getItem(STORAGE_KEY);
    if (ls) {
      return ls;
    }
  } catch {
    // ignore
  }

  try {
    const ss = window.sessionStorage.getItem(STORAGE_KEY);
    if (ss) {
      return ss;
    }
  } catch {
    // ignore
  }

  try {
    const match = document.cookie.match(new RegExp(`(^| )${STORAGE_KEY}=([^;]+)`));
    if (match) {
      return decodeURIComponent(match[2]);
    }
  } catch {
    // ignore
  }

  return '';
}

export function readStoredAdminKey() {
  return inMemoryAdminKey || readWindowMemoryKey() || readStorageKey();
}

export function writeStoredAdminKey(value) {
  const normalized = value.trim();
  inMemoryAdminKey = normalized;

  if (typeof window === 'undefined') {
    return;
  }

  window[WINDOW_MEMORY_KEY] = normalized;

  if (normalized) {
    try {
      window.localStorage.setItem(STORAGE_KEY, normalized);
    } catch {
      // ignore
    }
    try {
      window.sessionStorage.setItem(STORAGE_KEY, normalized);
    } catch {
      // ignore
    }
    try {
      document.cookie = `${STORAGE_KEY}=${encodeURIComponent(normalized)}; path=/; max-age=31536000; SameSite=Lax`;
    } catch {
      // ignore
    }
  } else {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    try {
      document.cookie = `${STORAGE_KEY}=; path=/; max-age=0; SameSite=Lax`;
    } catch {
      // ignore
    }
  }
}

export function getAdminAuthHeaders() {
  const key = readStoredAdminKey();
  return key ? { 'x-cutctx-admin-key': key } : {};
}

/**
 * Adopt an admin key from a `?key=` URL parameter, matching the same
 * query-param auth the proxy's own HTTP API and legacy dashboard already
 * accept for the page load itself. Without this, visiting a bookmarked
 * `/dashboard?key=...` link loads the page fine (the initial HTML request
 * carries the key) but every subsequent client-side fetch has nothing to
 * authenticate with, since this app only otherwise reads the key from
 * localStorage via the Playground page's input field.
 *
 * Persists the key the same way the Playground input does, then strips it
 * from the visible URL so it doesn't linger in browser history or get
 * accidentally copy-pasted onward.
 */
export function adoptAdminKeyFromUrl() {
  if (typeof window === 'undefined') {
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const key = params.get('key');
  if (!key) {
    return;
  }

  writeStoredAdminKey(key);

  params.delete('key');
  const query = params.toString();
  const nextUrl =
    window.location.pathname + (query ? `?${query}` : '') + window.location.hash;
  window.history.replaceState(null, '', nextUrl);
}
