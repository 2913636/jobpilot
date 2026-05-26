/* global chrome */

const API_HOST_KEY = "jobpilot_api_host";
const TOKEN_KEY = "jobpilot_token";

const $ = (id) => document.getElementById(id);

let apiHost = "";
let token = "";

async function init() {
  const stored = await chrome.storage.local.get([API_HOST_KEY, TOKEN_KEY]);
  apiHost = stored[API_HOST_KEY] || "http://localhost:8004";
  token = stored[TOKEN_KEY] || "";

  $("api-host").value = apiHost;
  $("token-input").value = token;

  if (token) {
    showMain();
  }

  // 自动获取当前 tab URL
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.url) {
    $("current-url").textContent = tab.url;
  }

  // 加载自动提交开关状态
  const autoSubmitStored = await chrome.storage.local.get(["auto_submit"]);
  $("auto-submit-toggle").checked = autoSubmitStored.auto_submit === true;
}

function showMain() {
  $("login-section").style.display = "none";
  $("main-section").style.display = "block";
  $("status-indicator").className = "status connected";
  $("status-indicator").textContent = "● 已连接";
  loadRecentApps();
}

// 登录
$("login-btn").addEventListener("click", async () => {
  apiHost = $("api-host").value.trim();
  token = $("token-input").value.trim();
  if (!token) {
    showMessage("请输入 JWT Token", "error");
    return;
  }
  await chrome.storage.local.set({ [API_HOST_KEY]: apiHost, [TOKEN_KEY]: token });
  showMain();
  showMessage("已连接", "success");
});

// 一键填表
$("fill-btn").addEventListener("click", async () => {
  $("fill-btn").disabled = true;
  $("fill-btn").textContent = "分析中...";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url) {
      showMessage("无法获取当前页面 URL", "error");
      return;
    }

    // 1. 调用后端分析表单
    const resp = await fetch(`${apiHost}/api/applications/fill-form`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
      body: JSON.stringify({ url: tab.url, user_id: "" }),
    });

    if (!resp.ok) {
      showMessage("填表分析失败: " + resp.status, "error");
      return;
    }

    const data = await resp.json();

    // 2. 发送填充指令到 content script
    const response = await chrome.tabs.sendMessage(tab.id, {
      command: "fill_form",
      fields: data.mappings,
      auto_submit: $("auto-submit-toggle").checked,
    });

    if (response?.success) {
      showMessage(`已填充 ${response.filled_count || data.mappings.length} 个字段`, "success");
    } else {
      showMessage("填充失败: " + (response?.error || "unknown"), "error");
    }
  } catch (err) {
    showMessage("错误: " + err.message, "error");
  }
  $("fill-btn").disabled = false;
  $("fill-btn").textContent = "一键填表";
});

// 自动提交开关
$("auto-submit-toggle").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ auto_submit: e.target.checked });
});

// 同步聊天开关
$("sync-chat-toggle").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ sync_chat: e.target.checked });
});

function showMessage(msg, type) {
  const el = $("message-box");
  el.textContent = msg;
  el.className = "message " + type;
  setTimeout(() => { el.className = "message"; }, 3000);
}

async function loadRecentApps() {
  try {
    const resp = await fetch(`${apiHost}/api/applications?page=1&page_size=3`, {
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.items && data.items.length > 0) {
        $("recent-apps").innerHTML = data.items
          .map(a => `<div style="padding:6px 0;border-bottom:1px solid #eee">
            <strong>${a.title || "无标题"}</strong> ${a.company ? "@" + a.company : ""}
            <span style="float:right;color:#1677ff">${a.status}</span></div>`)
          .join("");
      } else {
        $("recent-apps").textContent = "暂无申请记录";
      }
    }
  } catch {
    $("recent-apps").textContent = "加载失败";
  }
}

init();
