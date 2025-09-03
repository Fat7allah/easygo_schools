/**
 * EasyGo Education App JavaScript
 * Main client-side functionality for portals and forms
 */

// Global app namespace
window.EasyGoEducation = {
    // Current language (fr or ar)
    currentLang: 'fr',
    
    // Initialize app
    init: function() {
        this.setupLanguageToggle();
        this.setupPortalFeatures();
        this.setupFormValidation();
        console.log('EasyGo Education app initialized');
    },
    
    // Language toggle functionality
    setupLanguageToggle: function() {
        const langToggle = document.getElementById('lang-toggle');
        if (langToggle) {
            langToggle.addEventListener('click', this.toggleLanguage.bind(this));
        }
        
        // Apply RTL if Arabic is selected
        this.applyLanguageDirection();
    },
    
    toggleLanguage: function() {
        this.currentLang = this.currentLang === 'fr' ? 'ar' : 'fr';
        localStorage.setItem('easygo_lang', this.currentLang);
        this.applyLanguageDirection();
        // Reload page to apply language changes
        window.location.reload();
    },
    
    applyLanguageDirection: function() {
        const savedLang = localStorage.getItem('easygo_lang') || 'fr';
        this.currentLang = savedLang;
        
        if (savedLang === 'ar') {
            document.body.classList.add('rtl');
            document.documentElement.setAttribute('dir', 'rtl');
            document.documentElement.setAttribute('lang', 'ar');
        } else {
            document.body.classList.remove('rtl');
            document.documentElement.setAttribute('dir', 'ltr');
            document.documentElement.setAttribute('lang', 'fr');
        }
    },
    
    // Portal-specific features
    setupPortalFeatures: function() {
        this.setupAttendanceMarking();
        this.setupHomeworkSubmission();
        this.setupMessaging();
        this.setupMeetingBooking();
    },
    
    // Quick attendance marking for teachers
    setupAttendanceMarking: function() {
        const attendanceBtns = document.querySelectorAll('.attendance-btn');
        attendanceBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const studentId = this.dataset.student;
                const status = this.dataset.status;
                EasyGoEducation.markAttendance(studentId, status, this);
            });
        });
    },
    
    markAttendance: function(studentId, status, button) {
        // Remove active state from siblings
        const siblings = button.parentNode.querySelectorAll('.attendance-btn');
        siblings.forEach(btn => btn.classList.remove('active'));
        
        // Add active state to clicked button
        button.classList.add('active');
        
        // Update button styles based on status
        button.className = `attendance-btn attendance-${status} active`;
        
        // TODO: Send to backend
        console.log(`Marking student ${studentId} as ${status}`);
    },
    
    // Homework submission handling
    setupHomeworkSubmission: function() {
        const homeworkForms = document.querySelectorAll('.homework-submission-form');
        homeworkForms.forEach(form => {
            form.addEventListener('submit', this.handleHomeworkSubmission.bind(this));
        });
    },
    
    handleHomeworkSubmission: function(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        
        // Validate file upload
        const fileInput = form.querySelector('input[type="file"]');
        if (fileInput && fileInput.files.length === 0) {
            this.showAlert('Veuillez sélectionner un fichier à soumettre.', 'warning');
            return;
        }
        
        // Show loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Envoi en cours...';
        submitBtn.disabled = true;
        
        // TODO: Send to backend
        setTimeout(() => {
            this.showAlert('Devoir soumis avec succès!', 'success');
            form.reset();
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }, 1000);
    },
    
    // Messaging system
    setupMessaging: function() {
        const messageForm = document.getElementById('message-form');
        if (messageForm) {
            messageForm.addEventListener('submit', this.handleMessageSend.bind(this));
        }
        
        // Auto-refresh messages every 30 seconds
        setInterval(this.refreshMessages.bind(this), 30000);
    },
    
    handleMessageSend: function(event) {
        event.preventDefault();
        const form = event.target;
        const messageText = form.querySelector('textarea[name="message"]').value.trim();
        
        if (!messageText) {
            this.showAlert('Veuillez saisir un message.', 'warning');
            return;
        }
        
        // TODO: Send to backend
        console.log('Sending message:', messageText);
        form.reset();
        this.showAlert('Message envoyé!', 'success');
    },
    
    refreshMessages: function() {
        // TODO: Fetch new messages from backend
        console.log('Refreshing messages...');
    },
    
    // Meeting booking system
    setupMeetingBooking: function() {
        const meetingForm = document.getElementById('meeting-booking-form');
        if (meetingForm) {
            meetingForm.addEventListener('submit', this.handleMeetingBooking.bind(this));
        }
    },
    
    handleMeetingBooking: function(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        
        // TODO: Send to backend
        console.log('Booking meeting:', Object.fromEntries(formData));
        this.showAlert('Demande de rendez-vous envoyée!', 'success');
        form.reset();
    },
    
    // Form validation
    setupFormValidation: function() {
        const forms = document.querySelectorAll('form[data-validate]');
        forms.forEach(form => {
            form.addEventListener('submit', this.validateForm.bind(this));
        });
    },
    
    validateForm: function(event) {
        const form = event.target;
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                this.showFieldError(field, 'Ce champ est obligatoire.');
                isValid = false;
            } else {
                this.clearFieldError(field);
            }
        });
        
        if (!isValid) {
            event.preventDefault();
        }
    },
    
    showFieldError: function(field, message) {
        this.clearFieldError(field);
        field.classList.add('is-invalid');
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    },
    
    clearFieldError: function(field) {
        field.classList.remove('is-invalid');
        const errorDiv = field.parentNode.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.remove();
        }
    },
    
    // Utility functions
    showAlert: function(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.alert-container') || document.body;
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    },
    
    formatDate: function(date, locale = 'fr-FR') {
        return new Date(date).toLocaleDateString(locale);
    },
    
    formatCurrency: function(amount, currency = 'MAD') {
        return new Intl.NumberFormat('fr-MA', {
            style: 'currency',
            currency: currency
        }).format(amount);
    }
};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    EasyGoEducation.init();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EasyGoEducation;
}
