/**
 * Chat functionality for the main interface
 */

let searchHistory = [];
let currentSearchId = null;

// Initialize chat functionality
document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    const searchInput = document.getElementById('searchInput');
    
    if (searchForm) {
        searchForm.addEventListener('submit', handleSearch);
    }
    
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch(e);
            }
        });
    }
    
    // Load search history if user is logged in
    if (isLoggedIn()) {
        loadSearchHistory();
    }
});

// Handle search form submission
async function handleSearch(e) {
    e.preventDefault();
    
    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    const query = searchInput.value.trim();
    
    if (!query) return;
    
    // Check if user is logged in
    if (!isLoggedIn()) {
        const loginModal = document.getElementById('loginModal');
        if (loginModal) {
            loginModal.classList.remove('hidden');
        }
        return;
    }
    
    // Add user message to chat
    addMessage(query, 'user');
    
    // Clear input
    searchInput.value = '';
    
    // Set loading state
    setLoading(searchButton, true, '검색 중...');
    updateStatus('검색 중...', 'loading');
    
    // Hide welcome message
    const welcomeMessage = document.getElementById('welcomeMessage');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }
    
    try {
        // Create form data
        const formData = new FormData();
        formData.append('query', query);
        
        const response = await axios.post('/api/search/ask', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        
        const result = response.data;
        
        // Add AI response to chat
        addMessage(result.response, 'ai', result.sources, result.response_time);
        
        // Update search history
        currentSearchId = result.search_id;
        loadSearchHistory();
        
        updateStatus('준비됨', 'ready');
        
    } catch (error) {
        console.error('Search error:', error);
        const errorMessage = error.response?.data?.detail || '검색 중 오류가 발생했습니다.';
        addMessage(errorMessage, 'error');
        updateStatus('오류 발생', 'error');
    } finally {
        setLoading(searchButton, false);
    }
}

// Add message to chat area
function addMessage(content, type, sources = [], responseTime = null) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'flex mb-4';
    
    if (type === 'user') {
        messageDiv.innerHTML = `
            <div class="ml-auto max-w-3xl">
                <div class="bg-blue-600 text-white p-4 rounded-lg rounded-br-none">
                    <p class="whitespace-pre-wrap">${content}</p>
                </div>
                <div class="text-xs text-gray-500 text-right mt-1">${formatDate(new Date())}</div>
            </div>
        `;
    } else if (type === 'ai') {
        const sourcesHtml = sources.length > 0 ? `
            <div class="mt-4 p-3 bg-gray-50 rounded border">
                <h4 class="text-sm font-medium text-gray-700 mb-2">
                    <i class="fas fa-file-alt mr-1"></i>참조 문서 (${sources.length}개)
                </h4>
                <div class="space-y-2">
                    ${sources.map(source => `
                        <div class="text-xs bg-white p-2 rounded border">
                            <div class="flex items-center justify-between mb-1">
                                <span class="font-medium text-blue-600">${source.filename}</span>
                                <span class="text-gray-500">유사도: ${Math.round(source.similarity * 100)}%</span>
                            </div>
                            <p class="text-gray-600">${source.chunk_text}</p>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';
        
        const responseTimeHtml = responseTime ? `
            <div class="text-xs text-gray-500 mt-1">
                응답 시간: ${responseTime}ms
            </div>
        ` : '';
        
        messageDiv.innerHTML = `
            <div class="max-w-3xl">
                <div class="flex items-start space-x-3">
                    <div class="flex-shrink-0 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                        <i class="fas fa-robot text-white text-sm"></i>
                    </div>
                    <div class="flex-1">
                        <div class="bg-white border border-gray-200 p-4 rounded-lg rounded-tl-none shadow-sm">
                            <div class="prose prose-sm max-w-none">
                                ${content.split('\n').map(line => `<p>${line}</p>`).join('')}
                            </div>
                            ${sourcesHtml}
                        </div>
                        <div class="text-xs text-gray-500 mt-1">${formatDate(new Date())}</div>
                        ${responseTimeHtml}
                    </div>
                </div>
            </div>
        `;
    } else if (type === 'error') {
        messageDiv.innerHTML = `
            <div class="max-w-3xl">
                <div class="flex items-start space-x-3">
                    <div class="flex-shrink-0 w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                        <i class="fas fa-exclamation-triangle text-white text-sm"></i>
                    </div>
                    <div class="flex-1">
                        <div class="bg-red-50 border border-red-200 p-4 rounded-lg rounded-tl-none">
                            <p class="text-red-800">${content}</p>
                        </div>
                        <div class="text-xs text-gray-500 mt-1">${formatDate(new Date())}</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    const chatArea = document.getElementById('chatArea');
    chatArea.scrollTop = chatArea.scrollHeight;
}

// Update status indicator
function updateStatus(text, type) {
    const statusIndicator = document.getElementById('statusIndicator');
    const statusDot = document.getElementById('statusDot');
    
    if (statusIndicator) statusIndicator.textContent = text;
    
    if (statusDot) {
        statusDot.className = 'h-2 w-2 rounded-full ';
        if (type === 'ready') {
            statusDot.className += 'bg-green-500';
        } else if (type === 'loading') {
            statusDot.className += 'bg-yellow-500 animate-pulse';
        } else if (type === 'error') {
            statusDot.className += 'bg-red-500';
        } else {
            statusDot.className += 'bg-gray-400';
        }
    }
}

// Load search history
async function loadSearchHistory() {
    if (!isLoggedIn()) return;
    
    try {
        const response = await axios.get('/api/search/history?limit=10');
        searchHistory = response.data;
        renderSearchHistory();
    } catch (error) {
        console.error('Failed to load search history:', error);
    }
}

// Render search history in sidebar
function renderSearchHistory() {
    const historyContainer = document.getElementById('searchHistory');
    
    if (!historyContainer) return;
    
    if (searchHistory.length === 0) {
        historyContainer.innerHTML = '<p class="text-xs text-gray-500">검색 기록이 없습니다.</p>';
        return;
    }
    
    historyContainer.innerHTML = searchHistory.map(item => `
        <div class="p-3 hover:bg-gray-50 rounded-lg cursor-pointer border border-gray-200 mb-2" 
             onclick="loadSearchItem(${item.id})">
            <p class="text-sm font-medium text-gray-900 truncate">${item.query}</p>
            <p class="text-xs text-gray-500 mt-1">${formatDate(item.created_at)}</p>
            <div class="flex items-center mt-1">
                <span class="text-xs text-gray-400">${item.response_time}ms</span>
                <span class="text-xs text-gray-400 ml-2">${item.sources.length}개 문서</span>
            </div>
        </div>
    `).join('');
}

// Load a specific search item
async function loadSearchItem(searchId) {
    const item = searchHistory.find(h => h.id === searchId);
    if (!item) return;
    
    // Clear current chat
    newChat();
    
    // Add the search query and response
    addMessage(item.query, 'user');
    addMessage(item.response, 'ai', item.sources, item.response_time);
    
    currentSearchId = searchId;
}

// Start new chat
function newChat() {
    const chatMessages = document.getElementById('chatMessages');
    const welcomeMessage = document.getElementById('welcomeMessage');
    
    if (chatMessages) {
        chatMessages.innerHTML = '';
    }
    
    if (welcomeMessage) {
        welcomeMessage.style.display = 'block';
    }
    
    currentSearchId = null;
    updateStatus('준비됨', 'ready');
}