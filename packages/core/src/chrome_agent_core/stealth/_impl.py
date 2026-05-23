#!/usr/bin/env python3
"""
Stealth Mode - Anti-Detection Utilities
反检测工具 - 模拟真人操作行为
"""
import random
import time


def random_delay(min_ms: float = 100, max_ms: float = 1000):
    """
    随机延迟，模拟真人操作间隔
    默认100ms-1s，更激进的防检测可以设到5s
    """
    delay = random.uniform(min_ms, max_ms) / 1000
    time.sleep(delay)


def random_mouse_move(from_x: int = None, from_y: int = None,
                      to_x: int = None, to_y: int = None,
                      steps: int = None):
    """
    模拟真人鼠标移动，带加速曲线（不是匀速）
    """
    try:
        import pyautogui

        # Get current position if not provided
        if from_x is None or from_y is None:
            pos = pyautogui.position()
            from_x, from_y = pos.x, pos.y

        # Random target if not provided
        if to_x is None or to_y is None:
            to_x = from_x + random.randint(-50, 50)
            to_y = from_y + random.randint(-50, 50)

        # Random steps
        if steps is None:
            steps = random.randint(5, 15)

        # Generate bezier-like points with acceleration curve
        # Start slow, speed up, then slow down near end
        points = []
        for i in range(steps + 1):
            t = i / steps
            # Ease in-out curve
            ease = t * t * (3 - 2 * t) if random.random() > 0.3 else t
            x = from_x + (to_x - from_x) * ease + random.uniform(-2, 2)
            y = from_y + (to_y - from_y) * ease + random.uniform(-2, 2)
            points.append((x, y))

        # Move through points with variable speed
        for i, (x, y) in enumerate(points):
            duration = random.uniform(0.01, 0.05)
            pyautogui.moveTo(x, y, duration=duration)
            if i < len(points) - 1:
                time.sleep(random.uniform(0.005, 0.02))

    except ImportError:
        pass


def human_scroll(element_selector: str = None, direction: str = 'down',
                 amount: int = None, step_delay: bool = True):
    """
    模拟人类滚动，带随机停顿
    """
    if amount is None:
        amount = random.randint(3, 8)

    try:
        import pyautogui

        if direction == 'down':
            scroll_func = pyautogui.scroll
            scroll_amount = -random.randint(100, 300)
        else:
            scroll_func = pyautogui.scroll
            scroll_amount = random.randint(100, 300)

        for i in range(amount):
            scroll_func(scroll_amount)
            if step_delay:
                random_delay(200, 600)
    except:
        pass


def human_click(x: int, y: int, with_move: bool = True):
    """
    模拟人类点击 - 移动到目标后再点击
    """
    try:
        import pyautogui

        if with_move:
            # Move with bezier curve
            random_mouse_move(to_x=x, to_y=y)

        # Random pause before click
        random_delay(50, 200)

        # Click with slight randomness
        pyautogui.click(x + random.randint(-2, 2), y + random.randint(-2, 2))

    except ImportError:
        pass


def human_typing(text: str, min_char_delay: float = 0.03, max_char_delay: float = 0.12):
    """
    模拟人类打字 - 每个字符之间有随机延迟
    """
    try:
        import pyautogui

        for char in text:
            # Type character
            if char == ' ':
                pyautogui.press('space')
            elif char == '\n':
                pyautogui.press('enter')
            else:
                pyautogui.typewrite(char, interval=random.uniform(min_char_delay, max_char_delay))

            # Random pause between characters
            if random.random() > 0.7:
                random_delay(50, 150)

    except ImportError:
        pass


def random_scroll_page():
    """随机滚动页面，模拟人类浏览"""
    try:
        import pyautogui

        # Scroll down a bit
        amount = random.randint(200, 500)
        pyautogui.scroll(-amount)
        random_delay(500, 1500)

        # Maybe scroll back up a little
        if random.random() > 0.7:
            pyautogui.scroll(random.randint(100, 300))
    except:
        pass


def page_load_delay(min_sec: float = 2, max_sec: float = 5):
    """页面加载后的随机等待"""
    random_delay(min_sec * 1000, max_sec * 1000)


def before_action_delay():
    """操作前的随机延迟（100-500ms）"""
    random_delay(100, 500)


def after_action_delay():
    """操作后的随机延迟（200-800ms）"""
    random_delay(200, 800)


# ============================================================
# 反检测配置
# ============================================================

STEALTH_CONFIGS = {
    'relaxed': {
        'min_delay_ms': 100,
        'max_delay_ms': 500,
        'mouse_move': True,
        'scroll_chance': 0.3,
    },
    'normal': {
        'min_delay_ms': 200,
        'max_delay_ms': 800,
        'mouse_move': True,
        'scroll_chance': 0.4,
    },
    'strict': {
        'min_delay_ms': 500,
        'max_delay_ms': 2000,
        'mouse_move': True,
        'scroll_chance': 0.5,
    },
    'maximum': {
        'min_delay_ms': 1000,
        'max_delay_ms': 5000,
        'mouse_move': True,
        'scroll_chance': 0.6,
    },
}


def apply_stealth(config: str = 'normal'):
    """
    应用预设的反检测配置
    返回一个包含各种延迟函数的字典
    """
    cfg = STEALTH_CONFIGS.get(config, STEALTH_CONFIGS['normal'])

    return {
        'before_action': lambda: random_delay(cfg['min_delay_ms'], cfg['max_delay_ms']),
        'after_action': lambda: random_delay(cfg['min_delay_ms'] * 2, cfg['max_delay_ms'] * 2),
        'page_load': lambda: random_delay(cfg['min_delay_ms'] * 10, cfg['max_delay_ms'] * 5),
        'scroll': lambda: random_scroll_page() if random.random() < cfg['scroll_chance'] else None,
        'mouse_move': lambda x, y, with_move=True: random_mouse_move(to_x=x, to_y=y) if cfg['mouse_move'] else None,
    }


if __name__ == '__main__':
    print('Stealth Mode Utilities')
    print('Testing random delays...')

    print('Relaxed config:')
    s = apply_stealth('relaxed')
    start = time.time()
    s['before_action']()
    print(f'  Delay: {time.time() - start:.3f}s')

    print('Strict config:')
    s = apply_stealth('strict')
    start = time.time()
    s['before_action']()
    print(f'  Delay: {time.time() - start:.3f}s')
