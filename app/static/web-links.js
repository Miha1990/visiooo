(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebLinks = factory();
})(typeof window !== 'undefined' ? window : globalThis, function() {
  function normalize(value) {
    value = String(value || '').trim();
    if (!value || /[\x00-\x20]/.test(value)) return '';
    if (value.startsWith('//')) value = 'https:' + value;
    else if (/^[^/:?#\s]+:[0-9]+(?:[/?#]|$)/.test(value) || !/^[a-z][a-z0-9+.-]*:/i.test(value)) value = 'https://' + value;
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : '';
    } catch { return ''; }
  }
  return {normalize};
});
