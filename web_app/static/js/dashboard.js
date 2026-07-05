let charts = {};
let dailyAvg = false;
let validDates = [];
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
    overview: { api: null, rank: true },
    sales_types: { api: 'sales_types', rank: true },
    subcategories: { api: 'subcategories', rank: false, password: true },
    efficiency: { api: 'efficiency', rank: false },
    ai: { api: 'ai', rank: true },
};

function fmt(n) { return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }); }
function esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }
function lbl(k) { return L[k] || k; }
function numCell(v) { return `<td class="cell-center">${esc(v)}</td>`; }
function arCell(v) { return `<td class="cell-center" dir="auto">${esc(v)}</td>`; }
function rankCell(n) { return `<td class="cell-center cell-rank">${n}</td>`; }

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
        const na = parseFloat(va.replace(/,/g, '').replace(/[^\d.-]/g, ''));
        const nb = parseFloat(vb.replace(/,/g, '').replace(/[^\d.-]/g, ''));
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
    const labels = payload.column_labels || cols.map(c => lbl(c));
    if (withRank) {
        buildTableHeader(tableId, ['rank', ...cols], [lbl('rank'), ...labels]);
    } else {
        buildTableHeader(tableId, cols, labels);
    }
    const tbody = document.querySelector(`#${tableId} tbody`);
    tbody.innerHTML = (payload.rows || []).map((row, i) => {
        const tag = row.is_subtotal ? ' class="row-subtotal"' : '';
        let cells = withRank ? rankCell(i + 1) : '';
        cols.forEach(c => {
            const v = row[c];
            cells += (typeof v === 'number' || /^[\d,.]+$/.test(String(v))) ? numCell(v) : arCell(v);
        });
        return `<tr${tag}>${cells}</tr>`;
    }).join('');
}

function drawChart(canvasId, type, labels, values, label, horizontal) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (charts[canvasId]) charts[canvasId].destroy();
    const colors = ['#3498db', '#e74c3c', '#27ae60', '#f1c40f', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
    charts[canvasId] = new Chart(ctx, {
        type,
        data: { labels: labels || [], datasets: [{ label, data: values || [], backgroundColor: colors.slice(0, labels?.length || 0) }] },
        options: { indexAxis: horizontal ? 'y' : 'x', responsive: true, plugins: { legend: { display: type === 'doughnut' || type === 'pie' } } }
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
        options: { responsive: true }
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
        return;
    }
    document.getElementById('noData').classList.add('hidden');
    document.getElementById('dashboardContent').classList.remove('hidden');
    validDates = data.valid_dates || [];

    const k = data.kpis;
    document.getElementById('kpiSales').textContent = fmt(k.total_sales);
    document.getElementById('kpiReceipts').textContent = fmt(k.total_receipts);
    document.getElementById('kpiAvg').textContent = fmt(k.avg_receipt);
    document.getElementById('kpiPieces').textContent = fmt(k.total_pieces);
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
        `<tr>${rankCell(i + 1)}${arCell(r.name)}${arCell(r.branch)}${arCell(r.shift)}${arCell(r.top_type)}${numCell(fmt(r.sales))}</tr>`);

    renderDynamicTable('empTable', data.employee_overview, true);

    fillTable('prodTable', data.top_products, r =>
        `<tr>${numCell(r.code)}${arCell(r.description)}${arCell(r.category)}${arCell(r.material_group)}${numCell(fmt(r.qty))}${numCell(fmt(r.sales))}</tr>`);

    const ex = data.executive;
    document.getElementById('execBrief').innerHTML =
        `<strong>⭐ Top Shift:</strong> <span dir="auto">${esc(ex.best_shift)}</span><br><strong>🔥 Peak Hours:</strong> ${esc((ex.peak_hours || []).join(' & ') || 'N/A')}`;
    fillTable('execShiftTable', ex.shifts_by_branch, r =>
        `<tr>${arCell(r.branch)}${arCell(r.shift)}${numCell(fmt(r.sales))}${numCell(r.receipts)}${numCell(fmt(r.avg_receipt))}</tr>`);
    fillTable('execPharTable', ex.pharmacists, r =>
        `<tr>${arCell(r.name)}${arCell(r.branch)}${arCell(r.shift)}${numCell(fmt(r.sales))}${numCell(r.receipts)}${numCell(fmt(r.avg_receipt))}${arCell(r.top_sales_type)}${arCell(r.top_category)}${arCell(r.evaluation)}</tr>`);

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
    if (cfg.api === null) {
        const res = await fetch('/api/dashboard-data');
        const data = await res.json();
        renderDynamicTable('empTable', data.employee_overview, true);
        return;
    }
    const res = await fetch(`/api/employee/${cfg.api}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password || '' }),
    });
    const json = await res.json();
    if (!json.ok) { alert(json.error || 'Access denied'); return; }
    renderDynamicTable('empTable', json.data, cfg.rank);
}

async function refreshDashboard() {
    const res = await fetch('/api/filters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters: collectFilters(), daily_avg: dailyAvg }),
    });
    const data = await res.json();
    if (data.ok) renderDashboard(data.data);
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
        `<tr>${numCell(r.hour)}${numCell(fmt(r.p1_sales))}${numCell(fmt(r.p2_sales))}${numCell(r.variance)}</tr>`);
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
            return `<div class="kpi-card"><span class="kpi-label">${esc(k.title)}</span><span class="kpi-value" style="font-size:1rem">Old: ${fmt(k.old)} | New: ${fmt(k.new)}</span><span style="color:${c};font-weight:800">${k.pct > 0 ? '+' : ''}${k.pct.toFixed(1)}%</span></div>`;
        }).join('')}</div>`;
    buildTableHeader('trendTable', STATIC_TABLES.trendTable);
    fillTable('trendTable', d.rows, r =>
        `<tr>${arCell(r.employee)}${numCell(fmt(r.prev_sales))}${numCell(fmt(r.curr_sales))}${numCell(r.sales_delta)}${numCell(fmt(r.prev_recs))}${numCell(fmt(r.curr_recs))}${numCell(fmt(r.prev_avg))}${numCell(fmt(r.curr_avg))}${numCell(r.avg_delta)}${arCell(r.insight)}</tr>`);
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
        await refreshDashboard();
        const r2 = await fetch('/api/dashboard-data');
        const d2 = await r2.json();
        buildFilterList('empList', d2.filter_options?.employees, 'emp');
        buildFilterList('branchList', d2.filter_options?.branches, 'branch');
        buildFilterList('shiftList', d2.filter_options?.shifts, 'shift');
        buildFilterList('catList', d2.filter_options?.categories, 'cat');
        buildFilterList('matList', d2.filter_options?.materials, 'mat');
        if (d2.filter_options?.period) {
            document.getElementById('dateFrom').value = d2.filter_options.period.start;
            document.getElementById('dateTo').value = d2.filter_options.period.end;
        }
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
}));

let pendingSubcatMode = false;
document.querySelectorAll('.sub-tab').forEach(tab => tab.addEventListener('click', () => {
    document.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
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
        `<tr>${numCell(r.stagnant_code)}${arCell(r.stagnant_drug)}${numCell(r.alt_code)}${arCell(r.alt_drug)}${numCell(r.alt_qty)}${arCell(r.group_match)}</tr>`);
});

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
