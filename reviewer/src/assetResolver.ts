import type { ViewerPage } from './manifest';

export type AssetMap = Map<string, string>;

export function buildAssetMap(page: ViewerPage): AssetMap {
  const map = new Map<string, string>();
  for (const asset of page.assets) {
    map.set(asset.asset_uri, asset.local_url);
    map.set(asset.object_key, asset.local_url);
    map.set(asset.source_path, asset.local_url);
  }
  return map;
}

export function resolveAssetUrl(src: string | undefined, assetMap: AssetMap): string | null {
  if (!src) {
    return null;
  }
  const mapped = assetMap.get(src);
  if (mapped) {
    return mapped;
  }
  if (
    src.startsWith('/') ||
    src.startsWith('http://') ||
    src.startsWith('https://') ||
    src.startsWith('data:')
  ) {
    return src;
  }
  return null;
}
