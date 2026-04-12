"""
生成全书配图（300dpi PNG，适合16开印刷）
用法: python figures/generate_all.py
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from pathlib import Path

# 全局设置
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
DPI = 300
OUT = Path(__file__).parent

# 配色
C_PRIMARY = '#2563EB'    # 蓝
C_SUCCESS = '#16A34A'    # 绿
C_DANGER = '#DC2626'     # 红
C_WARNING = '#F59E0B'    # 黄
C_GRAY = '#6B7280'       # 灰
C_LIGHT = '#F3F4F6'      # 浅灰背景
C_DARK = '#1F2937'       # 深色文字


def fig1_5_timeline():
    """图1-5 三Agent执行时间线对比"""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('图1-5  三Agent执行时间线对比', fontsize=14, fontweight='bold', pad=20)

    y_positions = [7.5, 5, 2.5]
    agents = ['Claude Code\n(Opus 4.6)', 'Codex CLI\n(GPT-5.4)', 'Claw Code\n(DeepSeek-V3)']
    colors = [C_SUCCESS, C_PRIMARY, C_DANGER]

    # Claude Code
    phases_cc = [
        (0, 15, '读文档\n+源文件', C_LIGHT),
        (15, 45, '改3文件', '#DBEAFE'),
        (45, 60, '写测试\n[X]→修复[OK]', '#FEF3C7'),
        (60, 75, '全量验证\n488 passed', '#DCFCE7'),
    ]
    # Codex
    phases_cx = [
        (0, 20, '扫文件树\n+读源文件', C_LIGHT),
        (20, 25, '批量\n授权', '#FEF3C7'),
        (25, 55, '改3文件', '#DBEAFE'),
        (55, 70, '沙箱适配\n78 passed', '#DCFCE7'),
    ]
    # Claw Code
    phases_cw = [
        (0, 15, '读TASK\n+规划', C_LIGHT),
        (15, 25, 'bash\n失败→切换', '#FEF3C7'),
        (25, 55, '读源文件\n(3300行)', '#DBEAFE'),
        (55, 65, '[!] 上下文\n溢出', '#FEE2E2'),
    ]

    all_phases = [phases_cc, phases_cx, phases_cw]

    for i, (y, agent, color, phases) in enumerate(zip(y_positions, agents, colors, all_phases)):
        ax.text(-2, y, agent, ha='right', va='center', fontsize=9, fontweight='bold', color=color)
        for x0, x1, label, fc in phases:
            rect = FancyBboxPatch((x0, y-0.8), x1-x0, 1.6,
                                  boxstyle="round,pad=0.1", facecolor=fc, edgecolor=color, linewidth=1.5)
            ax.add_patch(rect)
            ax.text((x0+x1)/2, y, label, ha='center', va='center', fontsize=7, color=C_DARK)

    # 时间标注
    ax.annotate('~3分钟', xy=(75, 7.5), fontsize=9, color=C_SUCCESS, fontweight='bold')
    ax.annotate('~7分钟', xy=(70, 5), fontsize=9, color=C_PRIMARY, fontweight='bold')
    ax.annotate('失败 [X]', xy=(65, 2.5), fontsize=9, color=C_DANGER, fontweight='bold')

    fig.tight_layout()
    fig.savefig(OUT / 'fig1_5_timeline.png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('[OK] fig1_5_timeline.png')


def fig1_6_fault_chain():
    """图1-6 故障链因果图"""
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis('off')
    ax.set_title('图1-6  三道防线失效的故障链', fontsize=14, fontweight='bold', pad=20)

    nodes = [
        (5, 13, 'DeepSeek不在模型注册表中', C_WARNING, '#FEF3C7'),
        (5, 11, '第一道防线失效：预检跳过', C_DANGER, '#FEE2E2'),
        (5, 9.5, '输出配额 = 64,000（不合理默认值）', C_WARNING, '#FEF3C7'),
        (5, 8, '第二道防线失效：压缩跳过', C_DANGER, '#FEE2E2'),
        (5, 6.5, '145K input + 64K output > 128K窗口', C_WARNING, '#FEF3C7'),
        (5, 5, 'API返回400错误', C_GRAY, C_LIGHT),
        (5, 3.5, '第三道防线失效：400不可重试', C_DANGER, '#FEE2E2'),
        (5, 2, '[X] 任务终止', C_DANGER, '#FEE2E2'),
    ]

    for x, y, text, ec, fc in nodes:
        w = 8 if '第' in text else 7
        rect = FancyBboxPatch((x-w/2, y-0.55), w, 1.1,
                              boxstyle="round,pad=0.15", facecolor=fc, edgecolor=ec, linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y, text, ha='center', va='center', fontsize=9, fontweight='bold', color=C_DARK)

    # 箭头
    for i in range(len(nodes)-1):
        ax.annotate('', xy=(5, nodes[i+1][1]+0.6), xytext=(5, nodes[i][1]-0.6),
                    arrowprops=dict(arrowstyle='->', color=C_GRAY, lw=1.5))

    # 右侧标注
    annotations = [
        (9.5, 11, '不知道窗口大小\n→ 跳过检查'),
        (9.5, 8, '不知道80%阈值\n→ 不触发压缩'),
        (9.5, 3.5, '只重试408/429/5xx\n→ 400直接终止'),
    ]
    for x, y, text in annotations:
        ax.text(x, y, text, ha='center', va='center', fontsize=7, color=C_GRAY,
                style='italic', bbox=dict(boxstyle='round', facecolor='white', edgecolor=C_GRAY, alpha=0.5))

    fig.tight_layout()
    fig.savefig(OUT / 'fig1_6_fault_chain.png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('[OK] fig1_6_fault_chain.png')


def fig2_1_five_principles():
    """图2-1 五原则递进关系"""
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('图2-1  五原则递进关系：每一层的有效性依赖前一层到位', fontsize=13, fontweight='bold', pad=15)

    principles = [
        ('约束\nConstrain', '画红线\n不能做什么', C_DANGER),
        ('告知\nInform', '给地图\n该做什么', C_PRIMARY),
        ('验证\nVerify', '看结果\n做对没有', C_SUCCESS),
        ('纠正\nCorrect', '修错误\n自我恢复', C_WARNING),
        ('人在环中\nHITL', '最后防线\n人工介入', '#7C3AED'),
    ]

    x_positions = [10, 28, 46, 64, 82]
    for i, (x, (name, desc, color)) in enumerate(zip(x_positions, principles)):
        # 圆角矩形
        rect = FancyBboxPatch((x-8, 2), 16, 6,
                              boxstyle="round,pad=0.3", facecolor='white', edgecolor=color, linewidth=2.5)
        ax.add_patch(rect)
        ax.text(x, 6.2, name, ha='center', va='center', fontsize=10, fontweight='bold', color=color)
        ax.text(x, 3.5, desc, ha='center', va='center', fontsize=8, color=C_GRAY)

        # 箭头
        if i < len(principles) - 1:
            ax.annotate('', xy=(x_positions[i+1]-8, 5), xytext=(x+8, 5),
                        arrowprops=dict(arrowstyle='->', color=C_GRAY, lw=2))

    fig.tight_layout()
    fig.savefig(OUT / 'fig2_1_five_principles.png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('[OK] fig2_1_five_principles.png')


def fig2_2_six_layers():
    """图2-2 六层架构图"""
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 14)
    ax.axis('off')
    ax.set_title('图2-2  Harness六层架构模型', fontsize=14, fontweight='bold', pad=20)

    layers = [
        (6, 12, 11, '⑥ 编排层 Orchestration', '多Agent协作 · 任务委托 · 规划', '#7C3AED', '#EDE9FE'),
        (6, 10, 11, '⑤ 验证层 Verification', '对抗式评估 · LoopGuard · 自验证', C_SUCCESS, '#DCFCE7'),
        (3.5, 8, 5.5, '③ 上下文层', 'Prompt组装\nCache边界', C_PRIMARY, '#DBEAFE'),
        (8.5, 8, 5.5, '④ 记忆层', '会话压缩\n长期记忆', C_PRIMARY, '#DBEAFE'),
        (3.5, 5.5, 5.5, '① 约束层', '权限 · 沙箱\n预算熔断', C_DANGER, '#FEE2E2'),
        (8.5, 5.5, 5.5, '② 工具层', '6工具 · MCP\nJSON Schema', C_WARNING, '#FEF3C7'),
    ]

    for x, y, w, name, desc, ec, fc in layers:
        rect = FancyBboxPatch((x-w/2, y-0.9), w, 1.8,
                              boxstyle="round,pad=0.15", facecolor=fc, edgecolor=ec, linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y+0.3, name, ha='center', va='center', fontsize=10, fontweight='bold', color=ec)
        ax.text(x, y-0.4, desc, ha='center', va='center', fontsize=8, color=C_GRAY)

    # 观测贯穿
    rect = FancyBboxPatch((0.5, 3.2), 11, 1.2,
                          boxstyle="round,pad=0.1", facecolor='#F0F9FF', edgecolor=C_GRAY, linewidth=1, linestyle='--')
    ax.add_patch(rect)
    ax.text(6, 3.8, '<-> 观测贯穿所有层（成本追踪 · Token日志 · 行为指标）',
            ha='center', va='center', fontsize=9, color=C_GRAY, style='italic')

    fig.tight_layout()
    fig.savefig(OUT / 'fig2_2_six_layers.png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('[OK] fig2_2_six_layers.png')


def fig3_1_three_defense():
    """图3-1 三层防御模型"""
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis('off')
    ax.set_title('图3-1  约束层的三层防御模型', fontsize=14, fontweight='bold', pad=20)

    layers_data = [
        (5, 10, 'Layer 1: 规则层', 'CLAUDE.md约束 · Prompt指令', '可绕过性：高（Agent可能忽略）', '#FEF3C7', C_WARNING),
        (5, 7, 'Layer 2: 检查层', 'permissions + hooks代码拦截', '可绕过性：中（bash可间接绕过）', '#DBEAFE', C_PRIMARY),
        (5, 4, 'Layer 3: 沙箱层', 'Sandbox执行环境隔离', '可绕过性：低（环境级限制）', '#DCFCE7', C_SUCCESS),
    ]

    for x, y, name, desc, bypass, fc, ec in layers_data:
        rect = FancyBboxPatch((1, y-1.2), 8, 2.4,
                              boxstyle="round,pad=0.2", facecolor=fc, edgecolor=ec, linewidth=2.5)
        ax.add_patch(rect)
        ax.text(x, y+0.5, name, ha='center', va='center', fontsize=11, fontweight='bold', color=ec)
        ax.text(x, y-0.1, desc, ha='center', va='center', fontsize=9, color=C_DARK)
        ax.text(x, y-0.7, bypass, ha='center', va='center', fontsize=8, color=C_GRAY, style='italic')

    # 箭头
    ax.annotate('', xy=(5, 8.3), xytext=(5, 8.8), arrowprops=dict(arrowstyle='->', color=C_GRAY, lw=2))
    ax.annotate('', xy=(5, 5.3), xytext=(5, 5.8), arrowprops=dict(arrowstyle='->', color=C_GRAY, lw=2))

    # 入口和出口
    ax.text(5, 11.5, '[v] 工具调用请求', ha='center', fontsize=10, color=C_DARK)
    ax.text(5, 2.2, '[OK] 安全执行', ha='center', fontsize=10, color=C_SUCCESS, fontweight='bold')

    fig.tight_layout()
    fig.savefig(OUT / 'fig3_1_three_defense.png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('[OK] fig3_1_three_defense.png')


def fig3_2_sandbox_flow():
    """图3-2 Sandbox四步检查流程"""
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 16)
    ax.axis('off')
    ax.set_title('图3-2  Sandbox.check_tool_call() 四步检查', fontsize=13, fontweight='bold', pad=20)

    steps = [
        (5, 14, '工具调用请求', C_DARK, 'white'),
        (5, 12, '① 权限模式检查', C_PRIMARY, '#DBEAFE'),
        (5, 9.5, '② 文件系统检查', C_PRIMARY, '#DBEAFE'),
        (5, 7, '③ 网络隔离检查', C_PRIMARY, '#DBEAFE'),
        (5, 4.5, '④ 危险命令检查', C_PRIMARY, '#DBEAFE'),
        (5, 2, '[OK] 执行工具', C_SUCCESS, '#DCFCE7'),
    ]

    reject_msgs = [
        (9, 12, 'PLAN模式\n禁止写操作'),
        (9, 9.5, '路径不在\nallowed_roots'),
        (9, 7, '禁止curl/wget\n等网络命令'),
        (9, 4.5, 'rm -rf\n被拦截'),
    ]

    for x, y, text, ec, fc in steps:
        w = 6 if '请求' in text or '执行' in text else 5
        rect = FancyBboxPatch((x-w/2, y-0.6), w, 1.2,
                              boxstyle="round,pad=0.15", facecolor=fc, edgecolor=ec, linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y, text, ha='center', va='center', fontsize=10, fontweight='bold',
                color='white' if fc == 'white' else C_DARK)

    # 通过箭头
    for i in range(len(steps)-1):
        ax.annotate('', xy=(5, steps[i+1][1]+0.7), xytext=(5, steps[i][1]-0.7),
                    arrowprops=dict(arrowstyle='->', color=C_SUCCESS, lw=1.5))
        if i > 0 and i < len(steps)-1:
            ax.text(3.8, (steps[i][1] + steps[i+1][1])/2 + 0.3, '通过', fontsize=7, color=C_SUCCESS)

    # 拒绝箭头和消息
    for i, (rx, ry, msg) in enumerate(reject_msgs):
        step_y = steps[i+1][1]
        ax.annotate('', xy=(rx-0.8, ry), xytext=(7.5, step_y),
                    arrowprops=dict(arrowstyle='->', color=C_DANGER, lw=1.2, linestyle='--'))
        ax.text(rx, ry, msg, ha='center', va='center', fontsize=7, color=C_DANGER,
                bbox=dict(boxstyle='round', facecolor='#FEE2E2', edgecolor=C_DANGER, alpha=0.8))

    fig.tight_layout()
    fig.savefig(OUT / 'fig3_2_sandbox_flow.png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('[OK] fig3_2_sandbox_flow.png')


def fig3_3_permission_modes():
    """图3-3 权限模式阶梯"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('图3-3  四种权限模式的信任阶梯', fontsize=13, fontweight='bold', pad=15)

    modes = [
        (2, 2, 'PLAN', '只读模式\n禁止一切写操作', C_SUCCESS, '#DCFCE7'),
        (4, 4, 'ASK', '逐项确认\n每次写操作需审批', C_PRIMARY, '#DBEAFE'),
        (6, 6, 'ACCEPT', '自动批准编辑\n命令仍需确认', C_WARNING, '#FEF3C7'),
        (8, 8, 'BYPASS', '全自动\n无确认（仅限可信环境）', C_DANGER, '#FEE2E2'),
    ]

    for x, y, name, desc, ec, fc in modes:
        rect = FancyBboxPatch((x-1.5, y-0.8), 3, 1.6,
                              boxstyle="round,pad=0.15", facecolor=fc, edgecolor=ec, linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y+0.2, name, ha='center', va='center', fontsize=11, fontweight='bold', color=ec)
        ax.text(x, y-0.4, desc, ha='center', va='center', fontsize=7, color=C_GRAY)

    # 阶梯线
    for i in range(len(modes)-1):
        x1, y1 = modes[i][0]+1.5, modes[i][1]
        x2, y2 = modes[i+1][0]-1.5, modes[i+1][1]
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color=C_GRAY, lw=1.5))

    # 轴标签
    ax.text(0.5, 5, '自\n动\n化\n程\n度\n↑', ha='center', va='center', fontsize=9, color=C_GRAY)
    ax.text(5, 0.5, '信任程度 →', ha='center', fontsize=9, color=C_GRAY)

    fig.tight_layout()
    fig.savefig(OUT / 'fig3_3_permission_modes.png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('[OK] fig3_3_permission_modes.png')


if __name__ == '__main__':
    print('生成全书配图（300dpi PNG）...\n')
    fig1_5_timeline()
    fig1_6_fault_chain()
    fig2_1_five_principles()
    fig2_2_six_layers()
    fig3_1_three_defense()
    fig3_2_sandbox_flow()
    fig3_3_permission_modes()
    print(f'\n全部完成，输出目录: {OUT}/')
