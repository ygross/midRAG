/**
 * darkmode.js — shared dark/light toggle for every page.
 * Loaded from <head> so theme is applied before first paint (no flash).
 */

// Apply saved or OS preference immediately
(function () {
  var t = localStorage.getItem('rag-theme');
  var d = window.matchMedia && window.matchMedia('(prefers-color-scheme:dark)').matches;
  if (t === 'dark' || (t === null && d)) document.documentElement.classList.add('dark');
})();

function toggleDark() {
  var dk = document.documentElement.classList.toggle('dark');
  localStorage.setItem('rag-theme', dk ? 'dark' : 'light');
  _syncBtn(dk);
}

function _syncBtn(dk) {
  var b = document.getElementById('dark-toggle');
  if (!b) return;
  b.textContent = dk ? '☀️' : '🌙';
  b.title       = dk ? 'Switch to light mode' : 'Switch to dark mode';
}

document.addEventListener('DOMContentLoaded', function () {
  _syncBtn(document.documentElement.classList.contains('dark'));
});
