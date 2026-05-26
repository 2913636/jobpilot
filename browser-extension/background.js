/* JobPilot Background Service Worker */

chrome.runtime.onInstalled.addListener(() => {
  console.log("[JobPilot] Extension installed");
  chrome.storage.local.set({ sync_chat: true, auto_submit: false });
});

// 监听来自 popup 或 content script 的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.command === "get_token") {
    chrome.storage.local.get(["jobpilot_token", "jobpilot_api_host"], (result) => {
      sendResponse(result);
    });
    return true;
  }
});

// 监听标签页更新，注入 content script（如需要）
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url) {
    const jobSites = ["zhipin.com", "linkedin.com", "lagou.com", "liepin.com", "51job.com"];
    const isJobSite = jobSites.some((site) => tab.url.includes(site));
    if (isJobSite) {
      chrome.action.setBadgeText({ text: "ON", tabId });
      chrome.action.setBadgeBackgroundColor({ color: "#1677ff", tabId });
    }
  }
});
