// MedGuard AI - Animations and Interactions

// Fade in on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize page with fade-in effect
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s ease';
        document.body.style.opacity = '1';
    }, 50);

    // Setup form submission handlers
    setupFormHandlers();

    // Setup smooth scrolling for anchor links
    setupSmoothScrolling();

    // Setup card hover animations
    setupCardAnimations();
});

// Form submission loading state handler
function setupFormHandlers() {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                // Show loading state
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
                submitBtn.disabled = true;

                // Add loading class for additional styling
                submitBtn.classList.add('loading');

                // Re-enable after a timeout (fallback)
                setTimeout(() => {
                    if (submitBtn.disabled) {
                        submitBtn.innerHTML = originalText;
                        submitBtn.disabled = false;
                        submitBtn.classList.remove('loading');
                    }
                }, 30000); // 30 second timeout
            }
        });
    });
}

// Smooth scrolling for internal links
function setupSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Enhanced card animations
function setupCardAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe glass cards for staggered animation
    document.querySelectorAll('.glass-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.6s ease ${index * 0.1}s`;
        observer.observe(card);
    });
}

// Button press animation
document.addEventListener('click', function(e) {
    if (e.target.matches('.btn-primary, .btn-secondary')) {
        const button = e.target;
        button.style.transform = 'scale(0.98)';
        setTimeout(() => {
            button.style.transform = '';
        }, 100);
    }
});

// Enhanced form field focus animations
document.addEventListener('focusin', function(e) {
    if (e.target.matches('input, textarea')) {
        e.target.style.transform = 'scale(1.02)';
    }
});

document.addEventListener('focusout', function(e) {
    if (e.target.matches('input, textarea')) {
        e.target.style.transform = 'scale(1)';
    }
});

// Navbar scroll behavior
window.addEventListener('scroll', function() {
    const navbar = document.querySelector('.nav-pill');
    if (navbar) {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    }
});

// Risk pill animation on results page
function animateRiskPill() {
    const riskPill = document.querySelector('.risk-pill');
    if (riskPill) {
        riskPill.style.transform = 'scale(1.1)';
        setTimeout(() => {
            riskPill.style.transform = 'scale(1)';
        }, 300);
    }
}

// Call risk pill animation if on results page
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.risk-pill')) {
        setTimeout(animateRiskPill, 800);
    }
});

// Enhanced error display animation
function showFieldError(field, message) {
    const errorDiv = field.parentNode.querySelector('.form-error') || document.createElement('div');
    errorDiv.className = 'form-error';
    errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;

    if (!field.parentNode.querySelector('.form-error')) {
        field.parentNode.appendChild(errorDiv);
    }

    // Animation
    errorDiv.style.opacity = '0';
    errorDiv.style.transform = 'translateY(-10px)';
    setTimeout(() => {
        errorDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        errorDiv.style.opacity = '1';
        errorDiv.style.transform = 'translateY(0)';
    }, 50);
}

// Remove field error animation
function hideFieldError(field) {
    const errorDiv = field.parentNode.querySelector('.form-error');
    if (errorDiv) {
        errorDiv.style.opacity = '0';
        errorDiv.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            errorDiv.remove();
        }, 300);
    }
}

// Typing animation for text elements
function typeText(element, text, speed = 50) {
    element.innerHTML = '';
    let i = 0;

    function typeChar() {
        if (i < text.length) {
            element.innerHTML += text.charAt(i);
            i++;
            setTimeout(typeChar, speed);
        }
    }

    typeChar();
}

// Enhanced mobile touch feedback
if ('ontouchstart' in window) {
    document.addEventListener('touchstart', function(e) {
        const target = e.target.closest('.btn-primary, .btn-secondary, .glass-card');
        if (target) {
            target.style.transform = 'scale(0.98)';
        }
    });

    document.addEventListener('touchend', function(e) {
        const target = e.target.closest('.btn-primary, .btn-secondary, .glass-card');
        if (target) {
            setTimeout(() => {
                target.style.transform = '';
            }, 150);
        }
    });
}

// Preloader for better UX
function showPageLoader() {
    const loader = document.createElement('div');
    loader.id = 'page-loader';
    loader.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #CBDDE9;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        opacity: 1;
        transition: opacity 0.5s ease;
    `;
    loader.innerHTML = '<i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #2872A1;"></i>';
    document.body.appendChild(loader);

    return loader;
}

function hidePageLoader(loader) {
    if (loader) {
        loader.style.opacity = '0';
        setTimeout(() => {
            loader.remove();
        }, 500);
    }
}

// Progress indicator for long operations
function showProgressBar() {
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0;
        height: 3px;
        background: #2872A1;
        z-index: 10001;
        transition: width 2s ease;
    `;
    document.body.appendChild(progressBar);

    // Animate to 70%
    setTimeout(() => {
        progressBar.style.width = '70%';
    }, 100);

    return progressBar;
}

function completeProgressBar(progressBar) {
    if (progressBar) {
        progressBar.style.width = '100%';
        setTimeout(() => {
            progressBar.style.opacity = '0';
            setTimeout(() => {
                progressBar.remove();
            }, 300);
        }, 500);
    }
}

// Export functions for external use
window.MedGuardAnimations = {
    showFieldError,
    hideFieldError,
    typeText,
    showPageLoader,
    hidePageLoader,
    showProgressBar,
    completeProgressBar
};