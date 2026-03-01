#!/usr/bin/env bash
# evolve_auto.sh — HydroClaw 自进化流水线
#
# 数据来源:
#   1. HydroMAS 交互日志 (data/interactions/*.jsonl)
#   2. HydroClaw 记忆笔记 (data/memory/*/daily/*.md)
#
# 执行流程:
#   1. 收集近7天交互数据
#   2. 生成改进分析报告
#   3. (可选) 触发 Claude Code 自动开发
#   4. 运行测试门禁
#   5. 安全部署
#   6. 飞书通知结果
#
# 用法:
#   ./evolve_auto.sh [analyze|develop|deploy|full]
#
# 建议通过 cron 每天凌晨 3:00 运行:
#   0 3 * * * cd /home/admin/hydromas && ./evolve_auto.sh full >> /var/log/hydromas-evolve.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
INTERACTION_DIR="${SCRIPT_DIR}/data/interactions"
MEMORY_DIR="${SCRIPT_DIR}/data/memory"
REPORT_DIR="${SCRIPT_DIR}/data/evolution_reports"
LOG_FILE="${SCRIPT_DIR}/data/evolve.log"
DAYS_BACK="${EVOLVE_DAYS_BACK:-7}"
FEISHU_WEBHOOK="${FEISHU_ALERT_WEBHOOK_URL:-}"

# Ensure directories exist
mkdir -p "$INTERACTION_DIR" "$MEMORY_DIR" "$REPORT_DIR"

# --- Logging ---
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# --- Feishu notification ---
notify_feishu() {
    local title="$1"
    local content="$2"
    if [ -n "$FEISHU_WEBHOOK" ]; then
        curl -s -X POST "$FEISHU_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"msg_type\":\"interactive\",\"card\":{\"header\":{\"title\":{\"content\":\"🌊 HydroClaw 自进化: ${title}\",\"tag\":\"plain_text\"}},\"elements\":[{\"tag\":\"markdown\",\"content\":\"${content}\"}]}}" \
            > /dev/null 2>&1 || true
    fi
}

# --- Phase 1: Analyze ---
do_analyze() {
    log "=== Phase 1: 分析交互日志 ==="

    # Count interaction files
    local file_count
    file_count=$(find "$INTERACTION_DIR" -name "interactions_*.jsonl" -mtime -"$DAYS_BACK" 2>/dev/null | wc -l)
    log "发现 $file_count 个近 ${DAYS_BACK} 天的交互日志文件"

    if [ "$file_count" -eq 0 ]; then
        log "无交互日志，跳过分析"
        return 0
    fi

    # Generate evolution report using Python
    local report_file="${REPORT_DIR}/evolution_$(date '+%Y%m%d_%H%M%S').json"
    python3 -c "
import json, sys
sys.path.insert(0, '.')
from hydroclaw.evolution.analyzer import EvolutionAnalyzer
analyzer = EvolutionAnalyzer()
report = analyzer.analyze(days_back=${DAYS_BACK})
# Save JSON report
with open('${report_file}', 'w') as f:
    json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
# Save markdown report
md_file = '${report_file}'.replace('.json', '.md')
with open(md_file, 'w') as f:
    f.write(report.to_markdown())
print(f'Report generated: {len(report.improvements)} improvements found')
print(f'Total interactions: {report.total_interactions}')
print(f'Success rate: {report.success_rate}%')
" 2>&1 | tee -a "$LOG_FILE"

    log "分析报告已保存: $report_file"
    return 0
}

# --- Phase 2: Develop (Claude Code) ---
do_develop() {
    log "=== Phase 2: 自动开发 ==="

    # Find latest report
    local latest_report
    latest_report=$(ls -t "$REPORT_DIR"/evolution_*.md 2>/dev/null | head -1)

    if [ -z "$latest_report" ]; then
        log "无分析报告，先运行分析"
        do_analyze
        latest_report=$(ls -t "$REPORT_DIR"/evolution_*.md 2>/dev/null | head -1)
    fi

    if [ -z "$latest_report" ]; then
        log "仍无分析报告，跳过开发"
        return 0
    fi

    log "基于报告开发: $latest_report"

    # Check if Claude Code is available
    if ! command -v claude &> /dev/null; then
        log "Claude Code 未安装，跳过自动开发"
        notify_feishu "自动开发跳过" "Claude Code 未安装。分析报告: $(basename "$latest_report")"
        return 0
    fi

    # Create development branch
    local branch_name="evolve/$(date '+%Y%m%d')"
    git checkout -b "$branch_name" 2>/dev/null || git checkout "$branch_name" 2>/dev/null || true

    log "开发分支: $branch_name"
    log "注意: 自动开发需要人工审查后才能合并"

    notify_feishu "自动开发启动" "分支: ${branch_name}\\n报告: $(basename "$latest_report")"
    return 0
}

# --- Phase 3: Test ---
do_test() {
    log "=== Phase 3: 测试门禁 ==="

    # Run tests
    log "运行 pytest..."
    if python3 -m pytest tests/ -x -q --tb=short 2>&1 | tail -20 | tee -a "$LOG_FILE"; then
        log "✅ 测试通过"
        return 0
    else
        log "❌ 测试失败"
        notify_feishu "测试失败" "自进化测试未通过，请检查。"
        return 1
    fi
}

# --- Phase 4: Deploy ---
do_deploy() {
    log "=== Phase 4: 安全部署 ==="

    # Check we're on a safe branch
    local current_branch
    current_branch=$(git branch --show-current)

    if [ "$current_branch" = "master" ] || [ "$current_branch" = "main" ]; then
        log "已在主分支，无需额外部署操作"
    else
        log "当前分支: $current_branch (需要人工审查后合并到主分支)"
    fi

    log "✅ 部署检查完成"
    notify_feishu "自进化完成" "分支: ${current_branch}\\n状态: 已通过测试\\n请审查后合并部署"
    return 0
}

# --- Main ---
main() {
    local mode="${1:-analyze}"
    log "====== HydroClaw 自进化流水线启动 (mode: $mode) ======"

    case "$mode" in
        analyze)
            do_analyze
            ;;
        develop)
            do_analyze
            do_develop
            ;;
        test)
            do_test
            ;;
        deploy)
            do_test && do_deploy
            ;;
        full)
            do_analyze
            do_develop
            do_test && do_deploy
            ;;
        *)
            echo "Usage: $0 [analyze|develop|test|deploy|full]"
            exit 1
            ;;
    esac

    log "====== 自进化流水线完成 ======"
}

main "$@"
