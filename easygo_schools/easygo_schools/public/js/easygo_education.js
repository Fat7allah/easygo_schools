// EasyGo Education Custom JavaScript

// Portal functionality
frappe.ready(function() {
    // Initialize portal features
    initializePortalFeatures();
    
    // Setup RTL support
    setupRTLSupport();
    
    // Initialize dashboard widgets
    initializeDashboardWidgets();
});

function initializePortalFeatures() {
    // Quick actions for portal users
    $('.quick-action-btn').on('click', function(e) {
        e.preventDefault();
        const action = $(this).data('action');
        const doctype = $(this).data('doctype');
        
        if (action === 'new') {
            window.location.href = `/app/${doctype.toLowerCase().replace(' ', '-')}/new`;
        }
    });
    
    // Enhanced search functionality
    $('#portal-search').on('keyup', function() {
        const searchTerm = $(this).val().toLowerCase();
        $('.searchable-item').each(function() {
            const text = $(this).text().toLowerCase();
            $(this).toggle(text.includes(searchTerm));
        });
    });
}

function setupRTLSupport() {
    // Detect Arabic content and apply RTL
    $('.form-control, .input-with-feedback').each(function() {
        const text = $(this).val() || $(this).text();
        if (isArabicText(text)) {
            $(this).addClass('arabic-text');
            $(this).attr('dir', 'rtl');
        }
    });
}

function isArabicText(text) {
    const arabicRegex = /[\u0600-\u06FF\u0750-\u077F]/;
    return arabicRegex.test(text);
}

function initializeDashboardWidgets() {
    // Animate counters
    $('.counter').each(function() {
        const $this = $(this);
        const countTo = $this.attr('data-count');
        
        $({ countNum: $this.text() }).animate({
            countNum: countTo
        }, {
            duration: 2000,
            easing: 'swing',
            step: function() {
                $this.text(Math.floor(this.countNum));
            },
            complete: function() {
                $this.text(this.countNum);
            }
        });
    });
    
    // Refresh widgets periodically
    setInterval(refreshDashboardData, 300000); // 5 minutes
}

function refreshDashboardData() {
    // Refresh dashboard widgets without page reload
    $('.dashboard-widget[data-refresh="true"]').each(function() {
        const widget = $(this);
        const endpoint = widget.data('endpoint');
        
        if (endpoint) {
            frappe.call({
                method: endpoint,
                callback: function(r) {
                    if (r.message) {
                        updateWidgetData(widget, r.message);
                    }
                }
            });
        }
    });
}

function updateWidgetData(widget, data) {
    // Update widget content with new data
    widget.find('.widget-value').each(function() {
        const key = $(this).data('key');
        if (data[key] !== undefined) {
            $(this).text(data[key]);
        }
    });
}

// Notification helpers
function showSuccessMessage(message) {
    frappe.show_alert({
        message: message,
        indicator: 'green'
    });
}

function showErrorMessage(message) {
    frappe.show_alert({
        message: message,
        indicator: 'red'
    });
}

// Form enhancements
frappe.ui.form.on('*', {
    refresh: function(frm) {
        // Add custom buttons based on doctype
        addCustomButtons(frm);
        
        // Setup field dependencies
        setupFieldDependencies(frm);
    }
});

function addCustomButtons(frm) {
    const doctype = frm.doc.doctype;
    
    // Add portal-specific buttons
    if (doctype === 'Student' && frm.doc.name) {
        frm.add_custom_button(__('View Portal'), function() {
            window.open(`/student-portal?student=${frm.doc.name}`);
        });
    }
    
    if (doctype === 'Fee Bill' && frm.doc.status === 'Unpaid') {
        frm.add_custom_button(__('Record Payment'), function() {
            frappe.new_doc('Payment Entry', {
                fee_bill: frm.doc.name,
                student: frm.doc.student,
                amount: frm.doc.total_amount
            });
        });
    }
}

function setupFieldDependencies(frm) {
    // Dynamic field behavior based on selections
    if (frm.doc.doctype === 'Student Attendance') {
        frm.fields_dict.status.df.onchange = function() {
            if (frm.doc.status === 'Absent') {
                frm.set_df_property('justification', 'reqd', 1);
            } else {
                frm.set_df_property('justification', 'reqd', 0);
            }
        };
    }
}

// Export functions for global use
window.EasyGoEducation = {
    showSuccessMessage,
    showErrorMessage,
    refreshDashboardData,
    isArabicText
};
