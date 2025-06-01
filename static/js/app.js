// static/js/app.js
class EduPlatformAPI {
    constructor() {
        this.baseURL = '';
        this.token = localStorage.getItem('access_token');
        this.currentUser = null;
        this.init();
    }

    async init() {
        if (this.token) {
            await this.loadCurrentUser();
        }
        this.updateNavigation();
    }

    async request(endpoint, options = {}) {
        const url = this.baseURL + endpoint;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (this.token) {
            config.headers['Authorization'] = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(url, config);
            
            if (response.status === 401) {
                this.logout();
                throw new Error('Unauthorized');
            }

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Request failed');
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async login(email, password) {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        const response = await fetch('/token', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Invalid credentials');
        }

        const data = await response.json();
        this.token = data.access_token;
        localStorage.setItem('access_token', this.token);
        
        await this.loadCurrentUser();
        this.updateNavigation();
        
        return data;
    }

    async register(userData) {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }

        return await response.json();
    }

    logout() {
        this.token = null;
        this.currentUser = null;
        localStorage.removeItem('access_token');
        this.updateNavigation();
        window.location.href = '/';
    }

    async loadCurrentUser() {
        try {
            this.currentUser = await this.request('/users/me');
        } catch (error) {
            this.logout();
        }
    }

    updateNavigation() {
        const authNav = document.getElementById('authNav');
        if (!authNav) return;

        if (this.currentUser) {
            authNav.innerHTML = `
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">
                        <i class="bi bi-person-circle me-1"></i>${this.currentUser.name}
                    </a>
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item" href="/dashboard">
                            <i class="bi bi-grid me-2"></i>Панель управления
                        </a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="#" onclick="api.logout()">
                            <i class="bi bi-box-arrow-right me-2"></i>Выйти
                        </a></li>
                    </ul>
                </li>
            `;
        } else {
            authNav.innerHTML = `
                <li class="nav-item">
                    <a class="nav-link" href="#" onclick="showAuthModal()">
                        <i class="bi bi-box-arrow-in-right me-1"></i>Войти
                    </a>
                </li>
            `;
        }
    }

    async getCourses(filters = {}) {
        const params = new URLSearchParams(filters);
        return await this.request(`/courses?${params}`);
    }

    async createCourse(courseData) {
        return await this.request('/courses', {
            method: 'POST',
            body: JSON.stringify(courseData)
        });
    }

    async search(query) {
        const params = new URLSearchParams(query);
        return await this.request(`/search?${params}`);
    }

    async getUserProgress(userId) {
        return await this.request(`/analytics/user/${userId}/progress`);
    }

    async logActivity(activityData) {
        return await this.request('/activities', {
            method: 'POST',
            body: JSON.stringify(activityData)
        });
    }
}

// Global API instance
const api = new EduPlatformAPI();

// Authentication functions
function showAuthModal() {
    const modal = new bootstrap.Modal(document.getElementById('authModal'));
    modal.show();
}

function showLogin() {
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('authModalTitle').textContent = 'Вход в систему';
    updateAuthTabs('login');
}

function showRegister() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('authModalTitle').textContent = 'Регистрация';
    updateAuthTabs('register');
}

function updateAuthTabs(active) {
    const tabs = document.querySelectorAll('#authTabs .nav-link');
    tabs.forEach(tab => tab.classList.remove('active'));
    
    if (active === 'login') {
        tabs[0].classList.add('active');
    } else {
        tabs[1].classList.add('active');
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        await api.login(formData.get('username'), formData.get('password'));
        bootstrap.Modal.getInstance(document.getElementById('authModal')).hide();
        showAlert('Успешный вход в систему!', 'success');
        
        // Redirect to dashboard if on main page
        if (window.location.pathname === '/') {
            window.location.href = '/dashboard';
        } else {
            window.location.reload();
        }
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

async function handleRegister(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    const userData = {
        name: formData.get('name'),
        email: formData.get('email'),
        role: formData.get('role'),
        password: formData.get('password')
    };
    
    try {
        await api.register(userData);
        showAlert('Регистрация успешна! Теперь вы можете войти в систему.', 'success');
        showLogin();
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

// Search functions
function showSearchModal() {
    const modal = new bootstrap.Modal(document.getElementById('searchModal'));
    modal.show();
}

async function handleSearch(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    const query = {};
    for (let [key, value] of formData.entries()) {
        if (value) query[key] = value;
    }
    
    try {
        const results = await api.search(query);
        displaySearchResults(results);
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

function displaySearchResults(results) {
    const container = document.getElementById('searchResults');
    
    if (results.total_courses === 0 && results.total_materials === 0) {
        container.innerHTML = '<div class="alert alert-info">Ничего не найдено</div>';
        return;
    }
    
    let html = '';
    
    if (results.courses.length > 0) {
        html += '<h5>Курсы</h5>';
        results.courses.forEach(course => {
            html += `
                <div class="card mb-2">
                    <div class="card-body">
                        <h6 class="card-title">${course.title}</h6>
                        <p class="card-text">${course.description || ''}</p>
                        <span class="badge bg-primary">${course.category}</span>
                        <span class="badge bg-secondary">${course.level}</span>
                    </div>
                </div>
            `;
        });
    }
    
    if (results.materials.length > 0) {
        html += '<h5 class="mt-3">Материалы</h5>';
        results.materials.forEach(material => {
            html += `
                <div class="card mb-2">
                    <div class="card-body">
                        <h6 class="card-title">${material.title}</h6>
                        <span class="badge bg-info">${material.type}</span>
                    </div>
                </div>
            `;
        });
    }
    
    container.innerHTML = html;
}

// Main page functions
async function loadFeaturedCourses() {
    try {
        const courses = await api.getCourses({ limit: 6 });
        displayCourses(courses, 'coursesContainer');
    } catch (error) {
        console.error('Failed to load courses:', error);
    }
}

async function loadStatistics() {
    try {
        // Load basic statistics - you may need to implement these endpoints
        document.getElementById('totalCourses').textContent = '10+';
        document.getElementById('totalUsers').textContent = '100+';
        document.getElementById('totalMaterials').textContent = '50+';
    } catch (error) {
        console.error('Failed to load statistics:', error);
    }
}

function displayCourses(courses, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    if (courses.length === 0) {
        container.innerHTML = '<div class="col-12"><div class="alert alert-info">Курсы не найдены</div></div>';
        return;
    }
    
    container.innerHTML = courses.map(course => `
        <div class="col-md-6 col-lg-4 mb-4">
            <div class="card course-card h-100" onclick="openCourse(${course.id})">
                <div class="card-body">
                    <h5 class="card-title">${course.title}</h5>
                    <p class="card-text">${course.description || ''}</p>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-primary">${course.category}</span>
                        <span class="badge bg-secondary">${course.level}</span>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

function openCourse(courseId) {
    // Redirect to course details or open modal
    showAlert(`Открытие курса ${courseId}`, 'info');
}

// Dashboard functions
async function checkAuthAndLoadDashboard() {
    if (!api.currentUser) {
        window.location.href = '/';
        return;
    }
    
    // Show appropriate buttons based on user role
    if (api.currentUser.role === 'teacher' || api.currentUser.role === 'admin') {
        document.getElementById('createCourseBtn').style.display = 'block';
        document.getElementById('analyticsTab').style.display = 'block';
    }
    
    loadUserProfile();
    loadMyCourses();
}

async function loadUserProfile() {
    const container = document.getElementById('userProfile');
    if (!container) return;
    
    container.innerHTML = `
        <div class="d-flex align-items-center mb-3">
            <i class="bi bi-person-circle fs-1 me-3 text-primary"></i>
            <div>
                <h6 class="mb-1">${api.currentUser.name}</h6>
                <p class="text-muted mb-0">${api.currentUser.email}</p>
                <span class="badge bg-primary">${api.currentUser.role}</span>
            </div>
        </div>
    `;
}

async function loadMyCourses() {
    const container = document.getElementById('myCoursesContainer');
    if (!container) return;
    
    container.innerHTML = '<div class="loading"></div>';
    
    try {
        const courses = await api.getCourses();
        
        if (courses.length === 0) {
            container.innerHTML = '<div class="alert alert-info">У вас пока нет курсов</div>';
            return;
        }
        
        container.innerHTML = courses.map(course => `
            <div class="card mb-3">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="card-title">${course.title}</h5>
                            <p class="card-text">${course.description || ''}</p>
                            <span class="badge bg-primary me-2">${course.category}</span>
                            <span class="badge bg-secondary">${course.level}</span>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-outline-primary btn-sm" onclick="viewCourse(${course.id})">
                                <i class="bi bi-eye"></i>
                            </button>
                            <button class="btn btn-outline-success btn-sm" onclick="startCourse(${course.id})">
                                <i class="bi bi-play"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        container.innerHTML = '<div class="alert alert-danger">Ошибка загрузки курсов</div>';
    }
}

function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // Show selected tab
    document.getElementById(tabName + '-tab').style.display = 'block';
    
    // Update tab navigation
    document.querySelectorAll('#dashboardTabs .nav-link').forEach(link => {
        link.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Load tab content
    switch(tabName) {
        case 'progress':
            loadProgress();
            break;
        case 'analytics':
            loadAnalytics();
            break;
    }
}

async function loadProgress() {
    const container = document.getElementById('progressContainer');
    if (!container) return;
    
    container.innerHTML = '<div class="loading"></div>';
    
    try {
        const progress = await api.getUserProgress(api.currentUser.id);
        
        if (Object.keys(progress).length === 0) {
            container.innerHTML = '<div class="alert alert-info">Прогресс не найден</div>';
            return;
        }
        
        container.innerHTML = Object.values(progress).map(course => `
            <div class="progress-item">
                <h6>${course.course_title}</h6>
                <div class="progress mb-2">
                    <div class="progress-bar" style="width: ${course.completion_percentage}%">
                        ${Math.round(course.completion_percentage)}%
                    </div>
                </div>
                <div class="d-flex justify-content-between text-muted">
                    <small>Материалов завершено: ${course.completed_materials}/${course.total_materials}</small>
                    <small>Время: ${Math.round(course.total_time / 60)} мин</small>
                    ${course.avg_score ? `<small>Средний балл: ${course.avg_score.toFixed(1)}</small>` : ''}
                </div>
            </div>
        `).join('');
    } catch (error) {
        container.innerHTML = '<div class="alert alert-danger">Ошибка загрузки прогресса</div>';
    }
}

// Utility functions
function showAlert(message, type = 'info') {
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertContainer.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertContainer.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertContainer);
    
    setTimeout(() => {
        alertContainer.remove();
    }, 5000);
}

async function handleCreateCourse(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    const courseData = {
        title: formData.get('title'),
        description: formData.get('description'),
        category: formData.get('category'),
        level: formData.get('level'),
        teacher_id: api.currentUser.id
    };
    
    try {
        await api.createCourse(courseData);
        bootstrap.Modal.getInstance(document.getElementById('createCourseModal')).hide();
        showAlert('Курс успешно создан!', 'success');
        loadMyCourses();
        form.reset();
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

function showCreateCourseModal() {
    const modal = new bootstrap.Modal(document.getElementById('createCourseModal'));
    modal.show();
}

function viewCourse(courseId) {
    showAlert(`Просмотр курса ${courseId}`, 'info');
}

function startCourse(courseId) {
    // Log activity
    api.logActivity({
        user_id: api.currentUser.id,
        material_id: 1, // This should be the first material of the course
        action: 'start_course'
    });
    
    showAlert(`Начало изучения курса ${courseId}`, 'success');
}
