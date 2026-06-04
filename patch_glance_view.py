import os
import re

index_path = r"d:\Others\Varahe Work\Tasks\Form 20 Backlog Dashboard\templates\index.html"
js_path = r"d:\Others\Varahe Work\Tasks\Form 20 Backlog Dashboard\static\app.js"

# --- 1. Patch index.html ---
with open(index_path, "r", encoding="utf-8") as f:
    html = f.read()

# Remove the old glance-overlay modal
modal_pattern = r"<!-- ===== GLANCE REPORT MODAL ===== -->\s*<div id=\"glance-overlay\".*?</div>\s*</div>\s*</div>"
html = re.sub(modal_pattern, "", html, flags=re.DOTALL)

# Inject the glance-view next to dashboard-view
dashboard_end_pattern = r"        </div><!-- end dashboard-view -->"

glance_view_html = """        </div><!-- end dashboard-view -->

        <!-- ===== GLANCE REPORT VIEW ===== -->
        <div id="glance-view" class="hidden flex-1 flex-col relative h-full overflow-y-auto custom-scrollbar bg-slate-50/50">
            <!-- Header -->
            <div class="px-6 py-5 border-b border-slate-200 bg-white sticky top-0 z-10">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0">
                        <span class="material-symbols-outlined text-indigo-600 text-[20px]">fact_check</span>
                    </div>
                    <div>
                        <h2 class="text-[18px] font-black tracking-tight text-slate-800">Glance Report</h2>
                        <p class="text-[12px] font-medium text-slate-500">Weekly DB Pushed records overview</p>
                    </div>
                </div>
            </div>

            <!-- Content Area -->
            <div class="p-6">
                <!-- Filters Bar -->
                <div class="mb-4 flex items-center gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-sm flex-wrap">
                    <span class="material-symbols-outlined text-slate-400" style="font-size:18px;">filter_alt</span>
                    
                    <div class="flex items-center gap-2">
                        <label class="text-[11px] font-bold text-slate-500 uppercase">Month</label>
                        <select id="glance-month-filter" class="h-8 w-36 px-2 text-[12px] font-bold text-slate-700 border border-slate-200 bg-slate-50 rounded outline-none cursor-pointer hover:border-slate-300">
                            <option value="">All Months</option>
                        </select>
                    </div>
                    
                    <div class="flex items-center gap-2">
                        <label class="text-[11px] font-bold text-slate-500 uppercase">State</label>
                        <select id="glance-state-filter" class="h-8 w-32 px-2 text-[12px] font-bold text-slate-700 border border-slate-200 bg-slate-50 rounded outline-none cursor-pointer hover:border-slate-300">
                            <option value="">All States</option>
                        </select>
                    </div>
                    
                    <div class="flex items-center gap-2">
                        <label class="text-[11px] font-bold text-slate-500 uppercase">Type</label>
                        <select id="glance-type-filter" class="h-8 w-28 px-2 text-[12px] font-bold text-slate-700 border border-slate-200 bg-slate-50 rounded outline-none cursor-pointer hover:border-slate-300">
                            <option value="">All Types</option>
                        </select>
                    </div>

                    <div class="ml-auto">
                        <span class="text-[12px] font-bold bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-full" id="glance-panel-count">— records</span>
                    </div>
                </div>

                <!-- Weeks accordion -->
                <div id="glance-panel-accordion" class="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-sm divide-y divide-slate-100">
                    <div class="p-10 text-center flex flex-col items-center gap-3 text-slate-400">
                        <span class="material-symbols-outlined" style="font-size:36px;">hourglass_empty</span>
                        <p class="text-sm">Loading...</p>
                    </div>
                </div>
            </div>
        </div><!-- end glance-view -->"""

html = html.replace(dashboard_end_pattern, glance_view_html)

with open(index_path, "w", encoding="utf-8") as f:
    f.write(html)

# --- 2. Patch app.js ---
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

nav_pattern = r"  // ── Dashboard / Listing Tab Navigation ──────────────────────────────────.*?  document\.getElementById\('nav-retro'\)\.addEventListener\('click', e => \{"

new_nav = """  // ── Tab Navigation ───────────────────────────────────────────────────────
  const navTabs = [
    { id: 'nav-listing', viewId: 'listing-view', setup: () => { loadStats(); loadRecords(); } },
    { id: 'nav-dashboard', viewId: 'dashboard-view', setup: loadDashboardStats },
    { id: 'nav-glance', viewId: 'glance-view', setup: loadGlancePanel }
  ];

  function switchTab(activeId) {
    navTabs.forEach(t => {
      const nav = document.getElementById(t.id);
      const view = document.getElementById(t.viewId);
      if (!nav || !view) return;
      if (t.id === activeId) {
        view.classList.remove('hidden'); view.classList.add('flex');
        nav.classList.add('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
        nav.classList.remove('text-slate-500','font-medium');
        if(t.setup) t.setup();
      } else {
        view.classList.add('hidden'); view.classList.remove('flex');
        nav.classList.remove('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
        nav.classList.add('text-slate-500','font-medium');
      }
    });
  }

  navTabs.forEach(t => {
      const el = document.getElementById(t.id);
      if(el) el.addEventListener('click', () => switchTab(t.id));
  });

  // Month filter & refresh for Dashboard
  const dashMonthFilter = document.getElementById('dash-month-filter');
  const dashRefreshBtn  = document.getElementById('dash-refresh-btn');
  if (dashMonthFilter) dashMonthFilter.addEventListener('change', loadDashboardStats);
  if (dashRefreshBtn)  dashRefreshBtn.addEventListener('click',   loadDashboardStats);

  // Filters for Glance
  const glanceMoFil  = document.getElementById('glance-month-filter');
  const glanceStFil  = document.getElementById('glance-state-filter');
  const glanceTyFil  = document.getElementById('glance-type-filter');
  if (glanceMoFil) glanceMoFil.addEventListener('change', loadGlancePanel);
  if (glanceStFil) glanceStFil.addEventListener('change', loadGlancePanel);
  if (glanceTyFil) glanceTyFil.addEventListener('change', loadGlancePanel);

  document.getElementById('nav-retro').addEventListener('click', e => {"""

js = re.sub(nav_pattern, new_nav, js, flags=re.DOTALL)

# Update loadGlancePanel function
old_glance_fn = r"async function loadGlancePanel\(\) \{.*?\n\}"
new_glance_fn = """async function loadGlancePanel() {
    const monthFilter = (document.getElementById('glance-month-filter') || {}).value || '';
    const stateFilter = (document.getElementById('glance-state-filter') || {}).value || '';
    const typeFilter = (document.getElementById('glance-type-filter') || {}).value || '';
    try {
        const params = new URLSearchParams();
        if (monthFilter) params.append('month', monthFilter);
        if (stateFilter) params.append('state', stateFilter);
        if (typeFilter) params.append('el_type', typeFilter);
        
        const glance = await apiFetch('/api/glance_report?' + params.toString());
        
        // Populate filters if empty
        const moSel = document.getElementById('glance-month-filter');
        if (moSel && glance.available_months && moSel.options.length <= 1) {
            glance.available_months.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                const [yr, mo] = m.split('-');
                opt.textContent = new Date(yr, parseInt(mo) - 1).toLocaleString('default', { month: 'long', year: 'numeric' });
                moSel.appendChild(opt);
            });
        }
        
        // Also grab state/type filters from the main filter dropdows to populate these
        const stSel = document.getElementById('glance-state-filter');
        if (stSel && stSel.options.length <= 1) {
            const mainState = document.getElementById('filter-state');
            if (mainState && mainState.options) {
                Array.from(mainState.options).forEach(o => {
                    if (o.value) stSel.add(new Option(o.text, o.value));
                });
            }
        }
        const tySel = document.getElementById('glance-type-filter');
        if (tySel && tySel.options.length <= 1) {
            const mainType = document.getElementById('filter-type');
            if (mainType && mainType.options) {
                Array.from(mainType.options).forEach(o => {
                    if (o.value) tySel.add(new Option(o.text, o.value));
                });
            }
        }
        
        const accordion = document.getElementById('glance-panel-accordion');
        const countSpan = document.getElementById('glance-panel-count');
        const allWeeks = glance.all_weeks || [];
        
        if (countSpan) countSpan.textContent = allWeeks.reduce((acc, w) => acc + w.count, 0) + ' records';
        
        if (!accordion) return;

        if (allWeeks.length === 0) {
            accordion.innerHTML = `<div class="p-10 text-center flex flex-col items-center gap-3 text-slate-400">
                <span class="material-symbols-outlined" style="font-size:36px;">hourglass_empty</span>
                <p class="text-sm">No DB pushed records found.</p>
            </div>`;
        } else {
            accordion.innerHTML = allWeeks.map((w, i) => {
                const isCurrent = w.is_current;
                const badge = isCurrent
                    ? `<span class="ml-2 text-[10px] font-bold bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">Current Week</span>`
                    : '';
                const rows = w.records.map(r =>
                    `<tr class="hover:bg-indigo-50/40 transition-colors">
                        <td class="py-2 px-6 text-[12px] font-mono text-slate-700 font-semibold">${r.key}</td>
                        <td class="py-2 px-6 text-[12px] text-slate-400">${r.date}</td>
                        <td class="py-2 px-6"><span class="text-[10px] font-bold bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full border border-emerald-200">DB Pushed</span></td>
                    </tr>`
                ).join('');
                return `<div id="panel-week-${i}">
                    <button onclick="togglePanelWeek(${i})" class="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors text-left group border-none">
                        <div class="flex items-center gap-3">
                            <span class="w-2.5 h-2.5 rounded-full ${isCurrent ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]' : 'bg-indigo-300'} shrink-0"></span>
                            <span class="text-[13px] font-bold text-slate-800">${w.week}${badge}</span>
                        </div>
                        <div class="flex items-center gap-4">
                            <span class="text-[11px] font-bold ${isCurrent ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-50 text-slate-600 border-slate-200'} border px-3 py-1 rounded-full shadow-sm">${w.count} records</span>
                            <div class="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center group-hover:bg-slate-200 transition-colors">
                                <span class="material-symbols-outlined text-slate-400 group-hover:text-slate-600 panel-week-chevron-${i}" style="font-size:18px;transition:transform 0.2s">${i === 0 ? 'expand_less' : 'expand_more'}</span>
                            </div>
                        </div>
                    </button>
                    <div id="panel-week-body-${i}" class="${i === 0 ? '' : 'hidden'} border-t border-slate-100 bg-slate-50/30">
                        <table class="w-full">
                            <thead><tr class="border-b border-slate-200 bg-slate-100/50">
                                <th class="py-2 px-6 text-left text-[10px] font-bold text-slate-500 uppercase tracking-wider w-1/3">Election Key</th>
                                <th class="py-2 px-6 text-left text-[10px] font-bold text-slate-500 uppercase tracking-wider w-1/3">Date Pushed</th>
                                <th class="py-2 px-6 text-left text-[10px] font-bold text-slate-500 uppercase tracking-wider w-1/3">Status</th>
                            </tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                </div>`;
            }).join('');
        }
    } catch (e) {
        console.error('loadGlancePanel:', e);
    }
}"""
js = re.sub(old_glance_fn, new_glance_fn, js, flags=re.DOTALL)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)

print("Vanilla app patched to make Glance Report a full view.")
