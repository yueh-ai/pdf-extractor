import { createReadStream, realpathSync, statSync } from 'node:fs';
import { extname, resolve, sep } from 'node:path';

const SERVED_PREFIXES = ['/runs/', '/object_store/'];

const CONTENT_TYPES = new Map([
  ['.json', 'application/json; charset=utf-8'],
  ['.md', 'text/markdown; charset=utf-8'],
  ['.png', 'image/png'],
  ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'],
  ['.webp', 'image/webp'],
]);

export function contentTypeForPath(pathname) {
  return CONTENT_TYPES.get(extname(pathname).toLowerCase()) ?? 'application/octet-stream';
}

export function defaultRepoRoot() {
  return process.cwd().endsWith(`${sep}reviewer`) ? resolve(process.cwd(), '..') : process.cwd();
}

export function filePathForRepoRequest(pathname, repoRoot = defaultRepoRoot()) {
  const allowedRoot = allowedRootForRepoRequest(pathname, repoRoot);
  if (!allowedRoot) {
    return null;
  }

  let decodedPathname;
  try {
    decodedPathname = decodeURIComponent(pathname);
  } catch {
    return null;
  }

  const normalizedRepoRoot = resolve(repoRoot);
  const candidatePath = resolve(normalizedRepoRoot, decodedPathname.slice(1));
  return pathIsInside(candidatePath, allowedRoot) ? candidatePath : null;
}

export function allowedRootForRepoRequest(pathname, repoRoot = defaultRepoRoot()) {
  const prefix = SERVED_PREFIXES.find((candidate) => pathname.startsWith(candidate));
  if (!prefix) {
    return null;
  }

  let decodedPathname;
  try {
    decodedPathname = decodeURIComponent(pathname);
  } catch {
    return null;
  }

  if (!decodedPathname.startsWith(prefix)) {
    return null;
  }

  return resolve(repoRoot, prefix.slice(1, -1));
}

function pathIsInside(candidatePath, allowedRoot) {
  const normalizedAllowedRoot = resolve(allowedRoot);
  const normalizedCandidatePath = resolve(candidatePath);
  return (
    normalizedCandidatePath === normalizedAllowedRoot ||
    normalizedCandidatePath.startsWith(normalizedAllowedRoot + sep)
  );
}

export function createRepoRootStaticMiddleware(repoRoot = defaultRepoRoot()) {
  return function repoRootStaticMiddleware(req, res, next) {
    const method = req.method ?? 'GET';
    if (method !== 'GET' && method !== 'HEAD') {
      next();
      return;
    }

    const url = new URL(req.url ?? '/', 'http://localhost');
    const filePath = filePathForRepoRequest(url.pathname, repoRoot);
    if (!filePath) {
      next();
      return;
    }

    let stat;
    try {
      stat = statSync(filePath);
    } catch {
      next();
      return;
    }

    if (!stat.isFile()) {
      next();
      return;
    }

    const allowedRoot = allowedRootForRepoRequest(url.pathname, repoRoot);
    const realFilePath = realpathSync(filePath);
    const realAllowedRoot = realpathSync(allowedRoot);
    if (!pathIsInside(realFilePath, realAllowedRoot)) {
      next();
      return;
    }

    res.statusCode = 200;
    res.setHeader('Content-Type', contentTypeForPath(filePath));
    res.setHeader('Content-Length', String(stat.size));
    if (method === 'HEAD') {
      res.end();
      return;
    }

    createReadStream(filePath)
      .on('error', (error) => next(error))
      .pipe(res);
  };
}

export function repoRootStaticPlugin(repoRoot = defaultRepoRoot()) {
  return {
    name: 'repo-root-static-files',
    configureServer(server) {
      server.middlewares.use(createRepoRootStaticMiddleware(repoRoot));
    },
  };
}
