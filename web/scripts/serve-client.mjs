import { createReadStream, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";

const port = Number(process.env.PORT || 5000);
const root = resolve("build/client");
const indexFile = join(root, "index.html");

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".webp": "image/webp",
};

function resolveFile(urlPath) {
  const cleanPath = decodeURIComponent(urlPath.split("?")[0] || "/");
  const relativePath = normalize(cleanPath).replace(/^(\.\.(\/|\\|$))+/, "");
  const candidate = resolve(root, `.${sep}${relativePath}`);

  if (!candidate.startsWith(root)) {
    return indexFile;
  }

  try {
    const stats = statSync(candidate);
    return stats.isDirectory() ? indexFile : candidate;
  } catch {
    return indexFile;
  }
}

const server = createServer((request, response) => {
  const file = resolveFile(request.url || "/");
  const contentType = mimeTypes[extname(file)] || "application/octet-stream";

  response.writeHead(200, {
    "Cache-Control": file === indexFile ? "no-cache" : "public, max-age=31536000, immutable",
    "Content-Type": contentType,
  });

  const stream = createReadStream(file);

  // A browser that navigates away mid-response makes the socket emit 'error'.
  // Unhandled, that took the whole server down and failed every test still to
  // run, which reads as a wall of connection refusals rather than one abort.
  stream.on("error", () => {
    response.destroy();
  });
  response.on("error", () => {
    stream.destroy();
  });
  response.on("close", () => {
    stream.destroy();
  });

  stream.pipe(response);
});

// Client-socket resets surface here too, and are never worth exiting over.
server.on("clientError", (_error, socket) => {
  socket.destroy();
});
server.on("error", (error) => {
  console.error("[serve-client] server error:", error);
});

server.listen(port, "0.0.0.0");
