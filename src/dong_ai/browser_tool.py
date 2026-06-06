"""
浏览器工具 — 使用 Chrome headless 操控网页

依赖：Chrome（~/.agent-browser 中已有），零 Python 依赖

工具：
  browser_navigate url=https://... → 获取渲染后页面文本
  browser_screenshot url=https://... → 截图保存到桌面
"""

import subprocess, os, re, time
from pathlib import Path


def _find_chrome() -> str:
    """自动发现 Chrome/Chromium 路径"""
    candidates = [
        "/home/administrator/.agent-browser/browsers/chrome-*/chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    import glob
    for c in candidates:
        if "*" in c:
            matches = sorted(glob.glob(c))
            if matches:
                return matches[-1]  # 最新版本
        elif os.path.exists(c):
            return c
    return "google-chrome"  # 兜底


CHROME = _find_chrome()
BASE_FLAGS = ["--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
              "--disable-software-rasterizer", "--disable-extensions"]


def navigate(url: str, timeout: int = 15) -> str:
    """打开网页，返回渲染后的纯文本内容"""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        result = subprocess.run(
            [CHROME, *BASE_FLAGS, "--dump-dom", url],
            capture_output=True, text=True, timeout=timeout
        )
        html = result.stdout

        # 提取标题
        title = ""
        m = re.search(r'<title>([^<]+)', html)
        if m: title = m.group(1).strip()

        # 提取正文文本
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())

        # 截断
        if len(text) > 8000:
            text = text[:8000] + f"\n\n... (共 {len(text)} 字符，已截断)"

        return f"📄 {title or url}\n{'='*40}\n{text[:5000]}"

    except subprocess.TimeoutExpired:
        return "⏱ 页面加载超时"
    except FileNotFoundError:
        return "❌ Chrome 未找到"
    except Exception as e:
        return f"❌ {e}"


def screenshot(url: str, timeout: int = 15) -> str:
    """截图网页，保存到桌面"""
    if not url.startswith("http"):
        url = "https://" + url
    output = str(Path.home() / "Desktop" / f"screenshot_{int(time.time())}.png")
    try:
        result = subprocess.run(
            [CHROME, *BASE_FLAGS, "--screenshot=" + output,
             "--window-size=1280,720", url],
            capture_output=True, text=True, timeout=timeout
        )
        if os.path.exists(output):
            size = os.path.getsize(output)
            return f"✅ 截图已保存: {output} ({size:,} 字节)"
        else:
            return "❌ 截图失败"
    except subprocess.TimeoutExpired:
        return "⏱ 截图超时"
    except Exception as e:
        return f"❌ {e}"
