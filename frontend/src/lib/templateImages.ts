/**
 * Strip / re-inject inline base64 images in template HTML.
 *
 * A job template can embed megabytes of base64 (logo, signature, letterhead).
 * Dumping that into the raw-HTML textarea is unusable, so the HTML tab shows
 * short {EMBEDDED_IMAGE_N} placeholders instead and re-injects the real data
 * URIs on save. This mirrors strip_embedded_images / reinject_embedded_images
 * in app/services/ai_generator.py — keep the two in sync.
 */

const DATA_URI_RE = /data:image\/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+/g;

export function stripImages(html: string): { html: string; map: Record<string, string> } {
  const map: Record<string, string> = {};
  let n = 0;
  const stripped = html.replace(DATA_URI_RE, (match) => {
    n += 1;
    const token = `EMBEDDED_IMAGE_${n}`;
    map[token] = match;
    return `{${token}}`;
  });
  return { html: stripped, map };
}

export function injectImages(html: string, map: Record<string, string>): string {
  let out = html;
  for (const [token, dataUri] of Object.entries(map)) {
    out = out.split(`{${token}}`).join(dataUri);
  }
  return out;
}
