const SUPABASE_URL = 'https://udeekuvifncmqvoywhlg.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVkZWVrdXZpZm5jbXF2b3l3aGxnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ3OTQ3NjUsImV4cCI6MjEwMDM3MDc2NX0.Jhg4l0uf1ccwT-2Om3Ae3HOjy9SaCvX6EHnZ1FGhRGA';

const checkoutPanel = document.querySelector('#cutctx-checkout');
const checkoutForm = document.querySelector('#cutctx-checkout-form');
const checkoutEmail = document.querySelector('#checkout-email');
const checkoutSubmit = document.querySelector('#checkout-submit');
const checkoutStatus = document.querySelector('#checkout-status');
const checkoutSummary = document.querySelector('#checkout-plan-summary');
const planButtons = [...document.querySelectorAll('[data-plan-select]')];
let selectedPlan = null;
let plans = new Map();

function setStatus(message, state = '') {
  checkoutStatus.textContent = message;
  checkoutStatus.dataset.state = state;
}

function licensePortalUrl() {
  return new URL('/licenses', window.location.origin).toString();
}

async function request(path, body) {
  const response = await fetch(`${SUPABASE_URL}/functions/v1/${path}`, {
    method: 'POST',
    headers: { apikey: SUPABASE_ANON_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || 'The payment service is unavailable. Please try again.');
  return data;
}

function formatPrice(plan) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: plan.currency, minimumFractionDigits: 0 }).format(plan.amount / 100);
}

function loadRazorpay() {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const existing = document.querySelector('script[src="https://checkout.razorpay.com/v1/checkout.js"]');
    if (existing) {
      existing.addEventListener('load', resolve, { once: true });
      existing.addEventListener('error', () => reject(new Error('Secure checkout could not be loaded.')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = resolve;
    script.onerror = () => reject(new Error('Secure checkout could not be loaded.'));
    document.head.append(script);
  });
}

function openRazorpay(order, plan, email) {
  return new Promise((resolve, reject) => {
    const checkout = new window.Razorpay({
      key: order.keyId,
      amount: order.amount,
      currency: order.currency,
      name: 'CutCtx',
      description: `${plan.name} — ${plan.interval}`,
      order_id: order.orderId,
      prefill: { email },
      theme: { color: '#36d79b' },
      handler: resolve,
      modal: { ondismiss: () => reject(Object.assign(new Error('Checkout dismissed.'), { code: 'checkout_dismissed' })) },
    });
    checkout.on('payment.failed', (response) => reject(new Error(response.error?.description || 'Payment failed.')));
    checkout.open();
  });
}

function selectPlan(planId) {
  const plan = plans.get(planId);
  if (!plan) return;
  selectedPlan = plan;
  checkoutPanel.hidden = false;
  checkoutSummary.textContent = `${plan.name} — ${formatPrice(plan)} / ${plan.interval}`;
  setStatus('');
  checkoutPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
  checkoutEmail.focus();
}

async function loadPlans() {
  try {
    const data = await request('list-plans', { product: 'cutctx', billing: 'monthly' });
    plans = new Map(data.plans.map((plan) => [plan.planId, plan]));
    for (const plan of data.plans) {
      const price = document.querySelector(`[data-plan-price="${plan.planId}"]`);
      const description = document.querySelector(`[data-plan-description="${plan.planId}"]`);
      if (price) price.innerHTML = `${formatPrice(plan)} <small>/ ${plan.interval}</small>`;
      if (description) description.textContent = plan.description;
    }
    for (const button of planButtons) button.disabled = !plans.has(button.dataset.planSelect);
  } catch (error) {
    for (const price of document.querySelectorAll('[data-plan-price]')) price.textContent = 'Unavailable';
    setStatus(error instanceof Error ? error.message : 'Plans could not be loaded.', 'error');
  }
}

planButtons.forEach((button) => button.addEventListener('click', () => selectPlan(button.dataset.planSelect)));

checkoutForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!selectedPlan) return;
  const userEmail = checkoutEmail.value.trim();
  if (!userEmail) return;
  checkoutSubmit.disabled = true;
  try {
    setStatus('Creating secure payment…');
    const order = await request('create-order', { product: 'cutctx', planId: selectedPlan.planId, billing: selectedPlan.interval, userEmail });
    await loadRazorpay();
    const payment = await openRazorpay(order, selectedPlan, userEmail);
    setStatus('Verifying payment…');
    await request('verify-payment', {
      razorpay_payment_id: payment.razorpay_payment_id,
      razorpay_order_id: payment.razorpay_order_id,
      razorpay_signature: payment.razorpay_signature,
      planId: selectedPlan.planId,
      billing: selectedPlan.interval,
      userEmail,
    });
    window.location.assign(licensePortalUrl());
  } catch (error) {
    if (error?.code !== 'checkout_dismissed') setStatus(error instanceof Error ? error.message : 'Payment could not be completed.', 'error');
  } finally {
    checkoutSubmit.disabled = false;
  }
});

loadPlans();
