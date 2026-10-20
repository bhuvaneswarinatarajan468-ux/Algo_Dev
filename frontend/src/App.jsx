import { useEffect, useState, useCallback } from 'react';
import './App.css';
import Header from './components/Header';
import NotConfigured from './screens/NotConfigured';
import LoggedOut from './screens/LoggedOut';
import ProfileTab from './screens/ProfileTab';
import SignalsTab from './screens/SignalsTab';
import BacktestTab from './screens/BacktestTab';
import StrategyBuilderTab from './screens/StrategyBuilderTab';
import { getStatus, getProfile, SessionExpiredError } from './api';

const TABS = [
  { id: 'signals', label: 'Signals' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'strategy-builder', label: 'Strategy Builder' },
  { id: 'profile', label: 'Profile' },
];

const TAB_AUTH_KEY = 'algo.tabAuthenticated';

function markTabAuthenticated() {
  try {
    sessionStorage.setItem(TAB_AUTH_KEY, '1');
  } catch {
    // ignore (e.g. private browsing with storage disabled)
  }
}

function isTabAuthenticated() {
  try {
    return sessionStorage.getItem(TAB_AUTH_KEY) === '1';
  } catch {
    return false;
  }
}

function useQueryFlag(name) {
  const [present] = useState(() => new URLSearchParams(window.location.search).has(name));
  useEffect(() => {
    if (present) {
      const url = new URL(window.location.href);
      url.searchParams.delete(name);
      window.history.replaceState({}, '', url);
    }
  }, [present]);
  return present;
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [profile, setProfile] = useState(null);
  const [activeTab, setActiveTab] = useState('signals');
  const hadLoginError = useQueryFlag('login_error');
  const hadLoginSuccess = useQueryFlag('login_success');

  useEffect(() => {
    if (hadLoginSuccess) markTabAuthenticated();
  }, [hadLoginSuccess]);

  const refreshStatus = useCallback(async () => {
    try {
      const data = await getStatus();
      setStatus(data);
      setLoadError(null);
      return data;
    } catch (err) {
      setLoadError(err.message || 'Could not reach the Algo server');
      return null;
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (!status?.logged_in || !isTabAuthenticated()) {
      setProfile(null);
      return;
    }
    getProfile()
      .then(setProfile)
      .catch((err) => {
        if (err instanceof SessionExpiredError) {
          setStatus((s) => (s ? { ...s, logged_in: false } : s));
        }
      });
  }, [status?.logged_in]);

  const handleLoggedIn = useCallback(() => {
    markTabAuthenticated();
    refreshStatus();
  }, [refreshStatus]);

  if (loadError) {
    return (
      <main className="screen-center">
        <div className="panel panel--narrow">
          <h1 className="panel__title">Can't reach Algo</h1>
          <p className="panel__text">{loadError}</p>
        </div>
      </main>
    );
  }

  if (!status) {
    return (
      <main className="screen-center">
        <p className="helper-text">Loading…</p>
      </main>
    );
  }

  if (!status.configured) {
    return <NotConfigured />;
  }

  if (!status.logged_in || !isTabAuthenticated()) {
    return (
      <>
        {hadLoginError && (
          <div className="banner banner--error" role="alert">
            Login didn't complete. Please try again.
          </div>
        )}
        <LoggedOut loginUrl={status.login_url} onLoggedIn={handleLoggedIn} />
      </>
    );
  }

  const handleSessionExpired = () => setStatus((s) => (s ? { ...s, logged_in: false } : s));

  return (
    <>
      <Header
        profile={profile}
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      <main className="app-main">
        {activeTab === 'signals' && <SignalsTab onSessionExpired={handleSessionExpired} />}
        {activeTab === 'backtest' && <BacktestTab onSessionExpired={handleSessionExpired} />}
        {activeTab === 'strategy-builder' && <StrategyBuilderTab />}
        {activeTab === 'profile' &&
          (profile ? <ProfileTab profile={profile} /> : <p className="helper-text">Loading profile…</p>)}
      </main>
    </>
  );
}
