import os

JS_PATH = r"d:\Others\Varahe Work\Tasks\Form 20 Backlog Dashboard\static\app.js"

with open(JS_PATH, "r", encoding="utf-8") as f:
    js_content = f.read()

# 1. Add globals
if "let pieChart = null;" not in js_content:
    js_content = js_content.replace(
        "let activeKpi = null;",
        "let activeKpi = null;\nlet pieChart = null;\nlet barChart = null;"
    )

# 2. Add functions and listeners at the end of DOMContentLoaded block
# We'll just append it before the final `});`
dashboard_logic = """
  // Dashboard Navigation Logic
  const navListing = document.getElementById('nav-listing');
  const navDashboard = document.getElementById('nav-dashboard');
  const listingView = document.getElementById('listing-view');
  const dashboardView = document.getElementById('dashboard-view');

  if (navListing && navDashboard) {
      navListing.addEventListener('click', (e) => {
          navListing.classList.add('border-b-2', 'border-slate-800', 'dark:border-slate-400', 'text-slate-900', 'dark:text-white', 'font-bold');
          navListing.classList.remove('text-slate-500', 'dark:text-slate-400', 'font-medium');
          navDashboard.classList.remove('border-b-2', 'border-slate-800', 'dark:border-slate-400', 'text-slate-900', 'dark:text-white', 'font-bold');
          navDashboard.classList.add('text-slate-500', 'dark:text-slate-400', 'font-medium');
          listingView.classList.remove('hidden');
          listingView.classList.add('flex');
          dashboardView.classList.add('hidden');
          dashboardView.classList.remove('flex');
      });

      navDashboard.addEventListener('click', (e) => {
          navDashboard.classList.add('border-b-2', 'border-slate-800', 'dark:border-slate-400', 'text-slate-900', 'dark:text-white', 'font-bold');
          navDashboard.classList.remove('text-slate-500', 'dark:text-slate-400', 'font-medium');
          navListing.classList.remove('border-b-2', 'border-slate-800', 'dark:border-slate-400', 'text-slate-900', 'dark:text-white', 'font-bold');
          navListing.classList.add('text-slate-500', 'dark:text-slate-400', 'font-medium');
          dashboardView.classList.remove('hidden');
          dashboardView.classList.add('flex');
          listingView.classList.add('hidden');
          listingView.classList.remove('flex');
          loadDashboardStats();
      });
  }
"""

if "Dashboard Navigation Logic" not in js_content:
    js_content = js_content.replace(
        "loadStats();\n  loadRecords();\n});",
        f"{dashboard_logic}\n  loadStats();\n  loadRecords();\n}});"
    )


dashboard_fn = """
async function loadDashboardStats() {
    try {
        const stats = await apiFetch('/api/stats');
        const glance = await apiFetch('/api/glance_report');
        
        // Update Pie Chart
        const bs = stats.by_status;
        const pieData = {
            labels: ['Downloaded', 'Missing', 'Completed/DB Pushed', 'Pending'],
            datasets: [{
                data: [
                    bs.downloaded || 0,
                    bs.missing || 0,
                    (bs.completed || 0) + (bs.db_pushed || 0),
                    bs.pending || 0
                ],
                backgroundColor: ['#6366f1', '#ef4444', '#10b981', '#f59e0b'],
                borderWidth: 0
            }]
        };
        
        if (pieChart) {
            pieChart.data = pieData;
            pieChart.update();
        } else {
            const ctx = document.getElementById('statusPieChart').getContext('2d');
            pieChart = new Chart(ctx, {
                type: 'pie',
                data: pieData,
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'right' } }
                }
            });
        }
        
        // Update Bar Chart
        const weeks = Object.keys(glance.weekly_counts).reverse();
        const counts = weeks.map(w => glance.weekly_counts[w]);
        
        if (barChart) {
            barChart.data.labels = weeks;
            barChart.data.datasets[0].data = counts;
            barChart.update();
        } else {
            const ctx2 = document.getElementById('weeklyBarChart').getContext('2d');
            barChart = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: weeks,
                    datasets: [{
                        label: 'Completions',
                        data: counts,
                        backgroundColor: '#6366f1',
                        borderRadius: 4
                    }]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
                }
            });
        }
        
        // Update Glance Report
        document.getElementById('glance-week-label').textContent = glance.recent_week || 'No Data';
        document.getElementById('glance-total-count').textContent = glance.recent_records ? glance.recent_records.length : 0;
        
        const tbody = document.getElementById('glance-tbody');
        tbody.innerHTML = '';
        if (glance.recent_records && glance.recent_records.length > 0) {
            document.getElementById('glance-empty').classList.add('hidden');
            glance.recent_records.forEach(r => {
                tbody.innerHTML += `<tr class="border-b border-slate-50"><td class="py-2 px-3">${r.key}</td><td class="py-2 px-3">${r.date}</td></tr>`;
            });
        } else {
            document.getElementById('glance-empty').classList.remove('hidden');
        }
        
    } catch (e) {
        console.error(e);
    }
}
"""

if "async function loadDashboardStats" not in js_content:
    js_content += "\n" + dashboard_fn

with open(JS_PATH, "w", encoding="utf-8") as f:
    f.write(js_content)

print("Patched app.js successfully")
