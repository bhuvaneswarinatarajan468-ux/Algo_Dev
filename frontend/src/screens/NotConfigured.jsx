import './screens.css';

export default function NotConfigured() {
  return (
    <main className="screen-center">
      <div className="panel panel--narrow">
        <h1 className="panel__title">Algo isn't configured yet</h1>
        <p className="panel__text">
          No Kite Connect API credentials were found. Copy{' '}
          <code>.env.example</code> to <code>.env</code> in the project
          folder, fill in your <code>KITE_API_KEY</code> and{' '}
          <code>KITE_API_SECRET</code>, then restart the server:
        </p>
        <pre className="code-block">
          <code>copy .env.example .env{'\n'}python app.py</code>
        </pre>
        <p className="panel__hint">
          Your API key and secret stay on the server - they are never sent
          to or requested by this page.
        </p>
      </div>
    </main>
  );
}
