/* ============================================================
   MediCore HMS — Main JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── Sidebar Toggle ────────────────────────────────────────
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  const mainWrapper = document.getElementById('mainWrapper');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });

    // Close sidebar when clicking outside on mobile
    mainWrapper && mainWrapper.addEventListener('click', function () {
      if (window.innerWidth <= 992 && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
      }
    });
  }

  // ── Auto-dismiss flash alerts ─────────────────────────────
  const alerts = document.querySelectorAll('.hms-alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      bsAlert && bsAlert.close();
    }, 5000);
  });

  // ── Confirm Delete Helper ─────────────────────────────────
  window.confirmDelete = function (url, message) {
    if (confirm(message || 'Are you sure you want to delete this record? This cannot be undone.')) {
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = url;
      document.body.appendChild(form);
      form.submit();
    }
  };

  // ── Active nav link highlight (fallback) ──────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

  // ── Table row clickable (with data-href) ──────────────────
  document.querySelectorAll('tr[data-href]').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', function (e) {
      if (!e.target.closest('a, button, form')) {
        window.location.href = this.dataset.href;
      }
    });
  });

  // ── Tooltip initialization ────────────────────────────────
  const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipEls.forEach(el => new bootstrap.Tooltip(el));

  // ── Number input formatting (prevent negatives) ───────────
  document.querySelectorAll('input[type="number"]').forEach(inp => {
    if (inp.min === undefined || inp.min === '') return;
    inp.addEventListener('change', function () {
      if (parseFloat(this.value) < parseFloat(this.min)) {
        this.value = this.min;
      }
    });
  });

  // ── Date input default to today ───────────────────────────
  document.querySelectorAll('input[type="date"][data-today]').forEach(inp => {
    if (!inp.value) {
      inp.value = new Date().toISOString().split('T')[0];
    }
  });

  // ── Search form clear ─────────────────────────────────────
  document.querySelectorAll('[data-clear-search]').forEach(btn => {
    btn.addEventListener('click', function () {
      const form = this.closest('form');
      form.querySelectorAll('input[type="text"], input[type="search"]').forEach(inp => inp.value = '');
      form.submit();
    });
  });

  // ── Entrance animation for key UI blocks ──────────────────
  if (!reducedMotion) {
    const animatedEls = document.querySelectorAll('.hms-card, .stat-card, .alert, .table-responsive, .empty-state');
    animatedEls.forEach((el, index) => {
      el.classList.add('animate-in');
      el.style.animationDelay = `${Math.min(index * 35, 260)}ms`;
    });
  }

});

// ── AJAX helper ──────────────────────────────────────────────
window.hmsAjax = function (url, options = {}) {
  const defaults = {
    method: 'GET',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
  };
  return fetch(url, { ...defaults, ...options }).then(r => r.json());
};
