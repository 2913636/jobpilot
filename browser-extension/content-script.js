/* JobPilot Content Script - 表单填充 + 聊天监听 */

(function () {
  "use strict";

  // ── 表单填充引擎 ──────────────────────────────────────────────

  function fillField(fieldMapping) {
    const { form_field, suggested_value, field_type } = fieldMapping;
    if (!suggested_value) return false;

    try {
      const el = document.querySelector(form_field);
      if (!el) {
        // 尝试属性选择器的变体
        const [attr, val] = form_field.match(/\[(.*?)=['"](.*?)['"]\]/)?.slice(1) || [];
        if (attr && val) {
          const fallback = document.querySelector(`[${attr}*="${val}"]`);
          if (fallback) {
            return simulateInput(fallback, suggested_value, field_type);
          }
        }
        return false;
      }
      return simulateInput(el, suggested_value, field_type);
    } catch (e) {
      console.debug("[JobPilot] fillField error:", e.message);
      return false;
    }
  }

  function simulateInput(el, value, fieldType) {
    const tag = el.tagName.toLowerCase();

    if (tag === "select") {
      el.value = value;
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }

    if (tag === "input" || tag === "textarea") {
      // 模拟人类输入：随机延时后逐字符输入
      const delay = Math.floor(Math.random() * 50) + 20;
      el.focus();
      el.value = "";

      // 对于长文本，直接赋值（性能更好）
      if (value.length > 100) {
        el.value = value;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        el.dispatchEvent(new Event("blur", { bubbles: true }));
        return true;
      }

      // 短文本逐字符输入
      let i = 0;
      function typeChar() {
        if (i < value.length) {
          el.value += value.charAt(i);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          i++;
          setTimeout(typeChar, delay + Math.random() * 30);
        } else {
          el.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
      typeChar();
      return true;
    }

    return false;
  }

  // ── 聊天监听 ──────────────────────────────────────────────────

  function setupChatListener() {
    // 监听 XHR 和 fetch 请求
    const origFetch = window.fetch;
    window.fetch = async function (...args) {
      const resp = await origFetch.apply(this, args);
      interceptChatResponse(args[0], resp.clone());
      return resp;
    };

    // 拦截消息列表 API
    const origXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
      this._jobpilot_url = url;
      return origXHROpen.call(this, method, url, ...rest);
    };

    const origXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (body) {
      this.addEventListener("load", function () {
        interceptChatResponse(this._jobpilot_url, {
          status: this.status,
          json: async () => JSON.parse(this.responseText),
        });
      });
      return origXHRSend.call(this, body);
    };
  }

  async function interceptChatResponse(url, resp) {
    if (!url || resp.status !== 200) return;

    // 匹配招聘网站的聊天 API
    const chatPatterns = [
      /\/chat\/message\/list/, /\/geek\/chat\/.*\/history/,
      /\/api\/chat/, /\/im\/message/, /\/messaging/,
    ];

    const isChatAPI = chatPatterns.some((p) => p.test(url));
    if (!isChatAPI) return;

    try {
      const data = await resp.json();
      const messages = data?.data?.list || data?.data?.messages || data?.messages || [];
      if (!messages.length) return;

      // 检查是否启用同步
      const stored = await chrome.storage.local.get(["sync_chat", "jobpilot_token", "jobpilot_api_host"]);
      if (!stored.sync_chat || !stored.jobpilot_token) return;

      for (const msg of messages.slice(-5)) {
        await fetch(`${stored.jobpilot_api_host}/api/applications/crm/sync-chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${stored.jobpilot_token}`,
          },
          body: JSON.stringify({
            platform: detectPlatform(window.location.hostname),
            direction: msg.from_self || msg.from === "me" ? "out" : "in",
            sender_name: msg.sender_name || msg.name || "",
            content: msg.content || msg.text || msg.body || "",
            raw_payload: msg,
          }),
        });
      }
    } catch (e) {
      console.debug("[JobPilot] chat sync error:", e.message);
    }
  }

  function detectPlatform(hostname) {
    if (hostname.includes("zhipin.com")) return "boss";
    if (hostname.includes("linkedin.com")) return "linkedin";
    if (hostname.includes("lagou.com")) return "lagou";
    if (hostname.includes("liepin.com")) return "liepin";
    if (hostname.includes("51job.com")) return "51job";
    return "other";
  }

  // ── 消息监听 ──────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.command === "fill_form") {
      const { fields, auto_submit } = request;
      let filled = 0;
      for (const f of fields) {
        if (fillField(f)) filled++;
      }

      if (auto_submit) {
        // 查找提交按钮（用户授权自动提交时启用）
        const submitBtn = document.querySelector(
          'button[type="submit"], input[type="submit"], button:contains("提交"), button:contains("申请")'
        );
        if (submitBtn) {
          setTimeout(() => submitBtn.click(), 1000);
        }
      }

      sendResponse({ success: true, filled_count: filled });
    } else if (request.command === "get_form_info") {
      const forms = Array.from(document.querySelectorAll("form")).map((f) => ({
        action: f.action,
        method: f.method,
        fields: Array.from(f.querySelectorAll("input, select, textarea")).map((el) => ({
          tag: el.tagName.toLowerCase(),
          name: el.name,
          type: el.type || "",
          placeholder: el.placeholder || "",
          label: el.closest("label")?.textContent?.trim() || "",
        })),
      }));
      sendResponse({ forms });
    } else if (request.command === "ping") {
      sendResponse({ pong: true, url: window.location.href });
    }
    return true;
  });

  // ── 初始化 ────────────────────────────────────────────────────

  setupChatListener();
  console.log("[JobPilot] Content script loaded on", window.location.hostname);
})();
