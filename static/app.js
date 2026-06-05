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
let dashShowBp  = false;
let dashSirOnly = false;

let monthlyChart = null;

// Glance Report chart instances
let gWeekChart  = null;
let gStateChart = null;

const EL_TYPE_NAMES = { AE: 'Assembly', GE: 'General', BE: 'Bypoll', PE: 'Parliament', LE: 'Local', AC: 'Assembly' };
const STATE_NAMES_MAP = {};  // populated lazily from filter dropdown

const STATUS_CONFIG = {
  'missing':    { bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-100',     dot: 'bg-red-400',     label: 'Missing'   },
  'pending':    { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-100',   dot: 'bg-amber-400',   label: 'Pending'   },
  'downloaded': { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-100',    dot: 'bg-blue-400',    label: 'Downloaded'},
  'extracted':  { bg: 'bg-violet-50',  text: 'text-violet-700',  border: 'border-violet-100',  dot: 'bg-violet-400',  label: 'Extracted' },
  'completed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100', dot: 'bg-emerald-400', label: 'Completed' },
  'db_pushed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100', dot: 'bg-emerald-400', label: 'DB Pushed' },
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

    const pbFill = document.getElementById('progress-bar-fill');
    if (pbFill) pbFill.style.width = pct + '%';
    set('progress-text', `${completed} / ${total} completed`);

    const pctSidebar = document.getElementById('progress-pct-sidebar');
    if (pctSidebar) pctSidebar.textContent = pct + '%';
  } catch (e) { console.error('loadStats:', e); }
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
  document.getElementById('record-count-badge').textContent = `${allRecords.length} records`;

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
    downloaded: { id: 'kpi-downloaded', cls: 'kpi-active-blue'   },
    extracted:  { id: 'kpi-extracted',  cls: 'kpi-active-violet' },
    missing:    { id: 'kpi-missing',    cls: 'kpi-active-red'    },
  };
  ['downloaded', 'extracted', 'missing'].forEach(s => {
    const cfg = kpiMap[s];
    const btn = document.getElementById(cfg.id);
    if (!btn) return;
    if (s === status) {
      btn.classList.add(cfg.cls);
    } else {
      btn.classList.remove('kpi-active-blue', 'kpi-active-violet', 'kpi-active-red');
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
  }

  navTabs.forEach(t => {
    const el = document.getElementById(t.id);
    if (el) el.addEventListener('click', () => switchTab(t.id));
  });

  const dashMonthFilter = document.getElementById('dash-month-filter');
  const dashRefreshBtn  = document.getElementById('dash-refresh-btn');
  if (dashMonthFilter) dashMonthFilter.addEventListener('change', loadDashboardStats);
  if (dashRefreshBtn)  dashRefreshBtn.addEventListener('click',   loadDashboardStats);

  // Dashboard SIR Only toggle
  const dashSirBtn = document.getElementById('dash-sir-btn');
  if (dashSirBtn) {
    dashSirBtn.addEventListener('click', () => {
      dashSirOnly = !dashSirOnly;
      setDashToggle(dashSirBtn, dashSirOnly, 'priority_high', 'SIR Only', 'amber');
      loadDashboardStats();
    });
  }

  // Dashboard Show BP Years toggle
  const dashBpBtn = document.getElementById('dash-bp-btn');
  if (dashBpBtn) {
    dashBpBtn.addEventListener('click', () => {
      dashShowBp = !dashShowBp;
      setDashToggle(dashBpBtn, dashShowBp,
        dashShowBp ? 'filter_alt_off' : 'filter_alt',
        dashShowBp ? 'Hide BP Years' : 'Show BP Years', 'indigo');
      loadDashboardStats();
    });
  }

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
        a.download = m ? m[1] : 'Glance_Report.pdf';
        a.click();
        URL.revokeObjectURL(url);
        showToast('Glance Report PDF downloaded');
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
async function loadDashboardStats() {
  const monthFilter = (document.getElementById('dash-month-filter') || {}).value || '';
  try {
    // Build shared dashboard filter params (BP hidden by default)
    const statsParams = new URLSearchParams();
    if (!dashShowBp)  statsParams.set('hide_bp', '1');
    if (dashSirOnly)  statsParams.set('sir_only', '1');

    const glanceParams = new URLSearchParams();
    if (monthFilter)  glanceParams.set('month', monthFilter);
    if (!dashShowBp)  glanceParams.set('hide_bp', '1');
    if (dashSirOnly)  glanceParams.set('sir_only', '1');

    const [stats, glance] = await Promise.all([
      apiFetch('/api/stats?' + statsParams.toString()),
      apiFetch('/api/glance_report?' + glanceParams.toString()),
    ]);

    // Populate month dropdown once
    const sel = document.getElementById('dash-month-filter');
    if (sel && glance.available_months && sel.options.length <= 1) {
      glance.available_months.forEach(m => {
        const [yr, mo] = m.split('-');
        sel.appendChild(new Option(
          new Date(yr, parseInt(mo) - 1).toLocaleString('default', { month: 'long', year: 'numeric' }), m
        ));
      });
    }

    const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    const bs     = stats.by_status || {};
    const total  = stats.total || 0;
    const dbPushed = (bs.db_pushed || 0) + (bs.completed || 0);
    const pct    = total > 0 ? Math.round((dbPushed / total) * 100) : 0;

    // KPI cards
    setEl('dash-total',      total);
    setEl('dash-db-pushed',  dbPushed);
    setEl('dash-downloaded', bs.downloaded || 0);
    setEl('dash-missing',    bs.missing    || 0);

    // Progress
    setEl('dash-progress-pct', pct + '%');
    setEl('dash-progress-sub', `${dbPushed.toLocaleString()} / ${total.toLocaleString()} records pushed to DB`);
    const progBar    = document.getElementById('dash-prog-bar');
    const progBarKpi = document.getElementById('dash-prog-bar-kpi');
    if (progBar)    progBar.style.width    = pct + '%';
    if (progBarKpi) progBarKpi.style.width = pct + '%';

    // Sidebar progress sync
    const pctSidebar = document.getElementById('progress-pct-sidebar');
    const pbFill     = document.getElementById('progress-bar-fill');
    const progText   = document.getElementById('progress-text');
    if (pctSidebar) pctSidebar.textContent = pct + '%';
    if (pbFill)     pbFill.style.width     = pct + '%';
    if (progText)   progText.textContent   = `${dbPushed} / ${total} completed`;

    // Pipeline stages
    setEl('pipe-missing',    bs.missing    || 0);
    setEl('pipe-downloaded', bs.downloaded || 0);
    setEl('pipe-extracted',  bs.extracted  || 0);
    setEl('pipe-db-pushed',  dbPushed);

    // ── Status breakdown — horizontal bar chart ──────────────────────────────
    const pieLabels = ['Downloaded', 'Extracted', 'DB Pushed', 'Missing', 'Pending'];
    const pieVals   = [
      bs.downloaded || 0,
      bs.extracted  || 0,
      dbPushed,
      bs.missing    || 0,
      bs.pending    || 0,
    ];
    const pieColors = ['#3b82f6', '#7c3aed', '#10b981', '#ef4444', '#f59e0b'];

    const pieCtx = document.getElementById('statusPieChart')?.getContext('2d');
    if (pieCtx) {
      if (pieChart) { pieChart.destroy(); pieChart = null; }
      pieChart = new Chart(pieCtx, {
        type: 'bar',
        data: {
          labels: pieLabels,
          datasets: [{
            data: pieVals,
            backgroundColor: pieColors,
            borderRadius: 4,
            borderWidth: 0,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              beginAtZero: true,
              ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#9ca3af' },
              grid:  { color: '#f3f4f6' },
            },
            y: {
              ticks: { font: { size: 11, family: 'Inter' }, color: '#374151' },
              grid:  { display: false },
            },
          },
        },
      });
    }

    // ── Monthly bar chart ────────────────────────────────────────────────────
    const allMonthCounts = glance.monthly_counts || {};
    const thisMonthKey   = new Date().toISOString().slice(0, 7);
    const sortedMonths   = Object.keys(allMonthCounts).sort();
    const monthLabels    = sortedMonths.map(m => {
      const [yr, mo] = m.split('-');
      return new Date(yr, parseInt(mo) - 1).toLocaleString('default', { month: 'short', year: '2-digit' });
    });

    if (monthlyChart) { monthlyChart.destroy(); monthlyChart = null; }
    const mCtx = document.getElementById('monthlyBarChart')?.getContext('2d');
    if (mCtx) {
      monthlyChart = new Chart(mCtx, {
        type: 'bar',
        data: {
          labels: monthLabels,
          datasets: [{
            label: 'DB Pushed',
            data:  sortedMonths.map(m => allMonthCounts[m]),
            backgroundColor: sortedMonths.map(m => m === thisMonthKey ? '#10b981' : '#c7d2fe'),
            borderColor:     sortedMonths.map(m => m === thisMonthKey ? '#059669' : '#6366f1'),
            borderWidth: 1,
            borderRadius: 5,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#9ca3af' },
              grid:  { color: '#f3f4f6' },
            },
            x: {
              ticks: { font: { size: 10, family: 'Inter' }, color: '#9ca3af' },
              grid:  { display: false },
            },
          },
        },
      });
    }

    // ── Weekly velocity chart ────────────────────────────────────────────────
    const allWeekCounts = glance.weekly_counts || {};
    let weekKeys, weekCounts, subtitle;
    if (monthFilter && Object.keys(glance.weekly_in_month || {}).length > 0) {
      const wim   = glance.weekly_in_month;
      weekKeys    = Object.keys(wim).sort();
      weekCounts  = weekKeys.map(k => wim[k]);
      subtitle    = 'Weeks in ' + new Date(monthFilter + '-01').toLocaleString('default', { month: 'long', year: 'numeric' });
    } else {
      weekKeys    = Object.keys(allWeekCounts).sort();
      weekCounts  = weekKeys.map(k => allWeekCounts[k]);
      subtitle    = monthFilter ? 'No DB pushes recorded for this month' : 'All weeks since tracking began';
    }
    setEl('weekly-chart-subtitle', subtitle);

    if (barChart) {
      barChart.data.labels              = weekKeys.map(k => k.slice(5, 10));
      barChart.data.datasets[0].data   = weekCounts;
      barChart.update();
    } else {
      const wCtx = document.getElementById('weeklyBarChart')?.getContext('2d');
      if (wCtx) {
        barChart = new Chart(wCtx, {
          type: 'bar',
          data: {
            labels: weekKeys.map(k => k.slice(5, 10)),
            datasets: [{
              label: 'DB Pushed',
              data:  weekCounts,
              backgroundColor: '#c7d2fe',
              borderColor:     '#6366f1',
              borderWidth: 1,
              borderRadius: 4,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              y: {
                beginAtZero: true,
                ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#9ca3af' },
                grid:  { color: '#f3f4f6' },
              },
              x: {
                ticks: { font: { size: 10, family: 'Inter' }, color: '#9ca3af' },
                grid:  { display: false },
              },
            },
          },
        });
      }
    }

  } catch (e) { console.error('loadDashboardStats:', e); }
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
    if (tySel && tySel.options.length <= 1) {
      const mainType = document.getElementById('filter-type');
      if (mainType) Array.from(mainType.options).forEach(o => { if (o.value) tySel.add(new Option(o.text, o.value)); });
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

    accordion.innerHTML = allWeeks.map((w, i) => {
      const isCurrent = w.is_current;

      const badge = isCurrent
        ? `<span class="ml-2 text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">Current</span>`
        : '';

      const rows = w.records.map(r => `
        <tr class="hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0">
          <td class="py-2 px-5 text-[12px] font-mono text-gray-700 font-medium">${r.key}</td>
          <td class="py-2 px-5 text-[11.5px] text-gray-400">${r.date}</td>
          <td class="py-2 px-5">
            <span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100 px-2.5 py-0.5 rounded-full">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"></span>
              DB Pushed
            </span>
          </td>
        </tr>`).join('');

      return `
        <div id="panel-week-${i}">
          <button onclick="togglePanelWeek(${i})"
            class="w-full flex items-center justify-between px-5 py-3.5 hover:bg-gray-50 transition-colors text-left group">
            <div class="flex items-center gap-3">
              <span class="w-2 h-2 rounded-full ${isCurrent ? 'bg-emerald-400' : 'bg-gray-300'} shrink-0"></span>
              <span class="text-[13px] font-semibold text-gray-900">${w.week}</span>
              ${badge}
            </div>
            <div class="flex items-center gap-3">
              <span class="text-[11px] font-semibold px-2.5 py-1 rounded-full border
                ${isCurrent ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-gray-50 text-gray-600 border-gray-200'}">
                ${w.count} records
              </span>
              <span class="material-symbols-outlined text-gray-300 group-hover:text-gray-500 panel-week-chevron-${i} transition-transform"
                style="font-size:16px;">${i === 0 ? 'expand_less' : 'expand_more'}</span>
            </div>
          </button>
          <div id="panel-week-body-${i}" class="${i === 0 ? '' : 'hidden'} border-t border-gray-100">
            <table class="w-full">
              <thead>
                <tr class="bg-gray-50 border-b border-gray-100">
                  <th class="px-5 py-2 text-left text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Election Key</th>
                  <th class="px-5 py-2 text-left text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Date Pushed</th>
                  <th class="px-5 py-2 text-left text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </div>`;
    }).join('');

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
    const ty = parts[1] || '?';
    stateCounts[st] = (stateCounts[st] || 0) + 1;
    typeCounts[ty]  = (typeCounts[ty]  || 0) + 1;
  });

  // Weekly series (ascending by start date)
  const weekly   = glance.weekly_counts || {};
  const weekKeys = Object.keys(weekly).sort();
  const activeWeeks = weekKeys.length;

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
}

function togglePanelWeek(i) {
  const body    = document.getElementById('panel-week-body-' + i);
  const chevron = document.querySelector('.panel-week-chevron-' + i);
  if (!body) return;
  const hidden = body.classList.toggle('hidden');
  if (chevron) chevron.textContent = hidden ? 'expand_more' : 'expand_less';
}
