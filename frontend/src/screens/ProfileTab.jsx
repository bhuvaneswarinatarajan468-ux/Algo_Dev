import './screens.css';
import './ProfileTab.css';

export default function ProfileTab({ profile }) {
  return (
    <div className="profile-tab">
      <section className="profile-card">
        <h2 className="profile-card__title">Profile</h2>
        <dl className="profile-card__grid">
          <div>
            <dt>Name</dt>
            <dd>{profile.user_name}</dd>
          </div>
          <div>
            <dt>User ID</dt>
            <dd className="num">{profile.user_id}</dd>
          </div>
        </dl>
      </section>

      <section className="profile-card">
        <h3 className="profile-card__subtitle">Products</h3>
        <div className="chip-row">
          {profile.products.map((p) => (
            <span className="chip" key={p}>
              {p}
            </span>
          ))}
        </div>
      </section>

      <section className="profile-card">
        <h3 className="profile-card__subtitle">Exchanges</h3>
        <div className="chip-row">
          {profile.exchanges.map((e) => (
            <span className="chip" key={e}>
              {e}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
