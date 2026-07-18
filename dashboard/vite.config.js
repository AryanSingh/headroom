import react from '@vitejs/plugin-react';
import { Buffer } from 'node:buffer';
import { readFileSync } from 'node:fs';
import { request as httpRequest } from 'node:http';
import { resolve } from 'node:path';
import process from 'node:process';
import { defineConfig } from 'vite';

const CUTCTX_PROXY_HOST = process.env.CUTCTX_PROXY_HOST || '127.0.0.1';
const CUTCTX_PROXY_PORT = Number(process.env.CUTCTX_PROXY_PORT) || 8787;
const CUTCTX_PROXY_PREFIXES = [
  '/health',
  '/stats',
  '/v1',
  '/admin',
  '/config',
  '/audit',
  '/rbac',
  '/firewall/scan',
  '/firewall/status',
  // The Orchestrator page reads provider policy decisions; without this
  // prefix the dev server answers with the SPA shell and the panel shows
  // "/policy/status returned non-JSON response".
  '/policy',
  // Request-trace inspector (Overview) and Governance tier data.
  '/transformations',
  '/entitlements',
];
// SPA routes that look like they might match a proxy prefix but are not API endpoints.
const SPA_ROUTE_PREFIXES = ['/firewall', '/governance', '/orchestrator', '/capabilities', '/memory', '/playground', '/docs', '/'];
const DEV_ADMIN_KEY = process.env.CUTCTX_ADMIN_API_KEY || 'cutctx-local-admin';

function readCutctxVersion() {
  try {
    const pyproject = readFileSync(resolve(__dirname, '../pyproject.toml'), 'utf-8');
    const match = pyproject.match(/^\s*version\s*=\s*"([^"]+)"/m);
    return match?.[1] || 'unknown';
  } catch {
    return 'unknown';
  }
}

const CUTCTX_VERSION = readCutctxVersion();

function shouldProxy(url = '') {
  const pathname = url.split('?')[0].split('#')[0];
  if (SPA_ROUTE_PREFIXES.includes(pathname)) {
    return false;
  }
  return CUTCTX_PROXY_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

async function readRequestBody(req) {
  const chunks = [];

  for await (const chunk of req) {
    chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : chunk);
  }

  return chunks.length > 0 ? Buffer.concat(chunks) : undefined;
}

function buildUpstreamHeaders(req, body) {
  const headers = {};

  const contentType = req.headers['content-type'];
  const accept = req.headers.accept;
  const authorization = req.headers.authorization || `Bearer ${DEV_ADMIN_KEY}`;
  const adminKey = req.headers['x-cutctx-admin-key'] || DEV_ADMIN_KEY;

  if (contentType) {
    headers['content-type'] = contentType;
  }

  if (accept) {
    headers.accept = accept;
  }

  if (authorization) {
    headers.authorization = authorization;
  }

  if (adminKey) {
    headers['x-cutctx-admin-key'] = adminKey;
  }

  if (body) {
    headers['content-length'] = String(body.length);
  }

  return headers;
}

function proxyToCutctx(req, res, body) {
  return new Promise((resolve, reject) => {
    const upstreamReq = httpRequest(
      {
        host: CUTCTX_PROXY_HOST,
        port: CUTCTX_PROXY_PORT,
        path: req.url,
        method: req.method,
        headers: buildUpstreamHeaders(req, body),
      },
      (upstreamRes) => {
        res.statusCode = upstreamRes.statusCode || 502;

        for (const [key, value] of Object.entries(upstreamRes.headers)) {
          if (value == null || key.toLowerCase() === 'content-encoding') {
            continue;
          }
          res.setHeader(key, value);
        }

        upstreamRes.on('error', reject);
        upstreamRes.pipe(res);
        upstreamRes.on('end', resolve);
      },
    );

    upstreamReq.on('error', reject);

    if (body) {
      upstreamReq.write(body);
    }

    upstreamReq.end();
  });
}

function cutctxLocalProxyPlugin() {
  return {
    name: 'cutctx-local-proxy',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url || !shouldProxy(req.url)) {
          next();
          return;
        }

        try {
          const body = await readRequestBody(req);
          await proxyToCutctx(req, res, body);
        } catch (error) {
          res.statusCode = 502;
          res.setHeader('content-type', 'application/json');
          res.end(
            JSON.stringify({
              error: 'cutctx_proxy_unreachable',
              detail: error instanceof Error ? error.message : String(error),
            }),
          );
        }
      });
    },
  };
}

export default defineConfig({
  define: {
    'import.meta.env.VITE_CUTCTX_VERSION': JSON.stringify(CUTCTX_VERSION),
  },
  plugins: [
    react(),
    cutctxLocalProxyPlugin(),
    // Obfuscate the production bundle to prevent casual reverse engineering.
    // IS_PRODUCTION && javascriptObfuscator({ ... })
  ].filter(Boolean),
  build: {
    // Disable source maps in production — never ship a roadmap to your source
    sourcemap: false,
  },
});
