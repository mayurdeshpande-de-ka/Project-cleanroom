/* ═══════════════════════════════════════════════════════════════════════════
   app.js — Form 20 Backlog Dashboard
   ═══════════════════════════════════════════════════════════════════════════ */
'use strict';

let allRecords    = [];
let selectedIds   = new Set();
let sortCol       = 'state';
let sortDir       = 'asc';
let editingId     = null;
let toastTimer    = null;
let searchTimer   = null;
let retroMetadata = null;
let filterMetadata = null;
let confirmResolve = null;
let currentView   = 'states';
let currentDetailState = null;

const filters = {
  state: '', el_type: '', year: '', status: '', sir_only: false, search: '', wip: false, show_bp: false,
};

let activeKpi  = null;
let pieChart   = null;
let barChart   = null;

// Dashboard-only filters (BP hidden by default)
let dashShowBp   = false;
let dashSirOnly  = false;
let dashWeekFilter = '';   // week start date string e.g. "2026-06-01"

let monthlyChart    = null;
let _missingACsTotal = 0;  // total ACs across the 262 mapping entries not yet in Form 20
let _f20TotalYears  = 0;   // form20 distinct years (from SQLite stats)
let _f20Total       = 0;   // form20 total election entries (from SQLite stats)
let _f20ByType      = {};  // form20 by_type from SQLite stats (completed/total per type)

// Glance Report chart instances
let gWeekChart  = null;
let gStateChart = null;
let gCasteChart = null;

const EL_TYPE_NAMES = { AE: 'Assembly', GE: 'General', BE: 'Bypoll', PE: 'Parliament', LE: 'Local', AC: 'Assembly' };
const STATE_NAMES_MAP = {};  // populated lazily from filter dropdown

const STATUS_CONFIG = {
  'missing':    { bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-100',     dot: 'bg-red-400',     label: 'Remaining'   },
  'pending':    { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-100',   dot: 'bg-amber-400',   label: 'Pending'   },
  'downloaded': { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-100',    dot: 'bg-blue-400',    label: 'Downloaded'},
  'extracted':  { bg: 'bg-violet-50',  text: 'text-violet-700',  border: 'border-violet-100',  dot: 'bg-violet-400',  label: 'Extracted' },
  'completed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100', dot: 'bg-emerald-400', label: 'Completed' },
  'db_pushed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100', dot: 'bg-emerald-400', label: 'DB Pushed' },
};

// Canonical AC counts per state (from ac_mapping; same across years/types)
const STATE_AC_COUNTS = {
  'AP': 175, 'AR': 60,  'AS': 126, 'BR': 243, 'CG': 90,  'CT': 90,  'GA': 40,
  'GJ': 182, 'HR': 90,  'HP': 68,  'JH': 81,  'KA': 224, 'KL': 140, 'MP': 230,
  'MH': 288, 'MN': 60,  'ML': 60,  'MZ': 40,  'NL': 60,  'OR': 147, 'PB': 117,
  'RJ': 200, 'SK': 32,  'TN': 234, 'TS': 119, 'TR': 60,  'UP': 403, 'UK': 70,
  'WB': 294, 'DL': 70,  'PY': 30,  'JK': 90,  'LD': 1,   'AN': 1,   'CH': 1
};

document.addEventListener('DOMContentLoaded', () => {
  loadFilters();
  loadDashboardStats();
  bindEvents();
});

async function loadFilters() {
  try {
    const data = await apiFetch('/api/filters');
    filterMetadata = data.metadata;
    const stateNames = data.state_names;

    const stateEl = document.getElementById('filter-state');
    stateEl.innerHTML = '<option value="">All States</option>';
    Object.keys(filterMetadata).sort().forEach(s => {
      stateEl.appendChild(new Option(`${s} — ${stateNames[s]}`, s));
    });

    document.getElementById('filter-type').innerHTML = '<option value="">All Types</option>';
    document.getElementById('filter-type').disabled = true;
    document.getElementById('filter-year').innerHTML = '<option value="">All Years</option>';
    document.getElementById('filter-year').disabled = true;
  } catch (e) { console.error('loadFilters:', e); }
}

async function loadStats() {
  const params = new URLSearchParams();
  if (filters.state)    params.set('state',    filters.state);
  if (filters.el_type)  params.set('el_type',  filters.el_type);
  if (filters.year)     params.set('year',     filters.year);
  if (filters.status)   params.set('status',   filters.status);
  if (filters.sir_only) params.set('sir_only', '1');
  if (filters.wip)      params.set('wip', '1');
  if (filters.search)   params.set('search',   filters.search);
  if (!filters.show_bp) params.set('hide_bp',  '1');

  try {
    const s = await apiFetch('/api/stats?' + params);
    const bs = s.by_status || {};
    const total = s.total || 0;

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? '0'; };
    set('sl-all-count', total);
    set('sl-dl-count',  bs.downloaded || '0');
    set('sl-ex-count',  bs.extracted  || '0');
    set('sl-co-count',  (bs.db_pushed || 0) + (bs.completed || 0));
    set('sl-pe-count',  bs.pending    || '0');
    set('sl-mi-count',  bs.missing    || '0');
    set('sl-wip-count', s.wip_count   || '0');

    set('kpi-dl-count', bs.downloaded || '0');
    set('kpi-ex-count', bs.extracted  || '0');
    set('kpi-mi-count', bs.missing    || '0');

    const completed = (bs.db_pushed || 0) + (bs.completed || 0);
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    const totalRemaining = total - completed;

    // Listing pipeline strip
    set('kpi-tr-count', totalRemaining);
    const listPctEl  = document.getElementById('listing-pct');
    const listProgBar = document.getElementById('listing-prog-bar');
    if (listPctEl)  listPctEl.textContent  = pct + '%';
    if (listProgBar) listProgBar.style.width = pct + '%';

    const pbFill = document.getElementById('progress-bar-fill');
    if (pbFill) pbFill.style.width = pct + '%';
    set('progress-text', `${completed} / ${total} completed`);

    const pctSidebar = document.getElementById('progress-pct-sidebar');
    if (pctSidebar) pctSidebar.textContent = pct + '%';

    // ── AC counts per pipeline stage ─────────────────────────────────────────
    // Sum canonical AC count × elections-in-that-stage across all states
    if (s.by_state && s.by_state.length) {
      let acMissing = 0, acDownloaded = 0, acExtracted = 0;
      for (const row of s.by_state) {
        const ac = STATE_AC_COUNTS[row.state] || 0;
        acMissing    += (row.missing    || 0) * ac;
        acDownloaded += (row.downloaded || 0) * ac;
        acExtracted  += (row.extracted  || 0) * ac;
      }
      const acTotalRemaining = acMissing + acDownloaded + acExtracted;
      const fmtAC = n => n > 0 ? `${n.toLocaleString()} ACs` : '';
      set('kpi-tr-acs', fmtAC(acTotalRemaining));
      set('kpi-mi-acs', fmtAC(acMissing));
      set('kpi-dl-acs', fmtAC(acDownloaded));
      set('kpi-ex-acs', fmtAC(acExtracted));
    }
  } catch (e) { console.error('loadStats:', e); }

  // ── Missing ACs across the 262 mapping entries not yet in Form 20 ─────────
  try {
    const f20 = await apiFetch('/api/form20_card_stats');
    _missingACsTotal = f20.missing_acs || 0;
    updateRecordBadge();
  } catch (e) { console.warn('form20_card_stats (badge) unavailable:', e); }
}

// Updates the "N records" badge on the Listing page header, appending the
// total AC count still missing across the 262 mapping entries.
function updateRecordBadge() {
  const badge = document.getElementById('record-count-badge');
  if (!badge) return;
  const count = allRecords.length;
  let text = `${count} records`;
  if (_missingACsTotal > 0) text += ` · ${_missingACsTotal.toLocaleString()} ACs missing`;
  badge.textContent = text;
}

async function loadRecords() {
  const params = new URLSearchParams();
  if (filters.state)    params.set('state',    filters.state);
  if (filters.el_type)  params.set('el_type',  filters.el_type);
  if (filters.year)     params.set('year',     filters.year);
  if (filters.status)   params.set('status',   filters.status);
  if (filters.sir_only) params.set('sir_only', '1');
  if (filters.wip)      params.set('wip', '1');
  if (filters.search)   params.set('search',   filters.search);
  if (!filters.show_bp) params.set('hide_bp',  '1');

  try {
    allRecords = await apiFetch('/api/records?' + params);
    renderTable();
  } catch (e) {
    document.getElementById('table-body').innerHTML =
      `<tr><td colspan="7" class="px-5 py-10 text-center text-gray-500 text-[12px]">Failed to load — ${e.message}</td></tr>`;
  }
}

function renderTable() {
  const tbody = document.getElementById('table-body');
  const thead = document.getElementById('table-head');
  updateRecordBadge();

  if (!allRecords.length) {
    tbody.innerHTML = `
      <tr><td colspan="7" class="px-5 py-12 text-center">
        <div class="flex flex-col items-center gap-2 text-gray-400">
          <span class="material-symbols-outlined" style="font-size:28px;">search_off</span>
          <p class="text-[12px]">No records match the current filters.</p>
        </div>
      </td></tr>`;
    document.getElementById('pagination-text').textContent = 'Showing 0 records';
    return;
  }

  if (currentView === 'states') {
    // ── State grouped view ──────────────────────────────────────────────────
    const grouped = {};
    allRecords.forEach(rec => {
      const s = rec.state_name || rec.state;
      if (!grouped[s]) grouped[s] = [];
      grouped[s].push(rec);
    });
    const stateKeys = Object.keys(grouped).sort((a, b) => a.localeCompare(b));

    document.getElementById('pagination-text').textContent =
      `${allRecords.length} records across ${stateKeys.length} states`;

    thead.innerHTML = `
      <tr>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider">State</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider">Elections</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider">Status Breakdown</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider text-right">Open</th>
      </tr>`;

    let html = '';
    stateKeys.forEach(s => {
      const records = grouped[s];
      let missing = 0, extracted = 0, downloaded = 0, pending = 0;
      records.forEach(r => {
        const st = r.overall_status;
        if (st === 'missing')    missing++;
        else if (st === 'extracted')  extracted++;
        else if (st === 'downloaded') downloaded++;
        else if (st === 'pending')    pending++;
      });

      const chips = [
        extracted  > 0 ? `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-violet-50 text-violet-700 border border-violet-100 px-2 py-0.5 rounded-full">${extracted} Ext</span>` : '',
        downloaded > 0 ? `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full">${downloaded} Dwn</span>` : '',
        pending    > 0 ? `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-amber-50 text-amber-700 border border-amber-100 px-2 py-0.5 rounded-full">${pending} Pnd</span>` : '',
        missing    > 0 ? `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-gray-100 text-gray-500 border border-gray-200 px-2 py-0.5 rounded-full">${missing} Mis</span>` : '',
      ].filter(Boolean).join('');

      const stateCode = records[0]?.state;
      const canonicalAC = STATE_AC_COUNTS[stateCode] || 0;
      const totalStateACs = canonicalAC > 0 ? (records.length * canonicalAC).toLocaleString() : '';

      html += `
        <tr class="trow bg-white border-b border-gray-50 cursor-pointer transition-colors"
            onclick="openStateDetail('${s.replace(/'/g, "\\'")}')">
          <td class="px-5 py-3">
            <div class="flex items-center gap-3">
              <div class="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-gray-400" style="font-size:13px;">map</span>
              </div>
              <div>
                <p class="text-[13px] font-semibold text-gray-900">${x(s)}</p>
                <p class="text-[11px] text-gray-400">Click to view elections</p>
              </div>
            </div>
          </td>
          <td class="px-5 py-3">
            <span class="text-[13px] font-semibold text-gray-700 tabular-nums">${records.length}</span>
            <span class="text-[11px] text-gray-400 ml-1">elections</span>
            ${totalStateACs ? `<span class="text-[11px] text-gray-400 ml-1">(${totalStateACs} ACs)</span>` : ''}
          </td>
          <td class="px-5 py-3">
            <div class="flex items-center gap-1.5 flex-wrap">${chips || '<span class="text-[11px] text-gray-300">—</span>'}</div>
          </td>
          <td class="px-5 py-3 text-right">
            <span class="material-symbols-outlined text-gray-300" style="font-size:16px;">chevron_right</span>
          </td>
        </tr>`;
    });
    tbody.innerHTML = html;

  } else {
    // ── Detail view (records for a single state) ───────────────────────────
    const records = allRecords
      .filter(r => (r.state_name || r.state) === currentDetailState)
      .sort((a, b) => {
        let va = a[sortCol] ?? '', vb = b[sortCol] ?? '';
        if (typeof va === 'string') { va = va.toLowerCase(); vb = vb.toLowerCase(); }
        if (va < vb) return sortDir === 'asc' ? -1 : 1;
        if (va > vb) return sortDir === 'asc' ?  1 : -1;
        return 0;
      });

    document.getElementById('pagination-text').textContent =
      `${records.length} records for ${currentDetailState}`;

    thead.innerHTML = `
      <tr>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-50 sortable" data-col="state">Record ID</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider">Status</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider">Location</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider text-right">Actions</th>
      </tr>`;

    tbody.innerHTML = records.map(rec => {
      const sel = selectedIds.has(rec.id);
      const cfg = STATUS_CONFIG[rec.overall_status] || STATUS_CONFIG['missing'];
      const rowClass = sel ? 'trow-selected' : 'trow';

      return `
        <tr class="${rowClass} bg-white border-b border-gray-50 transition-colors" data-id="${rec.id}">
          <td class="px-5 py-2.5 cursor-pointer" onclick="openModal(${rec.id})">
            <p class="text-[12.5px] font-semibold text-gray-900 leading-tight">${x(rec.key)}</p>
            <p class="text-[11px] ${rec.is_sir_state ? 'text-amber-600 font-medium' : 'text-gray-400'} mt-0.5">${rec.is_sir_state ? 'SIR Priority' : 'Standard'}</p>
          </td>
          <td class="px-5 py-2.5">
            <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${cfg.bg} ${cfg.text} ${cfg.border}">
              <span class="w-1.5 h-1.5 rounded-full ${cfg.dot} shrink-0"></span>
              ${cfg.label}
            </span>
          </td>
          <td class="px-5 py-2.5">
            <p class="text-[12.5px] font-medium text-gray-700">${x(rec.state_name || rec.state)}</p>
            <p class="text-[11px] text-gray-400">${x(rec.el_type)} ${rec.el_year}</p>
          </td>
          <td class="px-5 py-2.5 text-right">
            <div class="flex items-center justify-end gap-1.5">
              <button class="btn-wip flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold border transition-colors
                ${rec.wip
                  ? 'bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100'
                  : 'bg-white text-gray-400 border-gray-200 hover:bg-gray-50 hover:text-gray-600'}"
                data-id="${rec.id}" title="Toggle LF In Progress">
                <span class="material-symbols-outlined" style="font-size:13px;">${rec.wip ? 'hourglass_top' : 'hourglass_empty'}</span>
                LF WIP
              </button>
              <button class="btn-edit p-1.5 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-700 transition-colors" data-id="${rec.id}">
                <span class="material-symbols-outlined" style="font-size:15px;">edit</span>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('.btn-wip').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        const id = +e.currentTarget.dataset.id;
        const rec = allRecords.find(r => r.id === id);
        if (!rec) return;
        try {
          const updated = await apiFetch(`/api/records/${id}`, 'PATCH', { wip: rec.wip ? 0 : 1 });
          const idx = allRecords.findIndex(r => r.id === id);
          if (idx >= 0) allRecords[idx] = updated;
          renderTable(); loadStats();
        } catch (err) {
          showToast('Failed to update WIP status', true);
        }
      });
    });

    tbody.querySelectorAll('.btn-edit').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        openModal(+e.currentTarget.dataset.id);
      });
    });

    thead.querySelectorAll('.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const c = th.dataset.col;
        sortDir = sortCol === c && sortDir === 'asc' ? 'desc' : 'asc';
        sortCol = c;
        renderTable();
      });
    });
  }
}

window.goBackToStates = function () {
  currentView = 'states';
  currentDetailState = null;
  document.getElementById('detail-header').classList.add('hidden');
  renderTable();
};

window.openStateDetail = function (stateName) {
  currentView = 'detail';
  currentDetailState = stateName;
  document.getElementById('detail-header').classList.remove('hidden');
  document.getElementById('detail-state-name').textContent = stateName;
  renderTable();
};

function x(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function updateSelectAll() {
  const cb = document.getElementById('select-all');
  if (!cb) return;
  const ids  = allRecords.map(r => r.id);
  const selN = ids.filter(id => selectedIds.has(id)).length;
  cb.indeterminate = selN > 0 && selN < ids.length;
  cb.checked       = ids.length > 0 && selN === ids.length;
}

function updateSelBar() {}
function clearSelection() { selectedIds.clear(); renderTable(); }

function openModal(id) {
  const rec = allRecords.find(r => r.id === id);
  if (!rec) return;
  editingId = id;
  document.getElementById('modal-title').textContent = `${rec.state} — ${rec.el_type} — ${rec.el_year}`;
  document.getElementById('modal-key').textContent   = rec.key;
  document.getElementById('edit-status').value       = rec.overall_status || 'missing';
  document.getElementById('edit-remark').value       = rec.remark || '';
  const overlay = document.getElementById('overlay');
  const card    = document.getElementById('modal-card');
  overlay.classList.remove('opacity-0', 'pointer-events-none');
  card.classList.remove('scale-95'); card.classList.add('scale-100');
}

function closeModal() {
  const overlay = document.getElementById('overlay');
  const card    = document.getElementById('modal-card');
  overlay.classList.add('opacity-0', 'pointer-events-none');
  card.classList.remove('scale-100'); card.classList.add('scale-95');
  editingId = null;
}

async function saveModal() {
  if (!editingId) return;
  const newStatus = document.getElementById('edit-status').value;
  if (newStatus === 'db_pushed') {
    const confirmed = await showConfirmModal();
    if (!confirmed) return;
  }
  const body = {
    overall_status: newStatus,
    remark: document.getElementById('edit-remark').value.trim() || null,
  };
  try {
    const updated = await apiFetch(`/api/records/${editingId}`, 'PATCH', body);
    const idx = allRecords.findIndex(r => r.id === editingId);
    if (idx >= 0) allRecords[idx] = updated;
    closeModal(); renderTable(); loadStats();
    showToast('Record updated successfully');
  } catch (e) { showToast('Save failed: ' + e.message, true); }
}

async function syncFromExcel() {
  const btn = document.getElementById('reload-btn');
  if (!btn) return;
  btn.disabled = true;
  try {
    const data = await apiFetch('/api/reload', 'POST', {});
    if (data.success) { showToast('Database synced from Excel'); loadStats(); loadRecords(); }
    else showToast('Sync failed: ' + data.error, true);
  } catch (e) { showToast('Sync error: ' + e.message, true); }
  finally { btn.disabled = false; }
}

async function syncAWS() {
  const btn = document.getElementById('sync-aws-btn');
  if (!btn) return;
  btn.disabled = true;
  try {
    const data = await apiFetch('/api/sync-rds', 'POST', {});
    if (data.success) { showToast(data.message); loadStats(); loadRecords(); }
    else showToast('AWS Sync failed: ' + data.message, true);
  } catch (e) { showToast('AWS Sync error: ' + e.message, true); }
  finally { btn.disabled = false; }
}

function handleSideNav(view) {
  document.querySelectorAll('.sidelink').forEach(el => {
    el.classList.remove('sl-active', 'sl-wip-active');
    el.classList.remove('text-gray-900', 'text-amber-900');

    if (el.dataset.view === view) {
      if (view === 'wip') {
        el.classList.add('sl-wip-active');
      } else {
        el.classList.add('sl-active');
      }
    }
  });

  const statusMap = { downloaded: 'downloaded', extracted: 'extracted', completed: 'completed', pending: 'pending', missing: 'missing' };
  if (statusMap[view]) {
    filters.status = statusMap[view];
    filters.wip    = false;
  } else if (view === 'wip') {
    filters.status = '';
    filters.wip    = true;
  } else {
    filters.status = '';
    filters.wip    = false;
  }
  setActiveKpi(null);
  loadStats(); loadRecords();
}

window.handleKpiClick = function (status) {
  if (activeKpi === status) {
    setActiveKpi(null);
    filters.status = '';
    filters.wip    = false;
  } else {
    setActiveKpi(status);
    filters.status = status;
    filters.wip    = false;
    document.querySelectorAll('.sidelink').forEach(el => {
      el.classList.remove('sl-active', 'sl-wip-active');
    });
  }
  goBackToStates();
  loadRecords();
};

function setActiveKpi(status) {
  activeKpi = status;
  const kpiMap = {
    remaining:  { id: 'kpi-total-remaining', cls: 'kpi-active-slate'   },
    downloaded: { id: 'kpi-downloaded',      cls: 'kpi-active-blue'    },
    extracted:  { id: 'kpi-extracted',       cls: 'kpi-active-violet'  },
    missing:    { id: 'kpi-missing',         cls: 'kpi-active-red'     },
  };
  const allCls = ['kpi-active-blue', 'kpi-active-violet', 'kpi-active-red', 'kpi-active-emerald', 'kpi-active-slate'];
  Object.entries(kpiMap).forEach(([s, cfg]) => {
    const btn = document.getElementById(cfg.id);
    if (!btn) return;
    if (s === status) {
      btn.classList.add(cfg.cls);
    } else {
      btn.classList.remove(...allCls);
    }
  });
}

function setDashToggle(btn, active, icon, label, color) {
  // color: 'amber' | 'indigo'
  const palette = {
    amber:  { bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-200',  iconOn: 'text-amber-500'  },
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', iconOn: 'text-indigo-500' },
  }[color];
  const iconCls = active ? palette.iconOn : 'text-gray-400';
  btn.innerHTML = `<span class="material-symbols-outlined ${iconCls}" style="font-size:13px;">${icon}</span> ${label}`;
  if (active) {
    btn.classList.remove('bg-white', 'text-gray-500', 'border-gray-200');
    btn.classList.add(palette.bg, palette.text, palette.border);
  } else {
    btn.classList.remove(palette.bg, palette.text, palette.border);
    btn.classList.add('bg-white', 'text-gray-500', 'border-gray-200');
  }
}

function showToast(msg, isErr = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = el.className.replace(/bg-\w+-\d+/g, '');
  el.classList.add(isErr ? 'bg-red-600' : 'bg-gray-900');
  el.classList.remove('opacity-0', 'pointer-events-none', 'translate-y-2');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.add('opacity-0', 'pointer-events-none', 'translate-y-2');
  }, 3000);
}

async function apiFetch(url, method = 'GET', body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function openRetroModal() {
  document.getElementById('retro-overlay').classList.remove('opacity-0', 'pointer-events-none');
  document.getElementById('retro-card').classList.remove('scale-95');
  document.getElementById('retro-card').classList.add('scale-100');

  (async () => {
    if (!retroMetadata) {
      try {
        retroMetadata = await apiFetch('/api/retro/metadata');
      } catch (e) {
        showToast('Failed to load retro metadata', true); return;
      }
    }
    const stateEl  = document.getElementById('retro-state');
    const currState = stateEl.value;
    stateEl.innerHTML = '<option value="">All States</option>';
    Object.keys(retroMetadata).sort().forEach(s => stateEl.appendChild(new Option(s, s)));
    if (currState && retroMetadata[currState]) {
      stateEl.value = currState;
    } else {
      document.getElementById('retro-type').innerHTML = '<option value="">All Types</option>';
      document.getElementById('retro-type').disabled  = true;
      document.getElementById('retro-year').innerHTML = '<option value="">All Years</option>';
      document.getElementById('retro-year').disabled  = true;
    }
    updateRetroCountLocal();
  })();
}

function closeRetroModal() {
  document.getElementById('retro-overlay').classList.add('opacity-0', 'pointer-events-none');
  document.getElementById('retro-card').classList.remove('scale-100');
  document.getElementById('retro-card').classList.add('scale-95');
}

function updateRetroCountLocal() {
  if (!retroMetadata) return;
  const s = document.getElementById('retro-state').value;
  const t = document.getElementById('retro-type').value;
  const y = document.getElementById('retro-year').value;

  let count = 0;
  if (s && t && y) {
    count = retroMetadata[s]?.[t]?.[y] || 0;
  } else if (s && t) {
    Object.values(retroMetadata[s]?.[t] || {}).forEach(c => count += c);
  } else if (s) {
    Object.values(retroMetadata[s] || {}).forEach(types => Object.values(types).forEach(c => count += c));
  } else {
    Object.values(retroMetadata || {}).forEach(states =>
      Object.values(states).forEach(types => Object.values(types).forEach(c => count += c)));
  }

  const preview = document.getElementById('retro-count-preview');
  preview.textContent = count === 1 ? '1 record found' : `${count.toLocaleString()} records found`;

  const btn = document.getElementById('retro-download');
  if (s && t && y && count > 0) {
    btn.disabled = false;
    btn.removeAttribute('aria-disabled');
    btn.className = 'px-4 py-2 text-[12.5px] font-semibold rounded-lg transition-all flex items-center gap-1.5 bg-gray-900 text-white hover:bg-gray-800 cursor-pointer';
  } else {
    btn.disabled = true;
    btn.setAttribute('aria-disabled', 'true');
    btn.className = 'px-4 py-2 text-[12.5px] font-semibold rounded-lg transition-all flex items-center gap-1.5 bg-gray-200 text-gray-400 cursor-not-allowed';
  }
}

function showConfirmModal() {
  return new Promise(resolve => {
    const overlay = document.getElementById('confirm-overlay');
    const card    = document.getElementById('confirm-card');
    overlay.classList.remove('opacity-0', 'pointer-events-none');
    card.classList.remove('scale-95'); card.classList.add('scale-100');
    confirmResolve = resolve;
  });
}

function closeConfirmModal(result) {
  const overlay = document.getElementById('confirm-overlay');
  const card    = document.getElementById('confirm-card');
  overlay.classList.add('opacity-0', 'pointer-events-none');
  card.classList.remove('scale-100'); card.classList.add('scale-95');
  if (confirmResolve) { confirmResolve(result); confirmResolve = null; }
}

function bindEvents() {
  document.getElementById('confirm-cancel').addEventListener('click',  () => closeConfirmModal(false));
  document.getElementById('confirm-proceed').addEventListener('click', () => closeConfirmModal(true));

  document.getElementById('filter-state').addEventListener('change', e => {
    filters.state   = e.target.value;
    filters.el_type = '';
    filters.year    = '';
    const typeEl = document.getElementById('filter-type');
    const yearEl = document.getElementById('filter-year');
    typeEl.innerHTML = '<option value="">All Types</option>';
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (filters.state && filterMetadata?.[filters.state]) {
      typeEl.disabled = false;
      Object.keys(filterMetadata[filters.state]).sort().forEach(t => typeEl.appendChild(new Option(t, t)));
    } else { typeEl.disabled = true; }
    yearEl.disabled = true;
    loadStats(); loadRecords();
  });

  document.getElementById('filter-type').addEventListener('change', e => {
    filters.el_type = e.target.value;
    filters.year    = '';
    const yearEl = document.getElementById('filter-year');
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (filters.state && filters.el_type && filterMetadata?.[filters.state]?.[filters.el_type]) {
      yearEl.disabled = false;
      Object.keys(filterMetadata[filters.state][filters.el_type]).sort((a, b) => b.localeCompare(a))
        .forEach(y => yearEl.appendChild(new Option(y, y)));
    } else { yearEl.disabled = true; }
    loadStats(); loadRecords();
  });

  document.getElementById('filter-year').addEventListener('change',  e => { filters.year     = e.target.value; loadStats(); loadRecords(); });
  document.getElementById('filter-sir').addEventListener('change',   e => { filters.sir_only = e.target.checked; loadStats(); loadRecords(); });

  document.getElementById('global-search').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { filters.search = e.target.value.trim(); loadRecords(); }, 250);
  });

  document.getElementById('clear-filters').addEventListener('click', () => {
    Object.assign(filters, { state: '', el_type: '', year: '', status: '', sir_only: false, search: '', show_bp: false });
    ['filter-state', 'filter-type', 'filter-year'].forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('filter-type').disabled = true;
    document.getElementById('filter-year').disabled = true;
    document.getElementById('filter-sir').checked   = false;
    document.getElementById('global-search').value  = '';
    setActiveKpi(null);
    const bpBtn = document.getElementById('toggle-bp-btn');
    if (bpBtn) {
      bpBtn.innerHTML = '<span class="material-symbols-outlined text-gray-400" style="font-size:13px;">filter_alt</span> Show BP';
      bpBtn.classList.remove('bg-indigo-50', 'text-indigo-700', 'border-indigo-200');
      bpBtn.classList.add('bg-white', 'text-gray-500', 'border-gray-200');
    }
    handleSideNav('all');
  });

  document.getElementById('select-all')?.addEventListener('change', e => {
    allRecords.forEach(r => e.target.checked ? selectedIds.add(r.id) : selectedIds.delete(r.id));
    renderTable(); updateSelBar();
  });

  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      sortDir = sortCol === col && sortDir === 'asc' ? 'desc' : 'asc';
      sortCol = col;
      renderTable();
    });
  });

  document.getElementById('modal-close').addEventListener('click',  closeModal);
  document.getElementById('modal-cancel').addEventListener('click', closeModal);
  document.getElementById('modal-save').addEventListener('click',   saveModal);
  document.getElementById('overlay').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });

  document.querySelectorAll('.sidelink').forEach(el => {
    el.addEventListener('click', e => { e.preventDefault(); handleSideNav(el.dataset.view); });
  });

  // ── Tab navigation ──────────────────────────────────────────────────────
  const navTabs = [
    { id: 'nav-listing',   viewId: 'listing-view',   setup: () => { loadStats(); loadRecords(); } },
    { id: 'nav-dashboard', viewId: 'dashboard-view', setup: loadDashboardStats },
    { id: 'nav-glance',    viewId: 'glance-view',    setup: loadGlancePanel },
  ];

  function switchTab(activeId) {
    navTabs.forEach(t => {
      const nav  = document.getElementById(t.id);
      const view = document.getElementById(t.viewId);
      if (!nav || !view) return;
      if (t.id === activeId) {
        view.classList.remove('hidden'); view.classList.add('flex');
        nav.classList.add('active');
        if (t.setup) t.setup();
      } else {
        view.classList.add('hidden'); view.classList.remove('flex');
        nav.classList.remove('active');
      }
    });

    // Pipeline Stages sidebar: only shown on the Listing page
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    if (sidebar && mainContent) {
      if (activeId === 'nav-listing') {
        sidebar.classList.remove('hidden'); sidebar.classList.add('flex');
        mainContent.classList.add('ml-[216px]');
      } else {
        sidebar.classList.add('hidden'); sidebar.classList.remove('flex');
        mainContent.classList.remove('ml-[216px]');
      }
    }
  }

  navTabs.forEach(t => {
    const el = document.getElementById(t.id);
    if (el) el.addEventListener('click', () => switchTab(t.id));
  });

  const dashRefreshBtn = document.getElementById('dash-refresh-btn');
  if (dashRefreshBtn) dashRefreshBtn.addEventListener('click', loadDashboardStats);

  ['glance-month-filter', 'glance-state-filter', 'glance-type-filter'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', loadGlancePanel);
  });

  // Glance Report → Download analytics PDF (this week in focus)
  const glancePdfBtn = document.getElementById('glance-pdf-btn');
  if (glancePdfBtn) {
    glancePdfBtn.addEventListener('click', async () => {
      const state = (document.getElementById('glance-state-filter') || {}).value || '';
      const type  = (document.getElementById('glance-type-filter')  || {}).value || '';
      const params = new URLSearchParams();
      if (state) params.set('state', state);
      if (type)  params.set('el_type', type);
      params.set('hide_bp', '1');

      const orig = glancePdfBtn.innerHTML;
      glancePdfBtn.disabled = true;
      glancePdfBtn.innerHTML = '<span class="material-symbols-outlined animate-spin" style="font-size:14px;">refresh</span> Generating…';
      try {
        const res = await fetch('/api/glance_report/pdf?' + params.toString());
        if (!res.ok) {
          let msg = 'PDF generation failed';
          try { msg = (await res.json()).error || msg; } catch (_) {}
          throw new Error(msg);
        }
        const blob = await res.blob();
        const cd   = res.headers.get('Content-Disposition') || '';
        const m    = cd.match(/filename="?([^"]+)"?/);
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href = url;
        a.download = m ? m[1] : 'Weekly_Report.pdf';
        a.click();
        URL.revokeObjectURL(url);
        showToast('Weekly Report PDF downloaded');
      } catch (e) {
        showToast(e.message, true);
      } finally {
        glancePdfBtn.disabled = false;
        glancePdfBtn.innerHTML = orig;
      }
    });
  }

  document.getElementById('nav-retro').addEventListener('click', e => {
    e.preventDefault(); openRetroModal();
  });

  document.getElementById('retro-close').addEventListener('click',  closeRetroModal);
  document.getElementById('retro-cancel').addEventListener('click', closeRetroModal);
  document.getElementById('retro-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeRetroModal();
  });

  document.getElementById('retro-state').addEventListener('change', e => {
    const s = e.target.value;
    const typeEl = document.getElementById('retro-type');
    const yearEl = document.getElementById('retro-year');
    typeEl.innerHTML = '<option value="">All Types</option>';
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (s && retroMetadata?.[s]) {
      typeEl.disabled = false;
      Object.keys(retroMetadata[s]).sort().forEach(t => typeEl.appendChild(new Option(t, t)));
    } else { typeEl.disabled = true; }
    yearEl.disabled = true;
    updateRetroCountLocal();
  });

  document.getElementById('retro-type').addEventListener('change', e => {
    const s = document.getElementById('retro-state').value;
    const t = e.target.value;
    const yearEl = document.getElementById('retro-year');
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (s && t && retroMetadata?.[s]?.[t]) {
      yearEl.disabled = false;
      Object.keys(retroMetadata[s][t]).sort((a, b) => b.localeCompare(a)).forEach(y => yearEl.appendChild(new Option(y, y)));
    } else { yearEl.disabled = true; }
    updateRetroCountLocal();
  });

  document.getElementById('retro-year').addEventListener('change', updateRetroCountLocal);

  document.getElementById('retro-download').addEventListener('click', async () => {
    const state  = document.getElementById('retro-state').value;
    const type   = document.getElementById('retro-type').value;
    const year   = document.getElementById('retro-year').value;
    const fmt    = document.getElementById('retro-format').value;
    if (!state || !type || !year) { showToast('Please select State, Type, and Year.', true); return; }

    const btn = document.getElementById('retro-download');
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined animate-spin" style="font-size:14px;">refresh</span> Downloading…';
    try {
      const res = await fetch(`/api/retro/export?state=${state}&el_type=${type}&year=${year}&format=${fmt}`);
      if (!res.ok) { const err = await res.json(); throw new Error(err.error || 'Export failed'); }
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = `Retro_${state}_${type}_${year}.${fmt}`; a.click();
      URL.revokeObjectURL(url);
      showToast('Download started');
      closeRetroModal();
    } catch (e) { showToast(e.message, true); }
    finally {
      btn.disabled = false;
      btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:14px;">download</span> Download';
      updateRetroCountLocal();
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closeRetroModal(); clearSelection(); }
  });

  // BP toggle
  const bpBtn = document.getElementById('toggle-bp-btn');
  if (bpBtn) {
    bpBtn.addEventListener('click', () => {
      filters.show_bp = !filters.show_bp;
      if (filters.show_bp) {
        bpBtn.innerHTML = '<span class="material-symbols-outlined text-indigo-500" style="font-size:13px;">filter_alt_off</span> Hide BP';
        bpBtn.classList.remove('bg-white', 'text-gray-500', 'border-gray-200');
        bpBtn.classList.add('bg-indigo-50', 'text-indigo-700', 'border-indigo-200');
      } else {
        bpBtn.innerHTML = '<span class="material-symbols-outlined text-gray-400" style="font-size:13px;">filter_alt</span> Show BP';
        bpBtn.classList.remove('bg-indigo-50', 'text-indigo-700', 'border-indigo-200');
        bpBtn.classList.add('bg-white', 'text-gray-500', 'border-gray-200');
      }
      loadStats(); loadRecords();
    });
  }
}


// ── Dashboard ─────────────────────────────────────────────────────────────────
// ── Dashboard extended analytics (retro, caste) ───────────
let analyticsLoaded = false;

async function loadDashboardAnalytics(forceRefresh = false) {
  if (analyticsLoaded && !forceRefresh) return;
  try {
    const res = await fetch('/api/dashboard/analytics');
    if (!res.ok && res.status !== 202) { console.error('analytics fetch:', res.status); return; }
    const d = await res.json();
    renderRetroPanel(d.retro);
    renderCastePanel(d.caste);
    if (d.mapping_years || d.mapping_entries) {
      updateForm20WithMapping(d.mapping_years || 0, d.mapping_entries || 0, _f20Total, d.mapping_by_type || {});
    }
    if (res.status === 200) {
      analyticsLoaded = true;
    } else {
      // Cache still building — retry in 15s to fill in by_type and top_states
      setTimeout(() => loadDashboardAnalytics(true), 15000);
    }
  } catch (e) {
    console.error('loadDashboardAnalytics:', e);
  }
}

function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString('en-IN');
}

function typeColor(type) {
  const m = { AE:'#6366f1', GE:'#3b82f6', 'AE-BP':'#a78bfa', 'GE-BP':'#93c5fd' };
  return m[type] || '#94a3b8';
}

function renderForm20Panel(stats) {
  const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const bs        = stats.by_status || {};
  const total     = stats.total || 0;
  const completed = (bs.db_pushed || 0) + (bs.completed || 0);
  const pct       = total > 0 ? Math.round((completed / total) * 100) : 0;
  const circ      = 163.4;
  const dash      = circ * (1 - pct / 100);

  // Ring chart
  const ring    = document.getElementById('f20-ring');
  const ringPct = document.getElementById('f20-ring-pct');
  if (ring)    ring.style.strokeDashoffset = dash;
  if (ringPct) ringPct.textContent = pct + '%';

  _f20TotalYears = stats.total_years || 0;
  _f20Total      = stats.total       || 0;
  _f20ByType     = stats.by_type     || {};

  setEl('f20-pct',        pct + '%');
  setEl('f20-pct-badge',  pct + '% complete');
  setEl('f20-counts',     `${completed.toLocaleString()} / ${total.toLocaleString()} elections in DB`);
  const progEl = document.getElementById('f20-prog');
  if (progEl) progEl.style.width = pct + '%';

  // By election type (AE, GE — excluding BP variants)
  const typeWrap = document.getElementById('f20-type-rows');
  if (typeWrap && stats.by_type) {
    const TYPE_META = {
      'AE': { label: 'Assembly', bg: 'bg-gray-700'  },
      'GE': { label: 'General',  bg: 'bg-blue-500'  },
    };
    const entries = Object.entries(stats.by_type)
      .filter(([t]) => !t.includes('-BP'))
      .sort((a, b) => b[1].total - a[1].total);

    typeWrap.innerHTML = entries.map(([type, d]) => {
      const p   = d.total > 0 ? Math.round((d.completed / d.total) * 100) : 0;
      const m   = TYPE_META[type] || { label: type, bg: 'bg-gray-400' };
      const pctColor = p === 100 ? 'text-emerald-600' : p >= 80 ? 'text-blue-600' : p >= 50 ? 'text-amber-600' : 'text-rose-500';
      return `
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 w-[90px] shrink-0">
            <span class="w-2 h-2 rounded-full ${m.bg} shrink-0"></span>
            <span class="text-[10.5px] font-semibold text-gray-700">${type}</span>
            <span class="text-[9.5px] text-gray-400">${m.label}</span>
          </div>
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${m.bg} bar-fill" style="width:${p}%"></div>
          </div>
          <div class="flex items-center gap-1 shrink-0 w-[72px] justify-end">
            <span class="text-[11px] font-bold tabular-nums ${pctColor}">${p}%</span>
            <span class="text-[9.5px] text-gray-400 tabular-nums">${d.completed}/${d.total}</span>
          </div>
        </div>`;
    }).join('');
  }

  // Top completed states
  const stateWrap = document.getElementById('f20-state-rows');
  if (stateWrap && stats.by_state) {
    const topStates = [...stats.by_state]
      .filter(s => s.completed > 0)
      .sort((a, b) => b.completed - a.completed)
      .slice(0, 8);
    const max = topStates[0]?.completed || 1;
    stateWrap.className = 'grid grid-cols-4 gap-1.5';
    stateWrap.innerHTML = topStates.map(s => {
      const intensity = Math.round((s.completed / max) * 9) + 1;
      const bg = intensity >= 8 ? 'bg-gray-100 border-gray-300' :
                 intensity >= 5 ? 'bg-gray-50 border-gray-200' : 'bg-gray-50 border-gray-100';
      const tc = intensity >= 8 ? 'text-gray-800' : 'text-gray-600';
      return `
        <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5">
          <span class="text-[10.5px] font-bold ${tc}">${s.state}</span>
          <span class="text-[12px] font-black text-gray-900 tabular-nums leading-none">${s.completed}</span>
        </div>`;
    }).join('');
  }
}

function updateForm20WithMapping(mappingYears, mappingEntries, form20Total, mappingByType = {}) {
  const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  // ── Entry-level coverage: (Form20 unique entries) / (mapping unique entries) ──
  if (mappingEntries && form20Total) {
    const pct  = Math.round((form20Total / mappingEntries) * 100);
    const circ = 163.4;
    const dash = circ * (1 - pct / 100);
    const ring    = document.getElementById('f20-ring');
    const ringPct = document.getElementById('f20-ring-pct');
    if (ring)    ring.style.strokeDashoffset = dash;
    if (ringPct) ringPct.textContent = pct + '%';
    setEl('f20-pct',       pct + '%');
    setEl('f20-pct-label', 'coverage');
    setEl('f20-pct-badge', pct + '% coverage');
    setEl('f20-counts',    `${form20Total.toLocaleString()} / ${mappingEntries.toLocaleString()} elections in Form 20`);
  }

  // ── By Election Type: re-render with 262 mapping totals as denominator ──
  // Numerator = pipeline-completed elections (from SQLite _f20ByType)
  // Denominator = total elections in AC-PC mapping (from RDS mapping_by_type)
  const typeWrap = document.getElementById('f20-type-rows');
  if (typeWrap && mappingByType && Object.keys(mappingByType).length > 0) {
    const TYPE_META = {
      'AE': { label: 'Assembly', bg: 'bg-gray-700'  },
      'GE': { label: 'General',  bg: 'bg-blue-500'  },
    };
    const entries = Object.entries(mappingByType)
      .filter(([t]) => !t.includes('-BP'))
      .sort((a, b) => b[1] - a[1]);

    typeWrap.innerHTML = entries.map(([type, mappingTotal]) => {
      const pipe  = _f20ByType[type] || { completed: 0, total: 0 };
      const done  = pipe.completed || 0;
      const p     = mappingTotal > 0 ? Math.round((done / mappingTotal) * 100) : 0;
      const m     = TYPE_META[type] || { label: type, bg: 'bg-gray-400' };
      const pctColor = p === 100 ? 'text-emerald-600' : p >= 80 ? 'text-blue-600' : p >= 50 ? 'text-amber-600' : 'text-rose-500';
      return `
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 w-[90px] shrink-0">
            <span class="w-2 h-2 rounded-full ${m.bg} shrink-0"></span>
            <span class="text-[10.5px] font-semibold text-gray-700">${type}</span>
            <span class="text-[9.5px] text-gray-400">${m.label}</span>
          </div>
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${m.bg} bar-fill" style="width:${p}%"></div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0 justify-end whitespace-nowrap">
            <span class="text-[11px] font-bold tabular-nums ${pctColor}">${p}%</span>
            <span class="text-[9.5px] text-gray-400 tabular-nums">${done}/${mappingTotal}</span>
          </div>
        </div>`;
    }).join('');
  }
}

function renderRetroPanel(r) {
  if (!r || !r.available) {
    const typeWrap  = document.getElementById('retro-type-rows');
    const stateWrap = document.getElementById('retro-state-rows');
    if (typeWrap)  typeWrap.innerHTML  = `<p class="text-[10.5px] text-gray-400 text-center py-2">${r?.error?.includes('permission') ? 'GRANT SELECT required' : (r?.error || 'Unavailable')}</p>`;
    if (stateWrap) stateWrap.innerHTML = '';
    return;
  }

  const acTotal = r.ac_total     || 0;
  const acAvail = r.ac_available || 0;
  const pctRaw  = acTotal > 0 ? (acAvail / acTotal) * 100 : 0;
  const pct     = parseFloat(pctRaw.toFixed(2));   // 2-decimal accuracy
  const circ    = 163.4;
  const dash    = circ * (1 - Math.min(pct, 100) / 100);

  // Ring chart
  const ring    = document.getElementById('retro-ring');
  const ringPct = document.getElementById('retro-ring-pct');
  if (ring)    ring.style.strokeDashoffset = dash;
  if (ringPct) ringPct.textContent = pct + '%';

  // Main numbers
  const setPct = document.getElementById('retro-pct');
  const setCov = document.getElementById('retro-covered-label');
  const setBar = document.getElementById('retro-prog');
  if (setPct) setPct.textContent = pct + '%';
  if (setCov) setCov.textContent = fmtNum(acAvail) + ' / ' + fmtNum(acTotal) + ' ACs in DB';
  if (setBar) setBar.style.width = Math.min(pct, 100) + '%';

  // Hero ribbon — retro coverage
  const hr = document.getElementById('hero-retro');
  const hrs = document.getElementById('hero-retro-sub');
  if (hr)  hr.textContent  = pct + '%';
  if (hrs) hrs.textContent = fmtNum(acAvail) + ' ACs in DB';

  // ── By Election Type (AE / GE — non-BP) ──────────────────────────────────
  const typeWrap = document.getElementById('retro-type-rows');
  if (typeWrap && r.by_type_ac) {
    const TYPE_META = {
      'AE': { label: 'Assembly', bg: 'bg-indigo-500', text: 'text-indigo-600' },
      'GE': { label: 'General',  bg: 'bg-blue-500',   text: 'text-blue-600'  },
    };
    typeWrap.innerHTML = r.by_type_ac.map(t => {
      const pRaw = t.total > 0 ? (t.available / t.total) * 100 : 0;
      const p    = parseFloat(pRaw.toFixed(2));   // 2-decimal accuracy
      const m = TYPE_META[t.type] || { label: t.type, bg: 'bg-gray-400', text: 'text-gray-600' };
      const pctColor = p >= 99.99 ? 'text-emerald-600' : p >= 80 ? 'text-blue-600' : p >= 50 ? 'text-amber-600' : 'text-rose-500';
      return `
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 w-[90px] shrink-0">
            <span class="w-2 h-2 rounded-full ${m.bg} shrink-0"></span>
            <span class="text-[10.5px] font-semibold text-gray-700">${t.type}</span>
            <span class="text-[9.5px] text-gray-400">${m.label}</span>
          </div>
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${m.bg} bar-fill" style="width:${Math.min(p, 100)}%"></div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0 justify-end whitespace-nowrap">
            <span class="text-[11px] font-bold tabular-nums ${pctColor}">${p}%</span>
            <span class="text-[9.5px] text-gray-400 tabular-nums">${fmtNum(t.available)}/${fmtNum(t.total)}</span>
          </div>
        </div>`;
    }).join('');
  }

  // ── Top States — pill grid with AC count + pct ───────────────────────────
  const stateWrap = document.getElementById('retro-state-rows');
  if (stateWrap && r.top_states_ac) {
    const max = r.top_states_ac[0]?.available || 1;
    stateWrap.className = 'grid grid-cols-4 gap-1.5';
    stateWrap.innerHTML = r.top_states_ac.map(s => {
      const intensity = Math.round((s.available / max) * 9) + 1;
      const bg = intensity >= 8 ? 'bg-indigo-100 border-indigo-200' :
                 intensity >= 5 ? 'bg-indigo-50 border-indigo-100' : 'bg-gray-50 border-gray-100';
      const tc = intensity >= 8 ? 'text-indigo-700' : intensity >= 5 ? 'text-indigo-600' : 'text-gray-600';
      return `
        <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5" title="${s.state}: ${fmtNum(s.available)} / ${fmtNum(s.expected)} ACs (${s.pct}%)">
          <span class="text-[10.5px] font-bold ${tc}">${s.state}</span>
          <span class="text-[12px] font-black text-gray-900 tabular-nums leading-none">${fmtNum(s.available)}</span>
          <span class="text-[9px] text-gray-400 tabular-nums leading-none">${s.pct}%</span>
        </div>`;
    }).join('');
  }
}

function _lockHTML(errMsg) {
  const notExist = errMsg && (errMsg.includes('does not exist') || errMsg.includes('relation'));
  const noPerm   = errMsg && errMsg.includes('permission');
  const icon  = notExist ? 'schedule' : 'lock';
  const title = notExist ? 'Table not yet populated' : noPerm ? 'DB access required' : 'Unavailable';
  const detail= notExist ? 'Data will appear once this table is loaded in RDS.'
              : noPerm   ? 'Contact DB admin to grant SELECT access on this table.'
              : (errMsg || 'Unable to load data');
  return `<div class="flex flex-col items-center justify-center gap-2 py-10 px-4 text-center flex-1">
    <span class="material-symbols-outlined text-gray-200" style="font-size:28px;">${icon}</span>
    <p class="text-[11px] font-semibold text-gray-400">${title}</p>
    <p class="text-[10px] text-gray-300 max-w-[180px] leading-relaxed">${detail}</p>
  </div>`;
}

// ── Caste category display-name normalisation ────────────────────────────────
// Merges dirty duplicates (e.g. "MUSLIM" + "Muslim", repeated "Buddhist") and
// produces a clean, human-readable label. Known acronyms stay upper-case.
const CASTE_ACRONYMS = new Set(['SC', 'ST', 'OBC', 'GEN', 'EBC', 'BC', 'SBC', 'MBC', 'DNT']);
function casteDisplayName(raw) {
  const k = String(raw || 'Other').trim();
  if (!k) return 'Other';
  const up = k.toUpperCase();
  if (CASTE_ACRONYMS.has(up)) return up;
  // Title-case multi-word / all-caps names: "MINORITY" -> "Minority"
  return k.toLowerCase().replace(/\b\w/g, ch => ch.toUpperCase());
}

// Palette for caste categories (stable, distinct)
const CASTE_PALETTE = ['#f59e0b','#6366f1','#10b981','#3b82f6','#ec4899','#8b5cf6','#14b8a6','#ef4444','#84cc16','#f97316','#06b6d4','#a855f7'];

function renderCastePanel(d) {
  const pctEl = document.getElementById('caste-pct');
  const subStatesEl = document.getElementById('caste-sub-states');
  const body  = document.getElementById('caste-body');

  // Hero ribbon (populate regardless of layout)
  const heroCaste    = document.getElementById('hero-caste');
  const heroCasteSub = document.getElementById('hero-caste-sub');

  if (!d || !d.available) {
    if (pctEl) pctEl.textContent = '—';
    if (heroCaste) heroCaste.textContent = '—';
    if (body)  body.innerHTML = _lockHTML(d?.error);
    return;
  }

  // ── Clean / dedupe categories ──────────────────────────────────────────────
  const merged = {};
  (d.by_category || []).forEach(c => {
    const name = casteDisplayName(c.category);
    if (!merged[name]) merged[name] = { category: name, acs: 0, rows: 0 };
    merged[name].acs  = Math.max(merged[name].acs, c.acs || 0); // distinct-AC: take max, not sum
    merged[name].rows += (c.rows || 0);
  });
  const cats = Object.values(merged).sort((a, b) => b.acs - a.acs);

  const acsCovered  = d.acs_with_data || 0;
  const totalRows   = d.total_rows || cats.reduce((a, c) => a + c.rows, 0);
  const realCatN    = cats.length;            // deduped count
  const rawCatN     = d.categories || realCatN;
  const density     = acsCovered > 0 ? (totalRows / acsCovered) : 0;

  if (pctEl) pctEl.textContent = fmtNum(acsCovered) + ' ACs';
  if (subStatesEl) subStatesEl.textContent = fmtNum(d.states);
  if (heroCaste)    heroCaste.textContent    = fmtNum(totalRows);
  if (heroCasteSub) heroCasteSub.textContent = `${realCatN} categories · ${fmtNum(acsCovered)} ACs`;

  if (!body) return;

  // ── Coverage tiers ─────────────────────────────────────────────────────────
  const tierOf = pct => pct >= 75 ? 'core' : pct >= 40 ? 'strong' : pct >= 10 ? 'regional' : 'sparse';
  const TIER_META = {
    core:     { label: 'Near-universal', color: '#059669', bg: 'bg-emerald-50 text-emerald-700' },
    strong:   { label: 'Strong',          color: '#2563eb', bg: 'bg-blue-50 text-blue-700' },
    regional: { label: 'Regional',        color: '#d97706', bg: 'bg-amber-50 text-amber-700' },
    sparse:   { label: 'Sparse',          color: '#94a3b8', bg: 'bg-slate-100 text-slate-500' },
  };
  cats.forEach(c => { c.pct = acsCovered > 0 ? (c.acs / acsCovered) * 100 : 0; c.tier = tierOf(c.pct); });

  const coreCats = cats.filter(c => c.tier === 'core');
  const tierCounts = cats.reduce((m, c) => { m[c.tier] = (m[c.tier] || 0) + 1; return m; }, {});

  // ── Auto-generated insight (PowerBI-style headline) ────────────────────────
  const topNames = coreCats.slice(0, 3).map(c => c.category);
  const longTail = cats.filter(c => c.tier === 'sparse' || c.tier === 'regional').slice(-3).map(c => c.category);
  let insight;
  if (topNames.length) {
    const named = coreCats.slice(0, 3);
    const minCore = Math.floor(Math.min(...named.map(c => c.pct)));
    insight = `<b>${topNames.join(', ')}</b> data reaches <b>${minCore}%+</b> of all ${fmtNum(acsCovered)} covered ACs — the most complete demographic dimensions.`;
    if (longTail.length) insight += ` In contrast, ${longTail.join(', ')} remain regional/sparse, signalling where caste enrichment is still thin.`;
  } else {
    insight = `Caste data spans ${realCatN} categories across ${fmtNum(d.states)} states with an average of <b>${density.toFixed(1)} records/AC</b>.`;
  }

  // ── Donut: record-volume share (top 6 + Others) ────────────────────────────
  const byRows = [...cats].sort((a, b) => b.rows - a.rows);
  const donutTop = byRows.slice(0, 6);
  const otherRows = byRows.slice(6).reduce((a, c) => a + c.rows, 0);
  const donutLabels = donutTop.map(c => c.category).concat(otherRows > 0 ? ['Others'] : []);
  const donutData   = donutTop.map(c => c.rows).concat(otherRows > 0 ? [otherRows] : []);
  const donutColors = donutTop.map((_, i) => CASTE_PALETTE[i % CASTE_PALETTE.length]).concat(otherRows > 0 ? ['#cbd5e1'] : []);

  const topStates = (d.top_states || []);
  const maxStateAc = topStates[0]?.acs || 1;

  body.innerHTML = `
    <div class="p-5 grid grid-cols-1 lg:grid-cols-12 gap-5 fade-up">

      <!-- LEFT: KPIs + donut -->
      <div class="lg:col-span-4 flex flex-col gap-4">
        <!-- KPI tiles -->
        <div class="grid grid-cols-2 gap-2.5">
          ${[
            { v: fmtNum(acsCovered), l: 'ACs Covered', c: 'text-amber-600', i: 'map' },
            { v: fmtNum(d.states),   l: 'States',      c: 'text-gray-900',  i: 'public' },
            { v: realCatN,           l: 'Categories',  c: 'text-gray-900',  i: 'category', sub: rawCatN > realCatN ? `${rawCatN} raw` : '' },
            { v: density.toFixed(1), l: 'Records / AC', c: 'text-indigo-600', i: 'density_medium' },
          ].map(k => `
            <div class="rounded-xl border border-gray-100 bg-gradient-to-br from-gray-50 to-white p-3">
              <div class="flex items-center justify-between mb-1">
                <span class="material-symbols-outlined text-gray-300" style="font-size:14px;">${k.i}</span>
                ${k.sub ? `<span class="text-[8.5px] font-semibold text-gray-300">${k.sub}</span>` : ''}
              </div>
              <p class="text-[20px] font-black tabular-nums leading-none ${k.c}">${k.v}</p>
              <p class="text-[9.5px] text-gray-400 font-medium mt-1 uppercase tracking-wide">${k.l}</p>
            </div>`).join('')}
        </div>

        <!-- Record volume donut -->
        <div class="rounded-xl border border-gray-100 p-3">
          <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">Record Volume Share</p>
          <div class="relative mx-auto" style="width:150px;height:150px;">
            <canvas id="casteDonut"></canvas>
            <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span class="text-[17px] font-black text-gray-900 tabular-nums leading-none">${fmtNum(totalRows)}</span>
              <span class="text-[9px] text-gray-400 font-medium">records</span>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-x-3 gap-y-1 mt-3">
            ${donutLabels.map((lbl, i) => {
              const share = totalRows > 0 ? Math.round((donutData[i] / totalRows) * 100) : 0;
              return `<div class="flex items-center gap-1.5 min-w-0">
                <span class="w-2 h-2 rounded-sm shrink-0" style="background:${donutColors[i]}"></span>
                <span class="text-[10px] text-gray-600 truncate flex-1">${lbl}</span>
                <span class="text-[10px] font-semibold text-gray-400 tabular-nums">${share}%</span>
              </div>`;
            }).join('')}
          </div>
        </div>
      </div>

      <!-- MIDDLE: insight + category reach -->
      <div class="lg:col-span-5 flex flex-col gap-3">
        <div class="insight-banner px-3.5 py-3 flex items-start gap-2.5">
          <span class="material-symbols-outlined text-amber-500 shrink-0" style="font-size:16px;">lightbulb</span>
          <p class="text-[11.5px] text-amber-900/90 leading-relaxed">${insight}</p>
        </div>

        <div class="flex items-center justify-between">
          <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Category Reach <span class="text-gray-300 normal-case font-medium">· % of covered ACs</span></p>
          <div class="flex items-center gap-1.5">
            ${['core','strong','regional','sparse'].filter(t => tierCounts[t]).map(t =>
              `<span class="tier-chip ${TIER_META[t].bg}"><span class="w-1.5 h-1.5 rounded-full" style="background:${TIER_META[t].color}"></span>${tierCounts[t]}</span>`
            ).join('')}
          </div>
        </div>

        <div class="flex flex-col gap-2">
          ${cats.map(c => {
            const tm = TIER_META[c.tier];
            const pctTxt = c.pct >= 10 ? Math.round(c.pct) : c.pct.toFixed(1);
            return `
              <div class="flex items-center gap-2.5">
                <span class="text-[11px] font-semibold text-gray-700 w-[68px] shrink-0 truncate" title="${c.category}">${c.category}</span>
                <div class="flex-1 h-2.5 cov-track">
                  <div class="cov-fill" style="width:${Math.max(c.pct, 1.5)}%;background:${tm.color}"></div>
                </div>
                <span class="text-[10.5px] font-bold tabular-nums w-9 text-right" style="color:${tm.color}">${pctTxt}%</span>
                <span class="text-[9.5px] text-gray-400 tabular-nums w-[58px] text-right">${fmtNum(c.acs)} ACs</span>
              </div>`;
          }).join('')}
        </div>
      </div>

      <!-- RIGHT: top states -->
      <div class="lg:col-span-3 flex flex-col">
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2.5">Top States by Coverage</p>
        <div class="flex flex-col gap-1.5">
          ${topStates.slice(0, 10).map((s, i) => {
            const p = Math.round((s.acs / maxStateAc) * 100);
            const rankColor = i === 0 ? 'bg-amber-100 text-amber-700' : i < 3 ? 'bg-gray-100 text-gray-600' : 'bg-gray-50 text-gray-400';
            return `
              <div class="flex items-center gap-2">
                <span class="w-4 h-4 rounded text-[9px] font-bold flex items-center justify-center shrink-0 ${rankColor}">${i + 1}</span>
                <span class="text-[11px] font-bold text-gray-700 w-7 shrink-0">${s.state}</span>
                <div class="flex-1 h-2 cov-track">
                  <div class="cov-fill" style="width:${p}%;background:linear-gradient(90deg,#fbbf24,#f59e0b)"></div>
                </div>
                <span class="text-[10px] tabular-nums text-gray-500 w-9 text-right shrink-0">${fmtNum(s.acs)}</span>
              </div>`;
          }).join('')}
        </div>
      </div>

    </div>`;

  // ── Instantiate donut ──────────────────────────────────────────────────────
  const ctx = document.getElementById('casteDonut')?.getContext('2d');
  if (ctx) {
    if (gCasteChart) { gCasteChart.destroy(); gCasteChart = null; }
    gCasteChart = new Chart(ctx, {
      type: 'doughnut',
      data: { labels: donutLabels, datasets: [{ data: donutData, backgroundColor: donutColors, borderColor: '#fff', borderWidth: 2, hoverOffset: 4 }] },
      options: {
        cutout: '68%', responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: c => {
                const share = totalRows > 0 ? ((c.parsed / totalRows) * 100).toFixed(1) : 0;
                return ` ${c.label}: ${fmtNum(c.parsed)} (${share}%)`;
              }
            }
          }
        }
      }
    });
  }
}

async function loadDashboardStats() {
  try {
    const stats = await apiFetch('/api/stats?hide_bp=1');

    const bs      = stats.by_status || {};
    const total   = stats.total || 0;
    const completed = (bs.db_pushed || 0) + (bs.completed || 0);
    const pct     = total > 0 ? Math.round((completed / total) * 100) : 0;

    // Sidebar progress sync
    const pctSidebar = document.getElementById('progress-pct-sidebar');
    const pbFill     = document.getElementById('progress-bar-fill');
    const progText   = document.getElementById('progress-text');
    if (pctSidebar) pctSidebar.textContent = pct + '%';
    if (pbFill)     pbFill.style.width     = pct + '%';
    if (progText)   progText.textContent   = `${completed} / ${total} completed`;

    // Form 20 analytics card — initial paint from SQLite
    renderForm20Panel(stats);

    // ── Load live Form 20 card stats (reads local JSON, instant) ─────────────
    try {
      const liveStats = await apiFetch('/api/form20_card_stats');
      populateForm20Card(liveStats);
    } catch (e) {
      console.warn('form20_card_stats unavailable:', e);
    }

    // Extended analytics panels (Retro, Caste) from RDS
    const isManualRefresh = document.activeElement?.id === 'dash-refresh-btn';
    loadDashboardAnalytics(isManualRefresh);

  } catch (e) { console.error('loadDashboardStats:', e); }
}

// ── Populate Form 20 card from live JSON stats ────────────────────────────────
function populateForm20Card(d) {
  if (!d) return;
  const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  const form20  = d.form20_entries  || 0;   // 175 unique (state, type, year) in Form 20
  const acpc    = d.acpc_entries    || 0;   // 560 unique (state, type, year) in AC-PC mapping
  const pct     = d.coverage_pct   || 0;
  const circ    = 163.4;
  const dash    = circ * (1 - pct / 100);

  // Ring chart + % text
  const ring    = document.getElementById('f20-ring');
  const ringPct = document.getElementById('f20-ring-pct');
  if (ring)    ring.style.strokeDashoffset = dash;
  if (ringPct) ringPct.textContent = pct + '%';

  setEl('f20-pct',       pct + '%');
  setEl('f20-pct-label', 'coverage');
  setEl('f20-pct-badge', pct + '% complete');
  setEl('f20-counts',    `${form20.toLocaleString()} / ${acpc.toLocaleString()} elections in Form 20`);

  // Hero ribbon — pipeline coverage
  setEl('hero-pipeline',     pct + '%');
  setEl('hero-pipeline-sub', `${form20.toLocaleString()} / ${acpc.toLocaleString()} elections`);

  // Update globals so updateForm20WithMapping (from RDS analytics) uses correct numerator/denominator
  _f20Total = form20;
  // Overwrite _f20ByType with ACTUAL Form 20 counts so the RDS override paints correctly too
  _f20ByType = {};
  Object.entries(d.by_type || {}).forEach(([type, td]) => {
    _f20ByType[type] = { completed: td.in_form20 || 0, total: td.in_form20 || 0 };
  });

  // ── By election type breakdown ─────────────────────────────────────────────
  const typeWrap = document.getElementById('f20-type-rows');
  if (typeWrap && d.by_type) {
    const TYPE_META = {
      'AE': { label: 'Assembly', bg: 'bg-gray-700'  },
      'GE': { label: 'General',  bg: 'bg-blue-500'  },
    };
    const entries = Object.entries(d.by_type)
      .filter(([t]) => !t.includes('-BP'))
      .sort((a, b) => b[1].in_mapping - a[1].in_mapping);

    typeWrap.innerHTML = entries.map(([type, td]) => {
      const done    = td.in_form20  || 0;
      const mapTot  = td.in_mapping || 0;
      const p       = mapTot > 0 ? Math.round((done / mapTot) * 100) : 0;
      const m       = TYPE_META[type] || { label: type, bg: 'bg-gray-400' };
      const pctColor = p === 100 ? 'text-emerald-600' : p >= 80 ? 'text-blue-600' : p >= 50 ? 'text-amber-600' : 'text-rose-500';
      return `
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 w-[90px] shrink-0">
            <span class="w-2 h-2 rounded-full ${m.bg} shrink-0"></span>
            <span class="text-[10.5px] font-semibold text-gray-700">${type}</span>
            <span class="text-[9.5px] text-gray-400">${m.label}</span>
          </div>
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${m.bg} bar-fill" style="width:${p}%"></div>
          </div>
          <div class="flex items-center gap-1 shrink-0 w-[72px] justify-end">
            <span class="text-[11px] font-bold tabular-nums ${pctColor}">${p}%</span>
            <span class="text-[9.5px] text-gray-400 tabular-nums">${done}/${mapTot}</span>
          </div>
        </div>`;
    }).join('');
  }

  // ── Top states from Form 20 ───────────────────────────────────────────────
  const stateWrap = document.getElementById('f20-state-rows');
  if (stateWrap && d.top_states && d.top_states.length > 0) {
    // (STATE_AC_COUNTS is defined at module level)
    const max = d.top_states[0]?.count || 1;
    stateWrap.className = 'grid grid-cols-4 gap-1.5';
    stateWrap.innerHTML = d.top_states.map(s => {
      const intensity = Math.round((s.count / max) * 9) + 1;
      const bg = intensity >= 8 ? 'bg-gray-100 border-gray-300' :
                 intensity >= 5 ? 'bg-gray-50 border-gray-200' : 'bg-gray-50 border-gray-100';
      const tc = intensity >= 8 ? 'text-gray-800' : 'text-gray-600';
      const acCount = STATE_AC_COUNTS[s.state] ? `(${(s.count * STATE_AC_COUNTS[s.state]).toLocaleString()})` : '';
      return `
        <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5">
          <span class="text-[10.5px] font-bold ${tc}">${s.state}</span>
          <span class="text-[12px] font-black text-gray-900 tabular-nums leading-none">
            ${s.count} <span class="text-[10px] font-semibold text-gray-500 tracking-tight ml-0.5">${acCount}</span>
          </span>
        </div>`;
    }).join('');
  }
}




// ── Glance Report ─────────────────────────────────────────────────────────────
async function loadGlancePanel() {
  const monthFilter = (document.getElementById('glance-month-filter') || {}).value || '';
  const stateFilter = (document.getElementById('glance-state-filter') || {}).value || '';
  const typeFilter  = (document.getElementById('glance-type-filter')  || {}).value || '';
  try {
    const params = new URLSearchParams();
    if (monthFilter) params.append('month',   monthFilter);
    if (stateFilter) params.append('state',   stateFilter);
    if (typeFilter)  params.append('el_type', typeFilter);
    params.append('hide_bp', '1');

    const glance = await apiFetch('/api/glance_report?' + params.toString());

    // Populate month filter once
    const moSel = document.getElementById('glance-month-filter');
    if (moSel && glance.available_months && moSel.options.length <= 1) {
      glance.available_months.forEach(m => {
        const [yr, mo] = m.split('-');
        moSel.appendChild(new Option(
          new Date(yr, parseInt(mo) - 1).toLocaleString('default', { month: 'long', year: 'numeric' }), m
        ));
      });
    }

    // Populate state/type filters from main selects once
    const stSel = document.getElementById('glance-state-filter');
    if (stSel && stSel.options.length <= 1) {
      const mainState = document.getElementById('filter-state');
      if (mainState) Array.from(mainState.options).forEach(o => { if (o.value) stSel.add(new Option(o.text, o.value)); });
    }
    const tySel = document.getElementById('glance-type-filter');
    if (tySel && tySel.options.length <= 1 && filterMetadata) {
      const allTypes = new Set();
      Object.values(filterMetadata).forEach(types => Object.keys(types).forEach(t => allTypes.add(t)));
      Array.from(allTypes).sort().forEach(t => tySel.add(new Option(t, t)));
    }

    const accordion = document.getElementById('glance-panel-accordion');
    const countSpan = document.getElementById('glance-panel-count');
    const allWeeks  = glance.all_weeks || [];

    if (countSpan) countSpan.textContent = allWeeks.reduce((acc, w) => acc + w.count, 0) + ' records';

    renderGlanceAnalytics(glance, allWeeks);

    if (!accordion) return;

    if (allWeeks.length === 0) {
      accordion.innerHTML = `
        <div class="p-12 text-center flex flex-col items-center gap-3 text-gray-400">
          <span class="material-symbols-outlined" style="font-size:32px;">inbox</span>
          <p class="text-[12.5px] font-medium">No DB pushed records found for the selected filters.</p>
        </div>`;
      return;
    }

    // ── Build state → { years: Set, byWeek: {weekLabel: count} } map ──────────
    // weekLabels from allWeeks in ascending order (oldest → newest, max 4)
    const weekLabels = allWeeks.map(w => w.week).reverse(); // oldest first

    const stateMap = {};
    allWeeks.forEach(w => {
      w.records.forEach(r => {
        const parts = String(r.key).split('-');
        const st = parts[0] || '?';
        const yr = parts.length >= 2 ? parts[parts.length - 1] : '';
        const ty = parts.length >= 3 ? parts.slice(1, -1).join('-') : '';
        if (!stateMap[st]) stateMap[st] = { elections: [], byWeek: {} };
        stateMap[st].elections.push({ type: ty, year: yr, key: r.key, date: r.date });
        stateMap[st].byWeek[w.week] = (stateMap[st].byWeek[w.week] || 0) + 1;
      });
    });

    const stateNames = {
      AP:'Andhra Pradesh', AR:'Arunachal Pradesh', AS:'Assam', BR:'Bihar', CG:'Chhattisgarh',
      GA:'Goa', GJ:'Gujarat', HR:'Haryana', HP:'Himachal Pradesh', JH:'Jharkhand',
      KA:'Karnataka', KL:'Kerala', MP:'Madhya Pradesh', MH:'Maharashtra', MN:'Manipur',
      ML:'Meghalaya', MZ:'Mizoram', NL:'Nagaland', OR:'Odisha', PB:'Punjab',
      RJ:'Rajasthan', SK:'Sikkim', TN:'Tamil Nadu', TR:'Tripura', UP:'Uttar Pradesh',
      UK:'Uttarakhand', WB:'West Bengal', TS:'Telangana', DL:'Delhi', JK:'Jammu & Kashmir',
      LA:'Ladakh', AN:'Andaman & Nicobar', CH:'Chandigarh', PY:'Puducherry', LD:'Lakshadweep',
      CT:'Chhattisgarh',
    };

    const sortedStates = Object.keys(stateMap).sort();
    const maxPerWeek = Math.max(...sortedStates.map(s =>
      Math.max(...weekLabels.map(w => stateMap[s].byWeek[w] || 0))
    ), 1);

    // ── Table header ──────────────────────────────────────────────────────────
    const weekShort = wl => {
      const start = wl.slice(5, 10); // MM-DD
      return start;
    };

    accordion.innerHTML = `
      <!-- Table header -->
      <div class="grid items-center bg-gray-50 border-b border-gray-200 px-5 py-2.5"
           style="grid-template-columns: 56px 1fr 220px auto;">
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">State</p>
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Completed Elections</p>
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider text-center">4-Week Trend</p>
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider text-right">Total</p>
      </div>
      <!-- Rows -->
      ${sortedStates.map(st => {
        const d = stateMap[st];
        // Group elections: deduplicate by type+year, sort by year desc
        const seen = new Set();
        const elections = d.elections.filter(e => {
          const k = e.type + '-' + e.year;
          if (seen.has(k)) return false;
          seen.add(k); return true;
        }).sort((a, b) => (b.year || '').localeCompare(a.year || ''));

        // Year tags grouped by type
        const byType = {};
        elections.forEach(e => {
          if (!byType[e.type]) byType[e.type] = [];
          byType[e.type].push(e.year);
        });

        const tags = Object.entries(byType).map(([ty, yrs]) => {
          const typeColor = {
            AE: 'bg-indigo-50 text-indigo-700 border-indigo-100',
            GE: 'bg-blue-50 text-blue-700 border-blue-100',
            'AE-BP': 'bg-violet-50 text-violet-700 border-violet-100',
            'GE-BP': 'bg-sky-50 text-sky-700 border-sky-100',
          }[ty] || 'bg-gray-50 text-gray-600 border-gray-200';
          return `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-0.5 rounded-md border ${typeColor}">
            <span class="font-bold">${ty}</span> <span class="text-[10px] font-normal">${yrs.join(', ')}</span>
          </span>`;
        }).join('');

        // Mini sparkbar (4 weeks, oldest left → newest right)
        const bars = weekLabels.map(wl => {
          const cnt = d.byWeek[wl] || 0;
          const h = cnt > 0 ? Math.max(20, Math.round((cnt / maxPerWeek) * 100)) : 4;
          const col = cnt > 0 ? '#6366f1' : '#e5e7eb';
          return `<div class="flex flex-col items-center gap-1" title="${weekShort(wl)}: ${cnt}">
            <span class="text-[8px] text-gray-400 tabular-nums">${cnt > 0 ? cnt : ''}</span>
            <div class="w-5 rounded-sm" style="height:${h}%;background:${col};min-height:3px;max-height:32px;"></div>
            <span class="text-[8px] text-gray-300">${weekShort(wl)}</span>
          </div>`;
        }).join('');

        const total = d.elections.length;
        const fullName = stateNames[st] || st;

        return `
        <div class="grid items-center px-5 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors"
             style="grid-template-columns: 56px 1fr 220px auto;">
          <!-- State -->
          <div>
            <span class="text-[12px] font-bold text-gray-900">${st}</span>
            <p class="text-[9.5px] text-gray-400 leading-none mt-0.5">${fullName}</p>
          </div>
          <!-- Election tags -->
          <div class="flex flex-wrap gap-1.5 pr-4">${tags}</div>
          <!-- Sparkbars -->
          <div class="flex items-end justify-center gap-1.5 h-[48px] px-2">${bars}</div>
          <!-- Total -->
          <div class="text-right">
            <span class="text-[14px] font-bold text-gray-700 tabular-nums">${total}</span>
            <p class="text-[9.5px] text-gray-400">done</p>
          </div>
        </div>`;
      }).join('')}
    `;

  } catch (e) { console.error('loadGlancePanel:', e); }
}

function renderGlanceAnalytics(glance, allWeeks) {
  // Flatten all pushed records
  const allRecs = [];
  allWeeks.forEach(w => w.records.forEach(r => allRecs.push(r)));
  const total = allRecs.length;

  // Aggregate by state / type from the record key (STATE-TYPE-YEAR)
  const stateCounts = {}, typeCounts = {};
  allRecs.forEach(r => {
    const parts = String(r.key).split('-');
    const st = parts[0] || '?';
    const ty = parts.length >= 3 ? parts.slice(1, -1).join('-') : (parts[1] || '?');
    stateCounts[st] = (stateCounts[st] || 0) + 1;
    typeCounts[ty]  = (typeCounts[ty]  || 0) + 1;
  });

  // Weekly series — last 4 weeks for Glance analytics, all-time for context
  const weekly      = glance.weekly_counts     || {};   // last 4 weeks
  const weekKeys    = Object.keys(weekly).sort();
  const activeWeeks = Object.keys(glance.all_weekly_counts || weekly).length; // total active weeks for avg

  // This week vs last week
  const curWeek = glance.current_week || '';
  const thisWeek = weekly[curWeek] || 0;
  let lastWeek = 0;
  if (curWeek) {
    const start = curWeek.slice(0, 10);
    const d = new Date(start + 'T00:00:00');
    d.setDate(d.getDate() - 7);
    const lwStart = d.toISOString().slice(0, 10);
    const lwLabel = Object.keys(weekly).find(k => k.startsWith(lwStart));
    if (lwLabel) lastWeek = weekly[lwLabel];
  }

  const setT = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  // ── Summary stat cards ──────────────────────────────────────────────────
  setT('glance-stat-total',     total.toLocaleString());
  setT('glance-stat-total-sub', total === 1 ? 'record in database' : 'records in database');
  setT('glance-stat-thisweek',  thisWeek);
  setT('glance-stat-avg',       activeWeeks ? (total / activeWeeks).toFixed(1) : '0');
  setT('glance-stat-weeks',     `over ${activeWeeks} active week${activeWeeks === 1 ? '' : 's'}`);
  setT('glance-stat-states',    Object.keys(stateCounts).length);

  const topState = Object.entries(stateCounts).sort((a, b) => b[1] - a[1])[0];
  setT('glance-stat-topstate',  topState ? `top: ${topState[0]} (${topState[1]})` : 'top: —');

  // Trend chip (this vs last week)
  const trendEl = document.getElementById('glance-stat-trend');
  if (trendEl) {
    const diff = thisWeek - lastWeek;
    let icon, color, text;
    if (diff > 0)      { icon = 'arrow_upward';   color = 'text-emerald-600'; text = `+${diff} vs last week`; }
    else if (diff < 0) { icon = 'arrow_downward'; color = 'text-red-500';     text = `${diff} vs last week`; }
    else               { icon = 'remove';          color = 'text-gray-400';    text = `same as last week`; }
    trendEl.innerHTML = `<span class="material-symbols-outlined ${color}" style="font-size:13px;">${icon}</span><span class="${color} font-medium">${text}</span>`;
  }

  // ── Weekly trend chart (area) ───────────────────────────────────────────
  const wCtx = document.getElementById('glanceWeeklyChart')?.getContext('2d');
  if (wCtx) {
    if (gWeekChart) { gWeekChart.destroy(); gWeekChart = null; }
    const labels = weekKeys.map(k => {
      const s = k.slice(5, 10); const e = k.slice(19, 24);
      return e ? `${s}–${e}` : s;
    });
    const grad = wCtx.createLinearGradient(0, 0, 0, 200);
    grad.addColorStop(0, 'rgba(99,102,241,0.25)');
    grad.addColorStop(1, 'rgba(99,102,241,0.01)');
    gWeekChart = new Chart(wCtx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'DB Pushed',
          data: weekKeys.map(k => weekly[k]),
          borderColor: '#6366f1',
          backgroundColor: grad,
          borderWidth: 2,
          pointBackgroundColor: '#6366f1',
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.35,
          fill: true,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#9ca3af' }, grid: { color: '#f3f4f6' } },
          x: { ticks: { font: { size: 10, family: 'Inter' }, color: '#9ca3af', maxRotation: 0, autoSkip: true }, grid: { display: false } },
        },
      },
    });
  }

  // ── State performance (horizontal bar, top 8) ───────────────────────────
  const sCtx = document.getElementById('glanceStateChart')?.getContext('2d');
  if (sCtx) {
    if (gStateChart) { gStateChart.destroy(); gStateChart = null; }
    const sorted = Object.entries(stateCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
    gStateChart = new Chart(sCtx, {
      type: 'bar',
      data: {
        labels: sorted.map(s => s[0]),
        datasets: [{ data: sorted.map(s => s[1]), backgroundColor: '#34d399', borderRadius: 4, borderWidth: 0 }],
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#9ca3af' }, grid: { color: '#f3f4f6' } },
          y: { ticks: { font: { size: 11, family: 'Inter' }, color: '#374151' }, grid: { display: false } },
        },
      },
    });
  }

  // ── Election type distribution (HTML bars) ──────────────────────────────
  const typeWrap = document.getElementById('glance-type-bars');
  if (typeWrap) {
    const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
    const palette = ['#6366f1', '#7c3aed', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'];
    if (!sortedTypes.length) {
      typeWrap.innerHTML = '<p class="text-[12px] text-gray-400 text-center py-3">No data</p>';
    } else {
      typeWrap.innerHTML = sortedTypes.map(([ty, cnt], i) => {
        const pct  = total ? Math.round((cnt / total) * 100) : 0;
        const name = EL_TYPE_NAMES[ty] || ty;
        const col  = palette[i % palette.length];
        return `
          <div class="flex items-center gap-3">
            <div class="w-28 shrink-0 flex items-center gap-2">
              <span class="w-2 h-2 rounded-full shrink-0" style="background:${col}"></span>
              <span class="text-[12px] font-semibold text-gray-700">${ty}</span>
              <span class="text-[11px] text-gray-400">${name}</span>
            </div>
            <div class="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div class="h-full rounded-full bar-fill" style="width:${pct}%;background:${col}"></div>
            </div>
            <div class="w-16 shrink-0 text-right">
              <span class="text-[12px] font-bold text-gray-800 tabular-nums">${cnt}</span>
              <span class="text-[11px] text-gray-400 ml-1">${pct}%</span>
            </div>
          </div>`;
      }).join('');
    }
  }

  // ── Election years: last week vs this week ──────────────────────────────
  renderYearComparison(allWeeks);
}

// Compares the set of election years pushed last week vs this week.
// allWeeks[0] is the current calendar week (live), allWeeks[1] is last week.
function renderYearComparison(allWeeks) {
  const wrap = document.getElementById('glance-year-compare');
  if (!wrap) return;

  const thisWeek = (allWeeks && allWeeks[0]) || { week: '', records: [] };
  const lastWeek = (allWeeks && allWeeks[1]) || { week: '', records: [] };

  const fmtRange = wl => {
    if (!wl || wl.length < 24) return '—';
    const s = wl.slice(0, 10), e = wl.slice(14, 24);
    const fmt = iso => {
      const [y, m, d] = iso.split('-');
      return `${parseInt(d)} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(m)-1]}`;
    };
    return `${fmt(s)} – ${fmt(e)} ${e.slice(0, 4)}`;
  };
  const rangeEl = document.getElementById('glance-year-compare-range');
  if (rangeEl) {
    rangeEl.textContent = `This week: ${fmtRange(thisWeek.week)}  |  Last week: ${fmtRange(lastWeek.week)}`;
  }

  const yearSet = recs => {
    const s = new Set();
    (recs || []).forEach(r => {
      const parts = String(r.key).split('-');
      const yr = parts[parts.length - 1];
      if (yr) s.add(yr);
    });
    return s;
  };

  const thisYears = yearSet(thisWeek.records);
  const lastYears = yearSet(lastWeek.records);

  const onlyLast = [...lastYears].filter(y => !thisYears.has(y)).sort();
  const both     = [...thisYears].filter(y => lastYears.has(y)).sort();
  const onlyThis = [...thisYears].filter(y => !lastYears.has(y)).sort();

  const renderChips = (years, emptyText, color) => {
    if (!years.length) return `<span class="text-[11px] text-gray-300">${emptyText}</span>`;
    return years.map(y => `<span class="inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded border ${color}">${y}</span>`).join(' ');
  };

  const col = (title, icon, iconColor, years, emptyText, chipColor) => `
    <div class="border border-gray-100 rounded-lg p-3">
      <div class="flex items-center gap-1.5 mb-2">
        <span class="material-symbols-outlined ${iconColor}" style="font-size:14px;">${icon}</span>
        <p class="text-[11px] font-semibold text-gray-700">${title}</p>
        <span class="text-[10px] text-gray-400 ml-auto tabular-nums">${years.length}</span>
      </div>
      <div class="flex flex-wrap gap-1">${renderChips(years, emptyText, chipColor)}</div>
    </div>`;

  wrap.innerHTML = [
    col('Only Last Week',  'history',         'text-amber-500',   onlyLast, 'None', 'bg-amber-50 text-amber-700 border-amber-100'),
    col('Both Weeks',      'sync_alt',        'text-indigo-500',  both,     'None', 'bg-indigo-50 text-indigo-700 border-indigo-100'),
    col('Only This Week',  'fiber_new',       'text-emerald-500', onlyThis, 'None', 'bg-emerald-50 text-emerald-700 border-emerald-100'),
  ].join('');
}

// togglePanelWeek removed — accordion replaced with state-grouped grid
