const SUPABASE_URL = 'https://udeekuvifncmqvoywhlg.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVkZWVrdXZpZm5jbXF2b3l3aGxnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ3OTQ3NjUsImV4cCI6MjEwMDM3MDc2NX0.Jhg4l0uf1ccwT-2Om3Ae3HOjy9SaCvX6EHnZ1FGhRGA';
const SESSION_KEY = 'cutctx-license-session';

const form = document.querySelector('#license-login-form');
const emailInput = document.querySelector('#license-email');
const submitButton = document.querySelector('#license-submit');
const status = document.querySelector('#license-status');
const results = document.querySelector('#license-results');
const list = document.querySelector('#license-list');
const signOutButton = document.querySelector('#license-signout');

function setStatus(message, state = '') {
  status.textContent = message;
  status.dataset.state = state;
}

function licensePortalUrl() {
  return new URL('/licenses', window.location.origin).toString();
}

function readSession() {
  try {
    return JSON.parse(window.localStorage.getItem(SESSION_KEY) || 'null');
  } catch {
    return null;
  }
}

function saveSession(session) {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

function clearSession() {
  window.localStorage.removeItem(SESSION_KEY);
}

function sessionFromUrl() {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const accessToken = hash.get('access_token');
  if (accessToken) {
    saveSession({ accessToken, expiresAt: Number(hash.get('expires_at') || 0) });
    window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
    return readSession();
  }
  if (hash.get('error_description')) {
    setStatus(decodeURIComponent(hash.get('error_description').replace(/\+/g, ' ')), 'error');
    window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
  }
  return null;
}

function request(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: {
      apikey: SUPABASE_ANON_KEY,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
}

function dateLabel(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'No expiry date' : date.toLocaleDateString();
}

function renderLicenses(licenses) {
  results.hidden = false;
  list.replaceChildren();
  if (!licenses.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No CutCtx licenses are associated with this account yet.';
    list.append(empty);
    return;
  }

  for (const license of licenses) {
    const card = document.createElement('article');
    card.className = 'license-card';
    const title = document.createElement('h3');
    title.textContent = license.tier;
    const key = document.createElement('p');
    key.textContent = 'License key: ';
    const keyValue = document.createElement('code');
    keyValue.textContent = license.key;
    key.append(keyValue);
    const details = document.createElement('p');
    details.textContent = `${license.status} · expires ${dateLabel(license.expiresAt)} · ${license.seatsUsed}/${license.seatsLimit} seats`;
    card.append(title, key, details);
    list.append(card);
  }
}

async function loadLicenses(session) {
  if (!session?.accessToken) return;
  setStatus('Loading your licenses…');
  const response = await request(`${SUPABASE_URL}/functions/v1/my-licenses`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${session.accessToken}` },
    body: '{}',
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    clearSession();
    results.hidden = true;
    setStatus(body.message || 'We could not load your licenses. Please request a new Magic Link.', 'error');
    return;
  }
  setStatus('');
  renderLicenses(body.licenses || []);
}

async function sendMagicLink(event) {
  event.preventDefault();
  const email = emailInput.value.trim();
  if (!email) return;

  submitButton.disabled = true;
  setStatus('Sending your secure Magic Link…');
  const response = await request(`${SUPABASE_URL}/auth/v1/otp`, {
    method: 'POST',
    body: JSON.stringify({ email, create_user: true, email_redirect_to: licensePortalUrl() }),
  });
  const body = await response.json().catch(() => ({}));
  submitButton.disabled = false;
  setStatus(response.ok ? 'Check your inbox for a secure Magic Link from CutCtx.' : (body.msg || body.message || 'We could not send the Magic Link. Please try again.'), response.ok ? 'success' : 'error');
}

form.addEventListener('submit', sendMagicLink);
signOutButton.addEventListener('click', () => {
  clearSession();
  results.hidden = true;
  list.replaceChildren();
  setStatus('You have been signed out.', 'success');
  emailInput.focus();
});

loadLicenses(sessionFromUrl() || readSession()).catch(() => {
  clearSession();
  setStatus('We could not load your licenses. Please request a new Magic Link.', 'error');
});
