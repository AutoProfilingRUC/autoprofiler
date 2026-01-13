// AutoProfiler Web 应用 JavaScript

// 全局变量
let currentAnalysisId = null;
let analysisInterval = null;
let recentAnalysesLoaded = false;

// DOM 加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化标签页切换
    initTabs();
    
    // 初始化文件上传
    initFileUpload();
    
    // 初始化URL上传
    initUrlUpload();
    
    // 初始化代码分析
    initCodeAnalysis();
    
    // 初始化结果操作按钮
    initResultActions();
    
    // 加载最近的分析记录
    loadRecentAnalyses();
    
    // 检查是否有正在进行的分析
    checkPendingAnalyses();
});

// 初始化标签页切换
function initTabs() {
    const tabs = document.querySelectorAll('.upload-option');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabId = this.id.replace('tab-', '');
            
            // 更新标签页状态
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // 显示对应的区域
            document.querySelectorAll('.upload-area').forEach(area => {
                area.classList.remove('active');
            });
            document.getElementById(`area-${tabId}`).classList.add('active');
        });
    });
    
    // 结果标签页
    const resultTabs = document.querySelectorAll('.results-tab');
    
    resultTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabId = this.id.replace('tab-', '');
            
            // 更新标签页状态
            resultTabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // 显示对应的内容面板
            document.querySelectorAll('.result-pane').forEach(pane => {
                pane.classList.remove('active');
            });
            document.getElementById(`pane-${tabId}`).classList.add('active');
        });
    });
}

// 初始化文件上传
function initFileUpload() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const selectFileBtn = document.getElementById('selectFileBtn');
    
    // 点击按钮选择文件
    selectFileBtn.addEventListener('click', function() {
        fileInput.click();
    });
    
    // 文件选择变化
    fileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });
    
    // 拖放功能
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });
}

// 处理文件上传
function handleFileUpload(file) {
    // 验证文件
    if (!file.name.match(/\.(py|pyw|txt)$/i)) {
        showError('请选择Python文件 (.py, .pyw 或 .txt)');
        return;
    }
    
    if (file.size > 50 * 1024 * 1024) {
        showError('文件太大（最大50MB）');
        return;
    }
    
    // 创建FormData
    const formData = new FormData();
    formData.append('file', file);
    
    // 开始上传
    startAnalysis('正在上传文件...');
    
    // 发送上传请求
    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentAnalysisId = data.analysis_id;
            document.getElementById('fileName').textContent = data.filename;
            document.getElementById('startTime').textContent = new Date().toLocaleString();
            
            // 开始轮询分析状态
            startPollingAnalysis();
            
            // 显示进度容器
            document.getElementById('progressContainer').style.display = 'block';
            
            // 更新进度文本
            updateProgress(10, '文件上传成功，开始分析...');
        } else {
            showError(data.error || '上传失败');
            endAnalysis();
        }
    })
    .catch(error => {
        showError('上传失败: ' + error.message);
        endAnalysis();
    });
}

// 初始化URL上传
function initUrlUpload() {
    const fetchUrlBtn = document.getElementById('fetchUrlBtn');
    const urlInput = document.getElementById('urlInput');
    
    fetchUrlBtn.addEventListener('click', function() {
        const url = urlInput.value.trim();
        
        if (!url) {
            showError('请输入URL');
            return;
        }
        
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            showError('请输入有效的HTTP/HTTPS URL');
            return;
        }
        
        // 开始分析
        startAnalysis('正在从URL下载文件...');
        
        // 发送URL上传请求
        fetch('/api/upload/url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentAnalysisId = data.analysis_id;
                document.getElementById('fileName').textContent = data.filename;
                document.getElementById('startTime').textContent = new Date().toLocaleString();
                
                // 开始轮询分析状态
                startPollingAnalysis();
                
                // 显示进度容器
                document.getElementById('progressContainer').style.display = 'block';
                
                // 更新进度文本
                updateProgress(10, 'URL文件下载成功，开始分析...');
            } else {
                showError(data.error || 'URL上传失败');
                endAnalysis();
            }
        })
        .catch(error => {
            showError('URL上传失败: ' + error.message);
            endAnalysis();
        });
    });
    
    // 按Enter键触发上传
    urlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            fetchUrlBtn.click();
        }
    });
}

// 初始化代码分析
function initCodeAnalysis() {
    const analyzeCodeBtn = document.getElementById('analyzeCodeBtn');
    const codeInput = document.getElementById('codeInput');
    
    analyzeCodeBtn.addEventListener('click', function() {
        const code = codeInput.value.trim();
        
        if (!code) {
            showError('请输入Python代码');
            return;
        }
        
        if (code.length > 100000) {
            showError('代码太长（最大100KB）');
            return;
        }
        
        // 开始分析
        startAnalysis('正在分析代码...');
        
        // 发送代码分析请求
        fetch('/api/analyze/code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code: code })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentAnalysisId = data.analysis_id;
                document.getElementById('fileName').textContent = 'inline_code.py';
                document.getElementById('startTime').textContent = new Date().toLocaleString();
                
                // 开始轮询分析状态
                startPollingAnalysis();
                
                // 显示进度容器
                document.getElementById('progressContainer').style.display = 'block';
                
                // 更新进度文本
                updateProgress(10, '代码提交成功，开始分析...');
            } else {
                showError(data.error || '代码分析失败');
                endAnalysis();
            }
        })
        .catch(error => {
            showError('代码分析失败: ' + error.message);
            endAnalysis();
        });
    });
}

// 开始分析
function startAnalysis(message) {
    // 重置UI
    endAnalysis();
    
    // 显示进度容器
    document.getElementById('progressContainer').style.display = 'block';
    
    // 隐藏结果区域
    document.getElementById('resultsSection').style.display = 'none';
    
    // 更新进度
    updateProgress(5, message || '开始分析...');
}

// 结束分析
function endAnalysis() {
    // 停止轮询
    if (analysisInterval) {
        clearInterval(analysisInterval);
        analysisInterval = null;
    }
    
    // 隐藏进度容器
    document.getElementById('progressContainer').style.display = 'none';
    
    // 重置进度条
    updateProgress(0, '');
}

// 更新进度
function updateProgress(percent, message) {
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    progressFill.style.width = percent + '%';
    progressText.textContent = percent + '%';
    
    if (message) {
        document.getElementById('analysisInfo').querySelector('p:first-child').innerHTML = 
            `<i class="fas fa-file"></i> 文件: <span id="fileName">-</span>`;
        document.getElementById('analysisInfo').querySelector('p:last-child').innerHTML = 
            `<i class="fas fa-clock"></i> 开始时间: <span id="startTime">-</span>`;
    }
}

// 开始轮询分析状态
function startPollingAnalysis() {
    if (analysisInterval) {
        clearInterval(analysisInterval);
    }
    
    // 立即查询一次
    pollAnalysisStatus();
    
    // 设置轮询间隔（2秒）
    analysisInterval = setInterval(pollAnalysisStatus, 2000);
}

// 轮询分析状态
function pollAnalysisStatus() {
    if (!currentAnalysisId) return;
    
    fetch(`/api/analysis/${currentAnalysisId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新进度
                updateProgress(data.progress, '');
                
                // 根据状态处理
                if (data.status === 'completed') {
                    // 分析完成，显示结果
                    displayAnalysisResults(data);
                    endAnalysis();
                } else if (data.status === 'failed') {
                    // 分析失败
                    showError(data.error || '分析失败');
                    endAnalysis();
                }
                // 如果状态是pending或analyzing，继续轮询
            } else {
                // API错误
                showError(data.error || '获取分析状态失败');
                endAnalysis();
            }
        })
        .catch(error => {
            showError('获取分析状态失败: ' + error.message);
            endAnalysis();
        });
}

// 显示分析结果
function displayAnalysisResults(data) {
    if (!data.result) return;
    
    const result = data.result;
    
    // 更新摘要信息
    document.getElementById('summaryDuration').textContent = result.session_info.duration.toFixed(2) + ' 秒';
    document.getElementById('summaryExitCode').textContent = result.session_info.exit_code;
    document.getElementById('summaryFindings').textContent = result.session_info.findings_count + ' 个';
    
    // 文件大小
    const fileSize = result.file_info.size;
    let fileSizeText;
    if (fileSize < 1024) {
        fileSizeText = fileSize + ' B';
    } else if (fileSize < 1024 * 1024) {
        fileSizeText = (fileSize / 1024).toFixed(1) + ' KB';
    } else {
        fileSizeText = (fileSize / (1024 * 1024)).toFixed(1) + ' MB';
    }
    document.getElementById('summaryFileSize').textContent = fileSizeText;
    
    // 显示报告
    document.getElementById('reportContent').textContent = result.report;
    
    // 显示性能问题
    displayFindings(result.findings);
    
    // 显示原始数据
    document.getElementById('rawDataContent').textContent = JSON.stringify(result, null, 2);
    
    // 高亮代码
    hljs.highlightAll();
    
    // 显示结果区域
    document.getElementById('resultsSection').style.display = 'block';
    
    // 滚动到结果区域
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
    
    // 重新加载最近分析记录
    loadRecentAnalyses();
}

// 显示性能问题
function displayFindings(findings) {
    const findingsContent = document.getElementById('findingsContent');
    
    if (!findings || findings.length === 0) {
        findingsContent.innerHTML = '<p class="no-data">没有发现性能问题</p>';
        return;
    }
    
    let html = '';
    
    findings.forEach((finding, index) => {
        // 确定严重程度
        let severityClass = 'mild';
        if (finding.id && finding.id.includes('high') || finding.id && finding.id.includes('critical')) {
            severityClass = 'severe';
        } else if (finding.id && finding.id.includes('medium')) {
            severityClass = '';
        }
        
        html += `
        <div class="finding-item ${severityClass}">
            <div class="finding-header">
                <div class="finding-title">问题 ${index + 1}: ${finding.id || '未知问题'}</div>
                ${finding.confidence ? `<div class="finding-confidence">置信度: ${finding.confidence}</div>` : ''}
            </div>
            <div class="finding-description">${finding.description || '没有描述'}</div>
            
            ${finding.evidence && Object.keys(finding.evidence).length > 0 ? `
            <div class="finding-evidence">
                <h4><i class="fas fa-clipboard-check"></i> 证据</h4>
                <pre>${JSON.stringify(finding.evidence, null, 2)}</pre>
            </div>
            ` : ''}
            
            ${finding.suggestions && finding.suggestions.length > 0 ? `
            <div class="finding-suggestions">
                <h4><i class="fas fa-lightbulb"></i> 建议</h4>
                <ul>
                    ${finding.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                </ul>
            </div>
            ` : ''}
        </div>
        `;
    });
    
    findingsContent.innerHTML = html;
}

// 初始化结果操作按钮
function initResultActions() {
    // 下载报告按钮
    document.getElementById('downloadReportBtn').addEventListener('click', function() {
        if (!currentAnalysisId) {
            showError('没有可下载的报告');
            return;
        }
        
        // 打开下载链接
        window.open(`/api/analysis/${currentAnalysisId}/report`, '_blank');
    });
    
    // 复制报告按钮
    document.getElementById('copyReportBtn').addEventListener('click', function() {
        const reportContent = document.getElementById('reportContent').textContent;
        
        if (!reportContent) {
            showError('没有可复制的报告内容');
            return;
        }
        
        navigator.clipboard.writeText(reportContent)
            .then(() => {
                showSuccess('报告已复制到剪贴板');
            })
            .catch(err => {
                showError('复制失败: ' + err.message);
            });
    });
    
    // 新的分析按钮
    document.getElementById('newAnalysisBtn').addEventListener('click', function() {
        // 重置UI
        resetAnalysisUI();
        
        // 滚动到顶部
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// 重置分析UI
function resetAnalysisUI() {
    // 清除当前分析ID
    currentAnalysisId = null;
    
    // 停止轮询
    endAnalysis();
    
    // 隐藏结果区域
    document.getElementById('resultsSection').style.display = 'none';
    
    // 重置表单
    document.getElementById('fileInput').value = '';
    document.getElementById('urlInput').value = '';
    document.getElementById('codeInput').value = '';
    
    // 切换到文件上传标签页
    document.querySelectorAll('.upload-option').forEach(tab => tab.classList.remove('active'));
    document.getElementById('tab-file').classList.add('active');
    
    document.querySelectorAll('.upload-area').forEach(area => area.classList.remove('active'));
    document.getElementById('area-file').classList.add('active');
}

// 加载最近的分析记录
function loadRecentAnalyses() {
    fetch('/api/recent-analyses')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.analyses.length > 0) {
                displayRecentAnalyses(data.analyses);
                recentAnalysesLoaded = true;
            }
        })
        .catch(error => {
            console.error('加载最近分析记录失败:', error);
        });
}

// 显示最近的分析记录
function displayRecentAnalyses(analyses) {
    const container = document.getElementById('recentAnalyses');
    const list = document.getElementById('recentAnalysesList');
    
    if (analyses.length === 0) {
        container.style.display = 'none';
        return;
    }
    
    container.style.display = 'block';
    
    let html = '';
    
    analyses.forEach(analysis => {
        // 状态显示
        let statusText = '';
        let statusClass = '';
        
        switch (analysis.status) {
            case 'pending':
                statusText = '等待中';
                statusClass = 'status-pending';
                break;
            case 'analyzing':
                statusText = '分析中';
                statusClass = 'status-analyzing';
                break;
            case 'completed':
                statusText = '已完成';
                statusClass = 'status-completed';
                break;
            case 'failed':
                statusText = '失败';
                statusClass = 'status-failed';
                break;
            default:
                statusText = analysis.status;
                statusClass = 'status-pending';
        }
        
        // 格式化时间
        const createdAt = new Date(analysis.created_at);
        const timeText = createdAt.toLocaleString();
        
        html += `
        <div class="recent-analysis-item" data-analysis-id="${analysis.id}">
            <div class="recent-analysis-info">
                <div class="recent-analysis-name">${analysis.original_name || '未命名文件'}</div>
                <div class="recent-analysis-meta">
                    <span><i class="far fa-clock"></i> ${timeText}</span>
                    <span class="recent-analysis-status ${statusClass}">
                        <i class="fas fa-circle"></i> ${statusText}
                    </span>
                    <span>进度: ${analysis.progress}%</span>
                </div>
            </div>
            <div class="recent-analysis-actions">
                ${analysis.status === 'completed' && analysis.has_result ? `
                <button class="btn btn-outline btn-sm view-result-btn" data-analysis-id="${analysis.id}">
                    <i class="fas fa-eye"></i> 查看
                </button>
                ` : ''}
            </div>
        </div>
        `;
    });
    
    list.innerHTML = html;
    
    // 绑定查看结果按钮事件
    document.querySelectorAll('.view-result-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const analysisId = this.getAttribute('data-analysis-id');
            viewAnalysisResult(analysisId);
        });
    });
}

// 查看分析结果
function viewAnalysisResult(analysisId) {
    // 设置当前分析ID
    currentAnalysisId = analysisId;
    
    // 获取分析结果
    fetch(`/api/analysis/${analysisId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.status === 'completed' && data.result) {
                // 显示结果
                displayAnalysisResults(data);
            } else {
                showError('无法查看该分析结果: ' + (data.error || '分析未完成'));
            }
        })
        .catch(error => {
            showError('获取分析结果失败: ' + error.message);
        });
}

// 检查是否有正在进行的分析
function checkPendingAnalyses() {
    fetch('/api/recent-analyses')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 查找正在进行的分析
                const pendingAnalysis = data.analyses.find(a => 
                    a.status === 'pending' || a.status === 'analyzing'
                );
                
                if (pendingAnalysis) {
                    // 询问用户是否继续监控
                    if (confirm(`检测到未完成的分析 "${pendingAnalysis.original_name}"，是否继续监控？`)) {
                        currentAnalysisId = pendingAnalysis.id;
                        document.getElementById('fileName').textContent = pendingAnalysis.original_name;
                        startPollingAnalysis();
                        document.getElementById('progressContainer').style.display = 'block';
                    }
                }
            }
        })
        .catch(error => {
            console.error('检查待处理分析失败:', error);
        });
}

// 显示错误消息
function showError(message) {
    // 创建错误消息元素
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    
    // 添加到容器顶部
    const container = document.querySelector('.container');
    container.insertBefore(errorDiv, container.firstChild);
    
    // 3秒后自动移除
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.parentNode.removeChild(errorDiv);
        }
    }, 5000);
}

// 显示成功消息
function showSuccess(message) {
    // 创建成功消息元素
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    
    // 添加到容器顶部
    const container = document.querySelector('.container');
    container.insertBefore(successDiv, container.firstChild);
    
    // 3秒后自动移除
    setTimeout(() => {
        if (successDiv.parentNode) {
            successDiv.parentNode.removeChild(successDiv);
        }
    }, 3000);
}