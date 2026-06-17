// ========== NEXA PALS – COMPLETE INTERACTIVE JAVASCRIPT ==========

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const messageBox = document.getElementById('messagePopup');
    const buddyAvatar = document.getElementById('buddyAvatar');
    const tryBtn = document.getElementById('tryBtn');
    const startBtn = document.getElementById('startBtn');
    const projectCounter = document.getElementById('projectCounter');
    const countSpan = document.getElementById('countNumber');
    const clickCounter = document.getElementById('clickCounter');
    const testimonialBox = document.getElementById('testimonialBox');
    const projectCards = document.querySelectorAll('.project-card');
    const featureCards = document.querySelectorAll('.feature-card');
    const buddyCards = document.querySelectorAll('.buddy-card');
    const socialIcons = document.querySelectorAll('.social-icons i');
    
    let projectCount = 150;
    let clickCount = 0;

    // Show popup message
    function showMessage(text, emoji = '✨') {
        if (!messageBox) return;
        messageBox.style.display = 'block';
        messageBox.innerHTML = `${emoji} ${text} ${emoji}`;
        setTimeout(() => {
            messageBox.style.display = 'none';
        }, 2000);
    }

    // Avatar click – random encouraging message
    if (buddyAvatar) {
        buddyAvatar.addEventListener('click', function() {
            const messages = [
                'Hey pal! Ready to code?',
                'Let\'s make something awesome!',
                'Coding is magic! ✨',
                'You\'re the best pal ever!',
                'I believe in you! 💪',
                'What shall we build today?'
            ];
            const randomMsg = messages[Math.floor(Math.random() * messages.length)];
            showMessage(randomMsg, '🤖');
            this.style.transform = 'scale(1.2)';
            setTimeout(() => this.style.transform = '', 300);
        });
    }

    // Project counter click – add 5 projects
    if (projectCounter && countSpan) {
        projectCounter.addEventListener('click', function() {
            projectCount += 5;
            countSpan.textContent = projectCount;
            showMessage(`🎉 ${projectCount}+ projects now!`, '🌟');
            this.style.backgroundColor = '#FFB347';
            setTimeout(() => this.style.backgroundColor = 'white', 200);
        });
    }

    // Fun click counter
    if (clickCounter) {
        clickCounter.addEventListener('click', function() {
            clickCount++;
            showMessage(`You clicked ${clickCount} times! 🎯`, '👆');
            if (clickCount === 5) showMessage('WOW! 5 clicks! You\'re a pro!', '🏆');
            if (clickCount === 10) showMessage('🌟 SUPER CLICKER! 🌟', '👑');
            if (clickCount === 20) showMessage('LEGENDARY CLICKER! 🔥', '⚡');
        });
    }

    // Try free button
    if (tryBtn) {
        tryBtn.addEventListener('click', function(e) {
            e.preventDefault();
            showMessage('🎁 Free coding coming right up!', '🎈');
        });
    }

    // Start button (CTA)
    if (startBtn) {
        startBtn.addEventListener('click', function() {
            showMessage('🚀 Let\'s go, pal! Adventure awaits!', '🎮');
        });
    }

    // Project cards – click to start building
    projectCards.forEach(card => {
        card.addEventListener('click', function() {
            const projectName = this.querySelector('h4')?.textContent || 'this project';
            showMessage(`✨ ${projectName} is ready to build!`, '🎯');
            // Optional: redirect to create page with template
            const templateId = this.getAttribute('data-template-id');
            if (templateId && window.location.pathname === '/') {
                setTimeout(() => {
                    window.location.href = `/create?template=${templateId}`;
                }, 800);
            }
        });
    });

    // Feature cards
    featureCards.forEach(card => {
        card.addEventListener('click', function() {
            const feature = this.querySelector('h3')?.textContent || 'power';
            showMessage(`⚡ ${feature} power activated!`, '💫');
        });
    });

    // Buddy cards
    buddyCards.forEach(card => {
        card.addEventListener('click', function() {
            const buddy = this.querySelector('h3')?.textContent || 'Pal';
            showMessage(`👋 ${buddy} says hello, pal!`, '💜');
        });
    });

    // Testimonial rotator (changes every 5 seconds)
    const testimonials = [
        { text: 'I made my first game in 1 hour!', author: 'Karabo, 10', emoji: '🎮' },
        { text: 'Nexa Pals is my favorite!', author: 'Relebohile, 11', emoji: '⭐' },
        { text: 'I taught my little brother!', author: 'Lesedi, 12', emoji: '💪' },
        { text: 'Way better than video games!', author: 'Kamo, 10', emoji: '🎯' },
        { text: 'My teacher uses it in class!', author: 'Thabo, 11', emoji: '📚' },
        { text: 'Coding is now my superpower!', author: 'Mia, 10', emoji: '🦸' }
    ];
    let testimonialIndex = 0;
    const testimonialText = document.getElementById('testimonialText');
    const testimonialAuthor = document.getElementById('testimonialAuthor');
    
    if (testimonialText && testimonialAuthor) {
        setInterval(() => {
            testimonialIndex = (testimonialIndex + 1) % testimonials.length;
            const t = testimonials[testimonialIndex];
            testimonialText.textContent = `${t.emoji} ${t.text}`;
            testimonialAuthor.textContent = t.author;
            if (testimonialBox) {
                testimonialBox.style.transform = 'scale(1.02)';
                setTimeout(() => testimonialBox.style.transform = '', 200);
            }
        }, 5000);
    }

    // Social icons click
    socialIcons.forEach(icon => {
        icon.addEventListener('click', function() {
            const platform = this.classList[1]?.replace('fa-', '') || 'social';
            showMessage(`📱 Find us on ${platform}!`, '🌟');
        });
    });

    // Welcome message after page loads
    setTimeout(() => {
        showMessage('👋 Welcome to Nexa Pals!', '🎈');
    }, 800);
});

// ========== PLAY PAGE SPECIFIC FUNCTIONS (code editor) ==========
// These are used only on the play.html page
window.runCode = function() {
    const html = document.getElementById('htmlEditor')?.value || '';
    const css = `<style>${document.getElementById('cssEditor')?.value || ''}</style>`;
    const js = `<script>${document.getElementById('jsEditor')?.value || ''}<\/script>`;
    const preview = document.getElementById('preview');
    if (preview) {
        preview.srcdoc = `<!DOCTYPE html><html><head>${css}</head><body>${html}${js}</body></html>`;
    }
};

window.saveProject = async function() {
    const title = document.getElementById('projectTitle')?.value.trim() || 'My Project';
    const html_code = document.getElementById('htmlEditor')?.value || '';
    const css_code = document.getElementById('cssEditor')?.value || '';
    const js_code = document.getElementById('jsEditor')?.value || '';
    
    try {
        const response = await fetch('/api/save_project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, html_code, css_code, js_code })
        });
        const data = await response.json();
        if (data.success) {
            alert('✅ Project saved successfully!');
            location.reload();
        } else {
            alert('❌ Error saving project');
        }
    } catch (error) {
        alert('❌ Network error. Please try again.');
    }
};

window.loadProject = async function() {
    const select = document.getElementById('projectSelect');
    const projectId = select?.value;
    if (!projectId) return;
    
    try {
        const response = await fetch(`/api/load_project/${projectId}`);
        const data = await response.json();
        if (data.success) {
            document.getElementById('htmlEditor').value = data.html_code;
            document.getElementById('cssEditor').value = data.css_code;
            document.getElementById('jsEditor').value = data.js_code;
            document.getElementById('projectTitle').value = data.title;
            if (typeof window.runCode === 'function') window.runCode();
        }
    } catch (error) {
        alert('❌ Error loading project');
    }
};

// Auto-run code on page load for play page
if (document.getElementById('htmlEditor')) {
    window.runCode();
}