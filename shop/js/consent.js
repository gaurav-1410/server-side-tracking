// ============================================================================
// consent.js – cookie banner (CookieConsent v3, open source) + Google Consent Mode v2.
//
// Load order in <head> (important!):
//   1. consent-default inline script  -> everything DENIED before any tag runs
//   2. GTM snippet                    -> tags load, but respect the denied state
//   3. this file (deferred)           -> shows banner, sends consent UPDATE on choice
//
// Category -> Consent Mode mapping (documented in docs/tracking-plan, tab 3):
//   necessary  -> security_storage, functionality_storage (always granted)
//   analytics  -> analytics_storage                        (GA4)
//   marketing  -> ad_storage, ad_user_data, ad_personalization (Meta, TikTok, Google Ads)
// ============================================================================

window.dataLayer = window.dataLayer || [];
function gtag() { dataLayer.push(arguments); }

function sendConsentUpdate() {
  const analytics = CookieConsent.acceptedCategory('analytics');
  const marketing = CookieConsent.acceptedCategory('marketing');
  const state = {
    analytics_storage: analytics ? 'granted' : 'denied',
    ad_storage: marketing ? 'granted' : 'denied',
    ad_user_data: marketing ? 'granted' : 'denied',
    ad_personalization: marketing ? 'granted' : 'denied'
  };
  gtag('consent', 'update', state);
  // A normal dataLayer event too, so GTM triggers (e.g. Meta Pixel) can fire right after consent.
  dataLayer.push({ event: 'consent_update', consent_analytics: state.analytics_storage, consent_marketing: state.ad_storage });
}

CookieConsent.run({
  // Re-ask when the categories change; store the choice for 6 months.
  revision: 1,
  cookie: { name: 'cc_cookie', expiresAfterDays: 182 },
  // Default (true) hides the banner from automated browsers, which would break
  // the Playwright QA tests on Day 2. Without a choice, everything stays denied anyway.
  hideFromBots: false,

  guiOptions: {
    consentModal: { layout: 'box', position: 'bottom right', equalWeightButtons: true },
    preferencesModal: { layout: 'box', equalWeightButtons: true }
  },

  // Restored choice on later page loads, and first choice / changes:
  onConsent: sendConsentUpdate,
  onChange: sendConsentUpdate,

  categories: {
    necessary: { enabled: true, readOnly: true },
    analytics: {},
    marketing: {}
  },

  language: {
    default: 'en',
    translations: {
      en: {
        consentModal: {
          title: 'We use cookies',
          description: 'Coffee House uses cookies to measure how the shop is used (analytics) and to measure our ads on Meta and TikTok (marketing). You decide what you allow. This is a demo shop for a tracking project.',
          acceptAllBtn: 'Accept all',
          acceptNecessaryBtn: 'Reject all',
          showPreferencesBtn: 'Settings'
        },
        preferencesModal: {
          title: 'Cookie settings',
          acceptAllBtn: 'Accept all',
          acceptNecessaryBtn: 'Reject all',
          savePreferencesBtn: 'Save settings',
          sections: [
            { title: 'Necessary', description: 'Needed for the shop to work (cart, this consent choice).', linkedCategory: 'necessary' },
            { title: 'Analytics', description: 'Google Analytics 4: how visitors use the shop. Data is processed via our own server first.', linkedCategory: 'analytics' },
            { title: 'Marketing', description: 'Meta and TikTok: measuring which ads lead to purchases.', linkedCategory: 'marketing' }
          ]
        }
      }
    }
  }
});
