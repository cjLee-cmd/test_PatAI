/**
 * Main application JavaScript
 */

// Global authentication helper
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    if (!token) return {};
    
    return {
        'Authorization': `Bearer ${token}`
    };
}

// Check if user is logged in
function isLoggedIn() {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    return token && user;
}

// Get current user data
function getCurrentUser() {
    const userData = localStorage.getItem('user');
    return userData ? JSON.parse(userData) : null;
}

// Logout function
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
}

// Show/hide loading state
function setLoading(element, isLoading, loadingText = '로딩 중...') {
    if (isLoading) {
        element.disabled = true;
        element.dataset.originalText = element.textContent;
        element.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>${loadingText}`;
    } else {
        element.disabled = false;
        element.textContent = element.dataset.originalText || element.textContent;
    }
}

// Show message (success/error)
function showMessage(message, type = 'info', duration = 5000) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm ${
        type === 'success' ? 'bg-green-100 text-green-800 border-green-200' :
        type === 'error' ? 'bg-red-100 text-red-800 border-red-200' :
        type === 'warning' ? 'bg-yellow-100 text-yellow-800 border-yellow-200' :
        'bg-blue-100 text-blue-800 border-blue-200'
    } border`;
    
    messageDiv.innerHTML = `
        <div class="flex items-center">
            <i class="fas ${
                type === 'success' ? 'fa-check-circle' :
                type === 'error' ? 'fa-exclamation-circle' :
                type === 'warning' ? 'fa-exclamation-triangle' :
                'fa-info-circle'
            } mr-2"></i>
            <span class="flex-1">${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-gray-500 hover:text-gray-700">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(messageDiv);
    
    // Auto remove after duration
    if (duration > 0) {
        setTimeout(() => {
            if (messageDiv.parentElement) {
                messageDiv.remove();
            }
        }, duration);
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Initialize Axios defaults (removed global Content-Type to allow multipart uploads)

// Add request interceptor to include auth headers
axios.interceptors.request.use(function (config) {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, function (error) {
    return Promise.reject(error);
});

// Add response interceptor to handle auth errors
axios.interceptors.response.use(function (response) {
    return response;
}, function (error) {
    if (error.response && error.response.status === 401) {
        // Unauthorized - clear local storage and redirect to login
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
            window.location.href = '/login';
        }
    }
    return Promise.reject(error);
});

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication status on protected pages
    const protectedPaths = ['/', '/admin'];
    const currentPath = window.location.pathname;
    
    if (protectedPaths.includes(currentPath) && !isLoggedIn()) {
        // Show login modal or redirect
        if (currentPath === '/') {
            const loginModal = document.getElementById('loginModal');
            if (loginModal) {
                loginModal.classList.remove('hidden');
            }
        } else {
            window.location.href = '/login';
        }
    }
    
    // Initialize user info if logged in
    if (isLoggedIn()) {
        const user = getCurrentUser();
        const userNameElement = document.getElementById('userName');
        const userRoleElement = document.getElementById('userRole');
        const adminPanel = document.getElementById('adminPanel');
        
        if (userNameElement) userNameElement.textContent = user.name;
        if (userRoleElement) userRoleElement.textContent = user.role === 'admin' ? '관리자' : '사용자';
        
        // Show admin panel if user is admin
        if (user.role === 'admin' && adminPanel) {
            adminPanel.classList.remove('hidden');
        }
        
        // Enable search functionality
        const searchInput = document.getElementById('searchInput');
        const searchButton = document.getElementById('searchButton');
        
        if (searchInput) searchInput.disabled = false;
        if (searchButton) searchButton.disabled = false;
    }
});