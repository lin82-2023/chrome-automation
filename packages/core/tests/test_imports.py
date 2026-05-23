"""测试公开 API 全部可导入（防止迁移过程中破坏导出）"""


def test_top_level_imports():
    from chrome_agent_core import (
        AgentSession,
        BailianLLM,
        ToolRegistry,
    )

    assert AgentSession is not None
    assert BailianLLM is not None
    assert ToolRegistry is not None


def test_submodule_imports():
    from chrome_agent_core import agent, browser, cdp, config, errors, llm, session, stealth, tools

    assert hasattr(agent, "ToolRegistry")
    assert hasattr(cdp, "cdp_navigate")
    assert hasattr(session, "SessionManager")
    assert hasattr(stealth, "apply_stealth_fingerprint")
    assert hasattr(browser, "ensure_chrome")
    assert hasattr(llm, "BailianLLM")
    assert hasattr(tools, "register_all_tools")
    assert hasattr(config, "get_config")
    assert hasattr(errors, "ChromeAgentError")
