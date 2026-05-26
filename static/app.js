/* ═══════════════════════════════════════════════════════════════════════════
   app.js — Form 20 Backlog Dashboard (Tailwind Dense View)
   ═══════════════════════════════════════════════════════════════════════════ */
'use strict';

let allRecords   = [];
let selectedIds  = new Set();
let sortCol      = 'state';
let sortDir      = 'asc';
let editingId    = null;
let toastTimer   = null;
let searchTimer  = null;
let retroMetadata = null;
let filterMetadata = null;
let confirmResolve = null;
let currentView = 'states'; 
let currentDetailState = null;

const filters = {
  state: '', el_type: '', year: '', status: '', sir_only: false, search: '', wip: false,
};

const STATUS_CONFIG = {
  'missing':    { bg: 'bg-slate-50',   text: 'text-slate-700',   border: 'border-slate-200',  dot: 'bg-slate-500',   label: 'Missing' },
  'pending':    { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-100',  dot: 'bg-amber-500',   label: 'Pending' },
  'downloaded': { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-100',   dot: 'bg-blue-500',    label: 'Downloaded' },
  'extracted':  { bg: 'bg-purple-50',  text: 'text-purple-700',  border: 'border-purple-100', dot: 'bg-purple-500',  label: 'Extracted' },
  'completed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100',dot: 'bg-emerald-500', label: 'Completed' },
  'db_pushed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100',dot: 'bg-emerald-500', label: 'DB Pushed' },
};

document.addEventListener('DOMContentLoaded', () => {
  loadFilters();
  loadStats();
  loadRecords();
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

// Previous loadRetroFilters removed

async function loadStats() {
  try {
    const s = await apiFetch('/api/stats');
    const bs = s.by_status || {};
    const total = s.total || 0;

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '0'; };
    set('sl-all-count', total);
    set('sl-dl-count',  bs.downloaded || '0');
    set('sl-ex-count',  bs.extracted  || '0');
    set('sl-co-count',  bs.db_pushed  || '0');
    set('sl-pe-count',  bs.pending    || '0');
    set('sl-mi-count',  bs.missing    || '0');
    set('sl-wip-count', s.wip_count   || '0');

    // Progress bar
    const completed = bs.db_pushed || 0;
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    document.getElementById('progress-bar-fill').style.width = `${pct}%`;
    document.getElementById('progress-text').textContent = `${completed} / ${total} Completed`;
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

  try {
    allRecords = await apiFetch('/api/records?' + params);
    renderTable();
  } catch (e) {
    document.getElementById('table-body').innerHTML =
      `<tr><td colspan="7" class="px-6 py-8 text-center text-slate-500 text-[13px]">Failed to load — ${e.message}</td></tr>`;
  }
}

function renderTable() {
  const tbody = document.getElementById('table-body');
  const thead = document.getElementById('table-head');
  document.getElementById('record-count-badge').textContent = `${allRecords.length} Total Records`;
  
  if (!allRecords.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-8 text-center text-slate-500 text-[13px]">No records match the current filters.</td></tr>`;
    document.getElementById('pagination-text').textContent = `Showing 0 records`;
    updateSelectAll(); return;
  }

  if (currentView === 'states') {
      // Group by state
      const grouped = {};
      allRecords.forEach(rec => {
        const s = rec.state_name || rec.state;
        if (!grouped[s]) grouped[s] = [];
        grouped[s].push(rec);
      });

      const stateKeys = Object.keys(grouped).sort((a, b) => a.localeCompare(b));
      document.getElementById('pagination-text').textContent = `Showing ${allRecords.length} records across ${stateKeys.length} states`;

      // Render State View Headers
      thead.innerHTML = `
        <tr>
            <th class="px-6 py-3 w-10"></th>
            <th class="px-2 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">State Name</th>
            <th class="px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Total Elections</th>
            <th class="px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Status Breakdown</th>
            <th class="px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider text-right">Actions</th>
        </tr>
      `;

      let html = '';
      stateKeys.forEach(s => {
        const records = grouped[s];
        
        // Count statuses
        let missing = 0, extracted = 0, downloaded = 0;
        records.forEach(r => {
            if (r.overall_status === 'missing') missing++;
            else if (r.overall_status === 'extracted') extracted++;
            else if (r.overall_status === 'downloaded') downloaded++;
        });

        html += `
        <tr class="bg-white hover:bg-slate-50 cursor-pointer border-b border-slate-100 transition-colors" onclick="openStateDetail('${s.replace(/'/g, "\\'")}')">
          <td class="px-6 py-3">
            <div class="w-8 h-8 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center">
                <span class="material-symbols-outlined text-[16px] text-indigo-500">map</span>
            </div>
          </td>
          <td class="px-2 py-3">
            <span class="font-bold text-slate-800 text-[13px] block">${x(s)}</span>
            <span class="text-[11px] text-slate-400">Click to view records</span>
          </td>
          <td class="px-6 py-3">
            <span class="text-[13px] font-semibold text-slate-700">${records.length}</span>
          </td>
          <td class="px-6 py-3">
            <div class="flex items-center gap-2 text-[11px] font-medium">
                ${extracted > 0 ? `<span class="text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-100">${extracted} Ext</span>` : ''}
                ${downloaded > 0 ? `<span class="text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-100">${downloaded} Dwn</span>` : ''}
                ${missing > 0 ? `<span class="text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">${missing} Mis</span>` : ''}
            </div>
          </td>
          <td class="px-6 py-3 text-right">
             <span class="material-symbols-outlined text-slate-300">chevron_right</span>
          </td>
        </tr>
        `;
      });
      tbody.innerHTML = html;
      updateSelectAll();
  } else {
      // Detail View
      const records = allRecords.filter(r => (r.state_name || r.state) === currentDetailState).sort((a, b) => {
        let va = a[sortCol] ?? '', vb = b[sortCol] ?? '';
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return sortDir === 'asc' ? -1 : 1;
        if (va > vb) return sortDir === 'asc' ?  1 : -1;
        return 0;
      });

      document.getElementById('pagination-text').textContent = `Showing 1-${records.length} of ${records.length} records for ${currentDetailState}`;

      // Render Detail View Headers
      thead.innerHTML = `
        <tr>
            <th class="px-2 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider sortable cursor-pointer hover:bg-slate-50" data-col="state">Record ID</th>
            <th class="px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Status</th>
            <th class="px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Location Details</th>
            <th class="px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider text-right">Actions</th>
        </tr>
      `;

      tbody.innerHTML = records.map(rec => {
        const sel = selectedIds.has(rec.id);
        const cfg = STATUS_CONFIG[rec.overall_status] || STATUS_CONFIG['missing'];
        const rowClass = sel ? 'selected-row' : 'table-row-hover';

        return `
        <tr class="${rowClass} transition-colors border-b border-slate-50" data-id="${rec.id}">
            <td class="px-2 py-2 cursor-pointer" onclick="openModal(${rec.id})">
            <div class="flex flex-col">
                <span class="text-[12.5px] font-bold text-slate-900 leading-tight">${x(rec.key)}</span>
                <span class="text-[11px] ${rec.is_sir_state ? 'text-amber-600 font-semibold' : 'text-slate-500'}">${rec.is_sir_state ? 'SIR Priority' : 'Standard Record'}</span>
            </div>
            </td>
            <td class="px-6 py-2">
            <span class="px-2 py-0.5 rounded-full text-[11px] font-semibold ${cfg.bg} ${cfg.text} border ${cfg.border} flex items-center w-fit gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full ${cfg.dot}"></span>
                ${cfg.label}
            </span>
            </td>
            <td class="px-6 py-2">
            <div class="flex flex-col">
                <span class="text-[12.5px] text-slate-700 font-medium">${x(rec.state_name || rec.state)}</span>
                <span class="text-[11px] text-slate-400">${x(rec.el_type)} ${rec.el_year}</span>
            </div>
            </td>
            <td class="px-6 py-2 text-right">
            <div class="flex items-center justify-end gap-2">
                <button class="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-bold border transition-colors btn-wip ${rec.wip ? 'bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100' : 'bg-white text-slate-400 border-slate-200 hover:bg-slate-50 hover:text-slate-600'}" data-id="${rec.id}" title="Toggle LF In Progress">
                    <span class="material-symbols-outlined text-[14px]">${rec.wip ? 'hourglass_top' : 'hourglass_empty'}</span>
                    LF WIP
                </button>
                <button class="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-700 transition-colors btn-edit" data-id="${rec.id}">
                <span class="material-symbols-outlined" style="font-size: 16px;">edit</span>
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
          } catch(err) {
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

      // Re-bind sort headers for Detail view
      thead.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => {
          const c = th.dataset.col;
          if (sortCol === c) {
            sortDir = sortDir === 'asc' ? 'desc' : 'asc';
          } else {
            sortCol = c;
            sortDir = 'asc';
          }
          renderTable();
        });
      });

      // Bind select all for Detail view
      const selectAllBtn = document.getElementById('select-all');
      if (selectAllBtn) {
        selectAllBtn.addEventListener('change', e => {
            records.forEach(r => {
                e.target.checked ? selectedIds.add(r.id) : selectedIds.delete(r.id);
            });
            renderTable();
            updateSelBar();
        });
      }

      // updateSelectAll();
  }
}

window.goBackToStates = function() {
    currentView = 'states';
    currentDetailState = null;
    document.getElementById('detail-header').classList.add('hidden');
    renderTable();
}

window.openStateDetail = function(stateName) {
    currentView = 'detail';
    currentDetailState = stateName;
    document.getElementById('detail-header').classList.remove('hidden');
    document.getElementById('detail-state-name').textContent = stateName;
    
    // Auto-select records? No, we maintain existing selection.
    renderTable();
}

function x(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function updateSelectAll() {
  const cb   = document.getElementById('select-all');
  if (!cb) return;
  const ids  = allRecords.map(r => r.id);
  const selN = ids.filter(id => selectedIds.has(id)).length;
  cb.indeterminate = selN > 0 && selN < ids.length;
  cb.checked       = ids.length > 0 && selN === ids.length;
}

function updateSelBar() {}

function clearSelection() {
  selectedIds.clear();
  renderTable();
}

function openModal(id) {
  const rec = allRecords.find(r => r.id === id);
  if (!rec) return;
  editingId = id;
  document.getElementById('modal-title').textContent = `${rec.state} — ${rec.el_type} — ${rec.el_year}`;
  document.getElementById('modal-key').textContent = rec.key;
  document.getElementById('edit-status').value = rec.overall_status || 'missing';
  document.getElementById('edit-remark').value = rec.remark || '';
  
  const overlay = document.getElementById('overlay');
  const card = document.getElementById('modal-card');
  overlay.classList.remove('opacity-0', 'pointer-events-none');
  card.classList.remove('scale-95');
  card.classList.add('scale-100');
}

function closeModal() {
  const overlay = document.getElementById('overlay');
  const card = document.getElementById('modal-card');
  overlay.classList.add('opacity-0', 'pointer-events-none');
  card.classList.remove('scale-100');
  card.classList.add('scale-95');
  editingId = null;
}

async function saveModal() {
  if (!editingId) return;
  const newStatus = document.getElementById('edit-status').value;
  
  if (newStatus === 'db_pushed') {
      const confirmed = await showConfirmModal();
      if (!confirmed) {
          return;
      }
  }

  const body = {
    overall_status: newStatus,
    remark:         document.getElementById('edit-remark').value.trim()   || null,
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
  btn.disabled = true;
  btn.innerHTML = '<span class="material-symbols-outlined animate-spin" style="font-size: 16px;">sync</span> Syncing...';
  try {
    const data = await apiFetch('/api/reload', 'POST', {});
    if (data.success) { showToast('Database synced from Excel'); loadStats(); loadRecords(); }
    else showToast('Sync failed: ' + data.error, true);
  } catch (e) { showToast('Sync error: ' + e.message, true); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 16px;">sync</span> Sync';
  }
}

function handleSideNav(view) {
  document.querySelectorAll('.sidelink').forEach(el => {
    const isAct = el.dataset.view === view;
    if (el.dataset.view === 'wip') {
      if (isAct) {
        el.classList.add('bg-amber-50', 'dark:bg-slate-800', 'text-amber-700', 'border-amber-500');
        el.classList.remove('text-slate-500', 'dark:text-slate-400', 'border-transparent');
      } else {
        el.classList.remove('bg-amber-50', 'dark:bg-slate-800', 'text-amber-700', 'border-amber-500');
        el.classList.add('text-slate-500', 'dark:text-slate-400', 'border-transparent');
      }
    } else {
      if (isAct) {
        el.classList.add('bg-slate-100', 'dark:bg-slate-800', 'text-slate-900', 'dark:text-white', 'font-bold', 'border-slate-800', 'dark:border-slate-400');
        el.classList.remove('text-slate-500', 'dark:text-slate-400', 'border-transparent');
        if (el.querySelector('.material-symbols-outlined')) el.querySelector('.material-symbols-outlined').classList.add('text-slate-800', 'dark:text-white');
      } else {
        el.classList.remove('bg-slate-100', 'dark:bg-slate-800', 'text-slate-900', 'dark:text-white', 'font-bold', 'border-slate-800', 'dark:border-slate-400');
        el.classList.add('text-slate-500', 'dark:text-slate-400', 'border-transparent');
        if (el.querySelector('.material-symbols-outlined')) el.querySelector('.material-symbols-outlined').classList.remove('text-slate-800', 'dark:text-white');
      }
    }
  });

  const statusMap = { downloaded:'downloaded', extracted:'extracted', completed:'completed', pending:'pending', missing:'missing' };
  if (statusMap[view]) {
    filters.status   = statusMap[view];
    filters.wip      = false;
  } else if (view === 'wip') {
    filters.status   = '';
    filters.wip      = true;
  } else {
    filters.status   = '';
    filters.wip      = false;
  }
  loadStats(); loadRecords();
}

function showToast(msg, isErr = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  if (isErr) {
    el.classList.remove('bg-slate-900');
    el.classList.add('bg-red-600');
  } else {
    el.classList.remove('bg-red-600');
    el.classList.add('bg-slate-900');
  }
  el.classList.remove('opacity-0', 'pointer-events-none', 'translate-y-4');
  
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { 
    el.classList.add('opacity-0', 'pointer-events-none', 'translate-y-4');
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
            showToast('Failed to load retro metadata', true);
            return;
        }
    }
    
    const stateEl = document.getElementById('retro-state');
    const currState = stateEl.value;
    stateEl.innerHTML = '<option value="">All States</option>';
    Object.keys(retroMetadata).sort().forEach(s => {
        stateEl.appendChild(new Option(s, s));
    });
    if (currState && retroMetadata[currState]) {
        stateEl.value = currState;
    } else {
        document.getElementById('retro-type').innerHTML = '<option value="">All Types</option>';
        document.getElementById('retro-type').disabled = true;
        document.getElementById('retro-year').innerHTML = '<option value="">All Years</option>';
        document.getElementById('retro-year').disabled = true;
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
        Object.values(retroMetadata[s] || {}).forEach(types => {
            Object.values(types).forEach(c => count += c);
        });
    } else {
        Object.values(retroMetadata || {}).forEach(states => {
            Object.values(states).forEach(types => {
                Object.values(types).forEach(c => count += c);
            });
        });
    }
    
    const preview = document.getElementById('retro-count-preview');
    preview.textContent = count === 1 ? '1 record found' : `${count.toLocaleString()} records found`;
    
    const btn = document.getElementById('retro-download');
    if (s && t && y && count > 0) {
      btn.disabled = false;
      btn.removeAttribute('aria-disabled');
      btn.className = btn.className.replace('bg-slate-300', 'bg-emerald-600').replace('text-slate-500', 'text-white').replace('cursor-not-allowed', 'hover:bg-emerald-700');
    } else {
      btn.disabled = true;
      btn.setAttribute('aria-disabled', 'true');
      btn.className = btn.className.replace('bg-emerald-600', 'bg-slate-300').replace('text-white', 'text-slate-500').replace('hover:bg-emerald-700', 'cursor-not-allowed');
    }
}

function showConfirmModal() {
    return new Promise(resolve => {
        const overlay = document.getElementById('confirm-overlay');
        const card = document.getElementById('confirm-card');
        overlay.classList.remove('opacity-0', 'pointer-events-none');
        card.classList.remove('scale-95');
        card.classList.add('scale-100');
        confirmResolve = resolve;
    });
}

function closeConfirmModal(result) {
    const overlay = document.getElementById('confirm-overlay');
    const card = document.getElementById('confirm-card');
    overlay.classList.add('opacity-0', 'pointer-events-none');
    card.classList.remove('scale-100');
    card.classList.add('scale-95');
    if (confirmResolve) {
        confirmResolve(result);
        confirmResolve = null;
    }
}

function bindEvents() {
  document.getElementById('confirm-cancel').addEventListener('click', () => closeConfirmModal(false));
  document.getElementById('confirm-proceed').addEventListener('click', () => closeConfirmModal(true));

  document.getElementById('filter-state').addEventListener('change', e => {
    filters.state = e.target.value;
    filters.el_type = '';
    filters.year = '';
    
    const typeEl = document.getElementById('filter-type');
    const yearEl = document.getElementById('filter-year');
    typeEl.innerHTML = '<option value="">All Types</option>';
    yearEl.innerHTML = '<option value="">All Years</option>';
    
    if (filters.state && filterMetadata && filterMetadata[filters.state]) {
        typeEl.disabled = false;
        Object.keys(filterMetadata[filters.state]).sort().forEach(t => typeEl.appendChild(new Option(t, t)));
    } else {
        typeEl.disabled = true;
    }
    yearEl.disabled = true;
    
    loadStats(); loadRecords();
  });

  document.getElementById('filter-type').addEventListener('change', e => {
    filters.el_type = e.target.value;
    filters.year = '';
    
    const yearEl = document.getElementById('filter-year');
    yearEl.innerHTML = '<option value="">All Years</option>';
    
    if (filters.state && filters.el_type && filterMetadata && filterMetadata[filters.state]?.[filters.el_type]) {
        yearEl.disabled = false;
        Object.keys(filterMetadata[filters.state][filters.el_type]).sort((a,b)=>b.localeCompare(a)).forEach(y => yearEl.appendChild(new Option(y, y)));
    } else {
        yearEl.disabled = true;
    }
    
    loadStats(); loadRecords();
  });

  document.getElementById('filter-year').addEventListener('change', e => {
    filters.year = e.target.value;
    loadStats(); loadRecords();
  });

  document.getElementById('filter-sir').addEventListener('change', e => {
    filters.sir_only = e.target.checked; loadStats(); loadRecords();
  });

  document.getElementById('global-search').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { filters.search = e.target.value.trim(); loadRecords(); }, 250);
  });

  document.getElementById('clear-filters').addEventListener('click', () => {
    Object.assign(filters, { state:'', el_type:'', year:'', status:'', sir_only:false, search:'' });
    ['filter-state','filter-type','filter-year'].forEach(id => {
      document.getElementById(id).value = '';
    });
    document.getElementById('filter-type').disabled = true;
    document.getElementById('filter-year').disabled = true;
    document.getElementById('filter-sir').checked   = false;
    document.getElementById('global-search').value  = '';
    handleSideNav('all'); // also resets status filter
  });

  document.getElementById('select-all')?.addEventListener('change', e => {
    const isChecked = e.target.checked;
    allRecords.forEach(r => isChecked ? selectedIds.add(r.id) : selectedIds.delete(r.id));
    renderTable();
    updateSelBar();
  });

  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      sortDir = sortCol === col && sortDir === 'asc' ? 'desc' : 'asc';
      sortCol = col;
      renderTable();
    });
  });

  // Selection export bar removed, keeping clearSelection internal for Esc key
  document.getElementById('reload-btn').addEventListener('click', syncFromExcel);

  document.getElementById('modal-close').addEventListener('click',  closeModal);
  document.getElementById('modal-cancel').addEventListener('click', closeModal);
  document.getElementById('modal-save').addEventListener('click',   saveModal);
  document.getElementById('overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });

  document.querySelectorAll('.sidelink').forEach(el => {
    el.addEventListener('click', e => { e.preventDefault(); handleSideNav(el.dataset.view); });
  });

  document.getElementById('nav-retro').addEventListener('click', e => {
    e.preventDefault();
    openRetroModal();
  });

  document.getElementById('retro-close').addEventListener('click', closeRetroModal);
  document.getElementById('retro-cancel').addEventListener('click', closeRetroModal);
  document.getElementById('retro-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeRetroModal();
  });

  // Cascading change handlers for retro dropdowns
  document.getElementById('retro-state').addEventListener('change', e => {
    const s = e.target.value;
    const typeEl = document.getElementById('retro-type');
    const yearEl = document.getElementById('retro-year');
    typeEl.innerHTML = '<option value="">All Types</option>';
    yearEl.innerHTML = '<option value="">All Years</option>';
    
    if (s && retroMetadata[s]) {
        typeEl.disabled = false;
        Object.keys(retroMetadata[s]).sort().forEach(t => typeEl.appendChild(new Option(t, t)));
    } else {
        typeEl.disabled = true;
    }
    yearEl.disabled = true;
    updateRetroCountLocal();
  });

  document.getElementById('retro-type').addEventListener('change', e => {
    const s = document.getElementById('retro-state').value;
    const t = e.target.value;
    const yearEl = document.getElementById('retro-year');
    yearEl.innerHTML = '<option value="">All Years</option>';
    
    if (s && t && retroMetadata[s]?.[t]) {
        yearEl.disabled = false;
        Object.keys(retroMetadata[s][t]).sort((a,b)=>b.localeCompare(a)).forEach(y => yearEl.appendChild(new Option(y, y)));
    } else {
        yearEl.disabled = true;
    }
    updateRetroCountLocal();
  });

  document.getElementById('retro-year').addEventListener('change', () => {
    updateRetroCountLocal();
  });

  document.getElementById('retro-download').addEventListener('click', async () => {
    const state = document.getElementById('retro-state').value;
    const type = document.getElementById('retro-type').value;
    const year = document.getElementById('retro-year').value;
    const fmt = document.getElementById('retro-format').value;

    if (!state || !type || !year) {
      showToast('Please select State, Type, and Year.', true);
      return;
    }
    
    const btn = document.getElementById('retro-download');
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[16px]">refresh</span> Downloading...';
    try {
      const res = await fetch(`/api/retro/export?state=${state}&el_type=${type}&year=${year}&format=${fmt}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Export failed');
      }
      
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Retro_${state}_${type}_${year}.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('Download started');
      closeRetroModal();
    } catch (e) {
      showToast(e.message, true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">download</span> Download';
      updateRetroCountLocal();
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closeRetroModal(); clearSelection(); }
  });
}
