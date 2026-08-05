/* Renderer Markdown seadanya untuk docs/TRADING_PLAN.md dan docs/DATA.md.
 *
 * Sengaja tidak memakai pustaka: yang perlu didukung cuma subset yang benar-benar
 * dipakai kedua berkas itu — heading, daftar, tabel, blok kode, kutipan, tebal,
 * miring, code inline, dan tautan. Semua teks di-escape lebih dulu, jadi tidak
 * ada HTML mentah yang bisa lolos dari berkas Markdown.
 */

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function inline(text) {
  let out = escapeHtml(text);
  // Code inline lebih dulu, lalu isinya dilindungi dari aturan lain. Penandanya
  // memakai NUL supaya mustahil bentrok dengan isi dokumen: penanda berbasis
  // angka biasa akan ikut menelan angka yang memang ada di teks.
  const codes = [];
  out = out.replace(/`([^`]+)`/g, (_, code) => {
    codes.push(code);
    return `\0${codes.length - 1}\0`;
  });
  out = out
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => {
      const safe = /^(https?:|#|\.|\/)/.test(href) ? href : '#';
      const external = /^https?:/.test(safe);
      return `<a href="${safe}"${external ? ' target="_blank" rel="noopener"' : ''}>${label}</a>`;
    })
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  return out.replace(/\0(\d+)\0/g, (_, i) => `<code>${codes[Number(i)]}</code>`);
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s§-]/g, '')
    .trim()
    .replace(/\s+/g, '-');
}

/** Ubah Markdown jadi HTML. Kembalikan { html, headings }. */
export function renderMarkdown(source) {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const out = [];
  const headings = [];
  let i = 0;

  const closeList = (stack) => {
    while (stack.length) out.push(stack.pop() === 'ul' ? '</ul>' : '</ol>');
  };
  const listStack = [];

  while (i < lines.length) {
    const line = lines[i];

    // Blok kode berpagar
    const fence = line.match(/^```(\w*)\s*$/);
    if (fence) {
      closeList(listStack);
      const body = [];
      i += 1;
      while (i < lines.length && !/^```/.test(lines[i])) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1;
      out.push(`<pre><code>${escapeHtml(body.join('\n'))}</code></pre>`);
      continue;
    }

    // Tabel: baris header diikuti baris pemisah
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      closeList(listStack);
      const cells = (row) =>
        row
          .replace(/^\s*\|/, '')
          .replace(/\|\s*$/, '')
          .split('|')
          .map((c) => c.trim());

      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        rows.push(cells(lines[i]));
        i += 1;
      }
      out.push('<div class="tablewrap"><table><thead><tr>');
      for (const c of head) out.push(`<th>${inline(c)}</th>`);
      out.push('</tr></thead><tbody>');
      for (const row of rows) {
        out.push('<tr>');
        for (const c of row) out.push(`<td>${inline(c)}</td>`);
        out.push('</tr>');
      }
      out.push('</tbody></table></div>');
      continue;
    }

    // Heading
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeList(listStack);
      const level = heading[1].length;
      const text = heading[2].replace(/\s*#+\s*$/, '');
      const id = slugify(text);
      if (level <= 2) headings.push({ level, text, id });
      out.push(`<h${level} id="${id}">${inline(text)}</h${level}>`);
      i += 1;
      continue;
    }

    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      closeList(listStack);
      out.push('<hr>');
      i += 1;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      closeList(listStack);
      const body = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        body.push(lines[i].replace(/^\s*>\s?/, ''));
        i += 1;
      }
      out.push(`<blockquote>${inline(body.join(' '))}</blockquote>`);
      continue;
    }

    const bullet = line.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
    if (bullet) {
      const ordered = /\d/.test(bullet[2]);
      const tag = ordered ? 'ol' : 'ul';
      if (!listStack.length || listStack[listStack.length - 1] !== tag) {
        closeList(listStack);
        listStack.push(tag);
        out.push(`<${tag}>`);
      }
      out.push(`<li>${inline(bullet[3])}</li>`);
      i += 1;
      continue;
    }

    if (!line.trim()) {
      closeList(listStack);
      i += 1;
      continue;
    }

    // Paragraf: kumpulkan sampai baris kosong atau blok lain dimulai.
    closeList(listStack);
    const para = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,6}\s|```|\s*>|\s*([-*+]|\d+\.)\s)/.test(lines[i]) &&
      !/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    if (para.length) out.push(`<p>${inline(para.join(' '))}</p>`);
  }

  closeList(listStack);
  return { html: out.join('\n'), headings };
}
