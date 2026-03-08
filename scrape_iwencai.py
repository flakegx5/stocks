#!/usr/bin/env python3
"""
同花顺问财 港股数据抓取脚本
抓取市值大于100亿港元的港股，包含 PE/PB/年报/季报等财务指标
"""

import json
import csv
import time
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("❌ 未安装 playwright，请先运行：")
    print("   pip3 install playwright")
    print("   python3 -m playwright install chromium")
    sys.exit(1)

QUERY_URL = (
    "https://www.iwencai.com/unifiedwap/result"
    "?w=港股范围内，市值大于100亿港元，列出最新pe、pb、总股本、所属行业，"
    "列出2024年年报和2025年三季报的分别以下数字，包括：归母净利润、总现金、"
    "流动资产、总负债、短期借款、长期借款、ROE、ROIC、经营活动现金流净额、"
    "投资活动现金流净额、资本性支出、融资活动现金流量净额、年度分红、"
    "现金流量表中的股份回购、现金流量表中的支付股息，归母净利润同比增速。"
    "&querytype=hkstock"
)

OUTPUT_JSON = Path(__file__).parent / "hk_stocks_data.json"
OUTPUT_CSV  = Path(__file__).parent / "hk_stocks_data.csv"


def wait_for_table(page, timeout=30000):
    """等待表格加载完成"""
    try:
        # 等待表格行出现
        page.wait_for_selector("table tbody tr, .stock-table tr, [class*='table'] tr, [class*='row']",
                                timeout=timeout)
        time.sleep(2)  # 额外等待数据渲染
        return True
    except PlaywrightTimeoutError:
        return False


def extract_table_data(page):
    """从当前页面提取表格数据"""
    return page.evaluate("""
    () => {
        const result = { headers: [], rows: [] };

        // 尝试多种表格选择器
        let table = document.querySelector('table');

        if (table) {
            // 标准 HTML table
            const headerCells = table.querySelectorAll('thead th, thead td, tr:first-child th, tr:first-child td');
            result.headers = Array.from(headerCells).map(th => th.innerText.trim()).filter(t => t);

            const bodyRows = table.querySelectorAll('tbody tr');
            if (bodyRows.length === 0) {
                // 没有 tbody，取所有 tr 跳过第一行
                const allRows = table.querySelectorAll('tr');
                for (let i = 1; i < allRows.length; i++) {
                    const cells = allRows[i].querySelectorAll('td, th');
                    const rowData = Array.from(cells).map(c => c.innerText.trim());
                    if (rowData.some(d => d)) result.rows.push(rowData);
                }
            } else {
                bodyRows.forEach(tr => {
                    const cells = tr.querySelectorAll('td');
                    const rowData = Array.from(cells).map(c => c.innerText.trim());
                    if (rowData.some(d => d)) result.rows.push(rowData);
                });
            }
        } else {
            // 尝试 div 模拟表格（问财常见结构）
            const tableWrap = document.querySelector(
                '[class*="wencai-table"], [class*="result-table"], [class*="stock-list"], ' +
                '[class*="DataGrid"], [class*="data-table"], .tableWrap, .table-wrap'
            );
            if (tableWrap) {
                const headerRow = tableWrap.querySelectorAll('[class*="head"] [class*="cell"], [class*="header"] [class*="col"], th');
                result.headers = Array.from(headerRow).map(h => h.innerText.trim()).filter(t => t);

                const dataRows = tableWrap.querySelectorAll('[class*="body"] [class*="row"], [class*="data-row"], [class*="tr"]');
                dataRows.forEach(row => {
                    const cells = row.querySelectorAll('[class*="cell"], [class*="col"], td');
                    const rowData = Array.from(cells).map(c => c.innerText.trim());
                    if (rowData.some(d => d)) result.rows.push(rowData);
                });
            }
        }

        // 提取分页信息
        const paginationEl = document.querySelector('[class*="pagination"], [class*="page"], .ant-pagination');
        let totalPages = 1;
        let currentPage = 1;
        if (paginationEl) {
            const pageText = paginationEl.innerText;
            const totalMatch = pageText.match(/共\s*(\d+)\s*[页条]/);
            const currentMatch = paginationEl.querySelector('[class*="active"], .ant-pagination-item-active');
            if (totalMatch) totalPages = parseInt(totalMatch[1]);
            if (currentMatch) currentPage = parseInt(currentMatch.innerText) || 1;
        }

        // 尝试从页面其他地方找总数
        const totalEl = document.querySelector('[class*="total"], [class*="count"]');
        const totalText = totalEl ? totalEl.innerText : '';

        return { ...result, totalPages, currentPage, totalText, url: window.location.href };
    }
    """)


def go_to_next_page(page):
    """点击下一页，返回是否成功"""
    try:
        # 尝试多种"下一页"按钮选择器
        next_selectors = [
            'button:has-text("下一页")',
            'a:has-text("下一页")',
            '[class*="next"]:not([disabled])',
            '.ant-pagination-next:not(.ant-pagination-disabled)',
            'li.ant-pagination-next:not(.ant-pagination-disabled) a',
            '[aria-label="next"]',
        ]
        for sel in next_selectors:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(3)
                return True
        return False
    except Exception as e:
        print(f"  翻页出错: {e}")
        return False


def take_debug_screenshot(page, name="debug"):
    """保存调试截图"""
    path = Path(__file__).parent / f"{name}.png"
    page.screenshot(path=str(path))
    print(f"  📸 截图已保存: {path}")


def scrape():
    all_rows = []
    headers = []

    with sync_playwright() as p:
        print("🚀 启动浏览器...")
        browser = p.chromium.launch(
            headless=False,  # 显示浏览器窗口，方便观察和手动处理验证码
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        print(f"🌐 导航到目标页面...")
        try:
            page.goto(QUERY_URL, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"⚠️  页面加载超时（继续尝试）: {e}")

        print("⏳ 等待数据加载（最多 30 秒）...")
        loaded = wait_for_table(page)

        if not loaded:
            print("⚠️  未检测到标准表格，尝试截图查看页面状态...")
            take_debug_screenshot(page, "page_state")
            print("  请查看截图 page_state.png，如有登录/验证码请手动处理")
            print("  完成后按回车继续...")
            input()
            wait_for_table(page, timeout=60000)

        page_num = 1
        max_pages = 20  # 安全上限

        while page_num <= max_pages:
            print(f"\n📄 抓取第 {page_num} 页...")
            data = extract_table_data(page)

            if not headers and data["headers"]:
                headers = data["headers"]
                print(f"  列头: {headers[:5]}... (共 {len(headers)} 列)")

            rows_this_page = data["rows"]
            if not rows_this_page:
                print("  ⚠️  本页未提取到数据行，保存截图...")
                take_debug_screenshot(page, f"empty_page_{page_num}")
                break

            all_rows.extend(rows_this_page)
            print(f"  ✅ 本页 {len(rows_this_page)} 行，累计 {len(all_rows)} 行")
            print(f"  分页信息: {data.get('totalText', '')} totalPages={data.get('totalPages', '?')}")

            # 判断是否还有下一页
            total_pages = data.get("totalPages", 1)
            if page_num >= total_pages and total_pages > 1:
                print("  已到最后一页")
                break

            if not go_to_next_page(page):
                print("  未找到下一页按钮，抓取完成")
                break

            page_num += 1

        print(f"\n✅ 共抓取 {len(all_rows)} 行数据")
        take_debug_screenshot(page, "final_state")
        browser.close()

    # 保存 JSON
    output = {"headers": headers, "rows": all_rows, "total": len(all_rows)}
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"💾 JSON 已保存: {OUTPUT_JSON}")

    # 保存 CSV
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if headers:
            writer.writerow(headers)
        writer.writerows(all_rows)
    print(f"💾 CSV 已保存:  {OUTPUT_CSV}")

    return output


if __name__ == "__main__":
    scrape()
