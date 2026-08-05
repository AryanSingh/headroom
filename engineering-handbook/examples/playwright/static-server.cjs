const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const root = __dirname;
const port = 41714;
const contentTypes = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8" };

function createFixtureServer() {
  return http.createServer((request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "content-type": "text/plain; charset=utf-8" });
    response.end("ready\n");
    return;
  }
  const requested = request.url === "/" ? "index.html" : request.url.slice(1);
  const file = path.resolve(root, requested);
  if (!file.startsWith(root) || !fs.existsSync(file)) {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("not found\n");
    return;
  }
  response.writeHead(200, { "content-type": contentTypes[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(response);
  });
}

if (require.main === module) {
  createFixtureServer().listen(port, "127.0.0.1");
}

module.exports = { createFixtureServer, port };
