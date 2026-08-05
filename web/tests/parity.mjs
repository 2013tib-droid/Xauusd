/* Uji paritas: port JavaScript harus menghasilkan angka yang sama dengan engine
 * Python, sampai ke tiap trade.
 *
 *     node web/tests/parity.mjs
 *
 * Fixture-nya dibuat oleh make_fixture.py. Kalau uji ini merah setelah kamu
 * mengubah sesuatu di web/js/, artinya web dan CLI sudah bercerita beda tentang
 * strategi yang sama — dan itu jauh lebih berbahaya daripada sekadar bug tampilan.
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gunzipSync } from 'node:zlib';

import { parseCsv } from '../js/data.js';
import { runBacktest } from '../js/engine.js';
import { summarise } from '../js/metrics.js';
import { REGISTRY } from '../js/strategies.js';

const HERE = dirname(fileURLToPath(import.meta.url));

const CONFIGS = {
  default: {},
  min_lot_no_partial: {
    undersizedPolicy: 'min',
    partialAtR: null,
    riskPct: 0.5,
    spread: 0.4,
  },
  big_account_no_trail: {
    initialEquity: 50000,
    riskPct: 2.0,
    trailAtR: null,
    commissionPerLot: 0,
    sessions: ['london', 'ny'],
    timeStopBars: 24,
  },
};

// Toleransi longgar untuk angka yang sudah dibulatkan di kedua sisi (round-half
// -even Python vs round-half-up JavaScript bisa berbeda satu digit terakhir),
// ketat untuk harga dan P/L mentah.
const SUMMARY_TOL = 0.011;
const TRADE_TOL = 1e-6;

let failures = 0;
const problems = [];

function fail(message) {
  failures += 1;
  if (problems.length < 25) problems.push(message);
}

function near(actual, expected, tol) {
  if (expected === null || expected === undefined) return actual === expected;
  if (typeof expected === 'string') {
    const asNumber = Number(expected);
    if (expected === 'inf' || expected === 'Infinity') return actual === Infinity;
    if (!Number.isNaN(asNumber)) return Math.abs(actual - asNumber) <= tol;
    return actual === expected;
  }
  if (typeof expected !== 'number') return actual === expected;
  if (!Number.isFinite(expected)) return actual === expected;
  return Math.abs(actual - expected) <= tol;
}

const expected = JSON.parse(readFileSync(join(HERE, 'expected.json'), 'utf8'));
const csv = gunzipSync(readFileSync(join(HERE, 'fixture.csv.gz'))).toString('utf8');
const df = parseCsv(csv, 0);

if (df.length !== expected.bars) {
  fail(`jumlah bar: JS ${df.length} vs Python ${expected.bars}`);
}

const TRADE_FIELDS = {
  side: TRADE_TOL,
  entry: TRADE_TOL,
  exit: TRADE_TOL,
  sl: TRADE_TOL,
  tp: TRADE_TOL,
  risk_dist: TRADE_TOL,
  lot: TRADE_TOL,
  risk_usd: TRADE_TOL,
  pnl: 1e-6,
  r: 1e-9,
  bars_held: 0,
};

const JS_FIELD = {
  risk_dist: 'riskDist',
  risk_usd: 'riskUsd',
  bars_held: 'barsHeld',
  exit_reason: 'exitReason',
};

for (const [cfgName, cfg] of Object.entries(CONFIGS)) {
  for (const stratName of Object.keys(REGISTRY)) {
    const caseKey = `${cfgName}/${stratName}`;
    const want = expected.cases[caseKey];
    if (!want) {
      fail(`kasus ${caseKey} tidak ada di expected.json`);
      continue;
    }

    const strategy = new REGISTRY[stratName]();
    const result = runBacktest(df, strategy, cfg);
    const got = summarise(result.trades, result.equity, result.config.initialEquity);

    if (result.trades.length !== want.trades.length) {
      fail(
        `${caseKey}: jumlah trade JS ${result.trades.length} vs Python ${want.trades.length}`,
      );
    }
    if (result.skippedUndersized !== want.skipped_undersized) {
      fail(
        `${caseKey}: skipped_undersized JS ${result.skippedUndersized} vs Python ${want.skipped_undersized}`,
      );
    }
    if (result.partialBlocked !== want.partial_blocked) {
      fail(
        `${caseKey}: partial_blocked JS ${result.partialBlocked} vs Python ${want.partial_blocked}`,
      );
    }

    const count = Math.min(result.trades.length, want.trades.length);
    for (let i = 0; i < count; i += 1) {
      const a = result.trades[i];
      const b = want.trades[i];

      const entryIso = new Date(a.entryTime).toISOString().replace('.000Z', '+00:00');
      if (entryIso !== b.entry_time) {
        fail(`${caseKey} trade ${i}: entry_time JS ${entryIso} vs Python ${b.entry_time}`);
      }
      for (const [field, tol] of Object.entries(TRADE_FIELDS)) {
        const actual = a[JS_FIELD[field] ?? field];
        if (!near(actual, b[field], tol)) {
          fail(`${caseKey} trade ${i}: ${field} JS ${actual} vs Python ${b[field]}`);
        }
      }
      if (a.exitReason !== b.exit_reason) {
        fail(`${caseKey} trade ${i}: exit_reason JS ${a.exitReason} vs Python ${b.exit_reason}`);
      }
      if (a.session !== b.session) {
        fail(`${caseKey} trade ${i}: session JS ${a.session} vs Python ${b.session}`);
      }
    }

    for (const [key, value] of Object.entries(want.summary)) {
      if (key === 'note') continue;
      if (!near(got[key], value, SUMMARY_TOL)) {
        fail(`${caseKey} summary.${key}: JS ${got[key]} vs Python ${value}`);
      }
    }
  }
}

const caseCount = Object.keys(expected.cases).length;
if (failures) {
  console.error(`\n✗ ${failures} ketidakcocokan pada ${caseCount} kasus:\n`);
  for (const p of problems) console.error(`  • ${p}`);
  if (failures > problems.length) console.error(`  … dan ${failures - problems.length} lagi`);
  process.exit(1);
}

const totalTrades = Object.values(expected.cases).reduce((a, c) => a + c.trades.length, 0);
console.log(`✓ paritas JS ↔ Python cocok: ${caseCount} kasus, ${totalTrades} trade, ${df.length} bar`);
