/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        surface: 'var(--surface)',
        border: 'var(--border)',
        text: 'var(--text)',
        muted: {
          DEFAULT: 'var(--muted)',
          surface: 'var(--muted-surface)',
        },
        navy: 'var(--navy)',
        orange: 'var(--orange)',
        ring: 'var(--ring)',
        accent: {
          DEFAULT: 'var(--accent)',
          tint: 'var(--accent-tint)',
          hover: 'var(--accent-hover)',
        },
        lifecycle: {
          blue: 'var(--lifecycle-blue)',
        },
        status: {
          compliant: {
            text: 'var(--status-compliant-text)',
            bg: 'var(--status-compliant-bg)',
          },
          partial: {
            text: 'var(--status-partial-text)',
            bg: 'var(--status-partial-bg)',
          },
          noncompliant: {
            text: 'var(--status-noncompliant-text)',
            bg: 'var(--status-noncompliant-bg)',
          },
          notevidenced: {
            text: 'var(--status-notevidenced-text)',
            bg: 'var(--status-notevidenced-bg)',
          },
          review: {
            DEFAULT: 'var(--status-review)',
          },
        },
        severity: {
          high: 'var(--severity-high)',
          medium: 'var(--severity-medium)',
          low: 'var(--severity-low)',
        },
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        'page-title': ['24px', { lineHeight: '32px', fontWeight: '600' }],
        'section-title': ['18px', { lineHeight: '24px', fontWeight: '600' }],
        'card-title': ['16px', { lineHeight: '22px', fontWeight: '600' }],
        'body': ['14px', { lineHeight: '20px', fontWeight: '400' }],
        'meta': ['12px', { lineHeight: '16px', fontWeight: '500' }],
        'table-header': ['12px', { lineHeight: '16px', fontWeight: '500' }],
      },
      boxShadow: {
        drawer: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
        dropdown: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
      },
    },
  },
  plugins: [],
};
