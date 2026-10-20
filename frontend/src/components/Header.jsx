import './Header.css';

export default function Header({ profile, tabs, activeTab, onTabChange }) {
  return (
    <header className="app-header">
      <div className="app-header__top">
        <div className="app-header__brand">
          <span className="app-header__mark" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M3 17l5-6 4 4 7-9"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="app-header__name">Algo</span>
        </div>
        {profile && (
          <div className="app-header__user">
            Signed in as <strong>{profile.user_name}</strong>{' '}
            <span className="app-header__user-id">({profile.user_id})</span>
          </div>
        )}
      </div>
      {tabs && tabs.length > 0 && (
        <nav className="app-header__tabs" aria-label="Sections">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={
                'app-header__tab' + (activeTab === tab.id ? ' app-header__tab--active' : '')
              }
              aria-current={activeTab === tab.id ? 'page' : undefined}
              onClick={() => onTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      )}
    </header>
  );
}
