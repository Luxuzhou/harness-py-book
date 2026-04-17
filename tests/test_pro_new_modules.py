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
