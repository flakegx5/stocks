/**
 * iwencai 港股数据抓取器（浏览器控制台版）
 *
 * 使用方法：
 * 1. 在 Chrome 打开目标问财页面（见 CLAUDE.md 中的 URL）
 * 2. 等页面数据加载完毕（能看到表格）
 * 3. 打开 DevTools (F12) → Console
 * 4. 粘贴本文件全部内容并回车
 * 5. 等待"✅ DONE"出现即可（约30~60秒）
 *
 * 前提：本地已启动 recv_server.py（run_server.sh）
 */

(async function () {
    'use strict';

    // ── Step 1: 安装拦截器，捕获下一次 API 请求 ──────────────────────────
    const API_SUFFIX = '/getDataList';  // 目标接口特征
    let _captured = null;

    const _origFetch = window.fetch;
    const _origXHROpen = XMLHttpRequest.prototype.open;
    const _origXHRSend = XMLHttpRequest.prototype.send;

    window.fetch = async function (...args) {
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
        if (url && url.includes(API_SUFFIX) && !_captured) {
            const opts = args[1] || {};
            _captured = { url, body: opts.body || '' };
            console.log('[Scraper] fetch 拦截成功:', url.slice(-60));
        }
        return _origFetch.apply(this, args);
    };

    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
        this._url = url;
        this._method = method;
        return _origXHROpen.apply(this, [method, url, ...rest]);
    };
    XMLHttpRequest.prototype.send = function (body) {
        if (this._url && this._url.includes(API_SUFFIX) && !_captured) {
            _captured = { url: this._url, body: body || '' };
            console.log('[Scraper] XHR 拦截成功:', this._url.slice(-60));
        }
        return _origXHRSend.apply(this, [body]);
    };

    // ── Step 2: 等用户翻一次页（或等页面自己发请求）触发拦截 ───────────────
    console.log('[Scraper] 拦截器已安装。');
    console.log('[Scraper] 请手动点击"第2页"按钮，触发 API 请求...');

    const MAX_WAIT_MS = 60000;
    const start = Date.now();
    while (!_captured && Date.now() - start < MAX_WAIT_MS) {
        await new Promise(r => setTimeout(r, 300));
    }

    if (!_captured) {
        console.error('[Scraper] ❌ 超时未捕获到 API 请求，请检查页面是否正确加载。');
        return;
    }

    // 恢复原始实现
    window.fetch = _origFetch;
    XMLHttpRequest.prototype.open = _origXHROpen;
    XMLHttpRequest.prototype.send = _origXHRSend;

    const { url: apiUrl, body: bodyStr } = _captured;
    console.log('[Scraper] 捕获到请求 URL:', apiUrl);

    // ── Step 3: 从 body 解析 page 参数，确认总页数 ─────────────────────────
    let bodyTemplate = bodyStr;

    // 先请求第1页拿 total
    const body1 = bodyTemplate.replace(/\bpage=\d+\b/, 'page=1');
    const resp1 = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
        body: body1,
        credentials: 'include',
    });
    const json1 = await resp1.json();
    const comp0 = json1?.answer?.components?.[0]?.data;
    if (!comp0) {
        console.error('[Scraper] ❌ API 响应结构异常，请检查:', JSON.stringify(json1).slice(0, 300));
        return;
    }

    const perpage = parseInt(bodyTemplate.match(/\bperpage=(\d+)\b/)?.[1] || '50');
    const total   = comp0.meta?.extra?.total_count ?? comp0.datas?.length ?? 50;
    const totalPages = Math.ceil(total / perpage);
    console.log(`[Scraper] 共 ${total} 条，每页 ${perpage}，需抓 ${totalPages} 页`);

    // ── Step 4: 逐页拉取，合并所有行 ─────────────────────────────────────
    let allRows = [];
    let allKeys = null;

    // 处理第1页已有数据
    const rows1 = comp0.datas || [];
    allRows = allRows.concat(rows1);
    if (!allKeys && rows1.length) allKeys = Object.keys(rows1[0]);
    console.log(`[Scraper] 第1页: ${rows1.length} 行，累计 ${allRows.length}`);

    for (let p = 2; p <= totalPages; p++) {
        const bodyP = bodyTemplate.replace(/\bpage=\d+\b/, `page=${p}`);
        try {
            const resp = await fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
                body: bodyP,
                credentials: 'include',
            });
            const js = await resp.json();
            const rows = js?.answer?.components?.[0]?.data?.datas || [];
            allRows = allRows.concat(rows);
            if (!allKeys && rows.length) allKeys = Object.keys(rows[0]);
            console.log(`[Scraper] 第${p}页: ${rows.length} 行，累计 ${allRows.length}`);
        } catch (e) {
            console.warn(`[Scraper] 第${p}页出错:`, e.message);
        }
        // 小延迟，避免被限速
        await new Promise(r => setTimeout(r, 200));
    }

    console.log(`[Scraper] 抓取完成，共 ${allRows.length} 行`);

    // ── Step 5: POST 到本地 recv_server ──────────────────────────────────
    const SERVER = 'http://localhost:9876';
    const payload = JSON.stringify({ rows: allRows, keys: allKeys || [] });
    console.log(`[Scraper] 发送 ${(payload.length / 1024).toFixed(0)} KB 到 ${SERVER}...`);
    try {
        const r = await fetch(SERVER, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload,
        });
        const text = await r.text();
        console.log(`[Scraper] ✅ DONE — 服务器响应: ${text}，共 ${allRows.length} 行保存成功`);
    } catch (e) {
        console.error('[Scraper] ❌ 发送失败（recv_server 是否已启动？）:', e.message);
    }
})();
