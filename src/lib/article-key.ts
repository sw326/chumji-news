export function createArticleKey(
  postId: string,
  sourceUrl: string,
  title: string
): string {
  const normalizedUrl = sourceUrl.trim().toLowerCase();
  const identity = normalizedUrl || `${postId}:${title.trim().toLowerCase()}`;
  let hash = 2166136261;

  for (let index = 0; index < identity.length; index += 1) {
    hash ^= identity.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return `${normalizedUrl ? "url" : "post"}:${(hash >>> 0).toString(36)}`;
}
