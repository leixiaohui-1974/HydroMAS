/**
 * HydroOS-Agent SPA — main application router.
 * HydroOS-Agent 单页应用 — 主路由。
 */

import { initAssistant } from './assistant.js';
import { render as renderDashboard } from './pages/dashboard.js';
import { render as renderSimulation } from './pages/simulation.js';
import { render as renderControl } from './pages/control.js';
import { render as renderPrediction } from './pages/prediction.js';
import { render as renderFourPred } from './pages/fourpred.js';
import { render as renderODD } from './pages/odd.js';
import { render as renderDesign } from './pages/design.js';
import { render as renderData } from './pages/data.js';
import { render as renderEvaluation } from './pages/evaluation.js';
import { render as renderReports } from './pages/reports.js';

// ---------- Navigation Definition ----------

const NAV_ITEMS = {
    dashboard:      { label: '仪表盘',    en: 'Dashboard',      icon: 'monitor',        render: renderDashboard },
    simulation:     { label: '仿真模拟',  en: 'Simulation',     icon: 'play-circle',    render: renderSimulation },
    control:        { label: '控制管理',  en: 'Control',        icon: 'sliders',        render: renderControl },
    prediction:     { label: '智能预测',  en: 'Prediction',     icon: 'trending-up',    render: renderPrediction },
    fourpred:       { label: '四预系统',  en: 'Four-Pred',      icon: 'alert-triangle', render: renderFourPred },
    scheduling:     { label: '调度优化',  en: 'Scheduling',     icon: 'calendar',       render: renderScheduling },
    odd:            { label: '安全监测',  en: 'ODD Monitor',    icon: 'shield',         render: renderODD },
    design:         { label: '优化设计',  en: 'Design',         icon: 'cpu',            render: renderDesign },
    data:           { label: '数据管理',  en: 'Data',           icon: 'database',       render: renderData },
    identification: { label: '系统辨识',  en: 'Identification', icon: 'crosshair',      render: renderIdentification },
    evaluation:     { label: '性能评价',  en: 'Evaluation',     icon: 'award',          render: renderEvaluation },
    reports:        { label: '报告生成',  en: 'Reports',        icon: 'file-text',      render: renderReports },
};

// SVG icons (inline for zero dependencies)
const ICONS = {
    'monitor':        '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
    'play-circle':    '<circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>',
    'sliders':        '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
    'trending-up':    '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    'alert-triangle': '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    'calendar':       '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    'shield':         '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    'cpu':            '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
    'database':       '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    'crosshair':      '<circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/>',
    'award':          '<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>',
    'file-text':      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
};

function svgIcon(name) {
    const path = ICONS[name] || ICONS['monitor'];
    return `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

// ---------- Role Config ----------

const ROLE_MODULES = {
    operator: ['dashboard', 'control', 'fourpred', 'odd', 'reports'],
    engineer: ['dashboard', 'simulation', 'design', 'control', 'identification'],
    analyst:  ['dashboard', 'prediction', 'data', 'evaluation', 'reports'],
    admin:    Object.keys(NAV_ITEMS),
};

const ROLE_LABELS = {
    operator: '运营', engineer: '设计', analyst: '分析', admin: '管理',
};

let currentRole = null;
let currentPage = null;

// ---------- Simple inline page renderers for modules without dedicated files ----------

async function renderScheduling(container) {
    const { apiPost, showLoader, fmt } = await import('./api.js');
    container.innerHTML = `
        <div class="card">
            <div class="card-header"><h3>调度优化 / Schedule Optimization</h3></div>
            <div class="form-group">
                <label>需求预测 (逗号分隔)</label>
                <textarea id="sched-demand" class="form-control" rows="2" style="font-family:var(--font-mono);font-size:0.8rem">${
                    Array.from({length:24}, (_,i) => (0.01 + 0.01*Math.sin(i*Math.PI/12)).toFixed(4)).join(', ')
                }</textarea>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>供水能力 (m³/s)</label>
                    <input id="sched-cap" class="form-control" type="number" value="0.04" step="0.005">
                </div>
                <div class="form-group">
                    <label>方法</label>
                    <select id="sched-method" class="form-control"><option value="lp">LP 线性规划</option><option value="rule">规则 Rule-based</option></select>
                </div>
            </div>
            <button id="sched-run" class="btn btn-primary">优化调度 / Optimize</button>
            <div id="sched-result" style="margin-top:1rem"><p style="color:var(--text-muted)">配置后运行</p></div>
        </div>
    `;
    document.getElementById('sched-run').addEventListener('click', async () => {
        const el = document.getElementById('sched-result');
        showLoader(el);
        try {
            const demand = document.getElementById('sched-demand').value.split(',').map(s => parseFloat(s.trim()));
            const result = await apiPost('/api/scheduling/run', {
                demand_forecast: demand,
                supply_capacity: +document.getElementById('sched-cap').value,
                method: document.getElementById('sched-method').value,
            });
            el.innerHTML = `<div class="result-block">${JSON.stringify(result, null, 2)}</div>`;
        } catch (err) {
            el.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
        }
    });
}

async function renderIdentification(container) {
    const { apiPost, showLoader, fmt } = await import('./api.js');
    container.innerHTML = `
        <div class="card">
            <div class="card-header"><h3>系统参数辨识 / System Identification</h3></div>
            <div class="alert alert-info">先运行开环仿真获取数据，然后进行参数辨识。</div>
            <button id="ident-run" class="btn btn-primary">运行辨识流程 / Run</button>
            <div id="ident-result" style="margin-top:1rem"><p style="color:var(--text-muted)">点击运行</p></div>
        </div>
    `;
    document.getElementById('ident-run').addEventListener('click', async () => {
        const el = document.getElementById('ident-result');
        showLoader(el);
        try {
            // First simulate to get data
            const sim = await apiPost('/api/simulation/run', {
                duration: 200, dt: 1.0, initial_h: 0.5,
                q_in_profile: [[0, 0.01], [60, 0.03], [120, 0.01]],
            });
            // Then identify
            const result = await apiPost('/api/identification/run', {
                observed_h: sim.water_level,
                observed_q_out: sim.outflow,
                model_type: 'nonlinear',
            });
            el.innerHTML = `
                <div class="card-grid card-grid-3" style="margin-bottom:0.75rem">
                    <div class="stat-card"><div class="stat-label">Tank Area</div><div class="stat-value primary">${fmt(result.estimated_params?.area, 3)}</div></div>
                    <div class="stat-card"><div class="stat-label">Cd</div><div class="stat-value info">${fmt(result.estimated_params?.cd, 3)}</div></div>
                    <div class="stat-card"><div class="stat-label">拟合误差</div><div class="stat-value">${fmt(result.fit_error, 6)}</div></div>
                </div>
                <div class="result-block">${JSON.stringify(result, null, 2)}</div>
            `;
        } catch (err) {
            el.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
        }
    });
}

// ---------- App Initialization ----------

function init() {
    // Role selection
    document.querySelectorAll('.role-card').forEach(card => {
        card.addEventListener('click', () => {
            const role = card.dataset.role;
            selectRole(role);
        });
    });

    // Assistant toggle
    document.getElementById('assistant-toggle').addEventListener('click', toggleAssistant);
    document.getElementById('assistant-close').addEventListener('click', toggleAssistant);

    // Role switch
    document.getElementById('role-switch-btn').addEventListener('click', () => {
        document.getElementById('role-overlay').classList.remove('hidden');
        document.getElementById('app').classList.add('hidden');
    });

    // Handle hash navigation
    window.addEventListener('hashchange', () => {
        const page = location.hash.replace('#', '') || 'dashboard';
        navigateTo(page);
    });
}

function selectRole(role) {
    currentRole = role;
    document.getElementById('role-overlay').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');

    // Update role badge
    document.getElementById('role-switch-btn').textContent = ROLE_LABELS[role] || role;

    // Build nav
    buildNav(role);

    // Init assistant
    initAssistant(role);

    // Navigate to dashboard
    navigateTo(location.hash.replace('#', '') || 'dashboard');
}

function buildNav(role) {
    const nav = document.getElementById('sidebar-nav');
    const modules = ROLE_MODULES[role] || ROLE_MODULES.admin;

    nav.innerHTML = modules.map(key => {
        const item = NAV_ITEMS[key];
        if (!item) return '';
        return `<div class="nav-item" data-page="${key}">${svgIcon(item.icon)}<span>${item.label}</span></div>`;
    }).join('');

    nav.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', () => {
            location.hash = el.dataset.page;
        });
    });
}

function navigateTo(page) {
    if (!NAV_ITEMS[page]) page = 'dashboard';
    currentPage = page;

    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === page);
    });

    // Update header
    const item = NAV_ITEMS[page];
    document.getElementById('page-title').textContent = `${item.label} / ${item.en}`;

    // Render page
    const content = document.getElementById('page-content');
    content.innerHTML = '<div class="loader"><div class="spinner"></div></div>';
    item.render(content).catch(err => {
        content.innerHTML = `<div class="alert alert-danger">页面加载失败: ${err.message}</div>`;
    });
}

function toggleAssistant() {
    document.getElementById('app').classList.toggle('assistant-open');
}

// Boot
init();
