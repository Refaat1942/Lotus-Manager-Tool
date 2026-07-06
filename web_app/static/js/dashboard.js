let charts = {};
let dailyAvg = false;
let validDates = [];
let activeEmpMode = 'overview';
let lastDashboardData = null;
const L = window.TABLE_LABELS || {};

const STATIC_TABLES = {
    topEmpTable: ['rank', 'name', 'branch', 'shift', 'top_type', 'sales'],
    prodTable: ['code', 'description', 'category', 'group', 'qty', 'sales'],
    execShiftTable: ['branch', 'shift', 'sales', 'receipts', 'avg'],
    execPharTable: ['name', 'branch', 'shift', 'sales', 'receipts', 'avg_receipt', 'top_sales_type', 'top_category', 'evaluation'],
    stagTable: ['stagnant_code', 'stagnant_drug', 'alt_code', 'alternative', 'alt_qty', 'group_match'],
    trendTable: ['employee', 'prev_sales', 'curr_sales', 'sales_delta', 'prev_recs', 'curr_recs', 'prev_avg', 'curr_avg', 'avg_delta', 'insight'],
    dateHourlyTable: ['hour', 'p1_sales', 'p2_sales', 'variance'],
};

const EMP_MODES = {
    overview: { api: null, rank: true, cache: 'employee_overview' },
    sales_types: { api: 'sales_types', rank: true, cache: 'employee_sales_types' },
    subcategories: { api: 'subcategories', rank: false, password: true },
    efficiency: { api: 'efficiency', rank: false, cache: 'employee_efficiency' },
    ai: { api: 'ai', rank: true, cache: 'employee_ai' },
};

const LOCALE = 'en-US';
const INT_COLS = new Set(['working_days', 'hour', 'rank', 'rank_in_group', 'alt_qty', 'stagnant_code', 'code']);
const COUNT_COLS = new Set(['receipts', 'prev_recs', 'curr_recs', 'materials', 'qty']);
const NUMERIC_COLS = new Set([
    'sales', 'avg', 'avg_receipt', 'materials_per_receipt', 'total_materials',
    'working_days', 'receipts', 'qty', 'materials', 'p1_sales', 'p2_sales',
    'prev_sales', 'curr_sales', 'prev_recs', 'curr_recs', 'prev_avg', 'curr_avg', 'alt_qty',
    'rank_in_group',
]);

function parseNum(s) {
    const t = String(s ?? '').trim();
    if (!t || t === '—' || t === 'N/A') return NaN;
    const neg = t.startsWith('(') && t.endsWith(')');
    const n = parseFloat(t.replace(/[(),]/g, ''));
    return neg ? -n : n;
}

function isNumericCol(c) {
    return NUMERIC_COLS.has(c) || (c && c.startsWith('cat_'));
}

function fmt(n, decimals = 2) {
    const v = typeof n === 'number' ? n : parseNum(n);
    if (n == null || Number.isNaN(v)) return decimals === 0 ? '0' : '0.00';
    const s = Math.abs(v).toLocaleString(LOCALE, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
    return v < 0 ? `(${s})` : s;
}

function fmtInt(n) {
    return fmt(n, 0);
}

function formatCellValue(col, v) {
    if (v == null || v === '' || v === '---' || v === 'N/A') return v;
    if (typeof v === 'string' && (/mins|%/.test(v) || v.includes(' %'))) return v;
    const n = typeof v === 'number' ? v : parseNum(v);
    if (Number.isNaN(n)) return v;
    if (INT_COLS.has(col)) return fmtInt(n);
    if (COUNT_COLS.has(col)) {
        return Number.isInteger(n) || Math.abs(n - Math.round(n)) < 0.05 ? fmtInt(Math.round(n)) : fmt(n, 1);
    }
    if (col === 'materials_per_receipt' || col === 'total_materials') return fmt(n, 2);
    return fmt(n, 2);
}

function formatInlineNumbers(text) {
    return String(text).replace(/\d+(?:\.\d+)?/g, (match) => {
        const n = Number(match);
        if (Number.isNaN(n)) return match;
        return match.includes('.') ? fmt(n, Math.min(match.split('.')[1].length, 2)) : fmtInt(n);
    });
}

function fmtPct(n) {
    const v = typeof n === 'number' ? n : parseNum(n);
    if (Number.isNaN(v)) return String(n);
    const sign = v > 0 ? '+' : '';
    return `${sign}${fmt(v, 1)}%`;
}

function fmtDelta(v) {
    const t = String(v ?? '').trim();
    if (!t) return '—';
    const n = parseFloat(t.replace('%', ''));
    return Number.isNaN(n) ? t : fmtPct(n);
}
function esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }
function lbl(k) { return L[k] || k; }
function numCell(v) { return `<td class="cell-center cell-num">${esc(String(v))}</td>`; }
function arCell(v) { return `<td class="cell-center" dir="auto">${esc(v)}</td>`; }
function rankCell(n) { return `<td class="cell-center cell-rank">${n}</td>`; }

function aiRecCell(value, row) {
    const items = (row?.recommendations || String(value || '').split(/\s\|\s/))
        .map(s => String(s).trim())
        .filter(Boolean);
    if (!items.length) return `<td class="cell-ai-rec">—</td>`;
    return `<td class="cell-ai-rec"><ul class="ai-rec-list">${items.map(i => `<li dir="auto">${esc(formatInlineNumbers(i))}</li>`).join('')}</ul></td>`;
}

function tierCell(v) {
    const t = String(v || '');
    let cls = 'tier-solid';
    if (/star|متميز/i.test(t)) cls = 'tier-star';
    else if (/needs|تحسين|training/i.test(t)) cls = 'tier-needs';
    return `<td class="cell-center cell-tier ${cls}">${esc(v)}</td>`;
}

function dataCell(c, v, row) {
    if (c === 'recommendation') return aiRecCell(v, row);
    if (c === 'tier') return tierCell(v);
    if (c === 'sales_delta' || c === 'avg_delta') return numCell(fmtDelta(v));
    if (isNumericCol(c) || typeof v === 'number') {
        return numCell(formatCellValue(c, v));
    }
    const n = parseNum(v);
    if (!Number.isNaN(n) && /^[\d,().+\s-]+$/.test(String(v).trim())) {
        return numCell(formatCellValue(c, n));
    }
    return arCell(v);
}

function displayNum(col, v) {
    return formatCellValue(col, v);
}

function buildTableHeader(tableId, columnKeys, customLabels) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const labels = (customLabels || columnKeys.map(k => lbl(k)));
    table.innerHTML = `<thead><tr>${labels.map(l => `<th class="sortable">${esc(l)}</th>`).join('')}</tr></thead><tbody></tbody>`;
    ensureSortable(table);
}

function ensureSortable(table) {
    if (!table || table.dataset.sortBound === '1') return;
    table.dataset.sortBound = '1';
    table.addEventListener('click', e => {
        const th = e.target.closest('th.sortable');
        if (!th || !table.contains(th)) return;
        sortTable(table, [...th.parentNode.children].indexOf(th), th);
    });
}

function sortTable(table, colIndex, th) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const asc = th.dataset.sort !== 'asc';
    table.querySelectorAll('th').forEach(h => { h.classList.remove('sort-asc', 'sort-desc'); h.dataset.sort = ''; });
    th.classList.add(asc ? 'sort-asc' : 'sort-desc');
    th.dataset.sort = asc ? 'asc' : 'desc';
    rows.sort((a, b) => {
        const va = a.cells[colIndex]?.textContent.trim() || '';
        const vb = b.cells[colIndex]?.textContent.trim() || '';
        const na = parseNum(va);
        const nb = parseNum(vb);
        if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
        return asc ? va.localeCompare(vb, undefined, { numeric: true }) : vb.localeCompare(va, undefined, { numeric: true });
    });
    rows.forEach(r => tbody.appendChild(r));
}

function fillTable(id, rows, fn) {
    const tbody = document.querySelector(`#${id} tbody`);
    if (tbody) tbody.innerHTML = (rows || []).map(fn).join('');
}

function renderDynamicTable(tableId, payload, withRank) {
    const cols = payload.columns || [];
    let labels;
    if (payload.column_labels && payload.column_labels.length === cols.length) {
        labels = payload.column_labels.map((text, i) => {
            const key = cols[i];
            if (key && key.startsWith('cat_')) return text;
            return lbl(key) || text;
        });
    } else {
        labels = cols.map(c => lbl(c));
    }
    if (withRank) {
        buildTableHeader(tableId, ['rank', ...cols], [lbl('rank'), ...labels]);
    } else {
        buildTableHeader(tableId, cols, labels);
    }
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!tbody) return;
    tbody.innerHTML = (payload.rows || []).map((row, i) => {
        const tag = row.is_subtotal ? ' class="row-subtotal"' : '';
        let cells = withRank ? rankCell(i + 1) : '';
        cols.forEach(c => {
            cells += dataCell(c, row[c], row);
        });
        return `<tr${tag}>${cells}</tr>`;
    }).join('');
}

function chartNumOptions(horizontal, type) {
    const base = {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true,
        plugins: {
            legend: { display: type === 'doughnut' || type === 'pie' },
            tooltip: {
                callbacks: {
                    label: ctx => `${ctx.dataset.label || ''}: ${fmt(ctx.raw)}`,
                },
            },
        },
    };
    if (type === 'doughnut' || type === 'pie') return base;
    const tickFmt = v => fmt(v, 0);
    base.scales = {
        x: { ticks: { callback: horizontal ? undefined : tickFmt } },
        y: { ticks: { callback: horizontal ? tickFmt : undefined } },
    };
    return base;
}

function drawChart(canvasId, type, labels, values, label, horizontal) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (charts[canvasId]) charts[canvasId].destroy();
    const colors = ['#3498db', '#e74c3c', '#27ae60', '#f1c40f', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
    charts[canvasId] = new Chart(ctx, {
        type,
        data: { labels: labels || [], datasets: [{ label, data: values || [], backgroundColor: colors.slice(0, labels?.length || 0) }] },
        options: chartNumOptions(horizontal, type),
    });
}

function drawDualChart(canvasId, labels, p1, p2) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (charts[canvasId]) charts[canvasId].destroy();
    charts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Period 1', data: p1, backgroundColor: '#95a5a6' },
                { label: 'Period 2', data: p2, backgroundColor: '#27ae60' },
            ]
        },
        options: chartNumOptions(false, 'bar'),
    });
}

function buildFilterList(containerId, items, prefix) {
    const el = document.getElementById(containerId);
    el.innerHTML = '';
    (items || []).forEach(v => {
        el.innerHTML += `<label><input type="checkbox" checked data-filter="${prefix}" value="${esc(v)}"> <span dir="auto">${esc(v)}</span></label>`;
    });
}

function getSelectedFilters(prefix) {
    return [...document.querySelectorAll(`input[data-filter="${prefix}"]:checked`)].map(cb => cb.value);
}

function collectFilters() {
    return {
        start_date: document.getElementById('dateFrom').value,
        end_date: document.getElementById('dateTo').value,
        employees: getSelectedFilters('emp'), branches: getSelectedFilters('branch'),
        shifts: getSelectedFilters('shift'), categories: getSelectedFilters('cat'), materials: getSelectedFilters('mat'),
    };
}

function initStaticTables() {
    Object.entries(STATIC_TABLES).forEach(([id, cols]) => buildTableHeader(id, cols));
}

function renderDashboard(data) {
    if (!data.has_data) {
        document.getElementById('noData').classList.remove('hidden');
        document.getElementById('dashboardContent').classList.add('hidden');
        lastDashboardData = null;
        return;
    }
    lastDashboardData = data;
    document.getElementById('noData').classList.add('hidden');
    document.getElementById('dashboardContent').classList.remove('hidden');
    validDates = data.valid_dates || [];

    const k = data.kpis;
    document.getElementById('kpiSales').textContent = fmt(k.total_sales);
    document.getElementById('kpiReceipts').textContent = formatCellValue('receipts', k.total_receipts);
    document.getElementById('kpiAvg').textContent = fmt(k.avg_receipt);
    document.getElementById('kpiPieces').textContent = formatCellValue('qty', k.total_pieces);
    document.getElementById('periodBadge').textContent = `${k.period.start} → ${k.period.end} (${k.period.days} days)`;

    drawChart('chartMaterial', 'bar', data.material_chart.labels, data.material_chart.values, 'Material Groups');
    drawChart('chartHourly', 'bar', data.hourly_chart.labels, data.hourly_chart.values, 'Hourly Sales');
    drawChart('chartShift', 'bar', data.shift_chart.labels, data.shift_chart.values, 'Shift Sales');
    drawChart('chartCategory', 'doughnut', data.category_chart.labels, data.category_chart.values, 'Categories');
    drawChart('chartAdvHourly', 'bar', data.hourly_chart.labels, data.hourly_chart.values, 'Hourly Sales Breakdown');
    drawChart('chartAdvProducts', 'bar', data.top_products_chart.labels, data.top_products_chart.values, 'Top 10 Products by Qty', true);
    drawChart('chartAdvShift', 'bar', data.shift_chart.labels, data.shift_chart.values, 'Sales by Shift');

    buildTableHeader('topEmpTable', STATIC_TABLES.topEmpTable);
    fillTable('topEmpTable', data.top_employees, (r, i) =>
        `<tr>${rankCell(i + 1)}${arCell(r.name)}${arCell(r.branch)}${arCell(r.shift)}${arCell(r.top_type)}${numCell(displayNum('sales', r.sales))}</tr>`);

    renderDynamicTable('empTable', data.employee_overview, true);

    fillTable('prodTable', data.top_products, r =>
        `<tr>${numCell(r.code)}${arCell(r.description)}${arCell(r.category)}${arCell(r.material_group)}${numCell(displayNum('qty', r.qty))}${numCell(displayNum('sales', r.sales))}</tr>`);

    const ex = data.executive;
    document.getElementById('execBrief').innerHTML =
        `<strong>⭐ Top Shift:</strong> <span dir="auto">${esc(ex.best_shift)}</span><br><strong>🔥 Peak Hours:</strong> ${esc((ex.peak_hours || []).join(' & ') || 'N/A')}`;
    fillTable('execShiftTable', ex.shifts_by_branch, r =>
        `<tr>${arCell(r.branch)}${arCell(r.shift)}${numCell(displayNum('sales', r.sales))}${numCell(displayNum('receipts', r.receipts))}${numCell(displayNum('avg_receipt', r.avg_receipt))}</tr>`);
    fillTable('execPharTable', ex.pharmacists, r =>
        `<tr>${arCell(r.name)}${arCell(r.branch)}${arCell(r.shift)}${numCell(displayNum('sales', r.sales))}${numCell(displayNum('receipts', r.receipts))}${numCell(displayNum('avg_receipt', r.avg_receipt))}${arCell(r.top_sales_type)}${arCell(r.top_category)}${arCell(r.evaluation)}</tr>`);

    if (validDates.length) {
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
        set('dcP1Start', validDates[0]);
        set('dcP1End', validDates[Math.min(validDates.length - 1, 6)]);
        set('dcP2Start', validDates[Math.min(validDates.length - 1, 7)]);
        set('dcP2End', validDates[validDates.length - 1]);
    }
}

async function loadEmployeeMode(mode, password) {
    const cfg = EMP_MODES[mode];
    if (!cfg) return;
    activeEmpMode = mode;

    if (mode !== 'subcategories' && lastDashboardData && cfg.cache && lastDashboardData[cfg.cache]) {
        renderDynamicTable('empTable', lastDashboardData[cfg.cache], cfg.rank);
        return;
    }

    if (cfg.api === null) {
        const res = await fetch('/api/dashboard-data');
        const data = await res.json();
        if (!data.has_data) return;
        lastDashboardData = data;
        renderDynamicTable('empTable', data.employee_overview, true);
        return;
    }
    try {
        const res = await fetch(`/api/employee/${cfg.api}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: password || '' }),
        });
        const json = await res.json();
        if (!res.ok || !json.ok) {
            alert(json.error || json.detail || 'Failed to load employee data');
            document.querySelectorAll('.sub-tab').forEach(t =>
                t.classList.toggle('active', t.dataset.emode === 'overview'));
            activeEmpMode = 'overview';
            if (lastDashboardData?.employee_overview) {
                renderDynamicTable('empTable', lastDashboardData.employee_overview, true);
            }
            return;
        }
        renderDynamicTable('empTable', json.data, cfg.rank);
    } catch (err) {
        alert('Failed to load employee data: ' + err.message);
    }
}

async function applyLoadedOptions(options) {
    if (options?.period) {
        document.getElementById('dateFrom').value = options.period.start;
        document.getElementById('dateTo').value = options.period.end;
    }
    buildFilterList('empList', options?.employees, 'emp');
    buildFilterList('branchList', options?.branches, 'branch');
    buildFilterList('shiftList', options?.shifts, 'shift');
    buildFilterList('catList', options?.categories, 'cat');
    buildFilterList('matList', options?.materials, 'mat');
    await refreshDashboard();
}

async function refreshDashboard() {
    const savedEmpMode = document.querySelector('.sub-tab[data-emode].active')?.dataset.emode || activeEmpMode || 'overview';
    const deepTabActive = isDeepSalesTabActive();
    deepSalesCache = null;
    const res = await fetch('/api/filters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters: collectFilters(), daily_avg: dailyAvg }),
    });
    const data = await res.json();
    if (data.ok) {
        renderDashboard(data.data);
        if (savedEmpMode === 'subcategories') {
            document.querySelectorAll('.sub-tab').forEach(t =>
                t.classList.toggle('active', t.dataset.emode === 'overview'));
            activeEmpMode = 'overview';
            return;
        }
        if (savedEmpMode !== 'overview') {
            document.querySelectorAll('.sub-tab').forEach(t =>
                t.classList.toggle('active', t.dataset.emode === savedEmpMode));
            await loadEmployeeMode(savedEmpMode);
        } else {
            activeEmpMode = 'overview';
        }
        if (deepTabActive) await loadDeepSales(true);
    }
}

async function runDateCompare() {
    const body = {
        p1_start: document.getElementById('dcP1Start').value,
        p1_end: document.getElementById('dcP1End').value,
        p2_start: document.getElementById('dcP2Start').value,
        p2_end: document.getElementById('dcP2End').value,
        mode: document.getElementById('dcMode').value,
    };
    const res = await fetch('/api/date-compare', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    const el = document.getElementById('dateCompareResult');
    if (data.error) { el.innerHTML = `<p class="alert alert-error">${esc(data.error)}</p>`; return; }
    if (data.mode === 'totals') {
        el.innerHTML = `<div class="kpi-row">
            <div class="kpi-card"><span class="kpi-label">P1 Sales</span><span class="kpi-value">${fmt(data.p1.sales)}</span></div>
            <div class="kpi-card"><span class="kpi-label">P2 Sales</span><span class="kpi-value">${fmt(data.p2.sales)}</span></div>
            <div class="kpi-card"><span class="kpi-label">P1 Receipts</span><span class="kpi-value">${fmt(data.p1.receipts)}</span></div>
            <div class="kpi-card"><span class="kpi-label">P2 Receipts</span><span class="kpi-value">${fmt(data.p2.receipts)}</span></div></div>`;
        return;
    }
    el.innerHTML = '<div class="chart-card"><canvas id="chartDateCompare"></canvas></div><div class="table-wrap"><table id="dateHourlyTable" class="data-table"></table></div>';
    drawDualChart('chartDateCompare', data.chart.labels, data.chart.p1, data.chart.p2);
    buildTableHeader('dateHourlyTable', STATIC_TABLES.dateHourlyTable);
    fillTable('dateHourlyTable', data.rows, r =>
        `<tr>${numCell(r.hour)}${numCell(displayNum('p1_sales', r.p1_sales))}${numCell(displayNum('p2_sales', r.p2_sales))}${numCell(fmtDelta(r.variance))}</tr>`);
}

async function loadTrendCompare(file) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/trend-compare', { method: 'POST', body: fd });
    const json = await res.json();
    if (!json.ok) { alert(json.error); return; }
    const d = json.data;
    const h = d.header;
    document.getElementById('trendCompareResult').innerHTML =
        `<p class="period-badge">🔄 History (${h.prev_days} days: ${h.prev_start} to ${h.prev_end}) VS Current (${h.curr_days} days: ${h.curr_start} to ${h.curr_end})</p>
        <div class="kpi-row">${d.kpis.map(k => {
            const c = k.pct > 0 ? '#2ecc71' : (k.pct < 0 ? '#e74c3c' : 'gray');
            return `<div class="kpi-card"><span class="kpi-label">${esc(k.title)}</span><span class="kpi-value" style="font-size:1rem">Old: ${fmt(k.old)} | New: ${fmt(k.new)}</span><span style="color:${c};font-weight:800">${fmtPct(k.pct)}</span></div>`;
        }).join('')}</div>`;
    buildTableHeader('trendTable', STATIC_TABLES.trendTable);
    fillTable('trendTable', d.rows, r =>
        `<tr>${arCell(r.employee)}${numCell(displayNum('prev_sales', r.prev_sales))}${numCell(displayNum('curr_sales', r.curr_sales))}${numCell(fmtDelta(r.sales_delta))}${numCell(displayNum('prev_recs', r.prev_recs))}${numCell(displayNum('curr_recs', r.curr_recs))}${numCell(displayNum('prev_avg', r.prev_avg))}${numCell(displayNum('curr_avg', r.curr_avg))}${numCell(fmtDelta(r.avg_delta))}${arCell(r.insight)}</tr>`);
}

async function exportTable(tableId, sheetName) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const headers = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim());
    const rows = [...table.querySelectorAll('tbody tr')].map(tr => [...tr.cells].map(td => td.textContent.trim()));
    const res = await fetch('/api/export/table', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headers, rows, sheet_name: sheetName }),
    });
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${sheetName}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
}

async function loadInitial() {
    initStaticTables();
    const res = await fetch('/api/dashboard-data');
    const data = await res.json();
    if (data.has_data) {
        if (data.filter_options?.period) {
            document.getElementById('dateFrom').value = data.filter_options.period.start;
            document.getElementById('dateTo').value = data.filter_options.period.end;
        }
        buildFilterList('empList', data.filter_options?.employees, 'emp');
        buildFilterList('branchList', data.filter_options?.branches, 'branch');
        buildFilterList('shiftList', data.filter_options?.shifts, 'shift');
        buildFilterList('catList', data.filter_options?.categories, 'cat');
        buildFilterList('matList', data.filter_options?.materials, 'mat');
        renderDashboard(data);
    }
}

document.getElementById('dataFile')?.addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData(); fd.append('file', file);
    document.getElementById('uploadStatus').textContent = 'Uploading...';
    const res = await fetch('/api/upload-data', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
        document.getElementById('uploadStatus').textContent = '✓ Data loaded';
        deepSalesCache = null;
        await applyLoadedOptions(data.options);
    } else {
        document.getElementById('uploadStatus').textContent = '✗ ' + data.error;
    }
});

document.getElementById('masterFile')?.addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData(); fd.append('file', file);
    const res = await fetch('/api/upload-master', { method: 'POST', body: fd });
    const data = await res.json();
    document.getElementById('uploadStatus').textContent = data.ok ? `✓ Master: ${data.count} items` : '✗ ' + data.error;
    if (data.ok) {
        deepSalesCache = null;
        if (isDeepSalesTabActive()) await loadDeepSales(true);
    }
});

document.getElementById('applyFilters')?.addEventListener('click', refreshDashboard);
document.querySelectorAll('.mode-btn').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    dailyAvg = btn.dataset.mode === 'daily';
    refreshDashboard();
}));

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    if (tab.dataset.tab === 'deepsales') loadDeepSales(false);
}));

let pendingSubcatMode = false;
document.querySelectorAll('.sub-tab[data-emode]').forEach(tab => tab.addEventListener('click', () => {
    document.querySelectorAll('.sub-tab[data-emode]').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const mode = tab.dataset.emode;
    if (EMP_MODES[mode]?.password) {
        pendingSubcatMode = mode;
        document.getElementById('subcatModal').classList.remove('hidden');
        return;
    }
    loadEmployeeMode(mode);
}));

document.getElementById('subcatOk')?.addEventListener('click', () => {
    loadEmployeeMode('subcategories', document.getElementById('subcatPwd').value);
    document.getElementById('subcatModal').classList.add('hidden');
    document.getElementById('subcatPwd').value = '';
});
document.getElementById('subcatCancel')?.addEventListener('click', () => {
    document.getElementById('subcatModal').classList.add('hidden');
    document.querySelector('.sub-tab[data-emode="overview"]')?.click();
});

document.getElementById('analyzeStagnant')?.addEventListener('click', async () => {
    const res = await fetch('/api/stagnant');
    const data = await res.json();
    buildTableHeader('stagTable', STATIC_TABLES.stagTable);
    fillTable('stagTable', data.rows, r =>
        `<tr>${numCell(r.stagnant_code)}${arCell(r.stagnant_drug)}${numCell(r.alt_code)}${arCell(r.alt_drug)}${numCell(displayNum('alt_qty', r.alt_qty))}${arCell(r.group_match)}</tr>`);
});

let deepSalesCache = null;
let activeDeepMode = 'sales_type_category';
let deepSalesLoading = false;

function isDeepSalesTabActive() {
    return document.getElementById('tab-deepsales')?.classList.contains('active');
}

function setDeepSalesStatus(msg, isError) {
    const status = document.getElementById('deepSalesStatus');
    if (!status) return;
    status.textContent = msg || '';
    status.classList.toggle('status-error', !!isError);
}

function renderDeepSalesMode(mode) {
    if (!deepSalesCache?.ok) return;
    const payload = deepSalesCache[mode];
    if (!payload?.columns?.length) {
        setDeepSalesStatus(window.DEEP_NO_ROWS || 'No rows for this view.', true);
        return;
    }
    renderDynamicTable('deepSalesTable', payload, false);
    const rowCount = payload.rows?.length || 0;
    setDeepSalesStatus(
        rowCount
            ? `${rowCount} rows · ${deepSalesCache.delivery_channels?.length ? 'Channels: ' + deepSalesCache.delivery_channels.join(', ') : ''}`.trim()
            : (window.DEEP_NO_ROWS || 'No matching sales in current filters.'),
        !rowCount
    );
    const chartWrap = document.getElementById('deepSalesChartWrap');
    if (mode === 'delivery_categories' && deepSalesCache.chart?.labels?.length) {
        chartWrap?.classList.remove('hidden');
        drawChart('chartDeepDelivery', 'bar', deepSalesCache.chart.labels, deepSalesCache.chart.values, 'Top Delivery Categories', true);
    } else if (chartWrap) {
        chartWrap.classList.add('hidden');
    }
}

async function loadDeepSales(force) {
    if (deepSalesLoading) return;
    if (!force && deepSalesCache?.ok) {
        renderDeepSalesMode(activeDeepMode);
        return;
    }
    deepSalesLoading = true;
    setDeepSalesStatus(window.DEEP_LOADING || 'Loading analysis...', false);
    try {
        const res = await fetch('/api/deep-sales');
        let data;
        try {
            data = await res.json();
        } catch (_) {
            throw new Error(`Server error (${res.status})`);
        }
        if (!res.ok || !data.ok) {
            deepSalesCache = null;
            document.getElementById('deepSalesInsights')?.classList.add('hidden');
            setDeepSalesStatus(data.error || data.detail || 'Failed to load deep sales analysis', true);
            return;
        }
        deepSalesCache = data;
        const ins = document.getElementById('deepSalesInsights');
        if (ins) {
            ins.classList.remove('hidden');
            const items = (data.insights || []).map(i => `<li dir="auto">${esc(i)}</li>`).join('');
            ins.innerHTML = items ? `<strong>💡 ${esc(window.DEEP_INSIGHTS || 'Key Insights')}</strong><ul class="ai-rec-list">${items}</ul>` : '';
            if (!data.delivery_categories?.rows?.length) {
                ins.innerHTML += `<p class="status-text">${esc(window.DEEP_NO_DELIVERY || '')}</p>`;
            }
        }
        renderDeepSalesMode(activeDeepMode);
    } catch (err) {
        deepSalesCache = null;
        document.getElementById('deepSalesInsights')?.classList.add('hidden');
        setDeepSalesStatus(err.message || 'Failed to load deep sales analysis', true);
    } finally {
        deepSalesLoading = false;
    }
}

document.getElementById('loadDeepSales')?.addEventListener('click', () => loadDeepSales(true));
document.querySelectorAll('.deep-sub').forEach(tab => tab.addEventListener('click', () => {
    document.querySelectorAll('.deep-sub').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    activeDeepMode = tab.dataset.dmode;
    if (deepSalesCache?.ok) renderDeepSalesMode(activeDeepMode);
    else loadDeepSales(false);
}));

document.getElementById('runDateCompare')?.addEventListener('click', runDateCompare);
document.getElementById('trendFile')?.addEventListener('change', e => { if (e.target.files[0]) loadTrendCompare(e.target.files[0]); });

document.querySelectorAll('.export-btn').forEach(btn => btn.addEventListener('click', () =>
    exportTable(btn.dataset.table, btn.dataset.sheet)));

document.querySelectorAll('.link-btn').forEach(btn => btn.addEventListener('click', () => {
    const checked = btn.dataset.action === 'all';
    document.querySelectorAll(`input[data-filter="${btn.dataset.target}"]`).forEach(cb => cb.checked = checked);
}));

document.getElementById('openPwdModal')?.addEventListener('click', () => document.getElementById('pwdModal').classList.remove('hidden'));
document.getElementById('pwdCancel')?.addEventListener('click', () => document.getElementById('pwdModal').classList.add('hidden'));
document.getElementById('pwdSave')?.addEventListener('click', async () => {
    const old_password = document.getElementById('pwdOld').value;
    const new_password = document.getElementById('pwdNew').value;
    const confirm = document.getElementById('pwdConfirm').value;
    if (new_password !== confirm) { document.getElementById('pwdMsg').textContent = 'Passwords do not match'; return; }
    const res = await fetch('/api/change-password', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password, new_password }),
    });
    const data = await res.json();
    document.getElementById('pwdMsg').textContent = data.ok ? '✓ Saved' : '✗ ' + (data.error || 'Error');
    if (data.ok) setTimeout(() => document.getElementById('pwdModal').classList.add('hidden'), 1000);
});

loadInitial();
