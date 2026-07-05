let charts = {};
let dailyAvg = false;
const L = window.TABLE_LABELS || {};

function fmt(n) {
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s ?? '';
    return d.innerHTML;
}

function numCell(v) {
    return `<td class="cell-center">${esc(v)}</td>`;
}

function arCell(v) {
    return `<td class="cell-center" dir="auto">${esc(v)}</td>`;
}

function rankCell(n) {
    return `<td class="cell-center cell-rank">${n}</td>`;
}

const TABLE_COLUMNS = {
    topEmpTable: ['rank', 'name', 'branch', 'shift', 'top_type', 'sales'],
    empOverview: ['rank', 'employee', 'position', 'shift', 'sales', 'receipts', 'avg_receipt', 'materials_per_receipt'],
    empAi: ['rank', 'employee', 'shift', 'tier', 'materials_per_receipt', 'recommendation'],
    prodTable: ['code', 'description', 'category', 'group', 'qty', 'sales'],
    execShiftTable: ['branch', 'shift', 'sales', 'receipts', 'avg'],
    stagTable: ['stagnant_code', 'stagnant_drug', 'alt_code', 'alternative', 'alt_qty'],
};

function buildTableHeader(tableId, columnKeys) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const labels = columnKeys.map(k => L[k] || k);
    table.innerHTML = `<thead><tr>${labels.map(l => `<th class="sortable">${esc(l)}</th>`).join('')}</tr></thead><tbody></tbody>`;
    ensureSortable(table);
}

function ensureSortable(table) {
    if (!table || table.dataset.sortBound === '1') return;
    table.dataset.sortBound = '1';
    table.addEventListener('click', e => {
        const th = e.target.closest('th.sortable');
        if (!th || !table.contains(th)) return;
        const colIndex = [...th.parentNode.children].indexOf(th);
        sortTable(table, colIndex, th);
    });
}

function initSortableTable(table) {
    ensureSortable(table);
}

function sortTable(table, colIndex, th) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const asc = th.dataset.sort !== 'asc';
    table.querySelectorAll('th').forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
        h.dataset.sort = '';
    });
    th.classList.add(asc ? 'sort-asc' : 'sort-desc');
    th.dataset.sort = asc ? 'asc' : 'desc';

    rows.sort((a, b) => {
        const va = a.cells[colIndex]?.textContent.trim() || '';
        const vb = b.cells[colIndex]?.textContent.trim() || '';
        const na = parseFloat(va.replace(/,/g, '').replace(/[^\d.-]/g, ''));
        const nb = parseFloat(vb.replace(/,/g, '').replace(/[^\d.-]/g, ''));
        if (!isNaN(na) && !isNaN(nb) && (va !== '' || vb !== '')) {
            return asc ? na - nb : nb - na;
        }
        return asc ? va.localeCompare(vb, undefined, { numeric: true }) : vb.localeCompare(va, undefined, { numeric: true });
    });
    rows.forEach(r => tbody.appendChild(r));
}

function fillTable(id, rows, fn) {
    const tbody = document.querySelector(`#${id} tbody`);
    if (!tbody) return;
    tbody.innerHTML = (rows || []).map(fn).join('');
}

function buildFilterList(containerId, items, prefix) {
    const el = document.getElementById(containerId);
    el.innerHTML = '';
    (items || []).forEach(v => {
        const id = `${prefix}_${v.replace(/\W/g, '_')}`;
        el.innerHTML += `<label><input type="checkbox" checked data-filter="${prefix}" value="${esc(v)}" id="${id}"> <span dir="auto">${esc(v)}</span></label>`;
    });
}

function getSelectedFilters(prefix) {
    return [...document.querySelectorAll(`input[data-filter="${prefix}"]:checked`)].map(cb => cb.value);
}

function collectFilters() {
    return {
        start_date: document.getElementById('dateFrom').value,
        end_date: document.getElementById('dateTo').value,
        employees: getSelectedFilters('emp'),
        branches: getSelectedFilters('branch'),
        shifts: getSelectedFilters('shift'),
        categories: getSelectedFilters('cat'),
        materials: getSelectedFilters('mat'),
    };
}

function renderDashboard(data) {
    if (!data.has_data) {
        document.getElementById('noData').classList.remove('hidden');
        document.getElementById('dashboardContent').classList.add('hidden');
        return;
    }
    document.getElementById('noData').classList.add('hidden');
    document.getElementById('dashboardContent').classList.remove('hidden');

    const k = data.kpis;
    document.getElementById('kpiSales').textContent = fmt(k.total_sales);
    document.getElementById('kpiReceipts').textContent = fmt(k.total_receipts);
    document.getElementById('kpiAvg').textContent = fmt(k.avg_receipt);
    document.getElementById('kpiPieces').textContent = fmt(k.total_pieces);
    document.getElementById('periodBadge').textContent =
        `${k.period.start} → ${k.period.end} (${k.period.days} days)`;

    drawChart('chartMaterial', 'bar', data.material_chart.labels, data.material_chart.values, 'Material Groups');
    drawChart('chartHourly', 'bar', data.hourly_chart.labels, data.hourly_chart.values, 'Hourly Sales');
    drawChart('chartShift', 'bar', data.shift_chart.labels, data.shift_chart.values, 'Shift Sales');
    drawChart('chartCategory', 'doughnut', data.category_chart.labels, data.category_chart.values, 'Categories');

    fillTable('topEmpTable', data.top_employees, (r, i) =>
        `<tr>${rankCell(i + 1)}${arCell(r.name)}${arCell(r.branch)}${arCell(r.shift)}${arCell(r.top_type)}${numCell(fmt(r.sales))}</tr>`);

    renderEmployees('overview', data.employee_overview);
    fillTable('prodTable', data.top_products, r =>
        `<tr>${numCell(r.code)}${arCell(r.description)}${arCell(r.category)}${arCell(r.material_group)}${numCell(fmt(r.qty))}${numCell(fmt(r.sales))}</tr>`);

    const ex = data.executive;
    document.getElementById('execBrief').innerHTML =
        `<strong>⭐ Top Shift:</strong> <span dir="auto">${esc(ex.best_shift)}</span><br><strong>🔥 Peak Hours:</strong> ${esc((ex.peak_hours || []).join(' & ') || 'N/A')}`;
    fillTable('execShiftTable', ex.shifts_by_branch, r =>
        `<tr>${arCell(r.branch)}${arCell(r.shift)}${numCell(fmt(r.sales))}${numCell(r.receipts)}${numCell(fmt(r.avg_receipt))}</tr>`);
}

function renderEmployees(mode, rows) {
    const cols = mode === 'ai' ? TABLE_COLUMNS.empAi : TABLE_COLUMNS.empOverview;
    buildTableHeader('empTable', cols);
    const tbody = document.querySelector('#empTable tbody');
    if (mode === 'overview') {
        tbody.innerHTML = (rows || []).map((r, i) =>
            `<tr>${rankCell(i + 1)}${arCell(r.employee)}${arCell(r.position)}${arCell(r.shift)}${numCell(fmt(r.sales))}${numCell(r.receipts)}${numCell(fmt(r.avg_receipt))}${numCell(r.materials_per_receipt)}</tr>`
        ).join('');
    } else {
        tbody.innerHTML = (rows || []).map((r, i) =>
            `<tr>${rankCell(i + 1)}${arCell(r.employee)}${arCell(r.shift)}${numCell(r.tier)}${numCell(r.materials_per_receipt)}${arCell(r.recommendation)}</tr>`
        ).join('');
    }
}

function drawChart(canvasId, type, labels, values, label) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (charts[canvasId]) charts[canvasId].destroy();
    const colors = ['#3498db', '#e74c3c', '#27ae60', '#f1c40f', '#9b59b6', '#1abc9c'];
    charts[canvasId] = new Chart(ctx, {
        type,
        data: {
            labels: labels || [],
            datasets: [{ label, data: values || [], backgroundColor: colors.slice(0, labels?.length || 0) }]
        },
        options: { responsive: true, plugins: { legend: { display: type === 'doughnut' } } }
    });
}

async function refreshDashboard() {
    const filters = collectFilters();
    const res = await fetch('/api/filters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters, daily_avg: dailyAvg })
    });
    const data = await res.json();
    if (data.ok) renderDashboard(data.data);
}

function initAllTableHeaders() {
    buildTableHeader('topEmpTable', TABLE_COLUMNS.topEmpTable);
    buildTableHeader('empTable', TABLE_COLUMNS.empOverview);
    buildTableHeader('prodTable', TABLE_COLUMNS.prodTable);
    buildTableHeader('execShiftTable', TABLE_COLUMNS.execShiftTable);
    buildTableHeader('stagTable', TABLE_COLUMNS.stagTable);
}

async function loadInitial() {
    initAllTableHeaders();
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
    const fd = new FormData();
    fd.append('file', file);
    document.getElementById('uploadStatus').textContent = 'Uploading...';
    const res = await fetch('/api/upload-data', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
        document.getElementById('uploadStatus').textContent = '✓ Data loaded';
        if (data.options?.period) {
            document.getElementById('dateFrom').value = data.options.period.start;
            document.getElementById('dateTo').value = data.options.period.end;
        }
        buildFilterList('empList', data.options?.employees, 'emp');
        buildFilterList('branchList', data.options?.branches, 'branch');
        buildFilterList('shiftList', data.options?.shifts, 'shift');
        buildFilterList('catList', data.options?.categories, 'cat');
        buildFilterList('matList', data.options?.materials, 'mat');
        await refreshDashboard();
    } else {
        document.getElementById('uploadStatus').textContent = '✗ ' + data.error;
    }
});

document.getElementById('masterFile')?.addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/upload-master', { method: 'POST', body: fd });
    const data = await res.json();
    document.getElementById('uploadStatus').textContent = data.ok ? `✓ Master: ${data.count} items` : '✗ ' + data.error;
});

document.getElementById('applyFilters')?.addEventListener('click', refreshDashboard);

document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        dailyAvg = btn.dataset.mode === 'daily';
        refreshDashboard();
    });
});

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    });
});

document.querySelectorAll('.sub-tab').forEach(tab => {
    tab.addEventListener('click', async () => {
        document.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const res = await fetch('/api/dashboard-data');
        const data = await res.json();
        renderEmployees(tab.dataset.emode, tab.dataset.emode === 'ai' ? data.employee_ai : data.employee_overview);
    });
});

document.getElementById('analyzeStagnant')?.addEventListener('click', async () => {
    buildTableHeader('stagTable', TABLE_COLUMNS.stagTable);
    const res = await fetch('/api/stagnant');
    const data = await res.json();
    fillTable('stagTable', data.rows, r =>
        `<tr>${numCell(r.stagnant_code)}${arCell(r.stagnant_drug)}${numCell(r.alt_code)}${arCell(r.alt_drug)}${numCell(r.alt_qty)}</tr>`);
});

document.querySelectorAll('.link-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.target;
        const checked = btn.dataset.action === 'all';
        document.querySelectorAll(`input[data-filter="${target}"]`).forEach(cb => cb.checked = checked);
    });
});

loadInitial();
