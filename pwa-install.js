'use strict';
(() => {
  const VISITS_KEY = 'plato-visit-count';
  const SESSION_KEY = 'plato-visit-counted';
  const IOS_DISMISSED_KEY = 'plato-ios-install-dismissed';

  if ('serviceWorker' in navigator) {
    addEventListener('load', () => navigator.serviceWorker.register('./service-worker.js'));
  }

  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (standalone) return;

  let visits = Number.parseInt(localStorage.getItem(VISITS_KEY) || '0', 10);
  if (!sessionStorage.getItem(SESSION_KEY)) {
    visits = Number.isFinite(visits) ? visits + 1 : 1;
    localStorage.setItem(VISITS_KEY, String(visits));
    sessionStorage.setItem(SESSION_KEY, 'true');
  }
  if (visits < 2) return;

  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  let installEvent;

  function showPrompt(kind) {
    if (document.querySelector('.install-prompt')) return;
    const prompt = document.createElement('aside');
    prompt.className = 'install-prompt';
    prompt.setAttribute('aria-label', 'Install Plato');
    prompt.innerHTML = kind === 'ios'
      ? '<p><strong>Add Plato to your Home Screen</strong><span>Tap Share, then “Add to Home Screen”.</span></p><button type="button" aria-label="Dismiss install hint">×</button>'
      : '<p><strong>Keep Plato handy</strong><span>Add it to your Home Screen.</span></p><button type="button" class="install-action">Add to Home Screen</button><button type="button" aria-label="Dismiss install prompt">×</button>';
    document.body.append(prompt);

    const buttons = prompt.querySelectorAll('button');
    const dismiss = buttons[buttons.length - 1];
    dismiss.addEventListener('click', () => {
      if (kind === 'ios') localStorage.setItem(IOS_DISMISSED_KEY, 'true');
      prompt.remove();
    });
    prompt.querySelector('.install-action')?.addEventListener('click', async () => {
      if (!installEvent) return;
      installEvent.prompt();
      await installEvent.userChoice;
      installEvent = undefined;
      prompt.remove();
    });
  }

  if (isIOS) {
    if (!localStorage.getItem(IOS_DISMISSED_KEY)) showPrompt('ios');
  } else {
    addEventListener('beforeinstallprompt', event => {
      event.preventDefault();
      installEvent = event;
      showPrompt('native');
    });
  }

  addEventListener('appinstalled', () => document.querySelector('.install-prompt')?.remove());
})();
