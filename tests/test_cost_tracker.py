"""CostTracker单元测试"""
import pytest
from src.cost_tracker import CostTracker


def test_cost_tracker_record():
    """测试CostTracker.record()方法"""
    tracker = CostTracker()
    
    # 测试记录功能
    tracker.record("gpt-4-input", 100)
    tracker.record("gpt-4-output", 50)
    tracker.record("gpt-4-input", 200)
    
    assert tracker.total_units == 350
    assert len(tracker.events) == 3
    assert tracker.events == ["gpt-4-input:100", "gpt-4-output:50", "gpt-4-input:200"]


def test_cost_tracker_summary():
    """测试CostTracker.summary()方法"""
    tracker = CostTracker()
    
    # 添加测试数据
    tracker.record("gpt-4-input", 100)
    tracker.record("gpt-4-output", 50)
    tracker.record("gpt-4-input", 200)
    tracker.record("gpt-3.5-input", 150)
    tracker.record("gpt-3.5-output", 75)
    tracker.record("gpt-3.5-input", 250)
    
    # 测试summary方法
    summary = tracker.summary()
    
    # 验证结果
    assert summary == {
        "gpt-4-input": 300,
        "gpt-4-output": 50,
        "gpt-3.5-input": 400,
        "gpt-3.5-output": 75
    }
    
    # 验证total_units
    assert tracker.total_units == 825


def test_cost_tracker_summary_empty():
    """测试空CostTracker的summary()方法"""
    tracker = CostTracker()
    summary = tracker.summary()
    assert summary == {}
    assert tracker.total_units == 0


def test_cost_tracker_summary_invalid_format():
    """测试包含无效格式事件的summary()方法"""
    tracker = CostTracker()
    
    # 添加有效和无效的事件
    tracker.events = [
        "gpt-4-input:100",
        "invalid_format",  # 缺少冒号
        "gpt-4-output:50",
        "another:invalid",  # 无效的数字
        "gpt-4-input:200"
    ]
    tracker.total_units = 350  # 手动设置total_units
    
    summary = tracker.summary()
    
    # 应该只统计有效格式的事件
    assert summary == {
        "gpt-4-input": 300,
        "gpt-4-output": 50
    }


def test_cost_tracker_integration():
    """测试CostTracker与agent的集成逻辑（模拟）"""
    from unittest.mock import Mock, patch
    import sys
    from pathlib import Path
    
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    try:
        from harness_py.config import ModelConfig, AgentConfig
        
        # 创建模拟的LLMClient
        mock_client = Mock()
        mock_response = {
            'content': '这是一个测试响应',
            'usage': {
                'prompt_tokens': 150,
                'completion_tokens': 75,
                'model': 'gpt-4'
            },
            'stop_reason': 'stop'
        }
        mock_client.complete.return_value = mock_response
        
        # 模拟agent.run函数中的关键部分
        with patch('harness_py.agent.LLMClient', return_value=mock_client):
            # 创建配置
            mc = ModelConfig(model="gpt-4", api_key="test-key", base_url="https://api.openai.com/v1")
            ac = AgentConfig(cwd=Path("."), max_iterations=1, allow_write=False, allow_shell=False)
            
            # 由于这是模拟测试，我们直接测试CostTracker的逻辑
            from src.cost_tracker import CostTracker
            tracker = CostTracker()
            
            # 模拟agent中的记录逻辑
            usage = mock_response['usage']
            input_tokens = usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0)
            
            tracker.record(f"{mc.model}_input", input_tokens)
            tracker.record(f"{mc.model}_output", output_tokens)
            
            # 验证记录
            assert tracker.total_units == 225
            assert len(tracker.events) == 2
            assert tracker.events == ["gpt-4_input:150", "gpt-4_output:75"]
            
            # 验证summary
            summary = tracker.summary()
            assert summary == {"gpt-4_input": 150, "gpt-4_output": 75}
    finally:
        # 清理Python路径
        sys.path.remove(str(project_root))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])