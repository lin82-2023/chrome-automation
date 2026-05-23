#!/usr/bin/env python3
"""
Chrome Browser Automation Engine
基于 CDP (Chrome DevTools Protocol) 的浏览器自动化引擎

功能:
- 网页DOM抓取 (get_elements)
- 元素点击 (click_element)
- 文本输入 (input_text)
- 表单提交 (submit_form)
- 多标签页管理 (get_tabs, switch_tab)
- Cookies管理 (save_cookies, load_cookies)
- 随机延迟防检测 (random_delay, random_mouse_move)

使用前提:
Chrome需要以 --remote-debugging-port=9222 --remote-allow-origins=* 启动

Stealth Mode:
默认启用随机延迟模拟真人操作
可配置 'relaxed', 'normal', 'strict', 'maximum'
"""
import json
import os
import platform
import queue
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

IS_MAC = platform.system() == "Darwin"

# ============================================================
# Event Type Constants
# ============================================================

class EventTypes:
    # Health
    BROWSER_ALIVE = 'browser_alive'
    BROWSER_DEAD = 'browser_dead'
    HEALTH_WARNING = 'health_warning'
    IDLE = 'idle'

    # Operations
    CLICK_SUCCESS = 'click_success'
    CLICK_FAILURE = 'click_failure'
    INPUT_SUCCESS = 'input_success'
    INPUT_FAILURE = 'input_failure'
    SUBMIT_SUCCESS = 'submit_success'
    SUBMIT_FAILURE = 'submit_failure'
    NAVIGATE_SUCCESS = 'navigate_success'
    NAVIGATE_FAILURE = 'navigate_failure'
    GET_ELEMENTS_SUCCESS = 'get_elements_success'
    GET_ELEMENTS_FAILURE = 'get_elements_failure'
    FIND_ELEMENT_SUCCESS = 'find_element_success'
    FIND_ELEMENT_FAILURE = 'find_element_failure'
    SWITCH_TAB_SUCCESS = 'switch_tab_success'
    SWITCH_TAB_FAILURE = 'switch_tab_failure'
    SAVE_COOKIES_SUCCESS = 'save_cookies_success'
    SAVE_COOKIES_FAILURE = 'save_cookies_failure'
    LOAD_COOKIES_SUCCESS = 'load_cookies_success'
    LOAD_COOKIES_FAILURE = 'load_cookies_failure'

    # DOM
    DOM_CAPTURED = 'dom_captured'
    ELEMENT_FOUND = 'element_found'
    ELEMENT_NOT_FOUND = 'element_not_found'

    # Errors
    CDP_ERROR = 'cdp_error'
    CONNECTION_LOST = 'connection_lost'
    SCRIPT_ERROR = 'script_error'
    TIMEOUT = 'timeout'
    EXCEPTION = 'exception'

    # Popup
    POPUP_DETECTED = 'popup_detected'
    POPUP_CLOSED = 'popup_closed'

    # Navigation
    NAVIGATION_START = 'navigation_start'
    NAVIGATION_COMPLETE = 'navigation_complete'

    # Tab
    TAB_CREATED = 'tab_created'
    TAB_CLOSED = 'tab_closed'
    TAB_SWITCHED = 'tab_switched'


class OverflowPolicy:
    DROP_OLDEST = 'drop_oldest'
    DROP_NEWEST = 'drop_newest'
    BLOCK = 'block'
    SECONDARY = 'secondary'


# ============================================================
# Async cache
# ============================================================

_cache = {}
_cache_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=4)

# Browser watchdog
_watchdog_state = {
    'last_active': time.time(),
    'last_url': '',
    'is_alive': False,
    'consecutive_failures': 0,
    'health_score': 100,
}
_watchdog_lock = threading.Lock()
_watchdog_pipe = None  # Queue pipe for watchdog events
_overflow_policy = OverflowPolicy.DROP_OLDEST
_secondary_queue = None

# Tab lifecycle管理 - 记录我们创建的标签页
_created_tab_ids: set = set()
_created_tab_ids_lock = threading.Lock()


def init_watchdog_pipe(maxsize: int = 100, overflow_policy: str = OverflowPolicy.DROP_OLDEST) -> 'queue.Queue':
    """
    初始化watchdog管道
    返回 watchdog event queue
    """
    global _watchdog_pipe, _overflow_policy
    _overflow_policy = overflow_policy
    _watchdog_pipe = queue.Queue(maxsize=maxsize)
    return _watchdog_pipe


def get_watchdog_pipe() -> 'queue.Queue':
    """获取watchdog管道"""
    return _watchdog_pipe


def set_overflow_policy(policy: str):
    """设置溢出策略: drop_oldest, drop_newest, block, secondary"""
    global _overflow_policy
    _overflow_policy = policy


def _handle_queue_overflow(event: dict):
    """当队列满时处理溢出"""
    global _overflow_policy, _secondary_queue

    if _overflow_policy == OverflowPolicy.DROP_OLDEST:
        try:
            _watchdog_pipe.get_nowait()
        except queue.Empty:
            pass
        try:
            _watchdog_pipe.put_nowait(event)
        except queue.Full:
            pass
    elif _overflow_policy == OverflowPolicy.DROP_NEWEST:
        pass  # 丢弃新事件
    elif _overflow_policy == OverflowPolicy.SECONDARY:
        if _secondary_queue is None:
            import collections
            _secondary_queue = collections.deque(maxlen=10000)
        _secondary_queue.append(event)


def emit_event(event_type: str,
              outcome: str = 'info',
              data: dict = None,
              source: str = None,
              trace_id: str = None,
              url: str = None,
              tab_id: str = None,
              element: dict = None,
              error: dict = None,
              duration_ms: float = None):
    """
    统一事件发射函数。所有浏览器操作调用此函数发布事件。
    """
    global _watchdog_pipe

    if source is None:
        import inspect
        for frame_info in inspect.stack()[1:]:
            name = frame_info.function
            if name not in ('emit_event', '_emit_watchdog_event',
                           '_get_caller_function_name', '_wrap_operation',
                           'emit_success', 'emit_failure'):
                source = name
                break
        if source is None:
            source = 'unknown'

    event = {
        'type': event_type,
        'time': time.time(),
        'source': source,
        'outcome': outcome,
        'data': data or {},
    }

    if trace_id is not None:
        event['trace_id'] = trace_id
    if url is not None:
        event['url'] = url
    if tab_id is not None:
        event['tab_id'] = tab_id
    if element is not None:
        event['element'] = element
    if error is not None:
        event['error'] = error
    if duration_ms is not None:
        event['duration_ms'] = duration_ms

    if _watchdog_pipe:
        try:
            _watchdog_pipe.put_nowait(event)
        except queue.Full:
            _handle_queue_overflow(event)


def emit_success(event_type: str, data: dict = None, **kwargs):
    """发射成功事件"""
    emit_event(event_type, 'success', data, **kwargs)


def emit_failure(event_type: str, data: dict = None, error: dict = None, **kwargs):
    """发射失败事件"""
    emit_event(event_type, 'failure', data, error=error, **kwargs)


def _generate_trace_id() -> str:
    """生成trace ID用于关联相关事件"""
    import uuid
    return str(uuid.uuid4())[:8]


def _get_current_url() -> str:
    """获取当前页面URL"""
    try:
        import urllib.request
        resp = urllib.request.urlopen('http://localhost:9222/json', timeout=3)
        tabs = json.loads(resp.read())
        for tab in tabs:
            if tab.get('type') == 'page':
                return tab.get('url', '')
    except Exception:
        pass
    return ''


# ============================================================
# browser_operation decorator
# ============================================================

def browser_operation(success_event: str, failure_event: str = None):
    """
    装饰器：自动为浏览器操作发射成功/失败事件

    跟踪开始时间、trace_id
    成功时发射成功事件并更新watchdog
    失败/False返回时发射失败事件
    异常时发射失败事件并更新watchdog状态

    用法:
        @browser_operation(EventTypes.CLICK_SUCCESS, EventTypes.CLICK_FAILURE)
        def click_element(...):
            ...
    """
    def decorator(func):
        from functools import wraps

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            trace_id = _generate_trace_id()
            current_url = _get_current_url()

            # Compute failure_event at call time to avoid cell variable issues
            _failure_event = failure_event or (success_event.rsplit('_', 1)[0] + '_failure')

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                if result:
                    _update_watchdog(url=current_url, activity=True)
                    emit_event(
                        success_event,
                        'success',
                        source=func.__name__,
                        trace_id=trace_id,
                        url=current_url,
                        duration_ms=duration_ms,
                    )
                else:
                    emit_event(
                        _failure_event,
                        'failure',
                        source=func.__name__,
                        trace_id=trace_id,
                        url=current_url,
                        duration_ms=duration_ms,
                    )
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                error_info = {
                    'type': type(e).__name__,
                    'message': str(e),
                }

                _update_watchdog(activity=False)
                emit_event(
                    _failure_event,
                    'failure',
                    source=func.__name__,
                    trace_id=trace_id,
                    url=current_url,
                    duration_ms=duration_ms,
                    error=error_info,
                )
                raise

        return wrapper
    return decorator


# 保留旧接口兼容
def _emit_watchdog_event(event_type: str, data: dict = None):
    """向管道发送watchdog事件（兼容旧接口）"""
    emit_event(event_type, 'info', data)


def _update_watchdog(url: str = None, activity: bool = True):
    """更新watchdog状态"""
    with _watchdog_lock:
        _watchdog_state['last_active'] = time.time()
        if url:
            _watchdog_state['last_url'] = url
        if activity:
            _watchdog_state['consecutive_failures'] = 0
            _watchdog_state['is_alive'] = True

    if activity and url:
        emit_event(EventTypes.NAVIGATION_COMPLETE, 'success', {'url': url})


def get_browser_health() -> dict[str, Any]:
    """
    获取浏览器健康状态
    返回: is_alive, health_score (0-100), idle_seconds, last_url, issues
    """
    with _watchdog_lock:
        state = _watchdog_state.copy()

    idle_sec = time.time() - state['last_active']
    issues = []

    # Check CDP connectivity first
    try:
        import urllib.request
        resp = urllib.request.urlopen('http://localhost:9222/json', timeout=3)
        tabs = json.loads(resp.read())
        state['is_alive'] = True
        _update_watchdog(activity=True)
    except Exception:
        issues.append('cdp_unreachable')
        state['is_alive'] = False

    if not state['is_alive']:
        with _watchdog_lock:
            _watchdog_state['health_score'] = 0
        return {
            'is_alive': False,
            'health_score': 0,
            'idle_seconds': round(idle_sec, 1),
            'last_url': state['last_url'],
            'issues': issues,
        }

    # Browser is alive, calculate health
    health = 100

    if idle_sec > 60:
        issues.append('idle_60s')
        health = max(0, 100 - (idle_sec - 60) * 2)

    if state['consecutive_failures'] > 3:
        issues.append('consecutive_failures')
        health = max(0, health - 20 * (state['consecutive_failures'] - 3))

    with _watchdog_lock:
        _watchdog_state['health_score'] = health

    return {
        'is_alive': True,
        'health_score': min(100, max(0, health)),
        'idle_seconds': round(idle_sec, 1),
        'last_url': state['last_url'],
        'issues': issues,
    }


def reset_browser_state():
    """重置浏览器状态（Chrome断开后调用）"""
    with _watchdog_lock:
        _watchdog_state['is_alive'] = False
        _watchdog_state['consecutive_failures'] += 1
    emit_event(EventTypes.BROWSER_DEAD, 'failure',
               {'failures': _watchdog_state['consecutive_failures']})


def _check_for_popups():
    """检查是否有弹窗/对话框"""
    ws_url, _ = get_cdp_connection()
    if not ws_url:
        return None

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        time.sleep(0.2)

        # Check for DOM modals (sweet-alert, .modal, swal-overlay, etc.)
        js = '''
        (function() {
            var modals = document.querySelectorAll(
                '.sweet-alert, .swal-overlay, .swal-modal, .modal[role="dialog"], [data-modal], .layui-layer, .layer-overlay'
            );
            if(modals.length > 0) {
                return {type: 'dom_modal', count: modals.length};
            }
            return null;
        })()
        '''
        ws.send(json.dumps({'id': 50, 'method': 'Runtime.evaluate',
                          'params': {'expression': js, 'returnByValue': True}}))

        result = None
        start = time.time()
        while time.time() - start < 3:
            try:
                r = ws.recv()
                if r:
                    d = json.loads(r)
                    if d.get('id') == 50:
                        val = d.get('result', {}).get('result', {}).get('value')
                        if val:
                            result = val
            except Exception:
                break

        ws.close()
        if result:
            return {'dialog_type': result.get('type'), 'url': _get_current_url()}
    except Exception:
        pass
    return None


def start_watchdog_monitor(interval: float = 10, health_threshold: int = 50):
    """
    启动后台watchdog监控线程
    interval: 检查间隔（秒）
    health_threshold: 健康分阈值，低于此值触发警告事件
    """
    def _monitor():
        while True:
            time.sleep(interval)

            health = get_browser_health()

            if not health['is_alive']:
                emit_event(EventTypes.BROWSER_DEAD, 'failure', health)
            elif health['health_score'] >= health_threshold:
                emit_event(EventTypes.BROWSER_ALIVE, 'info', health)

            if health['health_score'] < health_threshold:
                emit_event(EventTypes.HEALTH_WARNING, 'warning', health)

            # Check for popups
            popup = _check_for_popups()
            if popup:
                emit_event(EventTypes.POPUP_DETECTED, 'warning', popup)

            # Idle check
            if health['idle_seconds'] > 60:
                emit_event(EventTypes.IDLE, 'info', {'idle_seconds': health['idle_seconds']})

    t = threading.Thread(target=_monitor, daemon=True)
    t.start()
    return t

# Stealth config
STEALTH_LEVEL = os.environ.get('CHROME_STEALTH_LEVEL', 'normal')
STEALTH_MIN_DELAY = 200  # ms
STEALTH_MAX_DELAY = 800  # ms


def _get_stealth_config():
    """获取当前stealth配置"""
    global STEALTH_MIN_DELAY, STEALTH_MAX_DELAY

    configs = {
        'relaxed': (50, 300),
        'normal': (200, 800),
        'strict': (500, 2000),
        'maximum': (1000, 5000),
    }
    return configs.get(STEALTH_LEVEL, configs['normal'])


# ============================================================
# Stealth Mode - 防检测随机化
# ============================================================

def random_delay(min_ms: float = None, max_ms: float = None):
    """随机延迟，模拟真人操作间隔"""
    if min_ms is None or max_ms is None:
        min_ms, max_ms = _get_stealth_config()

    delay = random.uniform(min_ms, max_ms) / 1000
    time.sleep(delay)


def random_mouse_move(base_x: int, base_y: int, radius: int = 10):
    """随机鼠标移动到一个点附近"""
    try:
        import pyautogui
        offset_x = random.randint(-radius, radius)
        offset_y = random.randint(-radius, radius)
        target_x = base_x + offset_x
        target_y = base_y + offset_y
        pyautogui.moveTo(target_x, target_y, duration=random.uniform(0.1, 0.3))
    except Exception:
        pass


def get_human_user_agent() -> str:
    """返回一个真实的人类User-Agent"""
    agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    ]
    return random.choice(agents)


def apply_stealth_fingerprint():
    """
    注入JS去除自动化特征，防爬虫检测
    覆盖navigator.webdriver、WebGL、Canvas等
    """
    js = """
    // 1. 去除自动化标志
    Object.defineProperty(navigator, 'webdriver', {get: () => false});

    // 2. 模拟真实平台
    Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});

    // 3. Canvas 指纹加噪
    const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        const ctx = this.getContext('2d');
        if (ctx) {
            try {
                const imgData = ctx.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imgData.data.length; i += 4) {
                    imgData.data[i] ^= Math.random() > 0.5 ? 1 : 0;
                }
                ctx.putImageData(imgData, 0, 0);
            } catch(e) {}
        }
        return _origToDataURL.apply(this, args);
    };

    // 4. WebGL 厂商伪装
    const origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        if (p === 37445) return 'Intel Inc.';
        if (p === 37446) return 'Intel Iris OpenGL Engine';
        return origGetParam.apply(this, arguments);
    };

    // 5. 去除CDP自动化特征
    console.debug = () => {};
    try {
        delete window.cdc_;
        delete window.__webdriver__;
        delete window.__selenium_evaluate;
        delete window.__webdriver_script_func;
        delete window.__webdriver_script_function;
        delete window.__webdriver_script_atoms;
        delete window.__fxdriver_;
    } catch(e) {}

    // 6. Permissions API 伪装
    if (!navigator.permissions) {
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: (params) => Promise.resolve({state: 'granted', onchange: null})
            })
        });
    }

    // 7. Navigator plugins 伪装
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            {name: 'Chrome PDF Plugin', description: 'Portable Document Format'},
            {name: 'Chrome PDF Viewer', description: ''},
            {name: 'Native Client', description: ''},
        ]
    });

    // 8. Navigator mimeTypes 伪装
    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => [
            {type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'},
            {type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format'},
        ]
    });
    """
    cdp_execute(js)


# ============================================================
# Chrome CDP 连接管理
# ============================================================

_active_tab_index = 0  # Currently active tab index


def check_chrome_installed() -> bool:
    """
    检查Chrome浏览器是否已安装
    返回 True 如果已安装
    """
    if IS_MAC:
        import os
        return os.path.exists('/Applications/Google Chrome.app')
    return False


_CHROME_AGENT_PROFILE_PREFIX = "chrome_agent_"


def _marker_path(port: int) -> str:
    """chrome-agent 启动 Chrome 时写入 user-data-dir 的 marker 文件路径"""
    import os as _os
    import tempfile as _tempfile
    return _os.path.join(_tempfile.gettempdir(), f"chrome-agent-cdp-{port}.profile")


def _read_profile_marker(port: int) -> str | None:
    """读取 marker 文件，返回历史启动时记录的 user-data-dir 路径，验证仍存在"""
    import os as _os
    path = _marker_path(port)
    try:
        if not _os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            profile = f.read().strip()
        # marker 指向的目录仍存在才视为有效（Chrome 进程退出后路径会被清理或保留）
        if profile and _os.path.isdir(profile):
            return profile
    except Exception:
        pass
    return None


def _write_profile_marker(port: int, profile: str) -> None:
    """ensure_chrome 启动 Chrome 后调用，记录 user-data-dir"""
    try:
        with open(_marker_path(port), "w", encoding="utf-8") as f:
            f.write(profile)
    except Exception:
        pass


def _inspect_cdp_port_owner(port: int) -> tuple[bool, str | None]:
    """
    探测占用 ``port`` 的 Chrome 进程的 ``--user-data-dir``。

    返回 (cdp_listening, user_data_dir):
      - cdp_listening: 端口是否在监听并响应 /json
      - user_data_dir: 占用进程的 user-data-dir 路径；无法识别时为 None
    """
    import json as _json
    import re as _re
    import socket as _socket
    import subprocess as _subprocess
    import urllib.request as _urlreq

    # 1) TCP 连接 + /json 验证
    try:
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.settimeout(0.5)
        in_use = sock.connect_ex(("localhost", port)) == 0
        sock.close()
        if not in_use:
            return False, None
        resp = _urlreq.urlopen(f"http://localhost:{port}/json", timeout=2)
        if resp.status != 200:
            return False, None
        _json.loads(resp.read())
    except Exception:
        return False, None

    # 2) 通过 lsof 找到监听端口的 PID，再读 cmdline 中的 --user-data-dir
    #    注意：macOS 的 ps 在无 PTY 环境（nohup/daemon）下默认按 COLUMNS 截断，
    #    必须用 -ww 强制不限制输出宽度，否则 --user-data-dir 可能被截断
    import sys as _sys
    try:
        out = _subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        pids = [p.strip() for p in out.stdout.splitlines() if p.strip()]
        for pid in pids:
            try:
                ps = _subprocess.run(
                    ["ps", "-ww", "-p", pid, "-o", "command="],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                cmd = ps.stdout
            except (PermissionError, OSError) as e:
                # 某些受限环境（如沙盒）禁止执行 ps，回退到 marker
                print(f"⚠️  无法运行 ps 探测进程命令行（{e}），尝试读取 marker 文件...", file=_sys.stderr)
                cmd = ""
            m = _re.search(r"--user-data-dir=(\S+)", cmd)
            if m:
                return True, m.group(1)
    except Exception:
        pass

    # ps 探测失败时读取 marker 文件兜底（之前 ensure_chrome 启动的会写入）
    marker = _read_profile_marker(port)
    if marker:
        return True, marker

    return True, None


def ensure_chrome(confirm: bool = True, port: int = 9222, auto_launch: bool = True) -> bool:
    """
    确保 Chrome 已安装并且远程调试端口可用，且只复用 chrome-agent 起的干净实例。

    流程：
    1. 检查 Chrome 是否安装；未安装则提示用户下载
    2. 探测 ``port``：
       - 未监听 → 自动启动临时干净实例
       - 已监听且 user-data-dir 含 ``chrome_agent_`` 前缀 → 视为受控实例，复用
       - 已监听但占用者不是 chrome-agent → **拒绝复用**（避免误操控用户日常浏览器），
         返回 False 并提示用户处置
    3. 自动启动时使用 ``tempfile.mkdtemp(prefix='chrome_agent_')`` 隔离 user-data-dir，
       不会影响 ``~/Library/Application Support/Google/Chrome`` 下的日常配置

    confirm: True=未安装时打开下载页提示用户
    port: CDP 远程调试端口（默认 9222）
    auto_launch: 端口未就绪时是否自动启动 Chrome
    返回 True 表示 CDP 端口已可用且实例由 chrome-agent 受控
    """
    if not check_chrome_installed():
        if not confirm:
            return False
        try:
            import os as _os
            if IS_MAC:
                print("Google Chrome 未安装，正在尝试打开下载页面...")
                _os.system('open "https://www.google.com/chrome/"')
                print("请下载并安装 Chrome 后重试。")
        except Exception as e:
            print(f"打开下载页面失败: {e}")
        return False

    # 探测端口及其占用者
    cdp_listening, owner_profile = _inspect_cdp_port_owner(port)
    if cdp_listening:
        if owner_profile and _CHROME_AGENT_PROFILE_PREFIX in owner_profile:
            # 已是 chrome-agent 受控的干净实例，安全复用
            return True

        # 端口被占用，但不是 chrome-agent 起的（可能是用户日常 Chrome 自己开了 9222）
        print(
            f"⚠️  端口 {port} 已被另一个 Chrome 实例占用，但它不是 chrome-agent 启动的干净实例：\n"
            f"    user-data-dir = {owner_profile or '<未知>'}\n"
            f"为避免误操控你的日常浏览器，已拒绝复用。请按以下方式之一处理：\n"
            f"  1) 关闭那个 Chrome 实例后重试；\n"
            f"  2) 或者杀掉占用 {port} 的 Chrome 进程：\n"
            f"     lsof -nP -iTCP:{port} -sTCP:LISTEN -t | xargs kill\n"
            f"  3) 或为 chrome-agent 指定其他端口（暂不支持运行时切换，请联系开发者）。"
        )
        return False

    if not auto_launch:
        print(
            f"Chrome 远程调试端口 {port} 未就绪，请手动启动一个干净实例：\n"
            f"  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \\\n"
            f"      --remote-debugging-port={port} --remote-allow-origins='*' \\\n"
            f"      --user-data-dir=$(mktemp -d -t chrome_agent_) about:blank"
        )
        return False

    # 自动用临时 user-data-dir 启动一个干净实例（不影响用户日常 Chrome）
    import platform as _platform
    import subprocess as _subprocess
    import tempfile as _tempfile
    import time as _time

    system = _platform.system()
    if system == "Darwin":
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif system == "Windows":
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    else:
        chrome_path = "google-chrome"

    temp_profile = _tempfile.mkdtemp(prefix=_CHROME_AGENT_PROFILE_PREFIX)
    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={temp_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    print(f"🚀 自动启动干净的 Chrome 实例（临时配置 {temp_profile}）...")
    try:
        _subprocess.Popen(
            cmd,
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL,
            start_new_session=True,
        )
        # 写入 marker，便于后续在 ps 不可用的环境下识别为受控实例
        _write_profile_marker(port, temp_profile)
    except Exception as e:
        print(f"启动 Chrome 失败: {e}")
        return False

    # 轮询等待 CDP 就绪（最多 15 秒），并校验是我们启动的实例
    for _ in range(15):
        _time.sleep(1)
        ready, owner = _inspect_cdp_port_owner(port)
        if ready and owner and _CHROME_AGENT_PROFILE_PREFIX in owner:
            print(f"✅ Chrome 已就绪（端口 {port}，受控实例）")
            return True

    print(f"❌ 等待 Chrome CDP 端口 {port} 超时，请手动检查")
    return False


def get_cdp_connection(tab_index: int = None) -> tuple[str | None, list[dict]]:
    """
    获取CDP WebSocket URL和标签页列表
    tab_index: 指定标签页索引，None时使用当前活动标签页
    """
    if not IS_MAC:
        return None, []

    try:
        import urllib.request
        resp = urllib.request.urlopen('http://localhost:9222/json', timeout=5)
        tabs = json.loads(resp.read())
        if tabs:
            page_tabs = [t for t in tabs if t.get('type') == 'page']
            if page_tabs:
                idx = tab_index if tab_index is not None else _active_tab_index
                idx = max(0, min(idx, len(page_tabs) - 1))
                ws_url = page_tabs[idx].get('webSocketDebuggerUrl')
            else:
                ws_url = tabs[0].get('webSocketDebuggerUrl') if tabs else None
            _update_watchdog(activity=True)
            return ws_url, tabs
    except Exception:
        pass

    _update_watchdog(activity=False)
    return None, []


def _handle_dialog(accept: bool = True):
    """处理浏览器弹窗（alert/confirm/prompt）"""
    ws_url, _ = get_cdp_connection()
    if not ws_url:
        return False
    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({'id': 1, 'method': 'Page.enable'}))
        time.sleep(0.1)
        ws.send(json.dumps({
            'id': 2,
            'method': 'Page.handleJavaScriptDialog',
            'params': {'accept': accept, 'promptText': ''}
        }))
        ws.close()
        return True
    except Exception:
        return False


def _check_and_handle_dialogs():
    """检查并自动关闭所有弹窗"""
    ws_url, _ = get_cdp_connection()
    if not ws_url:
        return
    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({'id': 1, 'method': 'Page.enable'}))
        ws.send(json.dumps({'id': 2, 'method': 'Runtime.enable'}))
        time.sleep(0.2)
        ws.close()
        _handle_dialog(accept=True)
    except Exception:
        pass


def cdp_execute(js_code: str, timeout: int = 10) -> Any | None:
    """
    通过CDP执行JavaScript代码
    返回执行结果或None
    """
    ws_url, tabs = get_cdp_connection()
    if not ws_url or not tabs:
        return None

    # 先处理可能存在的弹窗
    _check_and_handle_dialogs()

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        time.sleep(0.2)

        ws.send(json.dumps({'id': 99, 'method': 'Runtime.evaluate',
                            'params': {'expression': js_code, 'returnByValue': True}}))

        start = time.time()
        while time.time() - start < timeout:
            try:
                r = ws.recv()
                if r:
                    d = json.loads(r)
                    if d.get('id') == 99:
                        ws.close()
                        return d.get('result', {}).get('result', {}).get('value')
            except Exception:
                pass
        ws.close()
    except Exception:
        pass
    return None


@browser_operation(EventTypes.NAVIGATE_SUCCESS, EventTypes.NAVIGATE_FAILURE)
def cdp_navigate(url: str, wait_load: float = 3) -> bool:
    """
    通过CDP导航到指定URL
    """
    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return False

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({'id': 1, 'method': 'Page.enable'}))
        ws.send(json.dumps({'id': 2, 'method': 'Runtime.enable'}))
        time.sleep(0.2)

        ws.send(json.dumps({'id': 99, 'method': 'Page.navigate', 'params': {'url': url}}))

        # Random delay before waiting
        random_delay()

        time.sleep(wait_load)

        # Apply stealth fingerprint after navigation
        apply_stealth_fingerprint()

        # 处理可能出现的弹窗
        _check_and_handle_dialogs()

        ws.close()
        return True
    except Exception:
        pass
    return False


# ============================================================
# DOM 抓取
# ============================================================

@browser_operation(EventTypes.GET_ELEMENTS_SUCCESS, EventTypes.GET_ELEMENTS_FAILURE)
def get_elements(limit: int = 500, use_stealth: bool = True) -> tuple[list[dict[str, Any]], str]:
    """
    获取当前页面的所有DOM元素
    返回 (elements, source)

    use_stealth: 是否使用随机延迟
    """
    if not IS_MAC:
        return [], 'unsupported'

    if use_stealth:
        random_delay(100, 300)

    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return [], 'no_connection'

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        time.sleep(0.3)

        # JavaScript to extract all elements with viewport coordinates
        js_code = """
        (function() {
            var result = [];
            var walk = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, null, false);
            var node, cnt = 0;
            var wx = window.screenX || 0;
            var wy = window.screenY || 0;
            while(node = walk.nextNode()) {
                if(cnt++ > 500) break;
                var rect = node.getBoundingClientRect();
                if(rect.width > 0 && rect.height > 0) {
                    var tag = node.tagName;
                    var id = node.id ? '#' + node.id : '';
                    var cls = node.className && typeof node.className === 'string' ? '.' + node.className.split(' ').join('.') : '';
                    var txt = node.innerText ? node.innerText.trim().substring(0, 80) : '';
                    var attrs = {};
                    try {
                        var attrs_arr = node.attributes;
                        for (var i = 0; i < attrs_arr.length; i++) {
                            var a = attrs_arr[i];
                            attrs[a.name] = a.value;
                        }
                    } catch(e) {}
                    var cursor = '';
                    try { cursor = window.getComputedStyle(node).cursor || ''; } catch(e) {}
                    var elemRole = '';
                    try { elemRole = node.getAttribute('role') || ''; } catch(e) {}
                    var sx = Math.round(rect.left + wx);
                    var sy = Math.round(rect.top + wy);
                    result.push({
                        tag: tag, id: id, class: cls.substring(0, 50), text: txt,
                        x: sx, y: sy, w: Math.round(rect.width), h: Math.round(rect.height),
                        attributes: attrs, role: elemRole, cursor: cursor,
                        vx: Math.round(rect.left), vy: Math.round(rect.top)
                    });
                }
            }
            return JSON.stringify(result);
        })()
        """.replace('\n', ' ').replace('  ', ' ')

        ws.send(json.dumps({'id': 99, 'method': 'Runtime.evaluate',
                          'params': {'expression': js_code, 'returnByValue': True}}))

        start = time.time()
        while time.time() - start < 15:
            try:
                result = ws.recv()
                if result:
                    d = json.loads(result)
                    if d.get('id') == 99:
                        val = d['result'].get('result', {}).get('value', '')
                        if val:
                            elements = json.loads(val)
                            ws.close()
                            return _filter_elements(elements), 'chrome_cdp'
            except Exception:
                pass

        ws.close()
    except Exception:
        pass

    return [], 'chrome_cdp_failed'


def _filter_elements(elems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """过滤垃圾元素，保留可交互的"""
    GARBAGE_TAGS = {'SCRIPT', 'STYLE', 'META', 'LINK', 'HEAD', 'BODY'}
    INTERACTIVE_TAGS = {'A', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION'}

    filtered = []
    for e in elems:
        tag = e.get('tag', '').upper()
        if tag in GARBAGE_TAGS:
            continue

        w, h = e.get('w', 0), e.get('h', 0)
        if w < 5 or h < 5:
            continue

        text = e.get('text', '').strip()
        if not text and not e.get('id'):
            continue

        e['type'] = e.get('role', '') or tag
        filtered.append(e)

    return filtered


# ============================================================
# 元素查找
# ============================================================

def find_element(elements: list[dict], text: str = None,
                 tag: str = None, by: str = 'text') -> dict[str, Any] | None:
    """
    在元素列表中查找匹配项

    by: 'text' - 按文本内容匹配
        'id' - 按ID匹配
        'css' - 按CSS选择器匹配
    """
    if not text and not tag:
        return None

    text_lower = text.lower() if text else ''
    matches = []

    for e in elements:
        # Tag filter
        if tag and e.get('tag', '').upper() != tag.upper():
            continue

        # Text/id filter
        if text_lower:
            if by == 'text':
                if not (text_lower in e.get('text', '').lower() or
                        text_lower in e.get('id', '').lower()):
                    continue
            elif by == 'id':
                if text_lower not in e.get('id', '').lower():
                    continue

        matches.append(e)

    if not matches:
        return None

    # 优先返回可交互元素中最小的（面积最小 = 最具体）
    interactive = [m for m in matches if _is_interactive(m)]
    if interactive:
        return min(interactive, key=lambda x: x.get('w', 0) * x.get('h', 0))

    return min(matches, key=lambda x: x.get('w', 0) * x.get('h', 0))


def _is_interactive(elem: dict) -> bool:
    """判断元素是否可交互"""
    tag = elem.get('tag', '').upper()
    if tag in ('A', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT'):
        return True
    if elem.get('cursor') == 'pointer':
        return True
    role = elem.get('role', '').lower()
    if role in ('button', 'link', 'menuitem', 'checkbox', 'radio'):
        return True
    return False


# ============================================================
# 元素操作 (Stealth增强版)
# ============================================================

@browser_operation(EventTypes.CLICK_SUCCESS, EventTypes.CLICK_FAILURE)
def click_element(text: str = None, tag: str = None,
                  by: str = 'text', use_stealth: bool = True) -> bool:
    """
    查找并点击元素（CDP Stealth模式）

    使用CDP Input.dispatchMouseEvent 进行精准点击
    use_stealth: 是否使用随机延迟模拟真人操作
    """
    if use_stealth:
        random_delay(200, 600)

    elements, _ = get_elements(use_stealth=False)
    elem = find_element(elements, text=text, tag=tag, by=by)

    if not elem:
        return False

    ws_url, _ = get_cdp_connection()
    if not ws_url:
        return False

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        ws.send(json.dumps({'id': 2, 'method': 'Input.enable'}))
        time.sleep(0.2)

        # Get element viewport coordinates
        x, y = elem.get('x', 0), elem.get('y', 0)
        vx, vy = elem.get('vx', 0), elem.get('vy', 0)
        w, h = elem.get('w', 0), elem.get('h', 0)

        if w <= 0 or h <= 0:
            ws.close()
            return False

        # Click at VIEWPORT coordinates (not screen)
        click_x = vx + w // 2
        click_y = vy + h // 2

        if use_stealth:
            random_delay(100, 300)

            # CDP mouse move with human-like curve (dispatch 3 move events)
            for step in range(3):
                t = (step + 1) / 3
                dx = click_x * t + random.uniform(-2, 2)
                dy = click_y * t + random.uniform(-2, 2)
                ws.send(json.dumps({
                    'id': 10 + step,
                    'method': 'Input.dispatchMouseEvent',
                    'params': {
                        'type': 'mouseMoved',
                        'x': dx,
                        'y': dy,
                        'button': 'none',
                        'clickCount': 0
                    }
                }))
                time.sleep(random.uniform(0.05, 0.15))

            random_delay(50, 150)

        # CDP mouse click at exact position
        ws.send(json.dumps({
            'id': 20,
            'method': 'Input.dispatchMouseEvent',
            'params': {
                'type': 'mousePressed',
                'x': click_x,
                'y': click_y,
                'button': 'left',
                'clickCount': 1
            }
        }))
        time.sleep(0.05)
        ws.send(json.dumps({
            'id': 21,
            'method': 'Input.dispatchMouseEvent',
            'params': {
                'type': 'mouseReleased',
                'x': click_x,
                'y': click_y,
                'button': 'left',
                'clickCount': 1
            }
        }))
        time.sleep(0.1)

        # Verify click was dispatched - drain responses
        try:
            ws.setblocking(False)
            for _ in range(5):
                try:
                    r = ws.recv()
                    if r:
                        d = json.loads(r)
                except Exception:
                    break
            ws.setblocking(True)
        except Exception:
            pass

        ws.close()
        if use_stealth:
            random_delay(200, 600)
        return True

    except Exception as e:
        print(f'click_element error: {e}')
        try:
            ws.close()
        except Exception:
            pass

    return False


@browser_operation(EventTypes.INPUT_SUCCESS, EventTypes.INPUT_FAILURE)
def input_text(text: str, selector: str = '#kw', use_stealth: bool = True) -> bool:
    """
    向输入框输入文本（CDP Stealth模式）

    使用 CDP Input.dispatchKeyEvent 进行精准按键模拟
    selector: CSS选择器，默认#kw（百度搜索框）
    use_stealth: 是否模拟真人输入
    """
    if use_stealth:
        random_delay(300, 800)

    ws_url, _ = get_cdp_connection()
    if not ws_url:
        return False

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        ws.send(json.dumps({'id': 2, 'method': 'Input.enable'}))
        time.sleep(0.2)

        # Focus and clear the input
        js_focus = f'''
        (function() {{
            var el = document.querySelector("{selector}");
            if(!el) return "not found";
            el.focus();
            el.value = "";
            return "ready";
        }})()
        '''
        ws.send(json.dumps({'id': 10, 'method': 'Runtime.evaluate',
                          'params': {'expression': js_focus, 'returnByValue': True}}))
        time.sleep(0.3)

        if use_stealth:
            random_delay(100, 300)

        # Type character by character with CDP key events
        for char in text:
            if char == ' ':
                ws.send(json.dumps({
                    'id': 100,
                    'method': 'Input.dispatchKeyEvent',
                    'params': {'type': 'keyDown', 'text': ' ', 'key': 'Space', 'code': 'Space'}
                }))
                time.sleep(random.uniform(0.05, 0.15))
                ws.send(json.dumps({
                    'id': 101,
                    'method': 'Input.dispatchKeyEvent',
                    'params': {'type': 'keyUp', 'text': ' ', 'key': 'Space', 'code': 'Space'}
                }))
            else:
                ws.send(json.dumps({
                    'id': 100,
                    'method': 'Input.dispatchKeyEvent',
                    'params': {'type': 'keyDown', 'text': char, 'key': char.upper(), 'code': f'Key{char.upper()}'}
                }))
                time.sleep(random.uniform(0.03, 0.12))
                ws.send(json.dumps({
                    'id': 101,
                    'method': 'Input.dispatchKeyEvent',
                    'params': {'type': 'keyUp', 'text': char, 'key': char.upper(), 'code': f'Key{char.upper()}'}
                }))

            if use_stealth and random.random() > 0.7:
                random_delay(50, 150)

        # Dispatch input event
        ws.send(json.dumps({
            'id': 200,
            'method': 'Runtime.evaluate',
            'params': {'expression': f'document.querySelector("{selector}").dispatchEvent(new Event("input", {{bubbles:true}}))', 'returnByValue': True}
        }))

        ws.close()
        if use_stealth:
            random_delay(200, 500)
        return True

    except Exception as e:
        print(f'input_text error: {e}')
        try:
            ws.close()
        except Exception:
            pass

    return False


@browser_operation(EventTypes.SUBMIT_SUCCESS, EventTypes.SUBMIT_FAILURE)
def submit_form(form_selector: str = 'form', use_stealth: bool = True) -> bool:
    """提交表单（Stealth模式）"""
    if use_stealth:
        random_delay(300, 700)

    ws_url, _ = get_cdp_connection()
    if not ws_url:
        return False

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        time.sleep(0.2)

        js = f'''
        (function() {{
            var form = document.querySelector("{form_selector}");
            if(form) {{
                form.submit();
                return "submitted";
            }}
            return "not found";
        }})()
        '''

        ws.send(json.dumps({'id': 99, 'method': 'Runtime.evaluate',
                          'params': {'expression': js, 'returnByValue': True}}))

        start = time.time()
        while time.time() - start < 8:
            try:
                r = ws.recv()
                if r:
                    d = json.loads(r)
                    if d.get('id') == 99:
                        ws.close()
                        if use_stealth:
                            random_delay(500, 1500)
                        return True
            except Exception:
                pass
        ws.close()
    except Exception:
        pass

    return False


# ============================================================
# 页面信息
# ============================================================

def get_page_info() -> dict[str, Any]:
    """获取当前页面信息"""
    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return {}

    try:
        import urllib.request
        resp = urllib.request.urlopen('http://localhost:9222/json', timeout=5)
        tabs_data = json.loads(resp.read())

        for tab in tabs_data:
            if tab.get('type') == 'page':
                return {
                    'url': tab.get('url', ''),
                    'title': tab.get('title', ''),
                    'id': tab.get('id', ''),
                }
    except Exception:
        pass

    return {}


def get_all_tabs() -> list[dict[str, Any]]:
    """获取所有标签页"""
    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return []

    result = []
    for i, tab in enumerate(tabs):
        if tab.get('type') == 'page':
            result.append({
                'index': i,
                'url': tab.get('url', ''),
                'title': tab.get('title', ''),
                'id': tab.get('id', ''),
            })
    return result


@browser_operation(EventTypes.SWITCH_TAB_SUCCESS, EventTypes.SWITCH_TAB_FAILURE)
def switch_tab(index: int) -> bool:
    """切换到指定标签页"""
    global _active_tab_index

    ws_url, tabs = get_cdp_connection()
    if not ws_url or not tabs:
        return False

    page_tabs = [t for t in tabs if t.get('type') == 'page']
    if index < 0 or index >= len(page_tabs):
        return False

    target = page_tabs[index]
    target_id = target.get('id')
    ws_url_target = target.get('webSocketDebuggerUrl')
    if not ws_url_target or not target_id:
        return False

    try:
        import websocket
        ws = websocket.create_connection(ws_url_target, timeout=10)
        # Activate the target tab
        ws.send(json.dumps({'id': 1, 'method': 'Target.activateTarget',
                          'params': {'targetId': target_id}}))
        ws.send(json.dumps({'id': 2, 'method': 'Runtime.enable'}))
        ws.send(json.dumps({'id': 3, 'method': 'Page.enable'}))
        ws.close()

        _active_tab_index = index
        random_delay(200, 500)
        return True
    except Exception:
        pass
    return False


@browser_operation(EventTypes.TAB_CREATED, EventTypes.TAB_CREATED.replace('created', 'failure'))
def create_tab(url: str = 'about:blank') -> bool:
    """创建新标签页"""
    global _active_tab_index

    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return False

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Target.createTarget',
                          'params': {'url': url}}))

        # Wait for response
        start = time.time()
        new_id = None
        while time.time() - start < 5:
            r = ws.recv()
            if r:
                d = json.loads(r)
                if d.get('id') == 1:
                    new_id = d.get('result', {}).get('targetId')
                    break
        ws.close()

        if new_id:
            # Refresh tabs list and find new tab
            _, new_tabs = get_cdp_connection()
            page_tabs = [t for t in new_tabs if t.get('type') == 'page']
            for i, t in enumerate(page_tabs):
                if t.get('id') == new_id:
                    _active_tab_index = i
                    break
            with _created_tab_ids_lock:
                _created_tab_ids.add(new_id)
            return True
    except Exception:
        pass
    return False


@browser_operation(EventTypes.TAB_CLOSED, EventTypes.TAB_CLOSED.replace('closed', 'failure'))
def close_tab(index: int = None) -> bool:
    """关闭指定标签页"""
    global _active_tab_index

    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return False

    page_tabs = [t for t in tabs if t.get('type') == 'page']
    if index is None:
        index = _active_tab_index
    if index < 0 or index >= len(page_tabs):
        return False

    target_id = page_tabs[index].get('id')
    if not target_id:
        return False

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Target.closeTarget',
                          'params': {'targetId': target_id}}))
        ws.close()

        with _created_tab_ids_lock:
            _created_tab_ids.discard(target_id)
        if _active_tab_index >= index and _active_tab_index > 0:
            _active_tab_index -= 1
        return True
    except Exception:
        pass
    return False


def close_extra_tabs(keep_count: int = 2) -> int:
    """
    关闭多余的空白标签页，节省资源
    keep_count: 保留的空白标签页数量，默认为2
    返回关闭的数量
    """
    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return 0

    page_tabs = [t for t in tabs if t.get('type') == 'page']
    blank_tabs = [t for t in page_tabs if not t.get('url') or t.get('url') in ('about:blank', '')]

    with _created_tab_ids_lock:
        # 只关闭我们自己创建的空白标签页
        to_close = [t for t in blank_tabs if t.get('id') in _created_tab_ids]

    if len(to_close) <= keep_count:
        return 0

    closed = 0
    for tab in to_close[keep_count:]:
        tab_id = tab.get('id')
        try:
            import websocket
            ws = websocket.create_connection(ws_url, timeout=5)
            ws.send(json.dumps({'id': 1, 'method': 'Target.closeTarget',
                              'params': {'targetId': tab_id}}))
            ws.close()
            with _created_tab_ids_lock:
                _created_tab_ids.discard(tab_id)
            closed += 1
        except Exception:
            pass

    return closed


def get_created_tab_ids() -> set:
    """获取我们创建的标签页ID集合"""
    with _created_tab_ids_lock:
        return set(_created_tab_ids)


# ============================================================
# Window 管理
# ============================================================

def get_window_bounds() -> dict[str, Any]:
    """获取当前窗口位置和大小"""
    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return {}

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Browser.getWindowBounds',
                          'params': {'windowId': 1}}))
        start = time.time()
        while time.time() - start < 5:
            r = ws.recv()
            if r:
                d = json.loads(r)
                if d.get('id') == 1:
                    ws.close()
                    return d.get('result', {}).get('bounds', {})
        ws.close()
    except Exception:
        pass
    return {}


def set_window_bounds(state: str = 'normal', **kwargs) -> bool:
    """
    设置窗口状态/大小/位置
    state: normal/minimized/maximized/fullscreen
    kwargs: x, y, width, height
    """
    ws_url, tabs = get_cdp_connection()
    if not ws_url:
        return False

    params = {'windowId': 1, 'bounds': {'state': state}}
    if kwargs:
        params['bounds'].update(kwargs)

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Browser.setWindowBounds', 'params': params}))
        ws.close()
        return True
    except Exception:
        pass
    return False


def minimize_window() -> bool:
    """最小化窗口"""
    return set_window_bounds(state='minimized')


def maximize_window() -> bool:
    """最大化窗口"""
    return set_window_bounds(state='maximized')


def restore_window() -> bool:
    """恢复窗口"""
    return set_window_bounds(state='normal')


def set_window_position(x: int, y: int) -> bool:
    """设置窗口位置"""
    return set_window_bounds(state='normal', x=x, y=y)


def set_window_size(width: int, height: int) -> bool:
    """设置窗口大小"""
    return set_window_bounds(state='normal', width=width, height=height)


# ============================================================
# 登录状态检测
# ============================================================

def detect_login_state() -> str:
    """
    检测当前页面登录状态
    返回 'logged_in' | 'logged_out' | 'unknown'
    """
    js = """
    (function() {
        // 1. 检测认证cookie存在（支持多种电商cookie格式）
        const cookieNames = [
            'auth_token', 'sessionid', 'sid', 'token', 'access_token',
            '_t', 'cookie_id', 'user_token', 'login_token',
            'TMM', 'MLOGIN', 'uc1', 'cookie16', 'cookie32',
            '_taobao_', '_m_h5_tk', '_fbp'
        ];
        const cookies = document.cookie.split(';');
        const cookieMap = {};
        cookies.forEach(c => {
            const [k, v] = c.trim().split('=');
            if (k && v) cookieMap[k.trim()] = v.trim();
        });

        // 淘宝/天猫特殊cookie检测
        const taobaoAuth = cookieMap['_m_h5_tk'] || cookieMap['MLOGIN'] ||
                          cookieMap['cookie_id'] || cookieMap['_t'];

        // 百度特殊cookie检测
        const baiduAuth = cookieMap['SESSIONID'] || cookieMap['BDUSS'] || cookieMap['STOKEN'];

        // 2. 检测登录相关DOM元素 - 更全面的选择器（必须实际存在且可见）
        const loginIndicators = [
            // 通用
            document.querySelector('[data-user-id]'),
            document.querySelector('.user-avatar'),
            document.querySelector('.user-name'),
            document.querySelector('[class*="avatar"]'),
            document.querySelector('a[href*="logout"]'),
            document.querySelector('a[href*="signout"]'),
            document.querySelector('[class*=" logged_in"]'),
            // 淘宝/天猫特有
            document.querySelector('.member'),
            document.querySelector('.username'),
            document.querySelector('[class*="nickname"]'),
            document.querySelector('[class*="user-nick"]'),
            document.querySelector('#J_UserInfo'),
            document.querySelector('.site-nav-user'),
            document.querySelector('[class*="userinfo"]'),
            // 京东特有
            document.querySelector('.nickname'),
            document.querySelector('#username'),
            document.querySelector('[class*="user-name"]'),
        ];

        // 检查元素是否可见（display不为none，visibility不为hidden）
        const visibleLoginElement = loginIndicators.find(el => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            return el.offsetParent !== null &&
                   style.display !== 'none' &&
                   style.visibility !== 'hidden';
        });

        // 3. 检测未登录提示（反式检测）- 这是更可靠的信号
        const notLoggedInIndicators = [
            'a[href*="login.taobao"]',
            'a[href*="login.tmall"]',
            'a[href*="passport"]',
            '[class*="login-box"]',
            '#login-form',
        ];
        const hasLoginBox = notLoggedInIndicators.some(sel =>
            document.querySelector(sel)
        );

        // 检查页面是否显示"请登录"
        const pageText = document.body?.innerText || '';
        const hasLoginPrompt = pageText.includes('亲，请登录') ||
                              pageText.includes('请先登录') ||
                              pageText.includes('免费注册');

        // 4. 判断逻辑 - 优先级从高到低

        // 最高优先：检查认证Cookie - 这些是登录的金标准
        // 一旦存在有效auth cookie，就认为已登录，不再看UI
        if (taobaoAuth) {
            return 'logged_in';
        }
        if (baiduAuth) {
            return 'logged_in';
        }

        // 次优先：检查可见的用户信息元素
        if (visibleLoginElement && !hasLoginBox) {
            return 'logged_in';
        }

        // 有登录提示但无用户元素 = 未登录
        if (hasLoginBox || hasLoginPrompt) {
            return 'logged_out';
        }

        // 默认根据是否有用户元素
        return visibleLoginElement ? 'logged_in' : 'logged_out';
    })();
    """
    result = cdp_execute(js)
    return result if result in ('logged_in', 'logged_out') else 'unknown'


def wait_for_manual_login(url: str, timeout: int = 300) -> bool:
    """
    导航到登录页，等待用户手动完成登录

    url: 登录页面URL
    timeout: 最大等待秒数，默认300s

    返回 True 如果检测到登录成功（URL不再包含login关键字）
    """
    print(f'请在浏览器中完成登录，脚本将在 {timeout}s 后自动检测...')
    print(f'导航到: {url}')

    cdp_navigate(url, wait_load=2)
    start = time.time()
    last_state = 'unknown'

    while time.time() - start < timeout:
        current = detect_login_state()
        if current != last_state:
            print(f'  状态: {current}')
            last_state = current

        if current == 'logged_in':
            print('检测到登录成功！')
            return True

        info = get_page_info()
        url_lower = info.get('url', '').lower()

        # 如果URL已离开登录页（登录成功后会跳转）
        if 'login' not in url_lower and 'signin' not in url_lower and 'auth' not in url_lower:
            print(f'  URL已离开登录页: {info.get("url", "")[:50]}')
            # 给页面充分加载时间，然后再次检测登录状态
            time.sleep(3)
            final_state = detect_login_state()
            if final_state == 'logged_in':
                print('检测到登录成功！')
                return True
            else:
                # 如果还是未登录，可能是其他原因导致的跳转
                print(f'  跳转后状态仍为: {final_state}，继续等待...')

        # 每3秒检测一次
        elapsed = int(time.time() - start)
        if elapsed % 15 == 0:
            print(f'  已等待 {elapsed}s，请尽快完成登录...')

        time.sleep(3)

    print(f'等待超时（{timeout}s），未检测到登录状态')
    return False


def need_manual_login(urls_with_auth: list = None) -> tuple[bool, str]:
    """
    检查是否需要对指定网站进行手动登录

    urls_with_auth: 需要登录态的域名列表
    返回 (need_login, domain)
    """
    if urls_with_auth is None:
        urls_with_auth = []

    for domain in urls_with_auth:
        sm = SessionManager(domain)
        if sm.exists() and not sm.is_expired():
            return False, domain
    return True, urls_with_auth[0] if urls_with_auth else ''


# ============================================================
# Session 管理
# ============================================================

SESSION_DIR = os.path.expanduser('~/.chrome-automation/sessions')


class SessionManager:
    """
    Session状态管理器
    保存/加载: cookies + localStorage + sessionStorage
    """

    def __init__(self, domain: str):
        self.domain = domain
        self.session_dir = os.path.join(SESSION_DIR, domain)
        self.metadata_file = os.path.join(self.session_dir, 'metadata.json')
        self.cookies_file = os.path.join(self.session_dir, 'cookies.json')
        self.localstorage_file = os.path.join(self.session_dir, 'localStorage.json')
        self.sessionstorage_file = os.path.join(self.session_dir, 'sessionStorage.json')

    def _ensure_dir(self):
        """确保目录存在"""
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir, exist_ok=True)

    def save(self) -> bool:
        """
        保存当前浏览器session状态
        包括: cookies, localStorage, sessionStorage
        """
        self._ensure_dir()

        # 1. 保存 cookies (CDP Network.getCookies)
        cookies = self._get_cookies_via_cdp()
        if cookies:
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)

        # 2. 保存 localStorage
        localstorage = cdp_execute("""
            JSON.stringify(Object.keys(localStorage).reduce((acc, k) => {
                acc[k] = localStorage.getItem(k);
                return acc;
            }, {}));
        """)
        if localstorage:
            try:
                with open(self.localstorage_file, 'w', encoding='utf-8') as f:
                    json.dump(json.loads(localstorage), f, indent=2)
            except Exception:
                pass

        # 3. 保存 sessionStorage
        sessionstorage = cdp_execute("""
            JSON.stringify(Object.keys(sessionStorage).reduce((acc, k) => {
                acc[k] = sessionStorage.getItem(k);
                return acc;
            }, {}));
        """)
        if sessionstorage:
            try:
                with open(self.sessionstorage_file, 'w', encoding='utf-8') as f:
                    json.dump(json.loads(sessionstorage), f, indent=2)
            except Exception:
                pass

        # 4. 保存 metadata
        info = get_page_info()
        metadata = {
            'domain': self.domain,
            'created_at': time.time(),
            'last_used': time.time(),
            'login_url': info.get('url', ''),
        }
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        return True

    def load(self) -> bool:
        """
        加载session到当前浏览器
        """
        if not self.exists():
            return False

        # 1. 加载 cookies
        self._load_cookies()

        # 2. 加载 localStorage
        if os.path.exists(self.localstorage_file):
            try:
                with open(self.localstorage_file, encoding='utf-8') as f:
                    data = json.load(f)
                for key, value in data.items():
                    cdp_execute(f"localStorage.setItem('{key}', '{value}');")
            except Exception:
                pass

        # 3. 加载 sessionStorage
        if os.path.exists(self.sessionstorage_file):
            try:
                with open(self.sessionstorage_file, encoding='utf-8') as f:
                    data = json.load(f)
                for key, value in data.items():
                    cdp_execute(f"sessionStorage.setItem('{key}', '{value}');")
            except Exception:
                pass

        # 4. 更新 last_used
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata['last_used'] = time.time()
                with open(self.metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
            except Exception:
                pass

        return True

    def exists(self) -> bool:
        """检查session是否存在"""
        return os.path.exists(self.metadata_file)

    def is_expired(self, days: int = 30) -> bool:
        """检查session是否过期"""
        if not self.exists():
            return True
        try:
            with open(self.metadata_file, encoding='utf-8') as f:
                metadata = json.load(f)
            last_used = metadata.get('last_used', 0)
            age_days = (time.time() - last_used) / 86400
            return age_days > days
        except Exception:
            return True

    def get_age_days(self) -> float:
        """获取session年龄（天）"""
        if not self.exists():
            return 0
        try:
            with open(self.metadata_file, encoding='utf-8') as f:
                metadata = json.load(f)
            created = metadata.get('created_at', time.time())
            return (time.time() - created) / 86400
        except Exception:
            return 0

    def delete(self):
        """删除session"""
        import shutil
        if os.path.exists(self.session_dir):
            shutil.rmtree(self.session_dir)

    def get_info(self) -> dict:
        """获取session信息"""
        if not self.exists():
            return {}
        try:
            with open(self.metadata_file, encoding='utf-8') as f:
                metadata = json.load(f)
            return {
                'domain': self.domain,
                'age_days': round(self.get_age_days(), 1),
                'expired': self.is_expired(),
                'last_url': metadata.get('login_url', ''),
            }
        except Exception:
            return {}

    def _get_cookies_via_cdp(self) -> list:
        """通过CDP Network.getCookies获取完整cookie"""
        ws_url, _ = get_cdp_connection()
        if not ws_url:
            return []

        try:
            import websocket
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
            time.sleep(0.1)

            # 获取所有cookies
            ws.send(json.dumps({'id': 2, 'method': 'Network.getAllCookies'}))

            start = time.time()
            cookies = []
            while time.time() - start < 5:
                r = ws.recv()
                if r:
                    d = json.loads(r)
                    if d.get('id') == 2:
                        cookies = d.get('result', {}).get('cookies', [])
                        break
            ws.close()
            return cookies
        except Exception:
            return []

    def _load_cookies(self):
        """加载cookies到浏览器"""
        if not os.path.exists(self.cookies_file):
            return

        try:
            with open(self.cookies_file, encoding='utf-8') as f:
                cookies = json.load(f)

            if not cookies:
                return

            import websocket
            ws_url, _ = get_cdp_connection()
            if not ws_url:
                return

            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
            time.sleep(0.2)

            # 设置所有cookies（不过滤httpOnly，因为CDP可以设置任何cookie）
            success_count = 0
            for cookie in cookies:
                params = {
                    'name': cookie.get('name', ''),
                    'value': cookie.get('value', ''),
                }

                # 添加domain（淘宝/天猫）
                cookie_domain = cookie.get('domain', '')
                if cookie_domain:
                    params['domain'] = cookie_domain

                # path
                path = cookie.get('path', '/')
                if path:
                    params['path'] = path

                # secure
                params['secure'] = cookie.get('secure', False)

                # sameSite
                same_site = cookie.get('sameSite', 'lax')
                if same_site and same_site != 'None':
                    params['sameSite'] = same_site

                ws.send(json.dumps({
                    'id': 10,
                    'method': 'Network.setCookie',
                    'params': params
                }))

                # Wait for response
                start = time.time()
                while time.time() - start < 2:
                    r = ws.recv()
                    if r:
                        d = json.loads(r)
                        if d.get('id') == 10:
                            if d.get('result', {}).get('success', False):
                                success_count += 1
                            break
            ws.close()
            print(f'  _load_cookies: 设置了 {success_count}/{len(cookies)} 个cookies')
        except Exception:
            pass


def save_session(domain: str) -> bool:
    """保存指定域名的session"""
    sm = SessionManager(domain)
    return sm.save()


def load_session(domain: str) -> bool:
    """加载指定域名的session"""
    sm = SessionManager(domain)
    return sm.load()


def list_sessions() -> list:
    """列出所有已保存的session"""
    if not os.path.exists(SESSION_DIR):
        return []

    sessions = []
    for domain in os.listdir(SESSION_DIR):
        domain_dir = os.path.join(SESSION_DIR, domain)
        if os.path.isdir(domain_dir):
            sm = SessionManager(domain)
            sessions.append(sm.get_info())
    return sessions


def delete_session(domain: str):
    """删除指定域名的session"""
    sm = SessionManager(domain)
    sm.delete()


# ============================================================
# Async 异步操作
# ============================================================

import asyncio


def _make_async(func):
    """将同步函数包装为async协程"""
    async def async_wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: func(*args, **kwargs)
        )
        return result
    return async_wrapper


async_cdp_navigate = _make_async(cdp_navigate)
async_click_element = _make_async(click_element)
async_input_text = _make_async(input_text)
async_submit_form = _make_async(submit_form)
async_get_elements = _make_async(get_elements)
async_get_page_info = _make_async(get_page_info)


def exec_async(coro) -> any:
    """
    从同步上下文执行async协程
    用法: result = exec_async(async_click_element('搜索', tag='A'))
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def exec_async_with_callback(coro, on_success=None, on_failure=None):
    """
    异步执行协程，带回调
    返回Future，可添加回调: future.add_done_callback(fn)
    """
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
            if on_success:
                on_success(result)
            return result
        except Exception as e:
            if on_failure:
                on_failure(e)
            raise
        finally:
            loop.close()

    return _executor.submit(run)


# ============================================================
# Cookies 管理
# ============================================================

COOKIES_FILE = os.path.expanduser('~/.chrome-automation/cookies.json')


@browser_operation(EventTypes.SAVE_COOKIES_SUCCESS, EventTypes.SAVE_COOKIES_FAILURE)
def save_cookies() -> bool:
    """保存当前网站的cookies到本地"""
    ws_url, _ = get_cdp_connection()
    if not ws_url:
        return False

    random_delay(100, 300)

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        ws.send(json.dumps({'id': 2, 'method': 'Network.enable'}))
        time.sleep(0.3)

        ws.send(json.dumps({'id': 99, 'method': 'Runtime.evaluate',
                          'params': {'expression': 'document.cookie', 'returnByValue': True}}))

        start = time.time()
        while time.time() - start < 8:
            try:
                r = ws.recv()
                if r:
                    d = json.loads(r)
                    if d.get('id') == 99:
                        cookies_str = d['result'].get('result', {}).get('value', '')
                        ws.close()

                        page_info = get_page_info()
                        url = page_info.get('url', '')

                        cookies_list = []
                        for part in cookies_str.split(';'):
                            part = part.strip()
                            if '=' in part:
                                name, value = part.split('=', 1)
                                cookies_list.append({
                                    'name': name.strip(),
                                    'value': value.strip(),
                                    'domain': url.split('/')[2] if '/' in url else ''
                                })

                        os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
                        with open(COOKIES_FILE, 'w') as f:
                            json.dump({'url': url, 'cookies': cookies_list}, f)

                        return True
            except Exception:
                pass
        ws.close()
    except Exception:
        pass

    return False


@browser_operation(EventTypes.LOAD_COOKIES_SUCCESS, EventTypes.LOAD_COOKIES_FAILURE)
def load_cookies() -> bool:
    """从本地加载cookies到当前页面"""
    if not os.path.exists(COOKIES_FILE):
        return False

    random_delay(100, 300)

    try:
        with open(COOKIES_FILE) as f:
            data = json.load(f)

        cookies = data.get('cookies', [])
        if not cookies:
            return False

        ws_url, _ = get_cdp_connection()
        if not ws_url:
            return False

        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        time.sleep(0.2)

        for cookie in cookies:
            js = f'document.cookie = "{cookie["name"]}={cookie["value"]}";'
            ws.send(json.dumps({'id': 99, 'method': 'Runtime.evaluate',
                              'params': {'expression': js, 'returnByValue': True}}))
            random_delay(50, 150)

        ws.close()
        return True
    except Exception:
        pass

    return False


# ============================================================
# 调试工具
# ============================================================

def dump_elements(elements: list[dict], limit: int = 30):
    """打印元素列表"""
    print(f'\n=== Found {len(elements)} elements ===')
    interactive = [e for e in elements if _is_interactive(e)]
    print(f'  ({len(interactive)} interactive)')

    for i, e in enumerate(elements[:limit]):
        tag = e.get('tag', '')[:12]
        txt = e.get('text', '')[:25]
        x, y = e.get('x', 0), e.get('y', 0)
        inter = '✓' if _is_interactive(e) else ' '
        print(f'  [{i}] {inter} {tag:12s} {txt:25s} @ ({x:.0f},{y:.0f})')

    if len(elements) > limit:
        print(f'  ... and {len(elements) - limit} more')
    print()


if __name__ == '__main__':
    print('Chrome Browser Automation Engine')
    print(f'Stealth Level: {STEALTH_LEVEL}')
    print('Testing connection...')

    health = get_browser_health()
    print(f'Browser Health: {health["health_score"]}% | Alive: {health["is_alive"]} | Idle: {health["idle_seconds"]}s')
    if health['issues']:
        print(f'Issues: {health["issues"]}')

    info = get_page_info()
    if info:
        print(f'Current page: {info.get("title", "")}')
        print(f'URL: {info.get("url", "")}')
    else:
        print('No Chrome connection found.')
        print('Start Chrome with: open -a "Google Chrome" --args --remote-debugging-port=9222 --remote-allow-origins=*')
