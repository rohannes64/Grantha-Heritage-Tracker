// Theme at launch, set before the first paint (loaded in every page's <head>, not as a module).
//
//   LAUNCH_IN_DARK = true   every new visit opens in dark mode; the toggle still works, and the choice lasts
//                           until the tab or browser is closed (sessionStorage), then the site opens dark again
//   LAUNCH_IN_DARK = false  the site opens light, and the visitor's choice is remembered (localStorage)
(function () {
  var LAUNCH_IN_DARK = true;
  var KEY = "grantha-theme";
  var store = null;
  try { store = LAUNCH_IN_DARK ? window.sessionStorage : window.localStorage; } catch (e) {}
  var saved = null;
  try { saved = store && store.getItem(KEY); } catch (e) {}
  var mode = saved || (LAUNCH_IN_DARK ? "dark" : "light");
  if (mode === "dark") document.documentElement.dataset.theme = "dark";
  window.granthaTheme = {
    mode: mode,
    save: function (m) { try { store && store.setItem(KEY, m); } catch (e) {} },
  };
})();
