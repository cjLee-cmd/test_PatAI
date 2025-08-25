/**
 * Admin panel functionality
 */

let currentDocuments = [];
let deleteDocumentId = null;

document.addEventListener('DOMContentLoaded', function() {
    // Check if user is admin
    checkAdminAccess();
    
    // Load initial data
    loadStats();
    loadDocuments();
    
    // Setup upload form
    setupUploadForm();
    
    // Setup delete modal
    setupDeleteModal();
});

// Check admin access
function checkAdminAccess() {
    if (!isLoggedIn()) {
        window.location.href = '/login';
        return;
    }
    
    const user = getCurrentUser();
    if (user.role !== 'admin') {
        showMessage('관리자 권한이 필요합니다.', 'error');
        setTimeout(() => {
            window.location.href = '/';
        }, 2000);
        return;
    }
    
    // Update admin name
    const adminNameElement = document.getElementById('adminName');
    if (adminNameElement) {
        adminNameElement.textContent = user.name;
    }
}

// Load system statistics
async function loadStats() {
    try {
        const response = await axios.get('/info');
        const stats = response.data.stats;
        
        document.getElementById('totalUsers').textContent = stats.total_users;
        document.getElementById('totalDocuments').textContent = stats.total_documents;
        document.getElementById('processedDocuments').textContent = stats.processed_documents;
        document.getElementById('totalSearches').textContent = stats.total_searches;
        
    } catch (error) {
        console.error('Failed to load stats:', error);
        showMessage('통계 데이터 로드에 실패했습니다.', 'error');
    }
}

// Load documents list
async function loadDocuments() {
    try {
        const response = await axios.get('/api/documents/');
        currentDocuments = response.data;
        renderDocuments();
        
    } catch (error) {
        console.error('Failed to load documents:', error);
        const documentList = document.getElementById('documentList');
        if (documentList) {
            documentList.innerHTML = '<p class="text-red-500">문서 목록 로드에 실패했습니다.</p>';
        }
    }
}

// Render documents list
function renderDocuments() {
    const documentList = document.getElementById('documentList');
    
    if (!documentList) return;
    
    if (currentDocuments.length === 0) {
        documentList.innerHTML = `
            <div class="text-center py-8">
                <i class="fas fa-file-pdf text-gray-300 text-4xl mb-4"></i>
                <p class="text-gray-500">업로드된 문서가 없습니다.</p>
            </div>
        `;
        return;
    }
    
    documentList.innerHTML = currentDocuments.map(doc => `
        <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
                <div class="flex-1">
                    <h5 class="font-medium text-gray-900">${doc.original_filename}</h5>
                    <div class="text-sm text-gray-600 mt-1">
                        <span class="inline-flex items-center">
                            <i class="fas fa-calendar-alt mr-1"></i>
                            ${formatDate(doc.upload_date)}
                        </span>
                        <span class="ml-4 inline-flex items-center">
                            <i class="fas fa-hdd mr-1"></i>
                            ${formatFileSize(doc.file_size)}
                        </span>
                        <span class="ml-4 inline-flex items-center">
                            <i class="fas fa-puzzle-piece mr-1"></i>
                            ${doc.chunk_count}개 청크
                        </span>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        doc.processed ? 
                        'bg-green-100 text-green-800' : 
                        'bg-yellow-100 text-yellow-800'
                    }">
                        <i class="fas ${doc.processed ? 'fa-check-circle' : 'fa-clock'} mr-1"></i>
                        ${doc.processed ? '처리완료' : '처리중'}
                    </span>
                    ${!doc.processed ? `
                    <button onclick="processDocument(${doc.id})" 
                            class="text-blue-600 hover:text-blue-800 p-2" 
                            title="문서 처리">
                        <i class="fas fa-play"></i>
                    </button>
                    ` : ''}
                    <button onclick="confirmDelete(${doc.id}, '${doc.original_filename}')" 
                            class="text-red-600 hover:text-red-800 p-2">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// Setup upload form
function setupUploadForm() {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const uploadButton = document.getElementById('uploadButton');
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                // Validate file
                if (!file.name.toLowerCase().endsWith('.pdf')) {
                    showMessage('PDF 파일만 업로드 가능합니다.', 'error');
                    this.value = '';
                    return;
                }
                
                if (file.size > 50 * 1024 * 1024) { // 50MB
                    showMessage('파일 크기는 50MB 이하여야 합니다.', 'error');
                    this.value = '';
                    return;
                }
            }
        });
    }
}

// Handle file upload
async function handleUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const uploadButton = document.getElementById('uploadButton');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadMessage = document.getElementById('uploadMessage');
    
    const file = fileInput.files[0];
    if (!file) {
        showMessage('파일을 선택해주세요.', 'warning');
        return;
    }
    
    // Show progress
    uploadProgress.classList.remove('hidden');
    uploadMessage.classList.add('hidden');
    setLoading(uploadButton, true, '업로드 중...');
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        console.log('Uploading file:', file.name, file.size, file.type);
        
        const response = await axios.post('/api/documents/upload', formData, {
            timeout: 300000, // 5 minutes timeout for large files
            onUploadProgress: function(progressEvent) {
                const percentCompleted = Math.round(
                    (progressEvent.loaded * 100) / progressEvent.total
                );
                const progressBar = uploadProgress.querySelector('.bg-blue-600');
                if (progressBar) {
                    progressBar.style.width = percentCompleted + '%';
                }
            }
        });
        
        const result = response.data;
        
        // Show success message
        uploadMessage.className = 'bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4';
        uploadMessage.textContent = result.message;
        uploadMessage.classList.remove('hidden');
        
        // Clear form
        fileInput.value = '';
        
        // Reload documents and stats
        await loadDocuments();
        await loadStats();
        
        showMessage('문서가 성공적으로 업로드되었습니다.', 'success');
        
    } catch (error) {
        console.error('Upload error:', error);
        console.error('Error details:', error.response);
        
        let errorMessage = '파일 업로드에 실패했습니다.';
        
        if (error.response && error.response.data) {
            if (typeof error.response.data === 'string') {
                errorMessage = error.response.data;
            } else if (error.response.data.detail) {
                if (Array.isArray(error.response.data.detail)) {
                    errorMessage = error.response.data.detail.map(e => e.msg).join(', ');
                } else {
                    errorMessage = error.response.data.detail;
                }
            }
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        uploadMessage.className = 'bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4';
        uploadMessage.textContent = errorMessage;
        uploadMessage.classList.remove('hidden');
        
        showMessage(errorMessage, 'error');
        
    } finally {
        uploadProgress.classList.add('hidden');
        setLoading(uploadButton, false);
        
        // Reset progress bar
        const progressBar = uploadProgress.querySelector('.bg-blue-600');
        if (progressBar) {
            progressBar.style.width = '0%';
        }
    }
}

// Setup delete confirmation modal
function setupDeleteModal() {
    const deleteModal = document.getElementById('deleteModal');
    const confirmButton = document.getElementById('confirmDelete');
    const cancelButton = document.getElementById('cancelDelete');
    
    if (confirmButton) {
        confirmButton.addEventListener('click', async function() {
            if (deleteDocumentId !== null) {
                await deleteDocument(deleteDocumentId);
                hideDeleteModal();
            }
        });
    }
    
    if (cancelButton) {
        cancelButton.addEventListener('click', hideDeleteModal);
    }
    
    // Close modal when clicking outside
    if (deleteModal) {
        deleteModal.addEventListener('click', function(e) {
            if (e.target === deleteModal) {
                hideDeleteModal();
            }
        });
    }
}

// Show delete confirmation
function confirmDelete(documentId, filename) {
    deleteDocumentId = documentId;
    
    const deleteModal = document.getElementById('deleteModal');
    const modalText = deleteModal.querySelector('p');
    
    if (modalText) {
        modalText.textContent = `"${filename}" 문서를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`;
    }
    
    deleteModal.classList.remove('hidden');
}

// Hide delete modal
function hideDeleteModal() {
    const deleteModal = document.getElementById('deleteModal');
    deleteModal.classList.add('hidden');
    deleteDocumentId = null;
}

// Process document
async function processDocument(documentId) {
    try {
        showMessage('문서 처리를 시작합니다...', 'info');
        
        const response = await axios.post(`/api/documents/${documentId}/process`, {}, {
            timeout: 300000 // 5 minutes timeout
        });
        
        // Reload documents and stats
        await loadDocuments();
        await loadStats();
        
        showMessage(response.data.message, 'success');
        
    } catch (error) {
        console.error('Process error:', error);
        let errorMessage = '문서 처리에 실패했습니다.';
        
        if (error.response && error.response.data) {
            errorMessage = error.response.data.detail || errorMessage;
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        showMessage(errorMessage, 'error');
    }
}

// Delete document
async function deleteDocument(documentId) {
    try {
        await axios.delete(`/api/documents/${documentId}`);
        
        // Remove from current documents
        currentDocuments = currentDocuments.filter(doc => doc.id !== documentId);
        renderDocuments();
        
        // Reload stats
        await loadStats();
        
        showMessage('문서가 성공적으로 삭제되었습니다.', 'success');
        
    } catch (error) {
        console.error('Delete error:', error);
        const errorMessage = error.response?.data?.detail || '문서 삭제에 실패했습니다.';
        showMessage(errorMessage, 'error');
    }
}

// Add sample data
async function addSampleData() {
    try {
        showMessage('샘플 데이터를 추가하는 중...', 'info');
        
        const response = await axios.post('/api/documents/add-sample-data', {}, {
            timeout: 300000 // 5 minutes timeout
        });
        
        // Reload documents and stats
        await loadDocuments();
        await loadStats();
        
        showMessage(response.data.message, 'success');
        
    } catch (error) {
        console.error('Add sample data error:', error);
        let errorMessage = '샘플 데이터 추가에 실패했습니다.';
        
        if (error.response && error.response.data) {
            errorMessage = error.response.data.detail || errorMessage;
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        showMessage(errorMessage, 'error');
    }
}