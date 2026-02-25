// Main UI logic (path-based analysis for file/project)
let currentAnalysisId = null;
let currentReport = null;
let currentMode = "file";
let currentStatusEndpoint = "";
let progressInterval = null;
let lastProgress = 0;

const progressContainer = document.getElementById("progress");
const resultContainer = document.getElementById("resultContainer");

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
});

function initEventListeners() {
  const modeInputs = document.querySelectorAll('input[name="analysisMode"]');
  modeInputs.forEach((input) => {
    input.addEventListener("change", () => {
      currentMode = input.value;
      const queryBox = document.getElementById("projectQuery");
      if (queryBox) queryBox.style.display = currentMode === "project" ? "block" : "none";
    });
  });
}

function showNotification(message, type = "success", duration = 3000) {
  const notification = document.getElementById("notification");
  if (!notification) return;
  notification.textContent = message;
  notification.className = `notification ${type}`;
  notification.classList.add("show");
  setTimeout(() => notification.classList.remove("show"), duration);
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMarkdownHtml(text) {
  const src = String(text || "");
  if (window.marked && typeof window.marked.parse === "function") {
    try {
      if (typeof window.marked.setOptions === "function") {
        window.marked.setOptions({ gfm: true, breaks: true });
      }
      return window.marked.parse(src);
    } catch (_) {}
  }
  return `<pre>${escapeHtml(src)}</pre>`;
}

function getSelectedMode() {
  const checked = document.querySelector('input[name="analysisMode"]:checked');
  return checked ? checked.value : "file";
}

function parseQueryTerms(input) {
  if (!input) return [];
  return input
    .split(",")
    .map((s) => s.trim())
    .filter((s) => !!s);
}

function hasUsableModelConfig(cfg) {
  const apiConfigured = !!(cfg && (cfg.api_key_configured || cfg.api_key));
  const hasApi = !!(cfg && apiConfigured && cfg.api_url && cfg.model);
  const hasLocal = !!(cfg && cfg.use_local_model && cfg.local_api_url && cfg.local_model);
  return hasApi || hasLocal;
}

async function saveDeepseekConfigQuiet(config) {
  const payload = {
    api_key: (config && config.api_key) || "",
    api_url:
      (config && config.api_url) || "https://api.deepseek.com/v1/chat/completions",
    model: (config && config.model) || "deepseek-chat",
    output_language: (config && config.output_language) || "zh",
    enable_blackbox: config && config.enable_blackbox !== false,
    enable_whitebox: config && config.enable_whitebox !== false,
    temperature:
      typeof (config && config.temperature) === "number"
        ? config.temperature
        : 0.3,
    use_local_model: !!(config && config.use_local_model),
    local_api_url:
      (config && config.local_api_url) || "http://127.0.0.1:11434/v1/chat/completions",
    local_model: (config && config.local_model) || "",
    local_api_key: (config && config.local_api_key) || "",
  };
  const resp = await fetch("/api/deepseek/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok || !data.success) {
    throw new Error(data.error || "保存配置失败");
  }
}

async function ensureModelConfigOrFallback(mode = "project") {
  const cfg = window.deepseekConfig || {};
  if (hasUsableModelConfig(cfg)) return cfg;

  const localOnlyHint =
    mode === "project"
      ? "将继续本地降级分析（项目模式）。"
      : "将继续本地分析（单文件模式，无 AI 分析）。";
  const confirmed = confirm(
    `当前未配置 API 或本地模型。\n点击“确定”输入 API Key 并保存；点击“取消”${localOnlyHint}`
  );
  if (!confirmed) return cfg;

  const apiKey = prompt("请输入 DeepSeek API Key（留空将继续本地降级分析）", "");
  if (!apiKey || !apiKey.trim()) return cfg;

  const next = {
    ...cfg,
    api_key: apiKey.trim(),
    api_url: cfg.api_url || "https://api.deepseek.com/v1/chat/completions",
    model: cfg.model || "deepseek-chat",
  };
  await saveDeepseekConfigQuiet(next);
  window.deepseekConfig = {
    ...cfg,
    api_key: "",
    api_key_configured: true,
    api_url: next.api_url,
    model: next.model,
  };
  if (typeof window.updateDeepSeekStatus === "function") {
    window.updateDeepSeekStatus(window.deepseekConfig);
  }
  showNotification("API 配置已保存，将使用模型增强分析。", "success");
  return window.deepseekConfig;
}

async function startPathAnalysis() {
  const pathInput = document.getElementById("targetPath");
  const mode = getSelectedMode();
  const targetPath = (pathInput ? pathInput.value : "").trim();
  const queryInput = document.getElementById("projectQuery");
  const query = parseQueryTerms(queryInput ? queryInput.value : "");

  if (!targetPath) {
    showNotification("请输入绝对路径", "warning");
    return;
  }

  currentMode = mode;
  progressContainer.style.display = "block";
  resetProgress();
  resultContainer.style.display = "none";
  updateProgress(5, "正在提交分析任务...");

  try {
    let deepseekConfig = window.deepseekConfig || {};
    deepseekConfig = await ensureModelConfigOrFallback(mode);

    const endpoint = mode === "project" ? "/api/proj-analyser/analyze" : "/api/analyze-file-path";
    const outputLanguage =
      (deepseekConfig && deepseekConfig.output_language) || "zh";
    const payload =
      mode === "project"
        ? {
            project_path: targetPath,
            query,
            output_language: outputLanguage,
          }
        : {
            file_path: targetPath,
            output_language: outputLanguage,
          };

    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "任务启动失败");
    }

    currentAnalysisId = data.analysis_id;
    currentStatusEndpoint =
      mode === "project"
        ? `/api/proj-analyser/analysis/${currentAnalysisId}`
        : `/api/analysis/${currentAnalysisId}`;
    updateProgress(10, "任务已创建，正在执行分析...");
    startProgressMonitoring();
  } catch (err) {
    showNotification(`启动失败: ${err.message}`, "error");
    resetProgress();
  }
}

function startProgressMonitoring() {
  if (progressInterval) clearInterval(progressInterval);
  progressInterval = setInterval(async () => {
    if (!currentAnalysisId || !currentStatusEndpoint) return;
    try {
      const response = await fetch(currentStatusEndpoint);
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || "状态查询失败");
      }
      updateProgress(data.progress || 0, data.progress_text || "分析中...");
      updateStepStatus(data.status || "analyzing");

      if (data.status === "completed") {
        currentReport = data.result || {};
        showResults(currentReport);
        updateProgress(100, "分析完成！");
        clearInterval(progressInterval);
        setTimeout(() => (progressContainer.style.display = "none"), 2000);
      } else if (data.status === "failed") {
        clearInterval(progressInterval);
        showNotification(`分析失败: ${data.error || "未知错误"}`, "error");
      }
    } catch (err) {
      showNotification(`状态查询失败: ${err.message}`, "error");
    }
  }, 1000);
}

function updateStepStatus(status) {
  const steps = ["step1", "step2", "step3", "step4", "step5"];
  const stepElements = steps.map((id) => document.getElementById(id));
  let currentStep = 0;

  if ((status || "").includes("analyzing")) currentStep = 1;
  if ((status || "").includes("deepseek_blackbox")) currentStep = 2;
  if (
    (status || "").includes("whitebox_analysis") ||
    (status || "").includes("deepseek_whitebox")
  )
    currentStep = 3;
  if ((status || "").includes("generating_report")) currentStep = 4;
  if (status === "completed") currentStep = 5;

  stepElements.forEach((step, index) => {
    if (!step) return;
    step.classList.remove("active", "completed");
    if (index < currentStep) step.classList.add("completed");
    else if (index === currentStep) step.classList.add("active");
  });
}

function showResults(result) {
  const htmlPreview = document.getElementById("htmlPreview");
  if (htmlPreview) htmlPreview.innerHTML = result.html || result.report_html || "";

  const markdownContent = document.getElementById("markdownContent");
  if (markdownContent) markdownContent.textContent = result.markdown || result.report_markdown || "";

  if (result.code_structure) displayCodeStructure(result.code_structure);
  if (result.deepseek_results) displayDeepSeekResults(result.deepseek_results);

  const rawData = document.getElementById("rawData");
  if (rawData) rawData.textContent = JSON.stringify(result, null, 2);

  displayStats(result);

  resultContainer.style.display = "block";
  resultContainer.scrollIntoView({ behavior: "smooth" });
  showNotification("分析完成！", "success");
}

function displayStats(result) {
  const statsContainer = document.getElementById("statsContainer");
  if (!statsContainer) return;

  const sessionInfo = result.session_info || {};
  const deepseekResults = result.deepseek_results || {};
  const codeStructure = result.code_structure || {};
  const analysisMode = String(result.analysis_mode || "");
  const isProject =
    (codeStructure && codeStructure.type === "project") ||
    analysisMode.startsWith("project_") ||
    analysisMode.startsWith("fallback_local");
  const tokenUsage = result.token_usage_summary || {};

  let html = "";
  if (isProject) {
    html += `
      <div class="stat-card">
        <div class="stat-value">${result.analysis_mode || "project"}</div>
        <div class="stat-label">分析模式</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${result.rounds || 0}</div>
        <div class="stat-label">API轮次</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${(result.context_summary || {}).files_scanned || 0}</div>
        <div class="stat-label">扫描文件数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${(result.focus_summary || {}).selected_count || 0}</div>
        <div class="stat-label">重点文件数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${tokenUsage.total_tokens || 0}</div>
        <div class="stat-label">Token总量</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${tokenUsage.prompt_tokens || 0}/${tokenUsage.completion_tokens || 0}</div>
        <div class="stat-label">Prompt/Completion</div>
      </div>
    `;
  } else {
    html += `
      <div class="stat-card">
        <div class="stat-value">${sessionInfo.duration ? sessionInfo.duration.toFixed(2) : "0.00"}</div>
        <div class="stat-label">运行时间(秒)</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${sessionInfo.findings_count || 0}</div>
        <div class="stat-label">发现问题</div>
      </div>
    `;
  }

  if (Object.keys(deepseekResults).length > 0) {
    html += `
      <div class="stat-card">
        <div class="stat-value">${Object.keys(deepseekResults).length}</div>
        <div class="stat-label">AI分析项</div>
      </div>
      <div class="stat-card">
        <div class="stat-value"><i class="fas fa-robot" style="color:#667eea"></i></div>
        <div class="stat-label">AI分析完成</div>
      </div>
    `;
  }

  if (codeStructure.basic_info) {
    if (codeStructure.type === "project") {
      html += `
        <div class="stat-card">
          <div class="stat-value">${(codeStructure.language_distribution || []).length}</div>
          <div class="stat-label">语言种类</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${(codeStructure.entrypoints_top || []).length}</div>
          <div class="stat-label">入口候选</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${(codeStructure.focus_files || []).length}</div>
          <div class="stat-label">结构重点文件</div>
        </div>
      `;
    } else {
      html += `
        <div class="stat-card">
          <div class="stat-value">${codeStructure.functions ? codeStructure.functions.length : 0}</div>
          <div class="stat-label">函数数量</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${codeStructure.classes ? codeStructure.classes.length : 0}</div>
          <div class="stat-label">类数量</div>
        </div>
      `;
    }
  }
  statsContainer.innerHTML = html;
}

function displayCodeStructure(structure) {
  const container = document.getElementById("codeStructure");
  if (!container) return;

  let html = '<div class="html-preview"><h3>代码结构分析</h3>';

  if (structure.type === "project") {
    const info = structure.basic_info || {};
    const langs = structure.language_distribution || [];
    const entrypoints = structure.entrypoints_primary || structure.entrypoints_top || [];
    const focusFiles = structure.focus_files || [];
    const topLevels = structure.top_level_overview || [];
    const hotDirs = structure.directories_top || [];

    html += '<div class="metric">';
    html += "<h4>项目概览</h4>";
    html += `<p><strong>项目根目录:</strong> ${info.repo_root || "-"}</p>`;
    html += `<p><strong>扫描文件数:</strong> ${info.files_scanned || 0}</p>`;
    html += `<p><strong>入口候选数:</strong> ${info.entrypoints_found || 0}</p>`;
    html += `<p><strong>总大小(bytes):</strong> ${info.total_size_bytes || 0}</p>`;
    html += "</div>";

    if (langs.length > 0) {
      html += '<div class="metric"><h4>语言分布</h4><table>';
      html += "<tr><th>语言</th><th>文件数</th><th>体积(bytes)</th></tr>";
      langs.slice(0, 10).forEach((it) => {
        html += `<tr><td>${it.language || "unknown"}</td><td>${it.files || 0}</td><td>${it.size_bytes || 0}</td></tr>`;
      });
      html += "</table></div>";
    }

    if (entrypoints.length > 0) {
      html += '<div class="metric"><h4>入口候选（Top）</h4><table>';
      html += "<tr><th>文件</th><th>分数</th><th>原因</th></tr>";
      entrypoints.slice(0, 10).forEach((ep) => {
        html += `<tr><td>${ep.file_path || "-"}</td><td>${ep.score || 0}</td><td>${(ep.reason || []).join(", ")}</td></tr>`;
      });
      html += "</table></div>";
    }

    if (focusFiles.length > 0) {
      html += '<div class="metric"><h4>重点分析文件（预算内）</h4><table>';
      html += "<tr><th>文件</th><th>分数</th><th>Token估算</th></tr>";
      focusFiles.slice(0, 12).forEach((f) => {
        html += `<tr><td>${f.path || "-"}</td><td>${f.score || 0}</td><td>${f.token_estimate || 0}</td></tr>`;
      });
      html += "</table></div>";
    }

    if (topLevels.length > 0) {
      html += '<div class="metric"><h4>顶层目录结构（Top）</h4><table>';
      html += "<tr><th>路径</th><th>文件数</th><th>体积(bytes)</th></tr>";
      topLevels.slice(0, 12).forEach((d) => {
        html += `<tr><td>${d.path || "-"}</td><td>${d.files || 0}</td><td>${d.size_bytes || 0}</td></tr>`;
      });
      html += "</table></div>";
    }

    if (hotDirs.length > 0) {
      html += '<div class="metric"><h4>目录热点（按文件数）</h4><table>';
      html += "<tr><th>目录</th><th>文件数</th><th>体积(bytes)</th></tr>";
      hotDirs.slice(0, 12).forEach((d) => {
        html += `<tr><td>${d.path || "-"}</td><td>${d.files || 0}</td><td>${d.size_bytes || 0}</td></tr>`;
      });
      html += "</table></div>";
    }

    container.innerHTML = html + "</div>";
    return;
  }

  if (structure.basic_info) {
    html += '<div class="metric">';
    html += "<h4>基本信息</h4>";
    html += `<p><strong>文件:</strong> ${structure.basic_info.filename}</p>`;
    html += `<p><strong>大小:</strong> ${(structure.basic_info.file_size / 1024).toFixed(2)} KB</p>`;
    html += `<p><strong>总行数:</strong> ${structure.basic_info.total_lines}</p>`;
    html += `<p><strong>代码行数:</strong> ${structure.basic_info.code_lines}</p>`;
    html += "</div>";
  }
  container.innerHTML = html + "</div>";
}

function displayDeepSeekResults(results) {
  const container = document.getElementById("deepseekResults");
  if (!container) return;

  let html = '<div class="html-preview"><div class="deepseek-section">';
  html += '<h3><i class="fas fa-robot"></i> AI分析结果</h3>';

  const entries = Object.entries(results || {});
  if (entries.length === 0) {
    html += '<div class="deepseek-content"><p>无可用 AI 结果。</p></div>';
  } else {
    entries.forEach(([key, value]) => {
      html += '<div class="deepseek-content">';
      html += `<h4>${escapeHtml(key)}</h4>`;
      html += renderMarkdownHtml(value);
      html += "</div>";
    });
  }
  container.innerHTML = html + "</div></div>";
}

function showTab(tabName) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach((content) => content.classList.remove("active"));
  const clicked = window.event && window.event.target ? window.event.target.closest(".tab") : null;
  if (clicked) clicked.classList.add("active");
  const target = document.getElementById(`${tabName}Tab`);
  if (target) target.classList.add("active");
}

function downloadReport(format) {
  if (!currentAnalysisId || !currentReport) {
    showNotification("没有可下载的报告", "warning");
    return;
  }

  let url = "";
  let filename = "";
  if (format === "html") {
    const blob = new Blob([currentReport.html || currentReport.report_html || ""], {
      type: "text/html",
    });
    url = URL.createObjectURL(blob);
    filename = "autoprofiler_report.html";
  } else if (format === "markdown") {
    const blob = new Blob([currentReport.markdown || currentReport.report_markdown || ""], {
      type: "text/markdown",
    });
    url = URL.createObjectURL(blob);
    filename = "autoprofiler_report.md";
  } else if (format === "pdf") {
    if (!currentReport.pdf_path || currentMode === "project") {
      showNotification("当前结果无 PDF 可下载", "warning");
      return;
    }
    url = `/api/download/pdf/${currentAnalysisId}`;
    filename = "autoprofiler_report.pdf";
  }

  if (format === "pdf") {
    window.open(url, "_blank");
    return;
  }

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function copyToClipboard(format) {
  if (!currentReport) {
    showNotification("没有可复制的内容", "warning");
    return;
  }
  const textToCopy =
    format === "html"
      ? currentReport.html || currentReport.report_html || ""
      : currentReport.markdown || currentReport.report_markdown || "";
  navigator.clipboard
    .writeText(textToCopy)
    .then(() => showNotification("已复制到剪贴板", "success"))
    .catch((err) => showNotification(`复制失败: ${err}`, "error"));
}

function resetAnalysis() {
  currentAnalysisId = null;
  currentReport = null;
  currentStatusEndpoint = "";
  resultContainer.style.display = "none";
  progressContainer.style.display = "none";

  ["htmlPreview", "markdownContent", "codeStructure", "deepseekResults", "rawData", "statsContainer"].forEach(
    (id) => {
      const e = document.getElementById(id);
      if (e) e.innerHTML = "";
    }
  );

  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
  resetProgress();
}

function updateProgress(percent, text) {
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  if (!progressBar || !progressText) return;

  const start = lastProgress;
  const end = percent;
  const duration = 400;
  const startTime = performance.now();

  function animate(now) {
    const p = Math.min((now - startTime) / duration, 1);
    const current = start + (end - start) * p;
    progressBar.style.width = `${current}%`;
    progressBar.textContent = `${Math.round(current)}%`;
    progressText.textContent = `${Math.round(current)}% - ${text}`;
    if (p < 1) requestAnimationFrame(animate);
    else lastProgress = end;
  }
  requestAnimationFrame(animate);
}

function resetProgress() {
  lastProgress = 0;
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  if (progressBar) {
    progressBar.style.width = "0%";
    progressBar.textContent = "";
  }
  if (progressText) {
    progressText.textContent = "0% - 准备开始分析...";
  }
  document.querySelectorAll(".progress-step").forEach((s) => s.classList.remove("active", "completed"));
  const first = document.querySelector(".progress-step");
  if (first) first.classList.add("active");
}

window.showTab = showTab;
window.downloadReport = downloadReport;
window.copyToClipboard = copyToClipboard;
window.resetAnalysis = resetAnalysis;
window.startPathAnalysis = startPathAnalysis;
