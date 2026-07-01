let charts = {};
let dailyAvg = false;
let filterState = {};

function fmt(n) {
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function buildFilterList(containerId, items, prefix) {
    const el = document.getElementById(containerId);
    el.innerHTML = '';
    (items || []).forEach(v => {
        const id = `${prefix}_${v.replace(/\W/g, '_')}`;
        el.innerHTML += `<label><input type="checkbox" checked data-filter="${prefix}" value="${v.replace(/"/g, '&quot;')}" id="${id}"> ${v}</label>`;
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

    fillTable('topEmpTable', data.top_employees, r =>
        `<tr><td>${r.name}</td><td>${r.branch}</td><td>${r.shift}</td><td>${r.top_type}</td><td>${fmt(r.sales)}</td></tr>`);

    renderEmployees('overview', data.employee_overview);
    fillTable('prodTable', data.top_products, r =>
        `<tr><td>${r.code}</td><td>${r.description}</td><td>${r.category}</td><td>${r.material_group}</td><td>${fmt(r.qty)}</td><td>${fmt(r.sales)}</td></tr>`);

    const ex = data.executive;
    document.getElementById('execBrief').innerHTML =
        `<strong>⭐ Top Shift:</strong> ${ex.best_shift}<br><strong>🔥 Peak Hours:</strong> ${(ex.peak_hours || []).join(' & ') || 'N/A'}`;
    fillTable('execShiftTable', ex.shifts_by_branch, r =>
        `<tr><td>${r.branch}</td><td>${r.shift}</td><td>${fmt(r.sales)}</td><td>${r.receipts}</td><td>${fmt(r.avg_receipt)}</td></tr>`);
}

function renderEmployees(mode, rows) {
    const tbody = document.querySelector('#empTable tbody');
    if (mode === 'overview') {
        tbody.innerHTML = rows.map(r =>
            `<tr><td>${r.employee}</td><td>${r.position}</td><td>${r.shift}</td><td>${fmt(r.sales)}</td><td>${r.receipts}</td><td>${fmt(r.avg_receipt)}</td><td>${r.materials_per_receipt}</td></tr>`
        ).join('');
    } else {
        tbody.innerHTML = rows.map(r =>
            `<tr><td>${r.employee}</td><td>${r.shift}</td><td>${r.tier}</td><td>${r.materials_per_receipt}</td><td>${r.recommendation}</td></tr>`
        ).join('');
    }
}

function fillTable(id, rows, fn) {
    const tbody = document.querySelector(`#${id} tbody`);
    tbody.innerHTML = (rows || []).map(fn).join('');
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

async function loadInitial() {
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
    const res = await fetch('/api/stagnant');
    const data = await res.json();
    fillTable('stagTable', data.rows, r =>
        `<tr><td>${r.stagnant_code}</td><td>${r.stagnant_drug}</td><td>${r.alt_code}</td><td>${r.alt_drug}</td><td>${r.alt_qty}</td></tr>`);
});

document.querySelectorAll('.link-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.target;
        const checked = btn.dataset.action === 'all';
        document.querySelectorAll(`input[data-filter="${target}"]`).forEach(cb => cb.checked = checked);
    });
});

loadInitial();
