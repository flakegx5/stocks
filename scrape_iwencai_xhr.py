#!/usr/bin/env python3
"""
同花顺问财 港股数据抓取 v2 —— Playwright + XHR Response 拦截
完全独立运行，无需 Claude browser session。

用法:
  首次登录:   python3 scrape_iwencai_xhr.py --login
  日常抓取:   python3 scrape_iwencai_xhr.py
  调试模式:   python3 scrape_iwencai_xhr.py --debug   （保存原始 API 响应）
  抓取后重建: python3 scrape_iwencai_xhr.py --build   （完成后自动运行 build_html.py）
"""

import json
import sys
import time
import threading
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("❌ 未安装 playwright，请先运行：")
    print("   pip3 install playwright")
    print("   python3 -m playwright install chromium")
    sys.exit(1)

# ---- 路径 ----
BASE_DIR    = Path(__file__).parent
COOKIE_FILE = BASE_DIR / 'iwencai_cookies.json'
OUTPUT_JSON = BASE_DIR / 'hk_stocks_data_new.json'
DEBUG_DIR   = BASE_DIR / 'debug_responses'

# ---- 查询 URL（含权益合计）----
QUERY_URL = (
    "https://www.iwencai.com/unifiedwap/result"
    "?w=港股范围内，市值大于50亿港元，列出最新pe、pb、总股本、所属行业，"
    "列出2023年一季报和2025年年报的分别以下数字，包括：归母净利润、总现金、"
    "流动资产、总负债、短期借款、长期借款、ROE、ROIC、经营活动现金流净额、"
    "投资活动现金流净额、资本性支出、融资活动现金流量净额、年度分红、"
    "现金流量表中的股份回购、现金流量表中的支付股息，归母净利润同比增速，权益合计。"
    "&querytype=hkstock"
)

# iwencai 数据 API 的 URL 特征（用于过滤无关响应）
DATA_URL_KEYWORDS = [
    'get-robot-data',
    'unified-result-datas',
    'stockpick-result',
    'unifiedwap/result-datas',
    'wencai.com/stockpick',
]

# ---- Session 工具（cookie + localStorage）----
SESSION_FILE = BASE_DIR / 'iwencai_session.json'

def load_session(context):
    """加载 cookie；localStorage 在导航后由 inject_localstorage() 注入。"""
    f = SESSION_FILE if SESSION_FILE.exists() else COOKIE_FILE
    if not f.exists():
        return False
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        # 兼容旧格式（纯 cookie list）和新格式（{cookies, localStorage}）
        cookies = data.get('cookies', data) if isinstance(data, dict) and 'cookies' in data else data
        if isinstance(cookies, list):
            context.add_cookies(cookies)
        print(f"✅ 已加载 {len(cookies)} 个 cookie（{f.name}）")
        return True
    except Exception as e:
        print(f"⚠️  Session 加载失败: {e}")
        return False


def inject_localstorage(page):
    """把保存的 localStorage 注入当前页面（需在 goto 之后调用）。"""
    f = SESSION_FILE
    if not f.exists():
        return
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        ls = data.get('localStorage', {})
        if not ls:
            return
        page.evaluate("""(items) => {
            for (const [k, v] of Object.entries(items)) {
                try { localStorage.setItem(k, v); } catch(e) {}
            }
        }""", ls)
        print(f"✅ 已注入 {len(ls)} 条 localStorage")
    except Exception as e:
        print(f"⚠️  localStorage 注入失败: {e}")


def save_session(context, page):
    """保存 cookie + localStorage 到 iwencai_session.json。"""
    cookies = context.cookies()
    # 读取 localStorage（排除过大的值）
    ls = page.evaluate("""() => {
        const out = {};
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            const v = localStorage.getItem(k);
            if (v && v.length < 4096) out[k] = v;
        }
        return out;
    }""")
    session = {'cookies': cookies, 'localStorage': ls}
    SESSION_FILE.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"✅ 已保存 {len(cookies)} 个 cookie + {len(ls)} 条 localStorage → {SESSION_FILE}")


# ---- API 响应解析 ----
def _extract_from_response(body, debug=False):
    """
    尝试从 iwencai API 原始响应中提取行数据（list of dict）。
    iwencai 的 stockpick API 有几种常见结构，逐一尝试。
    返回 None 表示未识别格式。
    """
    # 结构 A: data.answer[].txt[]/txt_list[].content.components[].data.datas
    # 实测路径: data.answer[0].txt[0].content.components[0].data.datas
    try:
        for answer in body.get('data', {}).get('answer', []):
            for txt_key in ('txt', 'txt_list'):
                for txt in answer.get(txt_key, []):
                    for comp in txt.get('content', {}).get('components', []):
                        datas = comp.get('data', {}).get('datas')
                        if isinstance(datas, list) and len(datas) > 0 and isinstance(datas[0], dict):
                            if debug:
                                print(f"    [结构A/{txt_key}] datas 行数={len(datas)}")
                            return datas
    except Exception:
        pass

    # 结构 B1: answer.components[].data.datas（getDataList 翻页端点）
    try:
        for comp in body.get('answer', {}).get('components', []):
            datas = comp.get('data', {}).get('datas')
            if isinstance(datas, list) and len(datas) > 0 and isinstance(datas[0], dict):
                if debug:
                    print(f"    [结构B1/getDataList] datas 行数={len(datas)}")
                return datas
    except Exception:
        pass

    # 结构 B2: data.datas（扁平）
    try:
        datas = body.get('data', {}).get('datas')
        if isinstance(datas, list) and len(datas) > 5 and isinstance(datas[0], dict):
            if debug:
                print(f"    [结构B2] datas 行数={len(datas)}")
            return datas
    except Exception:
        pass

    # 结构 C: data 本身就是 list
    try:
        datas = body.get('data')
        if isinstance(datas, list) and len(datas) > 5 and isinstance(datas[0], dict):
            if debug:
                print(f"    [结构C] data is list 行数={len(datas)}")
            return datas
    except Exception:
        pass

    # 结构 D: rows 直接在顶层（已是我们保存格式，跳过）
    if 'rows' in body and 'keys' in body:
        return None

    return None


def _is_data_url(url: str) -> bool:
    return any(kw in url for kw in DATA_URL_KEYWORDS)


# ---- 登录流程 ----
def do_login():
    print("🔐 打开浏览器，请手动登录同花顺问财...")
    print("   登录完成后回到终端，按 Enter 保存 cookie。\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto("https://www.iwencai.com/")
        input(">>> 浏览器已打开，请登录后按 Enter：")
        save_session(context, page)
        browser.close()
    print("✅ 登录完成，下次运行 python3 scrape_iwencai_xhr.py 即可自动抓取。")


# ---- 主抓取流程 ----
def do_scrape(debug=False):
    if not SESSION_FILE.exists() and not COOKIE_FILE.exists():
        print("❌ 未找到登录 session，请先运行：python3 scrape_iwencai_xhr.py --login")
        sys.exit(1)

    if debug:
        DEBUG_DIR.mkdir(exist_ok=True)
        print(f"🐛 调试模式：原始响应将保存到 {DEBUG_DIR}/")

    captured_req = {}    # 备用：保留 on_request 以防以后需要
    page1_meta   = {}    # 从第 1 页响应 meta 提取总行数
    all_rows     = []
    seen_pages   = set() # 去重：避免同一页被多次处理

    DATA_URLS = ('get-robot-data', 'getDataList')

    def on_response(resp):
        if not any(kw in resp.url for kw in DATA_URLS):
            return
        try:
            body = resp.json()
        except Exception:
            return

        # 提取 meta（含总行数）和当前页码
        cur_page = None
        # 结构 A（get-robot-data）: body['data']['answer'][0].txt[].content.components[].data.meta
        try:
            answer = body['data']['answer'][0]
            for txt_key in ('txt', 'txt_list'):
                for txt in answer.get(txt_key, []):
                    content = txt.get('content', {})
                    for comp in content.get('components', []):
                        meta = comp.get('data', {}).get('meta', {})
                        if meta:
                            if not page1_meta:
                                page1_meta.update(meta)
                            cur_page = meta.get('page', 1)
        except Exception:
            pass
        # 结构 B1（getDataList）: body['answer']['components'][].data.meta
        if cur_page is None:
            try:
                for comp in body.get('answer', {}).get('components', []):
                    meta = comp.get('data', {}).get('meta', {})
                    if meta:
                        if not page1_meta:
                            page1_meta.update(meta)
                        cur_page = meta.get('page', None)
                        break
            except Exception:
                pass

        if cur_page is not None and cur_page in seen_pages:
            return   # 已处理过这一页，跳过
        if cur_page is not None:
            seen_pages.add(cur_page)

        if debug:
            (DEBUG_DIR / f'resp_pg{cur_page}.json').write_text(
                json.dumps(body, ensure_ascii=False, indent=2), encoding='utf-8'
            )

        rows = _extract_from_response(body, debug=debug)
        if rows:
            all_rows.extend(rows)
            extra = page1_meta.get('extra', {})
            row_count = extra.get('row_count', '?')
            print(f"  ✅ 第 {cur_page} 页: {len(rows)} 行  (累计 {len(all_rows)}, 总行数={row_count})")

    max_pages = 30  # 备用上限

    with sync_playwright() as p:
        print("🚀 启动无头浏览器...")
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        load_session(context)
        pw_page = context.new_page()
        pw_page.on('response', on_response)

        print("🌐 注入登录态...")
        pw_page.goto("https://www.iwencai.com/", timeout=30_000, wait_until='domcontentloaded')
        inject_localstorage(pw_page)

        print("🌐 导航到查询页面...")
        try:
            pw_page.goto(QUERY_URL, timeout=60_000, wait_until='networkidle')
        except PWTimeout:
            print("⚠️  networkidle 超时，继续...")

        time.sleep(3)  # 确保第 1 页响应回调完成

        if debug:
            pw_page.screenshot(path=str(DEBUG_DIR / 'page1.png'))

        if not all_rows:
            print("❌ 第 1 页未抓到数据")
            browser.close()
            return False

        extra = page1_meta.get('extra', {})
        row_count = extra.get('row_count', 0)
        print(f"  总行数={row_count}")

        # 点击"下页"按钮翻页，每次等待 on_response 收到新数据
        print(f"📄 开始点击翻页（目标 {row_count} 行）...")

        def _next_btn_state():
            """检查"下页"按钮状态：'ok' / 'disabled' / 'notfound'，并返回调试信息。"""
            return pw_page.evaluate("""() => {
                const lis = document.querySelectorAll('.pager li, .pcwencai-pagination li');
                const info = [];
                let result = 'notfound';
                for (const li of lis) {
                    const txt = li.textContent.trim();
                    info.push(txt + (li.classList.contains('disabled') ? '[D]' : ''));
                    if (txt === '下页') {
                        result = li.classList.contains('disabled') ? 'disabled' : 'ok';
                    }
                }
                return {state: result, items: info};
            }""")

        pg = 1
        while len(all_rows) < row_count and pg < max_pages:
            btn = _next_btn_state()
            state = btn['state'] if isinstance(btn, dict) else btn
            if debug:
                print(f"  [分页按钮] {btn}")
            if state == 'notfound':
                print("  ⚠️  未找到下页按钮，停止")
                break
            if state == 'disabled':
                print(f"  ✅ 已到最后一页，停止")
                break

            # 用 expect_response 等待翻页 API 响应（getDataList 或 get-robot-data）
            try:
                with pw_page.expect_response(
                    lambda r: any(kw in r.url for kw in ('getDataList', 'get-robot-data')),
                    timeout=15_000
                ):
                    pw_page.locator('.pcwencai-pagination li:last-child a').scroll_into_view_if_needed()
                    pw_page.click('.pcwencai-pagination li:last-child a', timeout=5_000)
            except Exception as e:
                print(f"  ⚠️  第 {pg+1} 页点击/等待失败: {e}")
                break
            pg += 1
            time.sleep(1.5)  # 等待 on_response 回调 + Vue 组件重绘

        browser.close()

    print(f"\n📊 抓取完成：共 {len(seen_pages)} 页，{len(all_rows)} 行")

    if not all_rows:
        print("❌ 未抓取到任何数据，不覆盖输出文件")
        if not debug:
            print("   建议运行 --debug 模式查看原始响应")
        return False

    # 收集所有字段名（保持顺序）
    all_keys: list[str] = []
    seen_keys: set[str] = set()
    for row in all_rows:
        for k in row.keys():
            if k not in seen_keys:
                seen_keys.add(k)
                all_keys.append(k)

    output = {'rows': all_rows, 'keys': all_keys}
    OUTPUT_JSON.write_text(
        json.dumps(output, ensure_ascii=False), encoding='utf-8'
    )
    print(f"💾 已保存 → {OUTPUT_JSON}  ({OUTPUT_JSON.stat().st_size / 1024 / 1024:.2f} MB)")
    return True


# ---- 入口 ----
if __name__ == '__main__':
    args = set(sys.argv[1:])

    if '--login' in args:
        do_login()
        sys.exit(0)

    debug = '--debug' in args
    build = '--build' in args
    push  = '--push'  in args

    success = do_scrape(debug=debug)

    if success and build:
        import subprocess
        print("\n🔨 运行 build_html.py...")
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / 'build_html.py')],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print("❌ build_html.py 出错:", result.stderr)
        else:
            print("✅ HTML 已重建")

        if push:
            from datetime import datetime
            ts = datetime.now().strftime('%Y-%m-%d %H:%M')
            print(f"\n📤 推送至 GitHub ({ts})...")
            subprocess.run(['git', 'add',
                            'hk_stocks_data_new.json', 'data.js', 'index.html'],
                           cwd=BASE_DIR)
            ret = subprocess.run(
                ['git', 'commit', '-m', f'数据更新: {ts}'],
                cwd=BASE_DIR
            )
            if ret.returncode == 0:
                subprocess.run(['git', 'push'], cwd=BASE_DIR)
                print("✅ 已推送至 GitHub")
            else:
                print("⚠️  无变更可提交，跳过 push")
