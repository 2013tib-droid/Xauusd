/* Perekat antarmuka: baca CSV, jalankan backtest, tampilkan hasilnya.
 *
 * Seluruh perhitungan terjadi di browser. Berkas CSV-mu tidak pernah dikirim ke
 * server mana pun — halaman ini memang tidak punya server.
 */

import { drawDrawdown, drawEquity } from './chart.js';
import { formatUtc, parseCsv, synthetic } from './data.js';
import { DEFAULT_CONFIG, runBacktest } from './engine.js';
import { renderMarkdown } from './markdown.js';
import { breakdown, passes, summarise } from './metrics.js';
import { REGISTRY, STRATEGY_LABELS } from './strategies.js';

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  df: null,
  sourceLabel: '',
  isSynthetic: false,
  results: null,
  activeStrategy: null,
  tradePage: 0,
};

const PAGE_SIZE = 50;
const STRATEGY_KEYS = Object.keys(REGISTRY);

const SESSION_LABELS = { asia: 'Asia', london: 'London', ny: 'New York', off: 'di luar sesi' };
const EXIT_LABELS = {
  sl: 'Stop loss',
  tp: 'Take profit',
  be_stop: 'Stop di break even',
  trail_stop: 'Trailing stop',
  invalidated: 'Setup batal',
  time_stop: 'Time stop',
  end_of_data: 'Data habis',
  partial: 'Partial',
};

/* ------------------------------------------------------------------ navigasi */

function showPanel(name) {
  for (const btn of $$('.nav button')) btn.classList.toggle('active', btn.dataset.panel === name);
  for (const panel of $$('.panel')) panel.hidden = panel.id !== `panel-${name}`;
  if (name !== 'backtest') loadDoc(name);
  window.scrollTo({ top: 0 });
}

const docCache = new Map();
// Relatif terhadap halaman: build.sh menyalin docs/ ke sebelah index.html, jadi
// jalur ini sama persis saat dilayani lokal maupun dari GitHub Pages.
const DOC_SOURCES = { rencana: 'docs/TRADING_PLAN.md', data: 'docs/DATA.md' };

async function loadDoc(name) {
  const target = $(`#panel-${name} .doc`);
  const toc = $(`#panel-${name} .toc`);
  if (!target || docCache.has(name)) return;
  docCache.set(name, true);

  try {
    const res = await fetch(DOC_SOURCES[name]);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { html, headings } = renderMarkdown(await res.text());
    target.innerHTML = html;
    if (toc && headings.length > 2) {
      const items = headings
        .filter((h) => h.level === 2)
        .map((h) => `<li><a href="#${h.id}">${h.text}</a></li>`)
        .join('');
      toc.innerHTML = `<strong>Isi</strong><ol>${items}</ol>`;
      toc.hidden = false;
    }
  } catch (err) {
    docCache.delete(name);
    target.innerHTML = `<p class="note warn">Gagal memuat dokumen: ${err.message}. Halaman ini perlu dilayani lewat HTTP, bukan dibuka langsung dari disk — jalankan <code>bash web/build.sh &amp;&amp; python3 -m http.server -d _site</code>, atau buka versi GitHub Pages-nya.</p>`;
  }
}

/* --------------------------------------------------------------------- data */

function describeData() {
  const info = $('#datainfo');
  if (!state.df) {
    info.innerHTML = '';
    return;
  }
  const { df } = state;
  info.innerHTML = `
    <span class="badge">${df.length.toLocaleString('id-ID')} bar M15</span>
    <span>${formatUtc(df.ts[0])} → ${formatUtc(df.ts[df.length - 1])} UTC</span>
    <span>${state.sourceLabel}</span>`;
  $('#run').disabled = false;
}

function setError(message) {
  const box = $('#dataerror');
  box.hidden = !message;
  box.textContent = message || '';
}

async function loadFile(file) {
  setError('');
  try {
    const text = await file.text();
    const offset = Number($('#sourceTz').value);
    state.df = parseCsv(text, offset);
    state.isSynthetic = false;
    const tzLabel = offset === 0 ? 'UTC' : `UTC${offset > 0 ? '+' : ''}${offset}`;
    state.sourceLabel = `${file.name} · stempel dibaca sebagai ${tzLabel}`;
    describeData();
    $('#syntheticWarning').hidden = true;
  } catch (err) {
    state.df = null;
    describeData();
    $('#run').disabled = true;
    setError(err.message);
  }
}

function loadSynthetic() {
  setError('');
  state.df = synthetic({ bars: 12000, seed: 7 });
  state.isSynthetic = true;
  state.sourceLabel = 'data sintetis';
  describeData();
  $('#syntheticWarning').hidden = false;
}

/* --------------------------------------------------------------- konfigurasi */

function readConfig() {
  const sessions = $$('.session-check:checked').map((c) => c.value);
  return {
    initialEquity: Number($('#equity').value) || DEFAULT_CONFIG.initialEquity,
    riskPct: Number($('#risk').value),
    spread: Number($('#spread').value),
    commissionPerLot: Number($('#commission').value),
    minLot: Number($('#minLot').value) || DEFAULT_CONFIG.minLot,
    lotStep: Number($('#minLot').value) || DEFAULT_CONFIG.lotStep,
    undersizedPolicy: $('#undersized').value,
    sessions,
    partialAtR: $('#usePartial').checked ? 1.0 : null,
    trailAtR: $('#useTrail').checked ? 2.0 : null,
  };
}

/* ----------------------------------------------------------------- backtest */

async function run() {
  if (!state.df) return;
  const button = $('#run');
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span>Menghitung…';
  // Beri browser satu frame untuk melukis status sebelum loop panjang dimulai.
  await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));

  try {
    const cfg = readConfig();
    const results = {};
    for (const key of STRATEGY_KEYS) {
      const result = runBacktest(state.df, new REGISTRY[key](), cfg);
      results[key] = {
        ...result,
        summary: summarise(result.trades, result.equity, cfg.initialEquity),
      };
    }
    state.results = results;
    state.activeStrategy = state.activeStrategy ?? STRATEGY_KEYS[0];
    state.tradePage = 0;
    renderResults();
  } catch (err) {
    setError(`Backtest gagal: ${err.message}`);
  } finally {
    button.disabled = false;
    button.textContent = 'Jalankan backtest';
  }
}

/* ------------------------------------------------------------------ tampilan */

function fmt(value, digits = 2) {
  if (value === Infinity) return '∞';
  if (!Number.isFinite(value)) return '—';
  return value.toLocaleString('id-ID', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function signClass(value) {
  return value > 0 ? 'pos' : value < 0 ? 'neg' : '';
}

function renderResults() {
  if (!state.results) return;
  $('#results').hidden = false;

  const tabs = $('#strategyTabs');
  tabs.innerHTML = STRATEGY_KEYS.map((key) => {
    const n = state.results[key].trades.length;
    const active = key === state.activeStrategy ? ' class="active"' : '';
    return `<button data-strategy="${key}"${active}>${STRATEGY_LABELS[key]} <span class="pill">${n}</span></button>`;
  }).join('');

  const active = state.results[state.activeStrategy];
  renderSummary(active);
  renderVerdict(active);
  renderCharts(active);
  renderBreakdowns(active);
  renderTrades(active);
}

function renderSummary(result) {
  const s = result.summary;
  const box = $('#tiles');
  if (!s.trades) {
    box.innerHTML = '';
    return;
  }
  const tiles = [
    ['Jumlah trade', s.trades.toLocaleString('id-ID'), '', ''],
    ['Expectancy', `${fmt(s.expectancy_r, 3)}R`, 'per trade', signClass(s.expectancy_r)],
    ['Profit factor', fmt(s.profit_factor, 2), 'lolos ≥ 1,30', s.profit_factor >= 1.3 ? 'pos' : 'neg'],
    ['Win rate', `${fmt(s.win_rate_pct, 1)}%`, '', ''],
    ['Total R', `${fmt(s.total_r, 1)}R`, '', signClass(s.total_r)],
    ['Net P/L', `$${fmt(s.net_pnl_usd)}`, `${fmt(s.return_pct, 1)}%`, signClass(s.net_pnl_usd)],
    [
      'Max drawdown',
      `${fmt(s.max_drawdown_pct, 1)}%`,
      `$${fmt(s.max_drawdown_usd)} · lolos ≤ 15%`,
      s.max_drawdown_pct <= 15 ? '' : 'neg',
    ],
    ['Equity akhir', `$${fmt(s.final_equity)}`, '', ''],
    ['Kalah beruntun', `${s.max_losing_streak}`, 'trade berturut-turut', ''],
    ['Rata-rata durasi', `${fmt(s.avg_bars_held, 1)}`, 'bar M15', ''],
    ['Menang / kalah', `${fmt(s.avg_win_r, 2)} / ${fmt(s.avg_loss_r, 2)}`, 'rata-rata R', ''],
    ['Sharpe (kasar)', fmt(s.sharpe, 2), '', ''],
  ];
  box.innerHTML = tiles
    .map(
      ([label, value, sub, cls]) => `
      <div class="tile">
        <div class="label">${label}</div>
        <div class="value ${cls}">${value}</div>
        <div class="sub">${sub}</div>
      </div>`,
    )
    .join('');
}

function renderVerdict(result) {
  const box = $('#verdict');
  const s = result.summary;

  if (!s.trades) {
    box.className = 'note warn';
    box.innerHTML = `<strong>Tidak ada trade.</strong> ${s.note}`;
    return;
  }

  const { ok, reasons } = passes(s);
  box.className = ok ? 'note good' : 'note bad';
  box.innerHTML = ok
    ? '<strong>VERDIKT: LOLOS kriteria backtest (TRADING_PLAN §8).</strong> Lanjut ke forward test demo 30 trade sebelum uang riil — jangan lompati tahap itu.'
    : `<strong>VERDIKT: BELUM LOLOS — jangan dipakai live.</strong><ul>${reasons
        .map((r) => `<li>${r}</li>`)
        .join('')}</ul>`;

  // Dua kenyataan yang berasal dari batas lot minimum, bukan dari strategi.
  const caveats = [];
  if (result.skippedUndersized) {
    caveats.push(
      `<strong>${result.skippedUndersized} setup dilewati</strong> karena lot hasil hitungan lebih kecil dari ${result.config.minLot} lot. Modal terlalu kecil untuk stop selebar itu — TRADING_PLAN §3.2.`,
    );
  }
  if (result.partialBlocked) {
    caveats.push(
      `<strong>${result.partialBlocked} kali partial close di +1R tidak bisa dieksekusi</strong>: posisi sudah di ukuran lot minimum. Di ${result.config.minLot} lot, "tutup separuh" itu mustahil — yang tersisa hanya geser SL ke break even. TRADING_PLAN §3.3.`,
    );
  }
  const caveatBox = $('#caveats');
  caveatBox.hidden = !caveats.length;
  caveatBox.innerHTML = caveats.length ? `<ul>${caveats.map((c) => `<li>${c}</li>`).join('')}</ul>` : '';
}

function renderCharts(result) {
  drawEquity($('#equityChart'), result.ts, result.equity, result.config.initialEquity);
  drawDrawdown($('#ddChart'), result.ts, result.equity);
}

function renderBreakdowns(result) {
  const build = (rows, labels, headLabel) => {
    if (!rows.length) return '<p class="hint">Belum ada data.</p>';
    const body = rows
      .map(
        (r) => `<tr>
          <td>${labels[r.key] ?? r.key}</td>
          <td>${r.trades}</td>
          <td>${fmt(r.win_rate_pct, 1)}%</td>
          <td class="${signClass(r.expectancy_r)}">${fmt(r.expectancy_r, 3)}R</td>
          <td class="${signClass(r.total_r)}">${fmt(r.total_r, 2)}R</td>
          <td class="${signClass(r.net_usd)}">$${fmt(r.net_usd)}</td>
        </tr>`,
      )
      .join('');
    return `<div class="tablewrap"><table>
      <thead><tr><th>${headLabel}</th><th>Trade</th><th>Win</th><th>Expectancy</th><th>Total R</th><th>Net</th></tr></thead>
      <tbody>${body}</tbody></table></div>`;
  };

  $('#bySession').innerHTML = build(breakdown(result.trades, 'session'), SESSION_LABELS, 'Sesi');
  $('#byExit').innerHTML = build(breakdown(result.trades, 'exit_reason'), EXIT_LABELS, 'Alasan exit');
  $('#byMonth').innerHTML = build(breakdown(result.trades, 'month'), {}, 'Bulan');
}

function renderTrades(result) {
  const { trades } = result;
  const totalPages = Math.max(1, Math.ceil(trades.length / PAGE_SIZE));
  state.tradePage = Math.min(state.tradePage, totalPages - 1);
  const start = state.tradePage * PAGE_SIZE;
  const page = trades.slice(start, start + PAGE_SIZE);

  $('#tradeTable').innerHTML = !trades.length
    ? '<p class="hint">Tidak ada trade untuk ditampilkan.</p>'
    : `<div class="tablewrap"><table>
        <thead><tr>
          <th>Entry (UTC)</th><th>Arah</th><th>Sesi</th><th>Entry</th><th>SL</th><th>TP</th>
          <th>Exit</th><th>Lot</th><th>R</th><th>P/L</th><th>Bar</th><th>Alasan</th>
        </tr></thead>
        <tbody>${page
          .map(
            (t) => `<tr>
              <td>${formatUtc(t.entryTime)}</td>
              <td><span class="pill ${t.side === 1 ? 'buy' : 'sell'}">${t.side === 1 ? 'BUY' : 'SELL'}</span></td>
              <td>${SESSION_LABELS[t.session] ?? t.session}</td>
              <td>${fmt(t.entry)}</td>
              <td>${fmt(t.sl)}</td>
              <td>${fmt(t.tp)}</td>
              <td>${fmt(t.exit)}</td>
              <td>${t.lot.toFixed(2)}</td>
              <td class="${signClass(t.r)}">${fmt(t.r, 2)}</td>
              <td class="${signClass(t.pnl)}">$${fmt(t.pnl)}</td>
              <td>${t.barsHeld}</td>
              <td>${EXIT_LABELS[t.exitReason] ?? t.exitReason}</td>
            </tr>`,
          )
          .join('')}</tbody></table></div>`;

  $('#tradeFoot').innerHTML = trades.length
    ? `<span>Menampilkan ${start + 1}–${Math.min(start + PAGE_SIZE, trades.length)} dari ${trades.length} trade</span>
       <span>
         <button class="ghost" id="prevPage"${state.tradePage === 0 ? ' disabled' : ''}>← Sebelumnya</button>
         <button class="ghost" id="nextPage"${state.tradePage >= totalPages - 1 ? ' disabled' : ''}>Berikutnya →</button>
       </span>`
    : '';
}

/* -------------------------------------------------------------------- ekspor */

function exportCsv() {
  if (!state.results) return;
  const header = [
    'strategy', 'entry_time', 'exit_time', 'side', 'session', 'entry', 'exit', 'sl', 'tp',
    'risk_dist', 'lot', 'risk_usd', 'pnl', 'r', 'bars_held', 'exit_reason', 'equity_after',
  ];
  const rows = [header.join(',')];
  for (const key of STRATEGY_KEYS) {
    for (const t of state.results[key].trades) {
      rows.push(
        [
          key,
          new Date(t.entryTime).toISOString(),
          new Date(t.exitTime).toISOString(),
          t.side,
          t.session,
          t.entry, t.exit, t.sl, t.tp, t.riskDist, t.lot, t.riskUsd, t.pnl, t.r,
          t.barsHeld, t.exitReason, t.equityAfter,
        ].join(','),
      );
    }
  }

  const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'hasil_backtest.csv';
  a.click();
  URL.revokeObjectURL(url);
}

/* ------------------------------------------------------------------- pasang */

function wire() {
  for (const btn of $$('.nav button')) {
    btn.addEventListener('click', () => showPanel(btn.dataset.panel));
  }

  const drop = $('#drop');
  const input = $('#file');
  drop.addEventListener('click', () => input.click());
  drop.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      input.click();
    }
  });
  input.addEventListener('change', () => {
    if (input.files[0]) loadFile(input.files[0]);
  });
  for (const type of ['dragenter', 'dragover']) {
    drop.addEventListener(type, (e) => {
      e.preventDefault();
      drop.classList.add('over');
    });
  }
  for (const type of ['dragleave', 'drop']) {
    drop.addEventListener(type, (e) => {
      e.preventDefault();
      drop.classList.remove('over');
    });
  }
  drop.addEventListener('drop', (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (file) loadFile(file);
  });

  $('#useSynthetic').addEventListener('click', loadSynthetic);
  $('#run').addEventListener('click', run);
  $('#export').addEventListener('click', exportCsv);

  $('#strategyTabs').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-strategy]');
    if (!btn) return;
    state.activeStrategy = btn.dataset.strategy;
    state.tradePage = 0;
    renderResults();
  });

  $('#tradeFoot').addEventListener('click', (e) => {
    if (e.target.id === 'prevPage') state.tradePage -= 1;
    else if (e.target.id === 'nextPage') state.tradePage += 1;
    else return;
    renderTrades(state.results[state.activeStrategy]);
  });

  $('#sourceTz').addEventListener('change', () => {
    // Zona waktu memengaruhi cara berkas dibaca, jadi berkasnya harus dibaca ulang.
    if (input.files[0] && !state.isSynthetic) loadFile(input.files[0]);
  });
}

wire();
showPanel('backtest');
