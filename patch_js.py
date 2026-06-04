import os
import re

js_path = r"d:\Others\Varahe Work\Tasks\Form 20 Backlog Dashboard\static\app.js"
with open(js_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update DOMContentLoaded
old_init = """document.addEventListener('DOMContentLoaded', () => {
  loadFilters();
  loadStats();
  loadRecords();
  bindEvents();
});"""
new_init = """document.addEventListener('DOMContentLoaded', () => {
  loadFilters();
  // Dashboard is the default opening view
  loadDashboardStats();
  // Listing data loads lazily when user navigates to it
  bindEvents();
});"""
content = content.replace(old_init, new_init)

# 2. Update nav logic to include Glance Panel
old_nav = """  function showListing() {
    listingView.classList.remove('hidden'); listingView.classList.add('flex');
    dashView.classList.add('hidden');       dashView.classList.remove('flex');
    navListing.classList.add('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navListing.classList.remove('text-slate-500','font-medium');
    navDashboard.classList.remove('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navDashboard.classList.add('text-slate-500','font-medium');
  }
  function showDashboard() {
    dashView.classList.remove('hidden');    dashView.classList.add('flex');
    listingView.classList.add('hidden');    listingView.classList.remove('flex');
    navDashboard.classList.add('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navDashboard.classList.remove('text-slate-500','font-medium');
    navListing.classList.remove('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navListing.classList.add('text-slate-500','font-medium');
    loadDashboardStats();
  }
  if (navListing)   navListing.addEventListener('click',   showListing);
  if (navDashboard) navDashboard.addEventListener('click', showDashboard);

  // Month filter & refresh
  const dashMonthFilter = document.getElementById('dash-month-filter');
  const dashRefreshBtn  = document.getElementById('dash-refresh-btn');
  if (dashMonthFilter) dashMonthFilter.addEventListener('change', loadDashboardStats);
  if (dashRefreshBtn)  dashRefreshBtn.addEventListener('click',   loadDashboardStats);

  document.getElementById('nav-retro').addEventListener('click', e => {
    e.preventDefault();
    openRetroModal();
  });"""
new_nav = """  function showListing() {
    listingView.classList.remove('hidden'); listingView.classList.add('flex');
    dashView.classList.add('hidden');       dashView.classList.remove('flex');
    navListing.classList.add('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navListing.classList.remove('text-slate-500','font-medium');
    navDashboard.classList.remove('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navDashboard.classList.add('text-slate-500','font-medium');
    // Load listing data lazily
    loadStats();
    loadRecords();
  }
  function showDashboard() {
    dashView.classList.remove('hidden');    dashView.classList.add('flex');
    listingView.classList.add('hidden');    listingView.classList.remove('flex');
    navDashboard.classList.add('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navDashboard.classList.remove('text-slate-500','font-medium');
    navListing.classList.remove('font-bold','border-b-2','border-slate-800','dark:border-slate-400','text-slate-900');
    navListing.classList.add('text-slate-500','font-medium');
    loadDashboardStats();
  }
  if (navListing)   navListing.addEventListener('click',   showListing);
  if (navDashboard) navDashboard.addEventListener('click', showDashboard);

  // Month filter & refresh
  const dashMonthFilter = document.getElementById('dash-month-filter');
  const dashRefreshBtn  = document.getElementById('dash-refresh-btn');
  if (dashMonthFilter) dashMonthFilter.addEventListener('change', loadDashboardStats);
  if (dashRefreshBtn)  dashRefreshBtn.addEventListener('click',   loadDashboardStats);

  // ── Glance Report Panel ─────────────────────────────────────────────────
  const navGlance    = document.getElementById('nav-glance');
  const glanceOvl    = document.getElementById('glance-overlay');
  const glancePanel  = document.getElementById('glance-panel');
  const glanceClose  = document.getElementById('glance-close');
  const glanceMoFil  = document.getElementById('glance-month-filter');

  function openGlancePanel() {
    if (glanceOvl) glanceOvl.classList.remove('opacity-0','pointer-events-none');
    if (glancePanel) glancePanel.classList.remove('translate-x-full');
    loadGlancePanel();
  }
  function closeGlancePanel() {
    if (glanceOvl) glanceOvl.classList.add('opacity-0','pointer-events-none');
    if (glancePanel) glancePanel.classList.add('translate-x-full');
  }
  if (navGlance)   navGlance.addEventListener('click',  openGlancePanel);
  if (glanceClose) glanceClose.addEventListener('click', closeGlancePanel);
  if (glanceOvl)   glanceOvl.addEventListener('click', e => { if (e.target === glanceOvl) closeGlancePanel(); });
  if (glanceMoFil) glanceMoFil.addEventListener('change', loadGlancePanel);

  document.getElementById('nav-retro').addEventListener('click', e => {
    e.preventDefault();
    openRetroModal();
  });"""
content = content.replace(old_nav, new_nav)

# 3. Remove old Glance accordion from loadDashboardStats using regex to find exactly the part to remove
pattern = r"        // ── Glance Report Accordion \(DB Pushed only\) ──────────────────────────.*?        }\s*\} catch \(e\) \{"
content = re.sub(pattern, "    } catch (e) {", content, flags=re.DOTALL)

# 4. Remove toggleWeek function
toggle_pattern = r"function toggleWeek\(i\) \{.*?\}"
content = re.sub(toggle_pattern, "", content, flags=re.DOTALL)

# 5. Append loadGlancePanel and togglePanelWeek to the very end
glance_logic = """

async function loadGlancePanel() {
    const monthFilter = (document.getElementById('glance-month-filter') || {}).value || '';
    try {
        const glance = await apiFetch('/api/glance_report' + (monthFilter ? '?month=' + monthFilter : ''));
        
        // Populate month dropdown (only once)
        const sel = document.getElementById('glance-month-filter');
        if (sel && glance.available_months && sel.options.length <= 1) {
            glance.available_months.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                const [yr, mo] = m.split('-');
                opt.textContent = new Date(yr, parseInt(mo) - 1).toLocaleString('default', { month: 'long', year: 'numeric' });
                sel.appendChild(opt);
            });
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
                        <td class="py-2 px-5 text-[12px] font-mono text-slate-700 font-semibold">${r.key}</td>
                        <td class="py-2 px-5 text-[12px] text-slate-400">${r.date}</td>
                        <td class="py-2 px-5"><span class="text-[10px] font-bold bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full">DB Pushed</span></td>
                    </tr>`
                ).join('');
                return `<div id="panel-week-${i}">
                    <button onclick="togglePanelWeek(${i})" class="w-full flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 transition-colors text-left group">
                        <div class="flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full ${isCurrent ? 'bg-emerald-400' : 'bg-indigo-300'} shrink-0"></span>
                            <span class="text-[12px] font-semibold text-slate-700">${w.week}${badge}</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <span class="text-[11px] font-bold ${isCurrent ? 'bg-emerald-100 text-emerald-700' : 'bg-indigo-50 text-indigo-600'} px-2.5 py-0.5 rounded-full">${w.count} records</span>
                            <span class="material-symbols-outlined text-slate-300 group-hover:text-slate-500 panel-week-chevron-${i}" style="font-size:16px;transition:transform 0.2s">${i === 0 ? 'expand_less' : 'expand_more'}</span>
                        </div>
                    </button>
                    <div id="panel-week-body-${i}" class="${i === 0 ? '' : 'hidden'} border-t border-slate-50 bg-slate-50/50">
                        <table class="w-full">
                            <thead><tr class="border-b border-slate-100">
                                <th class="py-2 px-5 text-left text-[10px] font-bold text-slate-400 uppercase tracking-wider">Election Key</th>
                                <th class="py-2 px-5 text-left text-[10px] font-bold text-slate-400 uppercase tracking-wider">Date Pushed</th>
                                <th class="py-2 px-5 text-left text-[10px] font-bold text-slate-400 uppercase tracking-wider">Status</th>
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
}

function togglePanelWeek(i) {
    const body = document.getElementById('panel-week-body-' + i);
    const chevron = document.querySelector('.panel-week-chevron-' + i);
    if (!body) return;
    const hidden = body.classList.toggle('hidden');
    if (chevron) chevron.textContent = hidden ? 'expand_more' : 'expand_less';
}
"""
content += glance_logic

with open(js_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied")
