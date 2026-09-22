// Runs against the unmodified, pinned editor mounted with its real Vue runtime.
const editor = window.testEditor;
for (let n = 0; !editor.md && n < 200; n++) await new Promise(r => setTimeout(r, 50));
if (!editor.md) throw new Error('Editor markdown-it initialization timed out');
editor.stopFloatingAdRotation();
// Capture the outbound HTML instead of writing to the user's clipboard.
Object.defineProperty(document, 'hasFocus', {value: () => false});
const originalFallback = editor.clipboardFallback;
let copied = null;
editor.clipboardFallback = html => { copied = html; };
const cases = [];
const inventory = html => {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const props = new Set();
  for (const el of doc.querySelectorAll('[style]')) for (const prop of el.style) props.add(prop);
  return {
    tags: [...new Set([...doc.body.querySelectorAll('*')].map(el => el.localName))].sort(),
    css_properties: [...props].sort(), images: doc.images.length,
    grid_count: doc.querySelectorAll('.image-grid').length,
    table_count: doc.querySelectorAll('table').length,
    nested_lists: doc.querySelectorAll('li ul, li ol').length,
    links_in_lists: doc.querySelectorAll('li a').length,
    code_highlight_spans: doc.querySelectorAll('code span').length,
    image_sources: [...doc.images].map(el => el.getAttribute('src'))
  };
};
for (const [id, theme] of Object.entries(editor.STYLES)) {
  editor.currentStyle = id;
  editor.markdownInput = markdown;
  await Vue.nextTick();
  await editor.renderMarkdown();
  const preview = editor.renderedContent;
  copied = null;
  await editor.copyToClipboard();
  if (!copied || !copied.includes('THE END')) throw new Error(`Export missing: ${id}`);
  const detail = inventory(copied);
  if (detail.images !== 6 || detail.image_sources.some(src => !src.startsWith('data:image/'))) {
    throw new Error(`Export images missing or not embedded: ${id}`);
  }
  cases.push({id, name: theme.name, preview, exported: copied,
    preview_inventory: inventory(preview), export_inventory: detail});
}
editor.clipboardFallback = originalFallback;
return {method: 'Unmodified pinned app.js renderMarkdown() and copyToClipboard(), real Vue and markdown-it in WKWebView. Clipboard fallback sink intercepted; no clipboard writes.',
  input_kind: 'Authored common Markdown test article, not a published WeChat capture.',
  syntax_highlighter: typeof hljs === 'undefined' ? 'unavailable; upstream escapeHtml fallback used' : 'loaded', cases};
