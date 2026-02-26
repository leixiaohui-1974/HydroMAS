/**
 * Reports page — generate and view Markdown reports.
 * 报告页面 — 生成和查看 Markdown 报告。
 */

import { apiPost, showLoader } from '../api.js';

export async function render(container) {
    container.innerHTML = `
        <div class="card-grid card-grid-3">
            <div class="card" style="cursor:pointer" id="rpt-control-card">
                <div class="card-header"><h3>控制系统报告</h3></div>
                <p style="color:var(--text-secondary);font-size:0.85rem">运行控制系统设计 Skill 并生成报告</p>
                <button id="rpt-control" class="btn btn-primary" style="margin-top:0.75rem;width:100%">生成报告</button>
            </div>
            <div class="card" style="cursor:pointer">
                <div class="card-header"><h3>ODD 安全报告</h3></div>
                <p style="color:var(--text-secondary);font-size:0.85rem">运行 ODD 评估 Skill 并生成安全报告</p>
                <button id="rpt-odd" class="btn btn-primary" style="margin-top:0.75rem;width:100%">生成报告</button>
            </div>
            <div class="card" style="cursor:pointer">
                <div class="card-header"><h3>全生命周期报告</h3></div>
                <p style="color:var(--text-secondary);font-size:0.85rem">运行全生命周期 Skill 并生成综合报告</p>
                <button id="rpt-lifecycle" class="btn btn-primary" style="margin-top:0.75rem;width:100%">生成报告</button>
            </div>
        </div>
        <div class="card" style="margin-top:1rem">
            <div class="card-header"><h3>报告预览 / Report Preview</h3></div>
            <div id="rpt-preview"><p style="color:var(--text-muted)">点击上方按钮生成报告</p></div>
        </div>
    `;

    document.getElementById('rpt-control').addEventListener('click', genControlReport);
    document.getElementById('rpt-odd').addEventListener('click', genODDReport);
    document.getElementById('rpt-lifecycle').addEventListener('click', genLifecycleReport);
}

async function genControlReport() {
    const el = document.getElementById('rpt-preview');
    showLoader(el);

    try {
        // First run the control design skill
        const skillResult = await apiPost('/api/skills/control-design', {
            controller_type: 'PID', setpoint: 1.0, duration: 200, dt: 1.0,
        });

        if (!skillResult.success) throw new Error(skillResult.error || 'Skill failed');

        // Generate report
        const report = await apiPost('/api/skills/report/control', skillResult.data);
        renderMarkdown(el, report.report_markdown);
    } catch (err) {
        el.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

async function genODDReport() {
    const el = document.getElementById('rpt-preview');
    showLoader(el);

    try {
        const skillResult = await apiPost('/api/skills/run', {
            skill_name: 'odd_assessment', params: {},
        });

        if (skillResult.status !== 'completed') throw new Error(skillResult.error || 'Skill failed');

        const report = await apiPost('/api/skills/report/odd', skillResult.data);
        renderMarkdown(el, report.report_markdown);
    } catch (err) {
        el.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

async function genLifecycleReport() {
    const el = document.getElementById('rpt-preview');
    showLoader(el);

    try {
        const skillResult = await apiPost('/api/skills/lifecycle', {});

        if (!skillResult.success) throw new Error(skillResult.error || 'Skill failed');

        const report = await apiPost('/api/skills/report/lifecycle', skillResult.data);
        renderMarkdown(el, report.report_markdown);
    } catch (err) {
        el.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

function renderMarkdown(el, md) {
    // Simple markdown → HTML conversion
    let html = md
        .replace(/^### (.*)/gm, '<h3>$1</h3>')
        .replace(/^## (.*)/gm, '<h2>$1</h2>')
        .replace(/^# (.*)/gm, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\- (.*)/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\|(.+)\|/g, (match) => {
            const cells = match.split('|').filter(c => c.trim());
            if (cells.every(c => c.trim().match(/^-+$/))) return '';
            return '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
        });

    // Wrap table rows
    html = html.replace(/(<tr>.*?<\/tr>\s*)+/gs, '<table class="data-table">$&</table>');

    el.innerHTML = `<div class="report-preview"><p>${html}</p></div>`;
}
