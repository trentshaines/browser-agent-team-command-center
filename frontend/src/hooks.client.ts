import * as Sentry from '@sentry/sveltekit';

const dsn = import.meta.env.VITE_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
  });
}

export const handleError = dsn
  ? Sentry.handleErrorWithSentry()
  : ({ error }: { error: unknown }) => console.error(error);
