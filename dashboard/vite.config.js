import react from '@vitejs/plugin-react';
import javascriptObfuscator from 'vite-plugin-javascript-obfuscator';
import { Buffer } from 'node:buffer';
import { request as httpRequest } from 'node:http';
import process from 'node:process';
import { defineConfig } from 'vite';

const CUTCTX_PROXY_HOST = '127.0.0.1';
const CUTCTX_PROXY_PORT = 8787;
const CUTCTX_PROXY_PREFIXES = ['/health', '/stats', '/v1'];
const DEV_ADMIN_KEY = process.env.CUTCTX_ADMIN_API_KEY || 'headroom-local-admin';

function shouldProxy(url = '') {
  return CUTCTX_PROXY_PREFIXES.some((prefix) => url.startsWith(prefix));
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

const IS_PRODUCTION = process.env.NODE_ENV === 'production';

export default defineConfig({
  plugins: [
    react(),
    cutctxLocalProxyPlugin(),
    // Obfuscate the production bundle to prevent casual reverse engineering.
    // Only applied in production builds — dev stays readable for debugging.
    IS_PRODUCTION && javascriptObfuscator({
      options: {
        // Encode all string literals — grep for algo names fails on the bundle
        stringArray: true,
        stringArrayEncoding: ['base64'],
        stringArrayThreshold: 0.85,
        // Rotate and shuffle the string array at multiple call sites
        rotateStringArray: true,
        shuffleStringArray: true,
        // Flatten control flow — makes logic reconstruction expensive
        controlFlowFlattening: true,
        controlFlowFlatteningThreshold: 0.25,
        // Mangle identifiers beyond what minification does
        identifierNamesGenerator: 'mangled-shuffled',
        // Self-defending: code detects if it's been tampered with
        selfDefending: true,
        // Skip dead code injection — keeps bundle size reasonable
        deadCodeInjection: false,
        // Don't obfuscate the React internals — too slow at runtime
        exclude: [/node_modules/],
      },
    }),
  ].filter(Boolean),
  build: {
    // Disable source maps in production — never ship a roadmap to your source
    sourcemap: false,
  },
});
