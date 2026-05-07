"""harness_py_pro新增模块的基础测试。"""
import sys
sys.path.insert(0, '.')

import tempfile
import json
from pathlib import Path
import pytest

# === checkpoint.py ===
def test_checkpoint_create_and_list():
    from harness_py_pro.checkpoint import FileCheckpoint
    with tempfile.TemporaryDirectory() as d:
        cp = FileCheckpoint(Path(d))
        # 创建一个文件（.txt在_list_tracked_files的扫描后缀中）
        (Path(d) / 'test.txt').write_text('hello')
        cid = cp.create('test')
        assert cid
        checkpoints = cp.list_checkpoints()
        assert len(checkpoints) >= 1

def test_checkpoint_rewind():
    from harness_py_pro.checkpoint import FileCheckpoint
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'test.txt'
        p.write_text('original')
        cp = FileCheckpoint(Path(d))
        cid = cp.create('before edit')
        p.write_text('modified')
        assert p.read_text() == 'modified'
        restored = cp.rewind(cid)
        assert p.read_text() == 'original'

# === git_ops.py ===
def test_git_ops_is_git_repo():
    from harness_py_pro.git_ops import is_git_repo
    # 临时目录肯定不是git repo
    with tempfile.TemporaryDirectory() as d:
        assert is_git_repo(Path(d)) == False

def test_git_ops_current_branch_fallback():
    from harness_py_pro.git_ops import current_branch
    # 非git目录应返回'HEAD'（fallback值）
    with tempfile.TemporaryDirectory() as d:
        branch = current_branch(Path(d))
        assert branch == 'HEAD'

# === mcp_client.py ===
def test_mcp_client_manager_init():
    from harness_py_pro.mcp_client import McpClientManager, McpServerConfig
    mgr = McpClientManager()
    assert mgr.all_tools() == []
    mgr.add_server(McpServerConfig(name='test', command='echo'))
    # add_server创建了McpClient但还没connect，tool_map仍为空
    assert mgr.all_tools() == []

def test_mcp_tool_schema():
    from harness_py_pro.mcp_client import McpTool
    tool = McpTool(name='query', description='Run query', input_schema={'type': 'object'}, server_name='db')
    assert tool.name == 'query'
    assert tool.server_name == 'db'

# === skills.py ===
def test_skill_frontmatter_parse():
    from harness_py_pro.skills import parse_skill_frontmatter
    text = '---\nname: test-skill\ndescription: A test\nversion: 1.0\n---\n\nSkill content here.'
    meta, content = parse_skill_frontmatter(text)
    assert meta['name'] == 'test-skill'
    assert 'Skill content' in content

def test_skill_registry_discover():
    from harness_py_pro.skills import SkillRegistry
    with tempfile.TemporaryDirectory() as d:
        skill_dir = Path(d) / 'my-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text('---\nname: demo\ndescription: Demo skill\nversion: 1.0\n---\n\nDo stuff.')
        reg = SkillRegistry()
        reg.discover(Path(d))
        skills = reg.list_skills()
        assert len(skills) >= 1
        assert skills[0]['name'] == 'demo'

# === plugins.py ===
def test_plugin_manifest_parse():
    from harness_py_pro.plugins import PluginManifest
    m = PluginManifest(name='test-plugin', version='1.0', description='Test')
    assert m.name == 'test-plugin'

def test_plugin_loader_discover_empty():
    from harness_py_pro.plugins import PluginLoader
    with tempfile.TemporaryDirectory() as d:
        loader = PluginLoader()
        plugins = loader.discover(Path(d))
        assert plugins == []

# === tasks.py ===
def test_background_task_create():
    from harness_py_pro.tasks import BackgroundTaskManager, TaskStatus
    with tempfile.TemporaryDirectory() as d:
        mgr = BackgroundTaskManager(Path(d))
        tid = mgr.create('echo hello', label='test')
        assert tid
        task = mgr.get(tid)
        assert task.status == TaskStatus.PENDING

def test_background_task_list():
    from harness_py_pro.tasks import BackgroundTaskManager
    with tempfile.TemporaryDirectory() as d:
        mgr = BackgroundTaskManager(Path(d))
        mgr.create('echo 1')
        mgr.create('echo 2')
        assert len(mgr.list_tasks()) == 2

# === mailbox.py ===
def test_mailbox_send_receive():
    from harness_py_pro.mailbox import Mailbox
    with tempfile.TemporaryDirectory() as d:
        mb = Mailbox(Path(d))
        mb.send('alice', 'bob', 'task_result', 'plan.md已生成')
        msgs = mb.receive('bob')
        assert len(msgs) >= 1
        assert msgs[0].sender == 'alice'
        assert 'plan.md' in msgs[0].content

def test_mailbox_broadcast():
    from harness_py_pro.mailbox import Mailbox
    with tempfile.TemporaryDirectory() as d:
        mb = Mailbox(Path(d))
        # 先发消息创建收件箱文件，这样broadcast才有已知agent
        mb.send('coordinator', 'worker_a', 'status', 'init')
        mb.send('coordinator', 'worker_b', 'status', 'init')
        # 广播给所有已知agent（除发送者外）
        mb.broadcast('coordinator', 'status', '全部就绪')
        msgs_a = mb.receive('worker_a', unread_only=False)
        # worker_a应收到init + broadcast共2条
        assert len(msgs_a) >= 2
        assert any('全部就绪' in m.content for m in msgs_a)

# === lsp.py ===
def test_code_intelligence_index():
    from harness_py_pro.lsp import CodeIntelligence
    # 使用项目根目录下的harness_py包
    project_root = Path(__file__).resolve().parent.parent / 'harness_py'
    ci = CodeIntelligence(project_root)
    ci.index()
    symbols = ci.find_symbol('LoopGuard')
    assert len(symbols) >= 1
    assert symbols[0].kind == 'class'

def test_code_intelligence_outline():
    from harness_py_pro.lsp import CodeIntelligence
    project_root = Path(__file__).resolve().parent.parent / 'harness_py'
    ci = CodeIntelligence(project_root)
    ci.index()
    outline = ci.file_outline('loop_guard.py')
    assert len(outline) >= 1

# === cron.py ===
def test_cron_register_and_list():
    from harness_py_pro.cron import CronScheduler
    with tempfile.TemporaryDirectory() as d:
        sched = CronScheduler(Path(d))
        jid = sched.register('cleanup', '每30分钟', 'python cleanup.py', interval_seconds=1800)
        assert jid
        jobs = sched.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].name == 'cleanup'

def test_cron_enable_disable():
    from harness_py_pro.cron import CronScheduler
    with tempfile.TemporaryDirectory() as d:
        sched = CronScheduler(Path(d))
        jid = sched.register('backup', '每天', 'python backup.py', interval_seconds=86400)
        sched.disable(jid)
        jobs = sched.list_jobs()
        assert not jobs[0].enabled
        sched.enable(jid)
        jobs = sched.list_jobs()
        assert jobs[0].enabled

# === hot_reload.py ===
def test_config_watcher_no_change():
    from harness_py_pro.hot_reload import ConfigWatcher
    with tempfile.TemporaryDirectory() as d:
        cfg = Path(d) / 'settings.json'
        cfg.write_text('{}')
        called = []
        watcher = ConfigWatcher(cfg, on_change=lambda: called.append(1))
        assert watcher.check() == False  # 刚创建，没变
        assert len(called) == 0

def test_config_watcher_detects_change():
    from harness_py_pro.hot_reload import ConfigWatcher
    import time
    with tempfile.TemporaryDirectory() as d:
        cfg = Path(d) / 'settings.json'
        cfg.write_text('{}')
        called = []
        watcher = ConfigWatcher(cfg, on_change=lambda: called.append(1))
        # 确保mtime变化（某些文件系统精度为1秒）
        time.sleep(1.1)
        cfg.write_text('{"updated": true}')
        assert watcher.check() == True
        assert len(called) == 1


# === swarm.py: AgentRole.cwd + orchestrate.parallel_groups ===

def test_agent_role_accepts_cwd():
    """AgentRole 支持 cwd 字段，用于跨项目多Agent场景。"""
    from harness_py_pro.swarm import AgentRole
    role = AgentRole(
        name='Dev',
        role_prompt='test',
        cwd=Path('/tmp/demo'),
    )
    assert role.cwd == Path('/tmp/demo')


def test_agent_role_cwd_defaults_to_none():
    """不传 cwd 时默认 None，orchestrate 会 fallback 到全局 cwd。"""
    from harness_py_pro.swarm import AgentRole
    role = AgentRole(name='Dev', role_prompt='test')
    assert role.cwd is None


def test_orchestrate_signature_has_parallel_groups():
    """orchestrate() 签名支持 parallel_groups 参数。"""
    import inspect
    from harness_py_pro.swarm import orchestrate
    sig = inspect.signature(orchestrate)
    assert 'parallel_groups' in sig.parameters
    assert sig.parameters['parallel_groups'].default is None


class _StopClient:
    """最小假客户端：直接返回无工具调用的 assistant 响应，等价于 agent 一轮自然停。"""
    def __init__(self):
        self.calls = 0
        self.messages_log: list[list[dict]] = []

    def complete(self, messages, tools=None):
        self.calls += 1
        self.messages_log.append(messages)
        return {'content': f'output_{self.calls}', 'tool_calls': [], 'usage': {
            'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15,
        }}


def test_orchestrate_runs_with_parallel_groups_offline():
    """parallel_groups 参数能被 orchestrate 接受并记录角色的 cwd。"""
    from harness_py_pro.swarm import AgentRole, orchestrate
    from harness_py_pro.config import ModelConfig

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        java_root = root / 'java_proj'
        python_root = root / 'python_proj'
        java_root.mkdir()
        python_root.mkdir()

        roles = [
            AgentRole(name='JavaDev', role_prompt='java', max_iterations=1,
                      planning_turns=0, cwd=java_root),
            AgentRole(name='PyDev', role_prompt='python', max_iterations=1,
                      planning_turns=0, cwd=python_root),
        ]

        result = orchestrate(
            'build cross-language client',
            roles,
            model_config=ModelConfig(model='gpt-4o', api_key='test-key',
                                     base_url='https://example.com'),
            cwd=root,
            max_rounds=1,
            parallel_groups={1: ['JavaDev', 'PyDev']},
            completion_client=_StopClient(),
            verbose=False,
        )

        assert result.rounds == 1
        assert len(result.agents_run) == 2
        cwds = {r['cwd'] for r in result.agents_run}
        assert str(java_root) in cwds
        assert str(python_root) in cwds


def test_orchestrate_parallel_group_isolates_round_outputs():
    """并行组内角色不应在当轮任务描述里看到同组其他角色的产出。"""
    from harness_py_pro.swarm import AgentRole, orchestrate
    from harness_py_pro.config import ModelConfig

    client = _StopClient()

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        roles = [
            AgentRole(name='A', role_prompt='role_a', max_iterations=1, planning_turns=0),
            AgentRole(name='B', role_prompt='role_b', max_iterations=1, planning_turns=0),
        ]

        orchestrate(
            'task',
            roles,
            model_config=ModelConfig(model='gpt-4o', api_key='test-key',
                                     base_url='https://example.com'),
            cwd=root,
            max_rounds=1,
            parallel_groups={1: ['A', 'B']},
            completion_client=client,
            verbose=False,
        )

        assert client.calls == 2
        # B 是第二个被调用的角色，它的 user prompt 里不应含 "来自 A 的产出摘要"
        second_call_messages = client.messages_log[1]
        # 把整个 messages 拼起来搜索
        all_text = '\n'.join(
            (m.get('content') or '') if isinstance(m.get('content'), str)
            else str(m.get('content') or '')
            for m in second_call_messages
        )
        assert '来自 A 的产出摘要' not in all_text, \
            '并行组内 B 不应看到同组 A 的当轮产出'


def test_orchestrate_non_parallel_shares_round_outputs():
    """不在 parallel_groups 里的角色，应当在当轮看到前一个角色的产出。"""
    from harness_py_pro.swarm import AgentRole, orchestrate
    from harness_py_pro.config import ModelConfig

    client = _StopClient()

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        roles = [
            AgentRole(name='A', role_prompt='role_a', max_iterations=1, planning_turns=0),
            AgentRole(name='B', role_prompt='role_b', max_iterations=1, planning_turns=0),
        ]

        orchestrate(
            'task',
            roles,
            model_config=ModelConfig(model='gpt-4o', api_key='test-key',
                                     base_url='https://example.com'),
            cwd=root,
            max_rounds=1,
            parallel_groups=None,
            completion_client=client,
            verbose=False,
        )

        assert client.calls == 2
        second_call_messages = client.messages_log[1]
        all_text = '\n'.join(
            (m.get('content') or '') if isinstance(m.get('content'), str)
            else str(m.get('content') or '')
            for m in second_call_messages
        )
        assert '来自 A 的产出摘要' in all_text, \
            '非并行场景下 B 应当看到 A 的当轮产出'


def test_agent_config_accepts_custom_cost_tracker():
    """AgentConfig.cost_tracker 允许用户替换默认 CostTracker。"""
    from harness_py_pro.config import AgentConfig

    class FakeCostTracker:
        def __init__(self):
            self.calls: list = []
            self.total_cost = 0.0
            self.over_budget = False
        def record(self, model, input_tokens, output_tokens):
            self.calls.append((model, input_tokens, output_tokens))
        def summary(self):
            return {'calls': len(self.calls)}

    ct = FakeCostTracker()
    ac = AgentConfig(cost_tracker=ct)
    assert ac.cost_tracker is ct


def test_engine_uses_custom_cost_tracker():
    """engine.run 使用 AgentConfig.cost_tracker 而非新建 CostTracker。"""
    import tempfile
    from pathlib import Path as _Path
    from harness_py_pro.config import AgentConfig, ModelConfig
    from harness_py_pro.engine import run as run_engine

    class TupleClient:
        def __init__(self):
            self.calls = 0
        def complete(self, messages, tools=None):
            self.calls += 1
            return ({'content': 'done', 'tool_calls': [],
                     'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}, 'router-a')

    class FakeCostTracker:
        def __init__(self):
            self.records: list = []
            self.total_cost = 0.0
            self.over_budget = False
        def record(self, model, input_tokens, output_tokens):
            self.records.append((model, input_tokens, output_tokens))
        def summary(self):
            return {'records': len(self.records), 'is_fake': True}

    with tempfile.TemporaryDirectory() as d:
        ct = FakeCostTracker()
        result = run_engine(
            'noop',
            model_config=ModelConfig(model='gpt-4o', api_key='k',
                                     base_url='https://example.com'),
            agent_config=AgentConfig(cwd=_Path(d), max_iterations=1,
                                     cost_tracker=ct),
            completion_client=TupleClient(),
            verbose=False,
        )
        # 用户传入的 FakeCostTracker 被 engine 使用
        assert len(ct.records) >= 1
        assert result.cost_summary.get('is_fake') is True


# === Ch3 deepseek-review-driven enhancements ===

def test_loop_guard_blocks_identical_calls():
    """相同调用第 3 次被 block（对齐 TUI IDENTICAL_CALL_BLOCK_THRESHOLD=3）。"""
    from harness_py_pro.loop_guard import LoopGuard
    g = LoopGuard()
    assert g.check_pre('read_file', {'path': 'a.py'})[0] == 'proceed'
    assert g.check_pre('read_file', {'path': 'a.py'})[0] == 'proceed'
    action, msg = g.check_pre('read_file', {'path': 'a.py'})
    assert action == 'block'
    assert 'Blocked' in msg


def test_loop_guard_paginated_reads_not_blocked():
    """分页读取不同 offset 不应被 block。"""
    from harness_py_pro.loop_guard import LoopGuard
    g = LoopGuard()
    for offset in [0, 100, 200]:
        action, _ = g.check_pre('read_file', {'path': 'a.py', 'offset': offset})
        assert action == 'proceed', f'offset={offset} 不应被 block'


def test_loop_guard_failure_warn_at_three_halt_at_eight():
    """同一工具连续失败 3 次 warn，8 次 halt（对齐 TUI）。"""
    from harness_py_pro.loop_guard import LoopGuard
    g = LoopGuard()
    assert g.check_post('grep_search', False)[0] == 'continue'
    assert g.check_post('grep_search', False)[0] == 'continue'
    action, msg = g.check_post('grep_search', False)
    assert action == 'warn', f'第 3 次失败应 warn,  got {action}'
    assert 'failed 3 consecutive times' in msg

    for _ in range(4, 8):
        assert g.check_post('grep_search', False)[0] == 'continue'

    action, msg = g.check_post('grep_search', False)
    assert action == 'halt', f'第 8 次失败应 halt, got {action}'
    assert 'failed 8 consecutive times' in msg


def test_loop_guard_success_resets_failure_counter():
    """成功调用重置该工具的失败计数器。"""
    from harness_py_pro.loop_guard import LoopGuard
    g = LoopGuard()
    g.check_post('grep_search', False)
    g.check_post('grep_search', False)
    assert g.check_post('grep_search', True)[0] == 'continue'
    # 重置后重新计数
    assert g.check_post('grep_search', False)[0] == 'continue'


def test_model_config_supports_seed_and_pool_size():
    """ModelConfig 暴露 seed + pool_size，from_env 读取 HARNESS_SEED / HARNESS_POOL_SIZE。"""
    import os
    from harness_py_pro.config import ModelConfig
    # 直接构造
    mc = ModelConfig(model='gpt-4o', api_key='k', base_url='https://x', seed=42, pool_size=4)
    assert mc.seed == 42
    assert mc.pool_size == 4
    # 默认值
    mc_default = ModelConfig()
    assert mc_default.seed is None
    assert mc_default.pool_size == 1
    # 环境变量
    os.environ['HARNESS_SEED'] = '99'
    os.environ['HARNESS_POOL_SIZE'] = '8'
    try:
        mc_env = ModelConfig.from_env()
        assert mc_env.seed == 99
        assert mc_env.pool_size == 8
    finally:
        del os.environ['HARNESS_SEED']
        del os.environ['HARNESS_POOL_SIZE']


def test_filesystem_policy_blocks_symlinks_and_denied_filenames():
    """FilesystemPolicy 拦截符号链接和敏感文件名（书 3.2.1 新增）。"""
    import os
    from pathlib import Path
    from harness_py_pro.sandbox import FilesystemPolicy
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        # 1) 文件名级拒绝
        env_file = root / '.env'
        env_file.write_text('SECRET=x')
        policy = FilesystemPolicy(allowed_roots=[root])
        ok, reason = policy.check_path(env_file, 'read')
        assert not ok and '敏感文件名' in reason

        # .envoy 不应误伤（前缀相同但不是 .env）
        envoy = root / '.envoy'
        envoy.write_text('config')
        ok2, _ = policy.check_path(envoy, 'read')
        assert ok2

        # 2) 符号链接拦截（只在能创建符号链接的环境跑）
        target = root / 'real.txt'
        target.write_text('data')
        link = root / 'link.txt'
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            return  # Windows 无权限或 OS 不支持，跳过这一档
        ok3, reason3 = policy.check_path(link, 'read')
        assert not ok3 and '符号链接' in reason3


def test_create_docker_sandbox_command_hardened_default():
    """create_docker_sandbox_command 默认启用四项加固。"""
    from pathlib import Path
    from harness_py_pro.sandbox import create_docker_sandbox_command
    cmd = create_docker_sandbox_command('ls /', Path('/tmp'))
    for token in ('--read-only', '--tmpfs=/tmp', '--security-opt=no-new-privileges:true',
                  '--cap-drop=ALL', '--pids-limit=256', '--memory-swap='):
        assert token in cmd, f'加固选项缺失: {token}\n实际命令: {cmd}'
    # 关掉加固后这些都不应出现
    cmd_legacy = create_docker_sandbox_command('ls /', Path('/tmp'), hardened=False)
    assert '--read-only' not in cmd_legacy
    assert '--cap-drop=ALL' not in cmd_legacy


def test_check_permission_confirm_fn_timeout_default_deny():
    """confirm_fn 阻塞超过 confirm_timeout 时默认拒绝（书 3.5.2 新增）。"""
    import time
    from harness_py_pro.sandbox import PermissionMode, check_permission

    def slow_confirm(action, detail):
        time.sleep(2)  # 2s > timeout=1s
        return True

    allowed, reason = check_permission(
        PermissionMode.ASK, 'execute', 'rm something',
        confirm_fn=slow_confirm, confirm_timeout=1,
    )
    assert not allowed
    assert '超时' in reason


def test_check_permission_confirm_fn_within_timeout_allowed():
    """confirm_fn 在 timeout 内返回 True 时正常通过。"""
    from harness_py_pro.sandbox import PermissionMode, check_permission

    def fast_confirm(action, detail):
        return True

    allowed, _ = check_permission(
        PermissionMode.ASK, 'execute', 'mvn test',
        confirm_fn=fast_confirm, confirm_timeout=5,
    )
    assert allowed


# === Ch10 TUI 规划体系 ===

def test_plan_state_update_and_format():
    from harness_py_pro.plan_state import PlanState, StepStatus
    plan = PlanState()
    plan.update([
        {'step': 'Read Java code', 'status': 'pending'},
        {'step': 'Read Python code', 'status': 'in_progress'},
    ], explanation='Investigating both sides')
    assert len(plan.steps) == 2
    assert plan.steps[0].status == StepStatus.PENDING
    assert plan.steps[1].status == StepStatus.IN_PROGRESS
    text = plan.format_for_prompt()
    assert '○ Read Java code' in text
    assert '◎ Read Python code' in text
    assert 'Investigating both sides' in text


def test_plan_state_mark_completed():
    from harness_py_pro.plan_state import PlanState, StepStatus
    plan = PlanState()
    plan.update([{'step': 'A', 'status': 'pending'}])
    assert plan.mark_in_progress('A')
    assert plan.steps[0].status == StepStatus.IN_PROGRESS
    assert plan.mark_completed('A')
    assert plan.steps[0].status == StepStatus.COMPLETED
    assert not plan.mark_completed('B')  # not found


def test_checklist_state_crud():
    from harness_py_pro.plan_state import ChecklistState, StepStatus
    cl = ChecklistState()
    item = cl.add('Step 1', 'pending')
    assert item.id == 1
    assert item.status == StepStatus.PENDING
    cl.add('Step 2', 'in_progress')
    assert len(cl.items) == 2
    assert cl.completion_pct() == 0
    cl.update(1, 'completed')
    assert cl.items[0].status == StepStatus.COMPLETED
    assert cl.completion_pct() == 50
    assert cl.in_progress_id() == 2


def test_task_registry_crud():
    from harness_py_pro.plan_state import TaskRegistry
    reg = TaskRegistry()
    task = reg.create('Refactor auth', 'Move auth to middleware')
    assert task.title == 'Refactor auth'
    assert task.status.value == 'pending'
    assert reg.get(task.id) is not None
    reg.update(task.id, 'completed')
    assert reg.get(task.id).status.value == 'completed'
    assert len(reg.list()) == 1
    reg.cancel(task.id)
    assert len(reg.list()) == 0


def test_plan_state_manager_persistence():
    import tempfile
    from harness_py_pro.plan_state import PlanStateManager
    with tempfile.TemporaryDirectory() as d:
        mgr = PlanStateManager(Path(d))
        mgr.plan.update([{'step': 'S1', 'status': 'in_progress'}])
        mgr.checklist.add('C1', 'pending')
        mgr.tasks.create('T1')
        mgr.save()

        # 重新加载
        mgr2 = PlanStateManager(Path(d))
        assert len(mgr2.plan.steps) == 1
        assert mgr2.plan.steps[0].step == 'S1'
        assert len(mgr2.checklist.items) == 1
        assert len(mgr2.tasks.tasks) == 1


def test_plan_tools_schemas():
    from harness_py_pro.plan_tools import (
        UpdatePlanTool, ChecklistWriteTool, ChecklistUpdateTool,
        ChecklistListTool, TaskCreateTool, TaskListTool, TaskUpdateTool, TaskCancelTool,
    )
    for ToolCls in [UpdatePlanTool, ChecklistWriteTool, ChecklistUpdateTool,
                    ChecklistListTool, TaskCreateTool, TaskListTool, TaskUpdateTool, TaskCancelTool]:
        tool = ToolCls()
        schema = tool.get_schema()
        assert 'name' in schema
        assert 'description' in schema
        assert schema['name'] == ToolCls.name


def test_plan_tools_execution():
    import tempfile
    from harness_py_pro.plan_state import PlanStateManager
    from harness_py_pro.plan_tools import UpdatePlanTool, ChecklistWriteTool, ChecklistUpdateTool
    from harness_py_pro.config import AgentConfig
    with tempfile.TemporaryDirectory() as d:
        mgr = PlanStateManager(Path(d))
        config = AgentConfig(cwd=Path(d))

        # update_plan
        tool = UpdatePlanTool(mgr)
        ok, result = tool.execute({
            'steps': [
                {'step': 'Read code', 'status': 'in_progress'},
                {'step': 'Write plan', 'status': 'pending'},
            ],
            'explanation': 'Starting investigation',
        }, config)
        assert ok
        assert 'Read code' in result

        # checklist_write
        tool2 = ChecklistWriteTool(mgr)
        ok2, result2 = tool2.execute({
            'items': [
                {'content': 'Check Java', 'status': 'in_progress'},
                {'content': 'Check Python', 'status': 'pending'},
            ],
        }, config)
        assert ok2
        assert 'Check Java' in result2

        # checklist_update
        tool3 = ChecklistUpdateTool(mgr)
        ok3, result3 = tool3.execute({'updates': [{'id': 1, 'status': 'completed'}]}, config)
        assert ok3
        assert 'Updated 1 item' in result3


# === 异步子代理体系 (SubAgentManager) ===

def test_subagent_manager_spawn_and_poll():
    """SubAgentManager 异步 spawn，poll_completions 返回已完成记录。"""
    import time
    from harness_py_pro.subagent_manager import SubAgentManager

    mgr = SubAgentManager(max_concurrent=5)

    def runner():
        time.sleep(0.1)
        return True, 'Done'

    record = mgr.spawn('test-1', 'investigate', 'explore', runner)
    assert record.agent_id == 'test-1'
    assert record.status.value == 'running'

    # 等待完成
    result = mgr.wait('test-1', timeout=5)
    assert result is not None
    assert result['status'] == 'completed'
    assert 'Done' in result['result_summary']

    # consume_completions 应包含该记录（仅一次）
    completed = mgr.consume_completions()
    assert any(r.agent_id == 'test-1' for r in completed)
    # 再次消费应为空（已去重）
    assert mgr.consume_completions() == []

    mgr.shutdown()


def test_subagent_manager_cancel():
    """取消 running 的子代理。"""
    import time
    from harness_py_pro.subagent_manager import SubAgentManager

    mgr = SubAgentManager(max_concurrent=5)

    def slow_runner():
        time.sleep(10)
        return True, 'Should not finish'

    mgr.spawn('slow-1', 'task', 'explore', slow_runner)
    time.sleep(0.05)  # 确保已启动

    ok = mgr.cancel('slow-1')
    assert ok is True

    result = mgr.get_result('slow-1')
    assert result['status'] == 'cancelled'

    # 再次取消应失败
    assert mgr.cancel('slow-1') is False
    mgr.shutdown()


def test_subagent_manager_list_and_running_count():
    """list_agents 和 running_count 正确反映状态。"""
    import time
    from harness_py_pro.subagent_manager import SubAgentManager

    mgr = SubAgentManager(max_concurrent=5)

    def runner():
        time.sleep(0.2)
        return True, 'OK'

    mgr.spawn('a-1', 't1', 'explore', runner)
    mgr.spawn('a-2', 't2', 'plan', runner)

    agents = mgr.list_agents()
    assert len(agents) == 2

    # 等待全部完成
    mgr.wait('a-1', timeout=5)
    mgr.wait('a-2', timeout=5)

    assert mgr.running_count == 0
    mgr.shutdown()


def test_subagent_manager_persistence():
    """子代理完成后自动持久化到 session_dir。"""
    import time
    from harness_py_pro.subagent_manager import SubAgentManager

    with tempfile.TemporaryDirectory() as d:
        session_dir = Path(d)
        mgr = SubAgentManager(max_concurrent=5, session_dir=session_dir)

        def runner():
            time.sleep(0.05)
            return True, 'Persisted'

        mgr.spawn('persist-1', 'task', 'explore', runner)
        mgr.wait('persist-1', timeout=5)

        # 检查文件是否写入
        files = list(session_dir.glob('subagent_*.json'))
        assert len(files) >= 1
        data = json.loads(files[0].read_text(encoding='utf-8'))
        assert data['agent_id'] == 'persist-1'
        assert data['status'] == 'completed'

        mgr.shutdown()


def test_subagent_manager_failed_runner():
    """子代理 runner 抛异常时记录为 failed。"""
    import time
    from harness_py_pro.subagent_manager import SubAgentManager

    mgr = SubAgentManager(max_concurrent=5)

    def bad_runner():
        raise ValueError('boom')

    mgr.spawn('fail-1', 'task', 'explore', bad_runner)
    time.sleep(0.1)

    result = mgr.get_result('fail-1')
    assert result['status'] == 'failed'
    assert 'boom' in result['error']
    mgr.shutdown()
