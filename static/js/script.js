// ========== NEXA PALS -- INTERACTIVE JAVASCRIPT ==========

document.addEventListener('DOMContentLoaded', function() {
    // Elements that are actually present in the templates.
    const projectCards = document.querySelectorAll('.project-card');
    const featureCards = document.querySelectorAll('.feature-card');

    // Project cards (create.html) -- click to start building
    projectCards.forEach(card => {
        card.addEventListener('click', function() {
            const projectName = this.querySelector('h4')?.textContent || 'this project';
            window.showMessage?.(`${projectName} is ready to build!`);
            const templateId = this.getAttribute('data-template-id');
            if (templateId && window.location.pathname === '/') {
                setTimeout(() => {
                    window.location.href = `/create?template=${templateId}`;
                }, 800);
            }
        });
    });

    // Feature cards (index.html)
    featureCards.forEach(card => {
        card.addEventListener('click', function() {
            const feature = this.querySelector('h3')?.textContent || 'this feature';
            window.showMessage?.(`${feature}`);
        });
    });
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

// Tracks which saved project (if any) is currently loaded in the editor.
// This is the key piece that was missing: without it, "Save" always created
// a brand new project instead of updating the one you opened.
window.currentProjectId = window.currentProjectId || null;

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

window.saveProject = async function() {
    const title = document.getElementById('projectTitle')?.value.trim() || 'My Project';
    const html_code = document.getElementById('htmlEditor')?.value || '';
    const css_code = document.getElementById('cssEditor')?.value || '';
    const js_code = document.getElementById('jsEditor')?.value || '';

    try {
        const response = await fetch('/api/save_project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                project_id: window.currentProjectId,
                title, html_code, css_code, js_code
            })
        });
        const data = await response.json();
        if (data.success) {
            window.currentProjectId = data.project_id;
            if (data.xp_earned > 0 && typeof window.showXpToast === 'function') {
                window.showXpToast(data.xp_earned, 'Ship bonus!');
            } else if (typeof window.showMessage === 'function') {
                window.showMessage('Project saved!');
            } else {
                alert('Project saved!');
            }
            refreshProjectList(data.project_id);
        } else {
            alert(data.message || 'Error saving project');
        }
    } catch (error) {
        alert('Network error. Please try again.');
    }
};

window.loadProject = async function() {
    const select = document.getElementById('projectSelect');
    const projectId = select?.value;
    if (!projectId) {
        window.startNewProject();
        return;
    }

    try {
        const response = await fetch(`/api/load_project/${projectId}`);
        const data = await response.json();
        if (data.success) {
            document.getElementById('htmlEditor').value = data.html_code;
            document.getElementById('cssEditor').value = data.css_code;
            document.getElementById('jsEditor').value = data.js_code;
            document.getElementById('projectTitle').value = data.title;
            window.currentProjectId = data.project_id;
            if (typeof window.runCode === 'function') window.runCode();
        } else {
            alert(data.message || 'Error loading project');
        }
    } catch (error) {
        alert('Error loading project');
    }
};

window.startNewProject = function() {
    document.getElementById('htmlEditor').value = '<h1>Hello, Nexa Pals!</h1>\n<p>Change this code and see the magic.</p>\n<button id="myBtn">Click Me</button>';
    document.getElementById('cssEditor').value = 'h1 { color: #FFB347; font-family: sans-serif; }\nbutton { background: #9B7EDE; color: white; border: none; padding: 10px 20px; border-radius: 30px; cursor: pointer; }\nbutton:hover { background: #7B5EC0; }';
    document.getElementById('jsEditor').value = "document.getElementById('myBtn')?.addEventListener('click', () => {\n    alert('You clicked the button!');\n});";
    document.getElementById('projectTitle').value = '';
    window.currentProjectId = null;
    const select = document.getElementById('projectSelect');
    if (select) select.value = '';
    if (typeof window.runCode === 'function') window.runCode();
};

window.deleteCurrentProject = async function() {
    if (!window.currentProjectId) {
        alert('Nothing to delete – this project hasn\'t been saved yet.');
        return;
    }
    if (!confirm('Delete this project? This can\'t be undone!')) return;

    try {
        const response = await fetch(`/api/delete_project/${window.currentProjectId}`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() }
        });
        const data = await response.json();
        if (data.success) {
            alert('Project deleted');
            window.startNewProject();
            removeProjectFromList(window.currentProjectId);
        } else {
            alert(data.message || 'Error deleting project');
        }
    } catch (error) {
        alert('Network error. Please try again.');
    }
};

function refreshProjectList(selectedId) {
    const select = document.getElementById('projectSelect');
    if (!select) return;
    const title = document.getElementById('projectTitle')?.value || 'My Project';
    let existingOption = Array.from(select.options).find(o => o.value == selectedId);
    if (existingOption) {
        existingOption.textContent = title;
    } else {
        const opt = document.createElement('option');
        opt.value = selectedId;
        opt.textContent = title;
        select.appendChild(opt);
    }
    select.value = selectedId;
}

function removeProjectFromList(projectId) {
    const select = document.getElementById('projectSelect');
    if (!select) return;
    const opt = Array.from(select.options).find(o => o.value == projectId);
    if (opt) opt.remove();
}

// Auto-run code on page load for play page
if (document.getElementById('htmlEditor')) {
    window.runCode();
}
// ── XP Toast ──────────────────────────────────────────────────────────────
window.showXpToast = function(xp, msg) {
  const toast = document.getElementById('xpToast');
  if (!toast) return;
  document.getElementById('xpNum').textContent = '+' + xp;
  document.getElementById('xpMsg').textContent = msg || 'XP earned!';
  toast.classList.add('show');
  window.NexaSound?.correct();
  setTimeout(() => toast.classList.remove('show'), 3000);
};

// ── Confetti burst ───────────────────────────────────────────────────────
// A lightweight, dependency-free celebration for milestones (lesson pass,
// badge earned, level up) — small colored divs, CSS-animated, removed after
// they finish falling. No canvas, no external library, no images.
window.showConfetti = function(opts) {
  opts = opts || {};
  const count = opts.count || 60;
  const colors = ['#FFB347', '#9B7EDE', '#5D9BEC', '#1e5f4b', '#e25c5c'];
  const container = document.createElement('div');
  container.className = 'confetti-container';
  document.body.appendChild(container);
  for (let i = 0; i < count; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    piece.style.left = Math.random() * 100 + 'vw';
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDelay = (Math.random() * 0.4) + 's';
    piece.style.animationDuration = (2.2 + Math.random() * 1.2) + 's';
    piece.style.transform = `rotate(${Math.random() * 360}deg)`;
    piece.style.width = piece.style.height = (6 + Math.random() * 6) + 'px';
    container.appendChild(piece);
  }
  setTimeout(() => container.remove(), 3800);
};

// ── Message popup (global) ────────────────────────────────────────────────
window.showMessage = function(text) {
  const popup = document.getElementById('messagePopup');
  if (!popup) return;
  popup.textContent = text;
  popup.classList.add('show');
  setTimeout(() => popup.classList.remove('show'), 2500);
};

// ========== ANIMATIONS & VISUAL POLISH ==========
document.addEventListener('DOMContentLoaded', function () {
  // Navbar shadow on scroll
  const navbar = document.querySelector('.navbar');
  if (navbar) {
    const onScroll = () => {
      navbar.classList.toggle('scrolled', window.scrollY > 12);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // Scroll-triggered entrance animations
  const animTargets = document.querySelectorAll(
    '.path-track, .encourage-inner, .journey-progress-card, .feature-card, .project-card, .lesson-card, .lb-row, .stat-item, .hero-card'
  );
  if (animTargets.length && 'IntersectionObserver' in window) {
    animTargets.forEach((el, i) => {
      el.classList.add('anim-in');
      if (i % 5 === 1) el.classList.add('anim-in-delay-1');
      else if (i % 5 === 2) el.classList.add('anim-in-delay-2');
      else if (i % 5 === 3) el.classList.add('anim-in-delay-3');
      else if (i % 5 === 4) el.classList.add('anim-in-delay-4');
    });
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -24px 0px' }
    );
    animTargets.forEach((el) => io.observe(el));
  } else {
    animTargets.forEach((el) => el.classList.add('visible'));
  }

  // Smooth focus ring for keyboard users on interactive path nodes
  document.querySelectorAll('.path-node').forEach((node) => {
    node.addEventListener('focus', () => node.classList.add('focus-visible'));
    node.addEventListener('blur', () => node.classList.remove('focus-visible'));
  });
});

// ========== HOVER / INTERACTION ENHANCEMENTS ==========
document.addEventListener('DOMContentLoaded', function () {
  // Soft ripple on primary buttons
  document.querySelectorAll('.btn, .big-btn').forEach((btn) => {
    btn.addEventListener('click', function (e) {
      const rect = this.getBoundingClientRect();
      const ripple = document.createElement('span');
      const size = Math.max(rect.width, rect.height);
      ripple.style.cssText = [
        'position:absolute',
        'border-radius:50%',
        'background:rgba(255,255,255,0.35)',
        'pointer-events:none',
        'width:' + size + 'px',
        'height:' + size + 'px',
        'left:' + (e.clientX - rect.left - size / 2) + 'px',
        'top:' + (e.clientY - rect.top - size / 2) + 'px',
        'transform:scale(0)',
        'animation:rippleOut 0.65s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      ].join(';');
      if (getComputedStyle(this).position === 'static') {
        this.style.position = 'relative';
      }
      this.style.overflow = 'hidden';
      this.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    });
  });
});

// Inject ripple keyframes once
(function () {
  if (document.getElementById('nexa-ripple-style')) return;
  const s = document.createElement('style');
  s.id = 'nexa-ripple-style';
  s.textContent = '@keyframes rippleOut{to{transform:scale(2.4);opacity:0}}';
  document.head.appendChild(s);
})();

// ========== PAGE TRANSITIONS ==========
(function () {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Mark page ready for enter animation
  function markReady() {
    document.body.classList.add('page-ready');
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', markReady);
  } else {
    markReady();
  }

  if (reduceMotion) return;

  // Fade out before navigating to internal pages
  document.addEventListener('click', function (e) {
    const a = e.target.closest('a');
    if (!a) return;

    const href = a.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
    if (a.target === '_blank' || a.hasAttribute('download')) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    // External or same-page
    let url;
    try { url = new URL(href, window.location.origin); } catch (_) { return; }
    if (url.origin !== window.location.origin) return;
    if (url.pathname === window.location.pathname && url.hash) return; // in-page anchor

    // Don't animate form-like or JS handlers
    if (a.getAttribute('onclick') && href === '#') return;

    e.preventDefault();
    if (document.body.classList.contains('page-exit')) return;
    document.body.classList.remove('page-ready');
    document.body.classList.add('page-exit');

    let navigated = false;
    const go = () => {
      if (navigated) return;
      navigated = true;
      window.location.href = url.href;
    };
    setTimeout(go, 280);
  });

  // Handle browser back/forward cache restore
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) {
      document.body.classList.remove('page-exit');
      document.body.classList.add('page-ready');
    }
  });
})();
