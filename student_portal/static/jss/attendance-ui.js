document.addEventListener('DOMContentLoaded', function() {
    // Get all action cards
    const actionCards = document.querySelectorAll('.action-card');
    const contentSections = document.querySelectorAll('.content-section');
    
    // Function to update URL without reloading
    function updateURL(params = {}) {
        const url = new URL(window.location);
        
        // Update with new parameters
        Object.keys(params).forEach(key => {
            if (params[key] === null) {
                url.searchParams.delete(key);
            } else {
                url.searchParams.set(key, params[key]);
            }
        });
        
        window.history.pushState({}, '', url);
        return url.toString();
    }
    
    // Function to navigate to URL with parameters
    function navigateWithParams(params = {}) {
        const url = updateURL(params);
        window.location.href = url;
    }
    
    // Add click event to each action card
    actionCards.forEach(card => {
        card.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const view = targetId.replace('-section', '');
            
            // Remove active class from all cards and sections
            actionCards.forEach(c => c.classList.remove('active'));
            contentSections.forEach(s => s.classList.remove('active'));
            
            // Add active class to clicked card and target section
            this.classList.add('active');
            document.getElementById(targetId).classList.add('active');
            
            // Update URL with current view without page reload
            updateURL({ view });
        });
    });
    
    // Handle filter links
    document.querySelectorAll('.filter-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const classId = this.getAttribute('data-class');
            const currentView = new URLSearchParams(window.location.search).get('view');
            
            const params = {
                view: currentView || 'overview'
            };
            
            if (classId) {
                params.class = classId;
            }
            
            navigateWithParams(params);
        });
    });
    
    // Set initial active card based on URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const view = urlParams.get('view');
    
    if (view) {
        const targetCard = document.querySelector(`[data-target="${view}-section"]`);
        if (targetCard) {
            targetCard.click();
        }
    } else {
        // Default to overview section
        actionCards[0].click();
    }
    
    // Quick action button to view class stats
    document.getElementById('view-class-stats')?.addEventListener('click', function() {
        const classCard = document.querySelector('[data-target="class-section"]');
        if (classCard) {
            classCard.click();
        }
    });

    // Set progress bar width from data attribute
    document.querySelectorAll('.progress-bar').forEach(bar => {
        const width = bar.getAttribute('data-width');
        if (width) {
            bar.style.width = width + '%';
        }
    });
}); 