// 主要JavaScript逻辑
let currentAnalysisId = null;
let currentReport = null;
let progressInterval = null;
let lastProgress = 0;

// DOM元素
const dropArea = document.getElementById('dropArea');
const fileInput = document.getElementById('fileInput');
const progressContainer = document.getElementById('progress');
const resultContainer = document.getElementById('resultContainer');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
});

function initEventListeners() {
    // 拖放功能
    if (dropArea) {
        dropArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropArea.classList.add('dragover');
        });
        
        dropArea.addEventListener('dragleave', () => {
            dropArea.classList.remove('dragover');
        });
        
        dropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            dropArea.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });
        
        dropArea.addEventListener('click', () => {
            fileInput.click();
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (fileInput.files.length > 0) {
                uploadFile(fileInput.files[0]);
            }
        });
    }
}

// 通知系统
function showNotification(message, type = 'success', duration = 3000) {
    const notification = document.getElementById('notification');
    if (!notification) return;
    
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.add('show');
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, duration);
}

// 文件上传
function uploadFile(file) {
    if (!file.name.match(/\.(py|pyw)$/i)) {
        showNotification('请选择Python文件 (.py 或 .pyw)', 'error');
        return;
    }
    
    // 确保deepseekConfig已加载
    if (!window.deepseekConfig) {
        window.deepseekConfig = {};
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('deepseek_config', JSON.stringify(window.deepseekConfig));
    
    progressContainer.style.display = 'block';
    resetProgress();
    updateProgress(5, '正在上传文件...');
    
    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentAnalysisId = data.analysis_id;
            updateProgress(10, '文件上传完成，开始分析...');
            startProgressMonitoring();
        } else {
            showNotification('上传失败: ' + (data.error || '未知错误'), 'error');
            resetProgress();
        }
    })
    .catch(error => {
        showNotification('上传失败: ' + error.message, 'error');
        resetProgress();
    });
}

// 进度监控
function startProgressMonitoring() {
    if (progressInterval) clearInterval(progressInterval);
    
    progressInterval = setInterval(() => {
        if (!currentAnalysisId) return;
        
        fetch('/api/analysis/' + currentAnalysisId)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateProgress(data.progress, data.progress_text || '分析中...');
                updateStepStatus(data.status);
                
                if (data.status === 'completed') {
                    currentReport = data.result;
                    showResults(data.result);
                    updateProgress(100, '分析完成！');
                    clearInterval(progressInterval);
                    
                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                    }, 3000);
                } else if (data.status === 'failed') {
                    showNotification('分析失败: ' + (data.error || '未知错误'), 'error');
                    resetProgress();
                    clearInterval(progressInterval);
                }
            } else {
                showNotification('获取状态失败: ' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            showNotification('获取状态失败: ' + error.message, 'error');
        });
    }, 1000);
}

function updateStepStatus(status) {
    const steps = ['step1', 'step2', 'step3', 'step4', 'step5'];
    const stepElements = steps.map(id => document.getElementById(id));
    
    let currentStep = 0;
    if (status.includes('analyzing')) currentStep = 1;
    if (status.includes('deepseek_blackbox')) currentStep = 2;
    if (status.includes('whitebox_analysis') || status.includes('deepseek_whitebox')) currentStep = 3;
    if (status.includes('generating_report')) currentStep = 4;
    if (status === 'completed') currentStep = 5;
    
    stepElements.forEach((step, index) => {
        if (!step) return;
        step.classList.remove('active', 'completed');
        if (index < currentStep) {
            step.classList.add('completed');
        } else if (index === currentStep) {
            step.classList.add('active');
        }
    });
}

// 显示结果
function showResults(result) {
    // 显示HTML预览
    const htmlPreview = document.getElementById('htmlPreview');
    if (htmlPreview) htmlPreview.innerHTML = result.html;
    
    // 显示Markdown源码
    const markdownContent = document.getElementById('markdownContent');
    if (markdownContent) markdownContent.textContent = result.markdown;
    
    // 显示代码结构
    if (result.code_structure) {
        displayCodeStructure(result.code_structure);
    }
    
    // 显示DeepSeek分析结果
    if (result.deepseek_results) {
        displayDeepSeekResults(result.deepseek_results);
    }
    
    // 显示原始数据
    const rawData = document.getElementById('rawData');
    if (rawData) rawData.textContent = JSON.stringify(result, null, 2);
    
    // 显示统计信息
    displayStats(result);
    
    // 显示结果容器
    resultContainer.style.display = 'block';
    
    // 滚动到结果
    resultContainer.scrollIntoView({ behavior: 'smooth' });
    
    showNotification('分析完成！', 'success');
}

function displayStats(result) {
    const statsContainer = document.getElementById('statsContainer');
    if (!statsContainer) return;
    
    let statsHTML = '';
    const sessionInfo = result.session_info || {};
    const deepseekResults = result.deepseek_results || {};
    const codeStructure = result.code_structure || {};
    
    // 基本统计
    statsHTML += `
        <div class="stat-card">
            <div class="stat-value">${sessionInfo.duration ? sessionInfo.duration.toFixed(2) : '0.00'}</div>
            <div class="stat-label">运行时间(秒)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${sessionInfo.findings_count || 0}</div>
            <div class="stat-label">发现问题</div>
        </div>
    `;
    
    // DeepSeek统计
    if (Object.keys(deepseekResults).length > 0) {
        statsHTML += `
            <div class="stat-card">
                <div class="stat-value">${Object.keys(deepseekResults).length}</div>
                <div class="stat-label">AI分析项</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">
                    <i class="fas fa-robot" style="color:#667eea"></i>
                </div>
                <div class="stat-label">AI分析完成</div>
            </div>
        `;
    }
    
    // 代码结构统计
    if (codeStructure.basic_info) {
        statsHTML += `
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
    
    statsContainer.innerHTML = statsHTML;
}

function displayCodeStructure(structure) {
    const container = document.getElementById('codeStructure');
    if (!container) return;
    
    let html = '<div class="html-preview">';
    html += '<h3>代码结构分析</h3>';
    
    // 基本信息
    if (structure.basic_info) {
        html += '<div class="metric">';
        html += '<h4>基本信息</h4>';
        html += `<p><strong>文件:</strong> ${structure.basic_info.filename}</p>`;
        html += `<p><strong>大小:</strong> ${(structure.basic_info.file_size / 1024).toFixed(2)} KB</p>`;
        html += `<p><strong>总行数:</strong> ${structure.basic_info.total_lines}</p>`;
        html += `<p><strong>代码行数:</strong> ${structure.basic_info.code_lines}</p>`;
        html += '</div>';
    }
    
    // 函数信息
    if (structure.functions && structure.functions.length > 0) {
        html += '<div class="metric">';
        html += '<h4>函数分析</h4>';
        html += `<p>共 ${structure.functions.length} 个函数</p>`;
        html += '<table>';
        html += '<tr><th>函数名</th><th>行号</th><th>参数</th><th>文档</th><th>调用</th></tr>';
        structure.functions.slice(0, 10).forEach(func => {
            html += `<tr>
                <td>${func.name}</td>
                <td>${func.lineno}</td>
                <td>${func.args}</td>
                <td>${func.has_docstring ? '✓' : '✗'}</td>
                <td>${func.calls.length}</td>
            </tr>`;
        });
        html += '</table>';
        if (structure.functions.length > 10) {
            html += `<p>... 还有 ${structure.functions.length - 10} 个函数</p>`;
        }
        html += '</div>';
    }
    
    // 类信息
    if (structure.classes && structure.classes.length > 0) {
        html += '<div class="metric">';
        html += '<h4>类分析</h4>';
        html += `<p>共 ${structure.classes.length} 个类</p>`;
        html += '<table>';
        html += '<tr><th>类名</th><th>行号</th><th>方法数</th><th>继承</th><th>文档</th></tr>';
        structure.classes.forEach(cls => {
            html += `<tr>
                <td>${cls.name}</td>
                <td>${cls.lineno}</td>
                <td>${cls.methods.length}</td>
                <td>${cls.bases.join(', ') || '-'}</td>
                <td>${cls.has_docstring ? '✓' : '✗'}</td>
            </tr>`;
        });
        html += '</table>';
        html += '</div>';
    }
    
    container.innerHTML = html + '</div>';
}

function displayDeepSeekResults(results) {
    const container = document.getElementById('deepseekResults');
    if (!container) return;
    
    let html = '<div class="html-preview">';
    html += '<div class="deepseek-section">';
    html += '<h3><i class="fas fa-robot"></i> DeepSeek AI分析结果</h3>';
    
    if (results.blackbox) {
        html += '<div class="deepseek-content">';
        html += '<h4><i class="fas fa-chart-bar"></i> 黑盒性能分析</h4>';
        html += results.blackbox.replace(/\n/g, '<br>')
                               .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                               .replace(/\*(.*?)\*/g, '<em>$1</em>')
                               .replace(/^### (.*)$/gm, '<h3>$1</h3>')
                               .replace(/^## (.*)$/gm, '<h2>$1</h2>')
                               .replace(/^# (.*)$/gm, '<h1>$1</h1>');
        html += '</div>';
    }
    
    if (results.whitebox) {
        html += '<div class="deepseek-content">';
        html += '<h4><i class="fas fa-code"></i> 白盒代码分析</h4>';
        html += results.whitebox.replace(/\n/g, '<br>')
                               .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                               .replace(/\*(.*?)\*/g, '<em>$1</em>')
                               .replace(/^### (.*)$/gm, '<h3>$1</h3>')
                               .replace(/^## (.*)$/gm, '<h2>$1</h2>')
                               .replace(/^# (.*)$/gm, '<h1>$1</h1>');
        html += '</div>';
    }
    
    if (!results.blackbox && !results.whitebox) {
        html += '<div class="deepseek-content">';
        html += '<p>未启用DeepSeek分析或分析失败。请检查DeepSeek配置。</p>';
        html += '</div>';
    }
    
    container.innerHTML = html + '</div></div>';
}

// 标签页切换
function showTab(tabName) {
    // 更新标签页
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // 激活选中的标签页
    event.target.classList.add('active');
    document.getElementById(tabName + 'Tab').classList.add('active');
}

// 下载报告
function downloadReport(format) {
    if (!currentAnalysisId || !currentReport) {
        showNotification('没有可下载的报告', 'warning');
        return;
    }
    
    let url, filename;
    
    switch(format) {
        case 'html':
            const htmlBlob = new Blob([currentReport.html], { type: 'text/html' });
            url = URL.createObjectURL(htmlBlob);
            filename = 'autoprofiler_report.html';
            break;
        case 'markdown':
            const mdBlob = new Blob([currentReport.markdown], { type: 'text/markdown' });
            url = URL.createObjectURL(mdBlob);
            filename = 'autoprofiler_report.md';
            break;
        case 'pdf':
            if (!currentReport.pdf_path) {
                showNotification('PDF生成失败或不可用', 'warning');
                return;
            }
            url = `/api/download/pdf/${currentAnalysisId}`;
            filename = 'autoprofiler_report.pdf';
            break;
    }
    
    if (format !== 'pdf') {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showNotification(`${format.toUpperCase()}报告下载开始`, 'success');
    } else {
        window.open(url, '_blank');
    }
}

// 复制到剪贴板
function copyToClipboard(format) {
    if (!currentReport) {
        showNotification('没有可复制的内容', 'warning');
        return;
    }
    
    let textToCopy;
    if (format === 'html') {
        textToCopy = currentReport.html;
    } else {
        textToCopy = currentReport.markdown;
    }
    
    navigator.clipboard.writeText(textToCopy)
        .then(() => showNotification('已复制到剪贴板', 'success'))
        .catch(err => showNotification('复制失败: ' + err, 'error'));
}

// 重置分析
function resetAnalysis() {
    currentAnalysisId = null;
    currentReport = null;
    resultContainer.style.display = 'none';
    progressContainer.style.display = 'none';
    if (fileInput) fileInput.value = '';
    
    // 重置预览
    const previews = ['htmlPreview', 'markdownContent', 'codeStructure', 'deepseekResults', 'rawData', 'statsContainer'];
    previews.forEach(id => {
        const element = document.getElementById(id);
        if (element) element.innerHTML = '';
    });
    
    resetProgress();
    
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

// 进度条控制
function updateProgress(percent, text) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    if (!progressBar || !progressText) return;
    
    const start = lastProgress;
    const end = percent;
    const duration = 500;
    const startTime = performance.now();
    
    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const currentPercent = start + (end - start) * progress;
        
        progressBar.style.width = currentPercent + '%';
        progressBar.textContent = Math.round(currentPercent) + '%';
        progressText.textContent = Math.round(currentPercent) + '% - ' + text;
        
        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            lastProgress = end;
        }
    }
    
    requestAnimationFrame(animate);
}

function resetProgress() {
    lastProgress = 0;
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const steps = document.querySelectorAll('.progress-step');
    
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '';
    }
    
    if (progressText) {
        progressText.textContent = '0% - 准备开始分析...';
    }
    
    steps.forEach(step => {
        step.classList.remove('active', 'completed');
    });
    
    if (steps[0]) steps[0].classList.add('active');
}

// 暴露函数到全局作用域
window.showTab = showTab;
window.downloadReport = downloadReport;
window.copyToClipboard = copyToClipboard;
window.resetAnalysis = resetAnalysis;