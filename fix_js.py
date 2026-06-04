JS_PATH = r"d:\Others\Varahe Work\Tasks\Form 20 Backlog Dashboard\static\app.js"
with open(JS_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the orphan fragment starting with "ald-600' ..." through the duplicate }.join() block
bad_tail = """ald-600' : 'text-indigo-600'}\">${w.count}</span>
                            <span class="material-symbols-outlined text-slate-300 week-chevron-${i}" style="font-size:16px;transition:transform 0.2s">${i === 0 ? 'expand_less' : 'expand_more'}</span>
                        </div>
                    </button>
                    <div id="week-body-${i}" class="${i === 0 ? '' : 'hidden'} border-t border-slate-50">
                        <table class="w-full">
                            <thead><tr class="bg-slate-50"><th class="py-1.5 px-4 text-left text-[10px] font-bold text-slate-400 uppercase tracking-wider">Election Key</th><th class="py-1.5 px-4 text-left text-[10px] font-bold text-slate-400 uppercase tracking-wider">Date</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                </div>`;
            }).join('');
        }"""

if bad_tail in content:
    content = content.replace(bad_tail, '')
    print("Removed duplicate orphan block")
else:
    print("Orphan block not found by exact match - trying line scan")
    lines = content.split('\n')
    for i, l in enumerate(lines[1085:1104], start=1086):
        print(f"{i}: {repr(l[:80])}")

with open(JS_PATH, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
