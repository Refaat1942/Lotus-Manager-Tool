/* Deep Sales Analysis — standalone module (avoids stale dashboard.js cache) */
(function () {
    const L = window.TABLE_LABELS || {};
    const lbl = k => L[k] || k;
    let cache = null;
    let mode = 'sales_type_category';
    let loading = false;

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s ?? '';
        return d.innerHTML;
    }

    function status(msg, err) {
        const el = document.getElementById('deepSalesStatus');
        if (!el) return;
        el.textContent = msg || '';
        el.classList.toggle('status-error', !!err);
    }

    function arCell(v) {
        return `<td dir="auto">${esc(v ?? '')}</td>`;
    }

    function numCell(v) {
        return `<td class="num">${esc(v ?? '')}</td>`;
    }

    function renderTable(payload) {
        const table = document.getElementById('deepSalesTable');
        if (!table || !payload?.columns?.length) return false;
        const cols = payload.columns;
        const headers = cols.map(c => `<th class="sortable">${esc(lbl(c))}</th>`).join('');
        const rows = (payload.rows || []).map(row => {
            const cells = cols.map(c => {
                const v = row[c];
                if (c === 'sales' || c === 'qty' || c === 'rank_in_group') return numCell(v);
                return arCell(v);
            }).join('');
            return `<tr>${cells}</tr>`;
        }).join('');
        table.innerHTML = `<thead><tr>${headers}</tr></thead><tbody>${rows}</tbody>`;
        return true;
    }

    function renderInsights(data) {
        const ins = document.getElementById('deepSalesInsights');
        if (!ins) return;
        if (!data?.ok) {
            ins.classList.add('hidden');
            return;
        }
        ins.classList.remove('hidden');
        const items = (data.insights || []).map(i => `<li dir="auto">${esc(i)}</li>`).join('');
        ins.innerHTML = items
            ? `<strong>💡 ${esc(window.DEEP_INSIGHTS || 'Key Insights')}</strong><ul class="ai-rec-list">${items}</ul>`
            : '';
        if (!data.delivery_categories?.rows?.length) {
            ins.innerHTML += `<p class="status-text">${esc(window.DEEP_NO_DELIVERY || '')}</p>`;
        }
    }

    function renderChart(data) {
        const wrap = document.getElementById('deepSalesChartWrap');
        if (!wrap) return;
        if (mode !== 'delivery_categories' || !data.chart?.labels?.length || typeof Chart === 'undefined') {
            wrap.classList.add('hidden');
            return;
        }
        wrap.classList.remove('hidden');
        const ctx = document.getElementById('chartDeepDelivery');
        if (!ctx) return;
        if (window.__deepChart) {
            window.__deepChart.destroy();
        }
        window.__deepChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.chart.labels,
                datasets: [{ label: 'Top Delivery Categories', data: data.chart.values, backgroundColor: '#9b59b6' }],
            },
            options: { responsive: true, indexAxis: 'y' },
        });
    }

    function renderView() {
        if (!cache?.ok) return;
        const payload = cache[mode];
        if (!payload?.columns?.length) {
            status(window.DEEP_NO_ROWS || 'No rows for this view.', true);
            return;
        }
        if (!renderTable(payload)) {
            status('Could not render table.', true);
            return;
        }
        const n = payload.rows?.length || 0;
        const ch = cache.delivery_channels?.length ? ` · Channels: ${cache.delivery_channels.join(', ')}` : '';
        status(n ? `${n} rows${ch}` : (window.DEEP_NO_ROWS || 'No matching sales.'), !n);
        renderChart(cache);
    }

    async function load(force) {
        if (loading) return;
        if (!force && cache?.ok) {
            renderView();
            return;
        }
        loading = true;
        status(window.DEEP_LOADING || 'Loading deep sales analysis...', false);
        try {
            const res = await fetch('/api/deep-sales');
            let data;
            try {
                data = await res.json();
            } catch (_) {
                throw new Error(`Server error (${res.status})`);
            }
            if (!res.ok || !data.ok) {
                cache = null;
                renderInsights(null);
                status(data.error || data.detail || 'Failed to load deep sales analysis', true);
                return;
            }
            cache = data;
            if (window.deepSalesCache !== undefined) window.deepSalesCache = data;
            renderInsights(data);
            renderView();
        } catch (e) {
            cache = null;
            renderInsights(null);
            status(e.message || 'Failed to load deep sales analysis', true);
        } finally {
            loading = false;
        }
    }

    function applyData(data) {
        if (!data) return;
        cache = data;
        if (window.deepSalesCache !== undefined) window.deepSalesCache = data;
        renderInsights(data);
        if (document.getElementById('tab-deepsales')?.classList.contains('active')) {
            renderView();
        }
    }

    function bind() {
        document.getElementById('loadDeepSales')?.addEventListener('click', () => load(true));
        document.querySelectorAll('.deep-sub').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.deep-sub').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                mode = tab.dataset.dmode || 'sales_type_category';
                if (window.activeDeepMode !== undefined) window.activeDeepMode = mode;
                if (cache?.ok) renderView();
                else load(false);
            });
        });
        document.querySelectorAll('.tab[data-tab="deepsales"]').forEach(tab => {
            tab.addEventListener('click', () => setTimeout(() => load(false), 30));
        });
        window.addEventListener('lotus-dashboard-updated', e => applyData(e.detail?.deep_sales));
    }

    window.__runDeepSales = load;
    window.__applyDeepSales = applyData;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bind);
    } else {
        bind();
    }
})();
