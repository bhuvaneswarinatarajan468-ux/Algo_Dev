import { useState } from 'react';
import './screens.css';
import { loginWithToken } from '../api';

export default function LoggedOut({ loginUrl, onLoggedIn }) {
  const [requestToken, setRequestToken] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleFallbackSubmit(event) {
    event.preventDefault();
    if (!requestToken.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await loginWithToken(requestToken.trim());
      onLoggedIn();
    } catch (err) {
      setError(err.message || 'Could not complete login');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="screen-center">
      <div className="panel panel--narrow">
        <h1 className="panel__title">Sign in to Algo</h1>
        <p className="panel__text">
          Algo reads your Zerodha account to scan for signals. It never
          places, modifies, or cancels orders.
        </p>
        <a
          className="btn btn-primary btn-block"
          href={loginUrl || '#'}
          aria-disabled={!loginUrl}
        >
          Log in with Zerodha
        </a>

        <details className="disclosure">
          <summary>Redirect didn't bring you back here?</summary>
          <div className="disclosure-content">
            <p className="helper-text">
              After logging in on Kite, copy the <code>request_token</code>{' '}
              value from the redirected URL and paste it below.
            </p>
            <form onSubmit={handleFallbackSubmit}>
              <div className="form-field">
                <label htmlFor="request-token">Request token</label>
                <input
                  id="request-token"
                  type="text"
                  value={requestToken}
                  onChange={(e) => setRequestToken(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>
              <button
                type="submit"
                className="btn btn-secondary btn-block"
                disabled={submitting || !requestToken.trim()}
              >
                {submitting ? 'Signing in…' : 'Submit token'}
              </button>
              {error && (
                <p className="error-text" role="alert">
                  {error}
                </p>
              )}
            </form>
          </div>
        </details>
      </div>
    </main>
  );
}
