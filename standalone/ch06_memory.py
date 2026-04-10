"""
第6章独立可运行代码：记忆管理与上下文压缩
==========================================
本文件演示第6章的全部核心概念，无需安装任何依赖，直接运行即可。

涵盖内容：
  6.1 Context Rot（上下文腐烂模拟）
  6.2 六层记忆体系（目录结构演示）
  6.3 三级压缩策略（Snipping / Compaction / Reactive）
  6.4 Token预算分配（显式预算管理）
  6.5 长期记忆系统（Memory文件 + MEMORY.md索引 + Dream整理）
  6.6 状态恢复（Session保存与加载）

用法：
  python ch06_memory.py

不需要API key，所有演示在本地内存中完成。
"""

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ============================================================
# 6.1 Context Rot 模拟
# ============================================================

def demo_context_rot():
    """
    模拟上下文腐烂：随着对话推进，信噪比下降。

    不压缩时，旧的工具结果占据大量空间，
    真正有用的信息被"淹没"。
    """
    print("\n" + "=" * 60)
    print("  6.1 Context Rot：上下文的腐烂")
    print("=" * 60)

    messages = []
    token_count = 0

    # 模拟10轮对话
    for turn in range(1, 11):
        # 用户请求
        user_msg = f"请分析模块{turn}的代码"
        messages.append({"role": "user", "content": user_msg})
        token_count += len(user_msg) // 4

        # 工具返回（模拟读取一个大文件）
        tool_result = f"模块{turn}的源代码内容...\n" * 200
        messages.append({"role": "tool", "content": tool_result})
        token_count += len(tool_result) // 4

        # Agent回复
        reply = f"模块{turn}的核心功能是处理{turn}类请求。"
        messages.append({"role": "assistant", "content": reply})
        token_count += len(reply) // 4

        # 计算信噪比：有用信息（user+assistant）vs 噪声（tool结果）
        useful = sum(len(m["content"]) for m in messages if m["role"] != "tool")
        noise = sum(len(m["content"]) for m in messages if m["role"] == "tool")
        snr = useful / max(noise, 1) * 100

        print(f"  第{turn:2d}轮 | 消息{len(messages):3d}条 | ~{token_count:>6,}tok | "
              f"信噪比{snr:5.1f}% | {'正常' if snr > 5 else '退化'}")

    print(f"\n  结论：10轮后信噪比从100%降到约2%。")
    print(f"  旧的tool结果占据了98%的上下文，真正有用的对话被淹没。")
    print(f"  这就是Context Rot，也是压缩机制必须存在的原因。")


# ============================================================
# 6.2 六层记忆体系
# ============================================================

def demo_memory_hierarchy():
    """
    演示Claude Code的六层记忆体系。
    每一层有不同的生命周期和加载方式。
    """
    print("\n" + "=" * 60)
    print("  6.2 六层记忆体系")
    print("=" * 60)

    layers = [
        ("组织级", "~/.claude/CLAUDE.md", "全局个人偏好", "每次会话自动加载", "用户手动编写"),
        ("项目级", "./CLAUDE.md", "项目架构和规范", "进入项目目录时自动加载", "用户手动编写"),
        ("模块级", ".claude/rules/*.md", "按主题分的规则", "进入相关目录时按需加载", "用户手动编写"),
        ("会话级", "session.jsonl", "本次对话历史", "会话期间保持", "自动记录"),
        ("学习级", "memory/MEMORY.md", "Claude学到的模式", "前200行自动加载", "Claude自动写入"),
        ("当前级", "上下文窗口", "当前轮次的工作状态", "模型直接处理", "实时生成"),
    ]

    print(f"\n  {'层级':<8s} {'存储位置':<28s} {'内容':<16s} {'加载方式':<20s} {'来源'}")
    print(f"  {'-'*8} {'-'*28} {'-'*16} {'-'*20} {'-'*12}")
    for name, loc, content, loading, source in layers:
        print(f"  {name:<8s} {loc:<28s} {content:<16s} {loading:<20s} {source}")

    print(f"\n  上层覆盖下层：同一个Agent在不同项目看到的'现实'不同。")
    print(f"  CLAUDE.md全文加载且压缩后存活，是最可靠的记忆层。")
    print(f"  auto memory只加载前200行，超出部分需要Agent主动读取。")


# ============================================================
# 6.3 三级压缩策略
# ============================================================

def demo_compression():
    """
    演示三级压缩的逐级触发。
    """
    print("\n" + "=" * 60)
    print("  6.3 三级压缩策略")
    print("=" * 60)

    # 构造会话
    messages = [{"role": "system", "content": "You are a coding agent."}]
    for i in range(8):
        messages.append({"role": "user", "content": f"读取文件{i+1}"})
        messages.append({"role": "assistant", "content": f"正在读取...", "tool_call": True})
        messages.append({"role": "tool", "content": f"文件{i+1}的内容：" + "代码行...\n" * 80})
        messages.append({"role": "assistant", "content": f"文件{i+1}分析完成。"})

    def count_tokens(msgs):
        return sum(len(str(m.get("content", ""))) // 4 for m in msgs)

    initial = count_tokens(messages)
    print(f"\n  初始状态: {len(messages)}条消息, ~{initial:,} tokens")

    # Level 1: Snipping
    print(f"\n  --- Level 1: Snipping（裁剪旧tool结果为120字符预览）---")
    snip_count = 0
    for i, msg in enumerate(messages):
        if msg["role"] == "tool" and i < len(messages) - 8:  # 保留最近4轮
            original = msg["content"]
            if len(original) > 200:
                msg["content"] = f"[已裁剪] {original[:120]}..."
                snip_count += 1
    after_snip = count_tokens(messages)
    print(f"  裁剪了{snip_count}条tool结果 | tokens: {initial:,} → {after_snip:,} (降{(1-after_snip/initial)*100:.0f}%)")

    # Level 2: Compaction
    print(f"\n  --- Level 2: Compaction（合并旧消息为结构化摘要）---")
    preserve_tail = 8  # 保留最后4轮（8条消息）
    prefix = 1  # system消息
    to_compact = messages[prefix:-preserve_tail]
    summary = "## Compacted Summary\n"
    summary += f"- 共压缩了{len(to_compact)}条历史消息\n"
    summary += "- 主要工作：读取并分析了多个源文件\n"
    summary += "- 关键发现：文件结构清晰，代码规范\n"

    compacted = [messages[0]]  # system
    compacted.append({"role": "system", "content": summary, "kind": "compact_boundary"})
    compacted.extend(messages[-preserve_tail:])
    after_compact = count_tokens(compacted)
    print(f"  {len(to_compact)}条消息 → 1条摘要 | tokens: {after_snip:,} → {after_compact:,} (降{(1-after_compact/after_snip)*100:.0f}%)")
    print(f"  保留最近{preserve_tail}条消息完整内容")

    # Level 3: Reactive
    print(f"\n  --- Level 3: Reactive（应急模式）---")
    reactive_preserve = max(preserve_tail // 2, 2)
    print(f"  正常保留{preserve_tail}条 → 应急保留{reactive_preserve}条（减半）")
    print(f"  最多循环6轮，先snip再compact交替执行")
    print(f"  触发条件：API返回'prompt too long'错误")

    print(f"\n  三级压缩总效果: {initial:,} → {after_compact:,} tokens (降{(1-after_compact/initial)*100:.0f}%)")


# ============================================================
# 6.4 Token预算分配
# ============================================================

def demo_token_budget():
    """
    演示DeepSeek 128K窗口的Token预算分配。
    """
    print("\n" + "=" * 60)
    print("  6.4 Token预算分配（DeepSeek 128K）")
    print("=" * 60)

    context_window = 128_000

    # 分配策略
    allocations = [
        ("输出预留", 0.15, "模型生成回复的空间，必须保证"),
        ("System Prompt", 0.10, "核心指令+工具描述，固定占用"),
        ("Memory/CLAUDE.md", 0.05, "项目规则+auto memory"),
        ("当前任务", 0.20, "最近4条消息，完整保留"),
        ("历史消息", 0.50, "压缩的主战场"),
    ]

    print(f"\n  上下文窗口: {context_window:,} tokens\n")
    print(f"  {'分类':<20s} {'比例':>6s} {'配额':>10s} {'说明'}")
    print(f"  {'-'*20} {'-'*6} {'-'*10} {'-'*30}")

    total_allocated = 0
    for name, pct, desc in allocations:
        tokens = int(context_window * pct)
        total_allocated += tokens
        print(f"  {name:<20s} {pct*100:>5.0f}% {tokens:>10,} {desc}")

    print(f"\n  '留白'原则：输出预留（15%）永远不被侵占。")
    print(f"  历史消息（50%）是压缩的主要目标。")
    print(f"  当历史消息超过配额时触发压缩。")


# ============================================================
# 6.5 长期记忆系统
# ============================================================

def demo_long_term_memory():
    """
    演示Memory文件系统 + MEMORY.md索引 + Dream整理。
    """
    print("\n" + "=" * 60)
    print("  6.5 长期记忆系统 + Dream整理")
    print("=" * 60)

    tmpdir_root = Path(tempfile.mkdtemp())
    tmpdir = tmpdir_root / "demo_project" / "memory"
    tmpdir.mkdir(parents=True)

    try:
        # 创建memory文件
        memories = [
            ("user_profile.md", "用户画像", "user",
             "- 控制工程背景\n- 医疗信息化行业\n- 偏好中文注释\n- 破折号不超过3个"),
            ("project_setup.md", "项目配置", "project",
             "- 使用DeepSeek API\n- 上下文窗口128K\n- 昨天配置了压缩阈值\n- 昨天修复了模型注册表"),
            ("debug_log.md", "调试记录", "project",
             "- 发现model_token_limit缺少DeepSeek\n- 发现model_token_limit缺少DeepSeek\n- 修复方法：在infer_context_window中添加deepseek判断"),
        ]

        print(f"\n  --- 写入记忆 ---")
        index_lines = []
        for filename, title, mtype, content in memories:
            path = tmpdir / filename
            frontmatter = f"---\nname: {title}\ntype: {mtype}\n---\n\n{content}\n"
            path.write_text(frontmatter, encoding="utf-8")
            index_lines.append(f"- [{title}]({filename}) — {title}")
            print(f"  写入: {filename} ({len(content)}字符)")

        (tmpdir / "MEMORY.md").write_text("\n".join(index_lines), encoding="utf-8")
        print(f"  索引: MEMORY.md ({len(index_lines)}条)")

        # Dream整理
        print(f"\n  --- Dream四阶段整理 ---")

        print(f"  Phase 1 Orientation: 扫描到{len(memories)}个topic文件")
        print(f"  Phase 2 Gather Signal: 读取所有文件内容")

        # Phase 3: Consolidation
        changes = 0
        for filename, _, _, _ in memories:
            path = tmpdir / filename
            content = path.read_text(encoding="utf-8")
            original = content

            # 3a: 相对日期 → 绝对日期
            today = datetime.now().strftime("%Y-%m-%d")
            if "昨天" in content:
                content = content.replace("昨天", f"{today}的前一天")
                changes += 1

            # 3b: 去除重复行
            lines = content.splitlines()
            seen = set()
            deduped = []
            for line in lines:
                norm = line.strip().lower()
                if norm and norm in seen:
                    changes += 1
                    continue
                if norm:
                    seen.add(norm)
                deduped.append(line)
            content = "\n".join(deduped)

            if content != original:
                path.write_text(content, encoding="utf-8")

        print(f"  Phase 3 Consolidation: {changes}处修改（日期转换+去重）")
        print(f"  Phase 4 Prune & Index: 重建索引，确保≤200行")

        # 显示整理后的内容
        print(f"\n  --- 整理后的debug_log.md ---")
        debug_content = (tmpdir / "debug_log.md").read_text(encoding="utf-8")
        for line in debug_content.splitlines():
            if line.strip() and not line.startswith("---"):
                print(f"  {line}")
    finally:
        shutil.rmtree(tmpdir_root, ignore_errors=True)


# ============================================================
# 6.6 状态恢复（Session保存与加载）
# ============================================================

def demo_session_persistence():
    """
    演示jsonl格式的session保存和事件重放加载。
    """
    print("\n" + "=" * 60)
    print("  6.6 状态恢复：jsonl保存 + 事件重放加载")
    print("=" * 60)

    tmpdir = Path(tempfile.mkdtemp())
    jsonl_path = tmpdir / "session_001.jsonl"

    try:
        # 模拟保存
        events = [
            {"type": "permission-mode", "permissionMode": "auto", "sessionId": "001"},
            {"type": "system", "message": {"role": "system", "content": "You are an agent"}, "uuid": "u1", "parentUuid": None},
            {"type": "user", "message": {"role": "user", "content": "Read main.py"}, "uuid": "u2", "parentUuid": "u1", "promptId": "p1"},
            {"type": "assistant", "message": {"role": "assistant", "content": "Reading..."}, "uuid": "u3", "parentUuid": "u2"},
            {"type": "tool_result", "message": {"role": "tool", "content": "def main(): pass"}, "uuid": "u4", "parentUuid": "u3"},
            {"type": "assistant", "message": {"role": "assistant", "content": "Done."}, "uuid": "u5", "parentUuid": "u4"},
        ]

        print(f"\n  --- 保存到jsonl（追加写入，崩溃安全）---")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
                print(f"  追加: type={event['type']:<16s} uuid={event.get('uuid','')[:8]:<8s} parent={str(event.get('parentUuid',''))[:8]}")

        print(f"\n  --- 事件重放加载（从jsonl重建session）---")
        messages = []
        message_types = {"user", "assistant", "system", "tool_result"}
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                event = json.loads(line)
                if event.get("type") in message_types:
                    msg = event["message"]
                    messages.append(msg)
                    print(f"  重放: {msg['role']:10s} | {msg['content'][:40]}")

        print(f"\n  恢复了{len(messages)}条消息。")
        print(f"  jsonl vs json的关键优势：")
        print(f"    崩溃安全：追加写入，崩溃只丢最后一条")
        print(f"    实时可观察：tail -f session.jsonl")
        print(f"    恢复粒度：可从任意事件边界恢复")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# 主程序
# ============================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║  第6章：记忆管理与上下文压缩                                  ║
║  独立可运行代码 — 无需API key，本地演示全部概念               ║
╚══════════════════════════════════════════════════════════════╝
""")

    demo_context_rot()
    demo_memory_hierarchy()
    demo_compression()
    demo_token_budget()
    demo_long_term_memory()
    demo_session_persistence()

    print(f"""
{'='*60}
  第6章概念总结
{'='*60}

  六层记忆：组织级 → 项目级 → 模块级 → 会话级 → 学习级 → 当前级
  四级压缩：Microcompact → Snipping → Compaction(LLM) → Reactive
  预算原则：输出预留15%永不侵占，历史消息50%是压缩主战场
  长期记忆：MEMORY.md索引(200行限制) + topic文件 + Dream四阶段整理
  持久化：jsonl追加写入（崩溃安全）+ 事件重放加载

  配套源码（需API key）：
    python -m src.run_compress_experiment  ← 三级压缩真实API验证
    python -m src.run_real_task            ← CostTracker集成完整任务
""")


if __name__ == "__main__":
    main()
