(() => {
  const status = document.querySelector('[data-payment-status-url]');
  if (!status) return;
  let attempts = 0;
  const timer = setInterval(async () => {
    if (++attempts > 20) { clearInterval(timer); return; }
    try {
      const response = await fetch(status.dataset.paymentStatusUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      if (!response.ok) { clearInterval(timer); return; }
      const result = await response.json();
      if (result.status !== status.dataset.paymentInitial) { clearInterval(timer); location.reload(); }
    } catch { clearInterval(timer); }
  }, 3000);
})();
