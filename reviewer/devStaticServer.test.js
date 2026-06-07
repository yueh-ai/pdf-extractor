import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import {
  contentTypeForPath,
  createRepoRootStaticMiddleware,
  filePathForRepoRequest,
} from './devStaticServer.js';

describe('dev static server helpers', () => {
  it('maps repo-root reviewer URLs to files under allowed artifact roots only', () => {
    const repoRoot = mkdtempSync(join(tmpdir(), 'reviewer-repo-'));

    expect(filePathForRepoRequest('/runs/doc/viewer-manifest.json', repoRoot)).toBe(
      resolve(repoRoot, 'runs/doc/viewer-manifest.json'),
    );
    expect(filePathForRepoRequest('/object_store/pdf-extract/page.png', repoRoot)).toBe(
      resolve(repoRoot, 'object_store/pdf-extract/page.png'),
    );
    expect(filePathForRepoRequest('/reviewer/dist/index.html', repoRoot)).toBeNull();
    expect(filePathForRepoRequest('/runs/../reviewer/package.json', repoRoot)).toBeNull();
  });

  it('serves HEAD requests with the artifact content type', () => {
    const repoRoot = mkdtempSync(join(tmpdir(), 'reviewer-repo-'));
    const manifestPath = join(repoRoot, 'runs/doc/reconciled_viewer/viewer-manifest.json');
    mkdirSync(join(repoRoot, 'runs/doc/reconciled_viewer'), { recursive: true });
    writeFileSync(manifestPath, '{"pages":[]}', 'utf8');

    const middleware = createRepoRootStaticMiddleware(repoRoot);
    const req = {
      method: 'HEAD',
      url: '/runs/doc/reconciled_viewer/viewer-manifest.json',
    };
    const res = {
      statusCode: 0,
      headers: new Map(),
      setHeader(name, value) {
        this.headers.set(name, value);
      },
      end: vi.fn(),
    };
    const next = vi.fn();

    middleware(req, res, next);

    expect(next).not.toHaveBeenCalled();
    expect(res.statusCode).toBe(200);
    expect(res.headers.get('Content-Type')).toBe('application/json; charset=utf-8');
    expect(res.end).toHaveBeenCalledOnce();
  });

  it('uses image content types for source pages and object-store assets', () => {
    expect(contentTypeForPath('page.png')).toBe('image/png');
    expect(contentTypeForPath('asset.jpg')).toBe('image/jpeg');
  });
});
