"""CDP 集成测试

需要本地 Chrome 已通过 ``chrome-agent-core`` 启动并开启 9222 端口。
默认跳过；运行：``pytest -m integration``
"""
import time

import pytest

pytestmark = pytest.mark.integration


def test_cdp_connection_alive():
    from chrome_agent_core.cdp import get_cdp_connection

    ws_url, tabs = get_cdp_connection()
    assert ws_url, "Chrome 未在 9222 端口运行"
    assert len(tabs) > 0


def test_navigate_baidu():
    from chrome_agent_core.cdp import cdp_navigate, get_page_info

    cdp_navigate("https://www.baidu.com", wait_load=2)
    time.sleep(1)
    info = get_page_info()
    assert "baidu.com" in (info.get("url") or "")


def test_eval_js_returns_title():
    from chrome_agent_core.cdp import cdp_execute, cdp_navigate

    cdp_navigate("https://www.baidu.com", wait_load=2)
    time.sleep(1)
    title = cdp_execute("document.title")
    assert isinstance(title, str)
