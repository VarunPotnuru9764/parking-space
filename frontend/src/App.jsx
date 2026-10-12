import { useCallback, useEffect, useMemo, useState } from "react";
import ParkingLayoutApp from "./ParkingLayoutApp.jsx";
import VideoDetectionPage from "./VideoDetectionPage.jsx";
import SimulatorDetectionPage from "./SimulatorDetectionPage.jsx";
import { apiRequest, authStore } from "./api.js";
import {
  AccountSecuritySettings,
  ActiveParkingPage,
  AdminActivityPage,
  AdminReportsPage,
  AdminUsersPage,
  FareRulesPage,
  LoginActivityPage,
  MfaVerificationForm,
  PasswordResetPage,
  PasswordResetRequestForm,
  SessionHistoryPage,
  UserReportsPage,
} from "./PortalDataPages.jsx";

const USER_NAV = [
  ["Dashboard", "dashboard", "grid"],
  ["Parking Availability", "availability", "map"],
  ["Claim Parking", "claim", "key"],
  ["My Parking", "my-parking", "car"],
  ["Parking History", "history", "clock"],
  ["My Reports", "reports", "chart"],
  ["Profile & Settings", "settings", "user"],
];
const ADMIN_NAV = [
  ["Dashboard", "dashboard", "grid"],
  ["Parking Lots", "lots", "building"],
  ["Parking Spaces", "spaces", "parking"],
  ["Layout Configuration", "layout", "edit"],
  ["Video Detection", "video-detection", "video"],
  ["Simulator Detection", "simulator-detection", "video"],
  ["Fare Rules", "fares", "tag"],
  ["User Management", "users", "users"],
  ["Reports", "reports", "chart"],
  ["Activity Logs", "activity", "list"],
  ["Login Activity", "login-activity", "shield"],
  ["Settings", "settings", "settings"],
];

function go(path) {
  window.location.hash = `/${path}`.replace(/^\/+/, "/");
}

function moneyValue(value) {
  return value == null ? "—" : `₹${Number(value).toFixed(2)}`;
}

function Icon({ name, size = 18 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
    map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z" /><path d="M9 3v15M15 6v15" /></>,
    key: <><circle cx="8" cy="15" r="5" /><path d="m11.5 11.5 7-7 2 2-2 2 2 2-3 3-2-2-2 2" /></>,
    car: <><path d="m5 11 1.5-4.5h11L19 11l2 2v5h-2v-2H5v2H3v-5z" /><path d="M6.5 11h11M7 13.5h.01M17 13.5h.01" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    chart: <><path d="M4 19V5M4 19h17" /><path d="m7 15 4-4 3 2 5-6" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    building: <><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M9 21v-4h6v4M8 7h1m6 0h1M8 11h1m6 0h1" /></>,
    parking: <><path d="M6 21V3h7a5 5 0 0 1 0 10H6" /><path d="M7 7h6a1 1 0 0 1 0 2H7" /></>,
    edit: <><path d="m4 16-.8 4.8L8 20l11-11-4-4z" /><path d="m13.5 6.5 4 4" /></>,
    tag: <><path d="M20 13 11 22l-9-9V2h11z" /><circle cx="7" cy="7" r="1" /></>,
    users: <><circle cx="9" cy="8" r="3.5" /><path d="M2 21a7 7 0 0 1 14 0M16 5.5a3.5 3.5 0 0 1 0 6.8M18 15a6 6 0 0 1 4 6" /></>,
    list: <><path d="M9 6h12M9 12h12M9 18h12" /><path d="M4 6h.01M4 12h.01M4 18h.01" /></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11" /><path d="m9 12 2 2 4-4" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.5.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.5-.9l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.8l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.5-.9l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.5.9l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1 0 1.7z" /></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3" /><path d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    video: <><rect x="3" y="5" width="13" height="14" rx="2" /><path d="m16 10 5-3v10l-5-3z" /></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.grid}</svg>;
}

function Brand({ compact = false }) {
  return <a className={`brand ${compact ? "brand-compact" : ""}`} href="#/home" aria-label="ParkingSpace home">
    <span className="brand-icon"><Icon name="parking" size={19} /></span>
    <span><strong>Parking<span>Space</span></strong>{!compact && <small>SMART PARKING PLATFORM</small>}</span>
  </a>;
}

function getRoute() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return hash || "home";
}

function App() {
  const [route, setRoute] = useState(getRoute);
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(Boolean(authStore.getToken()));
  const [pendingChallenge, setPendingChallenge] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("parking_mfa_challenge") || "null"); }
    catch { return null; }
  });

  useEffect(() => {
    const updateRoute = () => {
      if (window.location.hash.startsWith("#/")) setRoute(getRoute());
    };
    const expireSession = () => {
      setUser(null);
      go("login");
    };
    window.addEventListener("hashchange", updateRoute);
    window.addEventListener("parking:unauthorized", expireSession);
    return () => {
      window.removeEventListener("hashchange", updateRoute);
      window.removeEventListener("parking:unauthorized", expireSession);
    };
  }, []);

  useEffect(() => {
    let active = true;
    if (!authStore.getToken()) {
      setAuthLoading(false);
      return undefined;
    }
    apiRequest("/auth/me").then((profile) => {
      if (active) setUser(profile);
    }).catch(() => {
      authStore.clear();
      if (active) setUser(null);
    }).finally(() => {
      if (active) setAuthLoading(false);
    });
    return () => { active = false; };
  }, []);

  const onAuthenticated = (profile) => {
    setUser(profile);
    go("app/dashboard");
  };
  const onMfaRequired = (challenge) => {
    sessionStorage.setItem("parking_mfa_challenge", JSON.stringify(challenge));
    setPendingChallenge(challenge);
    go("verify");
  };
  const onMfaVerified = async (token) => {
    authStore.setToken(token);
    sessionStorage.removeItem("parking_mfa_challenge");
    setPendingChallenge(null);
    try {
      const profile = await apiRequest("/auth/me");
      onAuthenticated(profile);
    } catch (error) {
      authStore.clear();
      setUser(null);
      go("login");
    }
  };
  const logout = () => {
    authStore.clear();
    setUser(null);
    go("home");
  };

  if (["login", "register", "forgot", "verify"].includes(route) || route.startsWith("reset-password")) {
    const resetToken = route.startsWith("reset-password") ? new URLSearchParams(window.location.hash.split("?")[1] || "").get("token") : "";
    return <AuthPage mode={route.startsWith("reset-password") ? "reset-password" : route} onAuthenticated={onAuthenticated} onMfaRequired={onMfaRequired} pendingChallenge={pendingChallenge} onMfaVerified={onMfaVerified} resetToken={resetToken} />;
  }
  if (route.startsWith("app/")) {
    if (authLoading) return <div className="full-loader"><span className="spinner" /> Checking your session…</div>;
    if (!user) {
      go("login");
      return <div className="full-loader"><span className="spinner" /> Redirecting to sign in…</div>;
    }
    return <Portal route={route.slice(4)} user={user} onLogout={logout} />;
  }
  return <HomePage user={user} />;
}

function HomePage({ user }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return <div className="public-site">
    <header className="public-nav">
      <div className="public-nav-inner">
        <Brand />
        <nav className={`public-links ${menuOpen ? "public-links-open" : ""}`} aria-label="Main navigation">
          <a className="active" href="#/home" onClick={() => setMenuOpen(false)}>Home</a>
          <a href="#about" onClick={() => setMenuOpen(false)}>About</a>
          <a href="#features" onClick={() => setMenuOpen(false)}>Features</a>
          <a href="#how-it-works" onClick={() => setMenuOpen(false)}>How It Works</a>
          <a href="#availability" onClick={() => setMenuOpen(false)}>Parking Availability</a>
        </nav>
        <button className="nav-menu-toggle" aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}><span /><span /><span /></button>
        <div className="nav-actions">
          {user ? <a className="button button-outline" href="#/app/dashboard">Dashboard <Icon name="arrow" size={15} /></a> : <>
            <a className="nav-login" href="#/login">Log in</a>
            <a className="button button-primary nav-register" href="#/register">Get started <Icon name="arrow" size={15} /></a>
          </>}
        </div>
      </div>
    </header>
    <main>
      <section className="hero-section">
        <div className="hero-grid">
          <div className="hero-copy">
            <div className="eyebrow"><span className="live-indicator" /> SMART PARKING, MADE SIMPLE</div>
            <h1>Smart Parking.<br /><em>Simplified.</em></h1>
            <p>Find an open space, see what’s happening in real time, and make every visit a little easier.</p>
            <div className="hero-actions">
              <a className="button button-primary button-large" href="#availability">Explore parking <Icon name="arrow" size={17} /></a>
              <a className="button button-text button-large" href="#/register">Get started <span className="round-arrow"><Icon name="arrow" size={15} /></span></a>
            </div>
            <div className="hero-trust"><span className="trust-avatars"><i>V</i><i>J</i><i>N</i></span><span>Smarter spaces. Smoother arrivals.</span></div>
          </div>
          <div className="hero-visual" aria-label="Illustration of an organized parking facility">
            <div className="visual-glow" />
            <div className="visual-topline"><span><i className="status-dot" /> PARKING OVERVIEW</span><span className="visual-time">VISUAL PREVIEW</span></div>
            <div className="parking-illustration">
              <div className="drive-lane"><span>ENTRY</span><span className="lane-arrow">↑</span><span>EXIT</span></div>
              <div className="parking-row">
                {["occupied", "free", "free", "occupied", "free", "free", "unknown", "free"].map((state, i) => <div key={i} className={`illustration-slot ${state}`}><span className={`illustration-car ${i % 3 === 0 ? "car-dark" : i % 2 ? "car-blue" : ""}`} /></div>)}
              </div>
              <div className="parking-row lower">
                {["free", "occupied", "free", "free", "unknown", "occupied", "free", "free"].map((state, i) => <div key={i} className={`illustration-slot ${state}`}><span className={`illustration-car ${i % 2 ? "car-silver" : ""}`} /></div>)}
              </div>
              <div className="lane-markings"><span /><span /><span /><span /><span /></div>
            </div>
            <div className="visual-bottom">
              <div className="visual-caption"><span className="caption-icon"><Icon name="map" size={17} /></span><span><strong>Parking, at a glance</strong><small>Find your next open spot</small></span></div>
              <span className="visual-status"><i /> Illustrative layout</span>
            </div>
            <div className="float-note"><span className="float-check"><Icon name="check" size={14} /></span><span><strong>Plan with confidence</strong><small>Know before you arrive</small></span></div>
          </div>
        </div>
        <div className="hero-bottom-rule"><span>SMARTER PARKING STARTS HERE</span><span>BUILT FOR BETTER ARRIVALS <b>↗</b></span></div>
      </section>

      <section className="about-section section-wrap" id="about">
        <div className="section-heading">
          <div><p className="section-kicker">A BETTER WAY TO PARK</p><h2>Less circling.<br /><span>More certainty.</span></h2></div>
          <p className="section-description">ParkingSpace brings live parking data and clear space visibility together—so drivers can make informed decisions and operators can manage with confidence.</p>
        </div>
        <div className="about-strip">
          <div className="about-mark"><Icon name="parking" size={24} /></div>
          <div><strong>Why ParkingSpace?</strong><p>A practical smart-parking platform that connects camera-based vehicle detection with up-to-date occupancy and parking information.</p></div>
          <a href="#how-it-works" className="text-link">See how it works <Icon name="arrow" size={16} /></a>
        </div>
      </section>

      <section className="features-section" id="features">
        <div className="section-wrap">
          <div className="section-title-row"><div><p className="section-kicker">THE PLATFORM</p><h2>Everything in its <span>right place.</span></h2></div><p>One connected view for drivers<br />and parking teams.</p></div>
          <div className="feature-grid">
            {[
              ["parking", "Vehicle detection", "Camera-driven vehicle detection helps keep space occupancy up to date."],
              ["map", "Occupancy monitoring", "Understand which spaces are vacant, occupied, or not currently available."],
              ["key", "Parking claims", "Claim eligible occupied spaces using the parking lot’s existing claim-code workflow."],
              ["tag", "Dynamic pricing", "See current rates calculated by the configured fare engine."],
              ["building", "Multiple parking lots", "Move between configured lots from a single parking experience."],
              ["chart", "Reports & history", "Review recorded activity where the system’s reporting APIs are available."],
            ].map(([icon, title, text], index) => <article key={title} className="feature-card"><span className={`feature-icon feature-tone-${index % 4}`}><Icon name={icon} size={20} /></span><h3>{title}</h3><p>{text}</p><span className="feature-number">0{index + 1}</span></article>)}
          </div>
        </div>
      </section>

      <section className="process-section section-wrap" id="how-it-works">
        <div className="section-title-row"><div><p className="section-kicker">FROM CAMERA TO CURB</p><h2>Four steps. <span>One smoother arrival.</span></h2></div></div>
        <div className="process-grid">
          {[
            ["01", "Detect", "Cameras and the detection pipeline identify vehicles in configured spaces."],
            ["02", "Update", "The system records occupancy changes and updates the lot view."],
            ["03", "Explore", "Drivers check availability and inspect mapped spaces before choosing."],
            ["04", "Manage", "Operators maintain layouts and manage their configured parking lots."],
          ].map(([number, title, text], index) => <article className="process-step" key={title}><div className="process-marker"><span>{number}</span>{index < 3 && <i />}</div><h3>{title}</h3><p>{text}</p></article>)}
        </div>
      </section>

      <section className="availability-section" id="availability"><PublicAvailability /></section>

      <section className="team-section section-wrap">
        <div className="team-panel">
          <div className="team-intro"><p className="section-kicker">THE PEOPLE BEHIND THE PROJECT</p><h2>Developed<br /><span>with purpose.</span></h2><p>A smart-parking project built with care at NITK.</p></div>
          <div className="team-details">
            <div className="team-block"><span className="team-label">DEVELOPED BY</span><div className="team-member"><span>VS</span><strong>Varun Sai Potnuru <small>(241IT080)</small></strong></div><div className="team-member"><span>JT</span><strong>Jatin Tolani <small>(241IT035)</small></strong></div><div className="team-member"><span>VS</span><strong>Vivaan Sharma <small>(241IT081)</small></strong></div></div>
            <div className="team-divider" />
            <div className="team-block guidance-block"><span className="team-label">UNDER THE GUIDANCE OF</span><strong>Prof. Jaidhar C D</strong><p>National Institute of Technology Karnataka (NITK)<br />Department of Information Technology</p><span className="nitk-seal">NITK <i>·</i> SURATHKAL</span></div>
          </div>
        </div>
      </section>
    </main>
    <footer className="site-footer">
      <div className="footer-main"><Brand /><p>A clearer view of every space.<br />A smoother way to get there.</p><div className="footer-nav"><a href="#about">About</a><a href="#features">Features</a><a href="#how-it-works">How it works</a><a href="#availability">Parking availability</a><a href="#/login">Log in</a></div></div>
      <div className="footer-bottom"><span>© {new Date().getFullYear()} ParkingSpace · National Institute of Technology Karnataka</span><span>Department of Information Technology</span></div>
    </footer>
  </div>;
}

function PublicAvailability() {
  const [lots, setLots] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [lotId, setLotId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const loadLots = useCallback(async () => {
    setLoading(true);
    try {
      const result = await apiRequest("/lots/");
      setLots(result);
      const selected = result.find((lot) => String(lot.lot_id) === lotId) || result[0];
      if (selected) {
        setLotId(String(selected.lot_id));
        setSpaces(await apiRequest(`/parking/?lot_id=${selected.lot_id}`));
      } else setSpaces([]);
      setError("");
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, [lotId]);
  useEffect(() => { loadLots(); }, []); // Initial public preview; selection changes are handled below.
  const changeLot = async (value) => {
    setLotId(value);
    const selected = lots.find((lot) => String(lot.lot_id) === value);
    if (!selected) return;
    setLoading(true);
    try {
      setSpaces(await apiRequest(`/parking/?lot_id=${selected.lot_id}`));
      setError("");
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };
  const vacant = spaces.filter((space) => space.status === "vacant").length;
  const occupied = spaces.filter((space) => space.status === "occupied").length;
  return <div className="section-wrap availability-wrap">
    <div className="section-title-row availability-heading"><div><p className="section-kicker">KNOW BEFORE YOU GO</p><h2>Find your <span>next open spot.</span></h2><p className="availability-subtext">Parking availability is sourced from the connected parking system.</p></div><a className="button button-outline" href="#/login">Open parking view <Icon name="arrow" size={15} /></a></div>
    <div className="availability-panel">
      <div className="availability-map-panel">
        <div className="availability-topline"><div><span className="section-kicker">LIVE AVAILABILITY</span><strong>{lots.find((lot) => String(lot.lot_id) === lotId)?.name || "Parking lots"}</strong></div>
          <label className="lot-select-wrap"><span className="sr-only">Select parking lot</span><select value={lotId} onChange={(event) => changeLot(event.target.value)} disabled={!lots.length}><option value="">Select a lot</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>)}</select></label>
        </div>
        {loading ? <div className="availability-empty"><span className="spinner" /> Loading connected spaces…</div> : error ? <div className="availability-empty"><strong>Availability could not be loaded</strong><span>{error}</span><button className="button button-outline" onClick={loadLots}>Try again</button></div> : spaces.length ? <div className="availability-slots">{spaces.slice(0, 48).map((space) => <span key={space.parking_id} title={`${space.slot_number} · ${space.status}`} className={`availability-slot ${space.status}`}><i />{space.slot_number}</span>)}</div> : <div className="availability-empty"><strong>No connected spaces to display</strong><span>Parking-space records will appear here when the backend has configured them.</span></div>}
        <div className="availability-legend"><span><i className="legend-vacant" />Vacant</span><span><i className="legend-occupied" />Occupied</span><span><i className="legend-unknown" />Unknown</span><small>Map preview is a live list view; mapped geometry is available in the parking portal.</small></div>
      </div>
      <div className="availability-summary">
        <span className="summary-label">SPACE STATUS</span><h3>Live lot overview</h3><p>Check a space before you set out.</p>
        <div className="status-summary"><div><span className="summary-dot vacant-dot" /><span>Vacant</span><strong>{loading ? "—" : vacant}</strong></div><div><span className="summary-dot occupied-dot" /><span>Occupied</span><strong>{loading ? "—" : occupied}</strong></div><div><span className="summary-dot unknown-dot" /><span>Total spaces</span><strong>{loading ? "—" : spaces.length}</strong></div></div>
        <a className="button button-primary full-width" href="#/register">Get started <Icon name="arrow" size={15} /></a>
      </div>
    </div>
  </div>;
}

function AuthPage({ mode, onAuthenticated, onMfaRequired, pendingChallenge, onMfaVerified, resetToken }) {
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const update = (key) => (event) => setForm((old) => ({ ...old, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError(""); setSuccess("");
    if (mode === "register" && form.password !== form.confirm) {
      setError("The passwords do not match.");
      return;
    }
    if (mode === "register" && form.password.length < 8) {
      setError("Use a password with at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        await apiRequest("/auth/register", { method: "POST", body: JSON.stringify({ name: form.name.trim(), email: form.email.trim(), password: form.password }) });
        setSuccess("Your account has been created. Sign in to continue.");
        setTimeout(() => go("login"), 900);
      } else {
        const response = await apiRequest("/auth/login", { method: "POST", body: JSON.stringify({ email: form.email.trim(), password: form.password }) });
        if (response.mfa_required) {
          onMfaRequired(response);
        } else {
          authStore.setToken(response.access_token);
          const profile = await apiRequest("/auth/me");
          onAuthenticated(profile);
        }
      }
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const isRegister = mode === "register";
  const isReset = mode === "reset-password";
  const isVerify = mode === "verify";

  return <main className="auth-page">
    <header className="auth-header"><Brand /><a className="back-home" href="#/home">Back to home <Icon name="arrow" size={15} /></a></header>
    <div className="auth-background">
      <div className="auth-visual"><div className="auth-kicker"><span className="live-indicator" /> SMARTER PARKING, ONE STEP AHEAD</div><h1>Your next space<br />is closer than<br /><em>you think.</em></h1><p>Clear parking information for a smoother journey from arrival to departure.</p><div className="auth-mini-illustration"><div className="mini-road"><span>ENTRY</span><b>↗</b></div><div className="mini-space-row">{["free", "occupied", "free", "free"].map((item, index) => <span key={index} className={`mini-space ${item}`}><i /></span>)}</div></div></div>
      <section className="auth-card">
        <div className="auth-card-brand"><span className="brand-icon"><Icon name="parking" size={18} /></span><strong>Parking<span>Space</span></strong></div>
        <p className="section-kicker">{isReset || mode === "forgot" || isVerify ? "ACCOUNT SECURITY" : isRegister ? "JOIN PARKINGSPACE" : "WELCOME BACK"}</p>
        <h2>{mode === "forgot" || isReset ? "Reset your password" : isVerify ? "Two-step verification" : isRegister ? "Create an account" : "Sign in to your account"}</h2>
        <p className="auth-card-sub">{isReset || mode === "forgot" || isVerify ? "Secure account access" : isRegister ? "Get started with smarter parking." : "Continue to your parking dashboard."}</p>
        {mode === "forgot" ? <div className="unsupported-notice"><span className="notice-icon"><Icon name="shield" size={19} /></span><strong>Request a password reset</strong><p>If an account matches, the backend will send a reset link. The response does not reveal whether an email is registered.</p><PasswordResetRequestForm /><a className="button button-outline full-width" href="#/login">Back to sign in</a></div> :
          isReset ? <div className="unsupported-notice"><span className="notice-icon"><Icon name="shield" size={19} /></span><PasswordResetPage token={resetToken} onComplete={() => window.setTimeout(() => go("login"), 1200)} /><a className="button button-outline full-width" href="#/login">Back to sign in</a></div> :
          isVerify ? <div className="unsupported-notice"><span className="notice-icon"><Icon name="shield" size={19} /></span>{pendingChallenge ? <MfaVerificationForm challenge={pendingChallenge} onVerified={onMfaVerified} /> : <><strong>Verification session unavailable</strong><p>Sign in again to request a new code.</p><a className="button button-outline full-width" href="#/login">Back to sign in</a></>}</div> :
          <form onSubmit={submit} className="auth-form">
            {isRegister && <label>Full name<input autoComplete="name" required value={form.name} onChange={update("name")} placeholder="Your full name" /></label>}
            <label>Email address<input autoComplete="email" type="email" required value={form.email} onChange={update("email")} placeholder="you@example.com" /></label>
            <label>Password<div className="password-input"><input autoComplete={isRegister ? "new-password" : "current-password"} type={showPassword ? "text" : "password"} required value={form.password} onChange={update("password")} placeholder="Enter your password" minLength={isRegister ? 8 : undefined} /><button type="button" onClick={() => setShowPassword((show) => !show)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button></div></label>
            {isRegister && <label>Confirm password<input autoComplete="new-password" type={showPassword ? "text" : "password"} required value={form.confirm} onChange={update("confirm")} placeholder="Re-enter your password" minLength={8} /></label>}
            {!isRegister && <div className="auth-remember"><a href="#/forgot">Forgot password?</a></div>}
            {error && <div className="form-alert error-alert" role="alert">{error}</div>}
            {success && <div className="form-alert success-alert" role="status">{success}</div>}
            <button className="button button-primary full-width auth-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"} <Icon name="arrow" size={15} /></button>
          </form>}
        {(mode === "login" || mode === "register") && <div className="auth-switch">{isRegister ? <>Already have an account? <a href="#/login">Sign in</a></> : <>New to ParkingSpace? <a href="#/register">Create an account</a></>}</div>}
        <div className="auth-security"><Icon name="shield" size={14} /> Secure access · Your account stays yours</div>
      </section>
    </div>
    <footer className="auth-footer">© {new Date().getFullYear()} ParkingSpace <span>·</span> National Institute of Technology Karnataka</footer>
  </main>;
}

function Portal({ route, user, onLogout }) {
  const [lots, setLots] = useState([]);
  const [lotId, setLotId] = useState("");
  const [lotsError, setLotsError] = useState("");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const admin = user.role === "admin";
  const navItems = admin ? ADMIN_NAV : USER_NAV;
  const page = route.split("/")[0] || "dashboard";
  const pageTitle = (navItems.find((item) => item[1] === page)?.[0]) || "Dashboard";

  useEffect(() => {
    apiRequest("/lots/").then((data) => {
      setLots(data);
      setLotId((current) => current || (data[0] ? String(data[0].lot_id) : ""));
      setLotsError("");
    }).catch((err) => setLotsError(err.message));
  }, []);
  useEffect(() => setMobileNavOpen(false), [route]);

  const selectedLot = lots.find((lot) => String(lot.lot_id) === lotId) || null;
  const titlePage = admin ? {
    dashboard: "System overview", lots: "Parking lots", spaces: "Parking spaces", layout: "Layout configuration", "video-detection": "Video detection", "simulator-detection": "Simulator detection",
    fares: "Fare rules", users: "User management", reports: "Reports", activity: "Activity logs",
    "login-activity": "Login activity", settings: "Settings",
  } : {
    dashboard: "Your parking, at a glance", availability: "Parking availability", claim: "Claim parking", "my-parking": "My parking",
    history: "Parking history", reports: "My reports", settings: "Profile & settings", "login-activity": "Login activity",
  };

  return <div className="portal-shell">
    <aside className={`portal-sidebar ${mobileNavOpen ? "sidebar-open" : ""}`}>
      <div className="sidebar-brand"><Brand compact /><button className="mobile-close" onClick={() => setMobileNavOpen(false)} aria-label="Close navigation"><Icon name="close" /></button></div>
      <div className="workspace-label">{admin ? "ADMIN WORKSPACE" : "MY WORKSPACE"}</div>
      <nav className="portal-nav" aria-label={`${admin ? "Administrator" : "User"} navigation`}>
        {navItems.map(([label, slug, icon]) => <a key={label} className={page === slug ? "selected" : ""} href={`#/app/${slug}`}><Icon name={icon} size={18} /><span>{label}</span>{label === "Parking Availability" && <i className="nav-new-dot" />}</a>)}
      </nav>
      {admin && <div className="sidebar-note"><span className="sidebar-note-mark"><Icon name="shield" size={16} /></span><strong>Administrator access</strong><p>Management changes are protected by your account role.</p></div>}
      <div className="sidebar-bottom">
        <div className="sidebar-user"><span className="avatar">{(user.name || "U").slice(0, 1).toUpperCase()}</span><span><strong>{user.name}</strong><small>{user.email}</small></span><button aria-label="Log out" onClick={onLogout}><Icon name="logout" size={16} /></button></div>
        <button className="sidebar-logout" onClick={onLogout}><Icon name="logout" size={17} /> Log out</button>
      </div>
    </aside>
    <div className="portal-main">
      <header className="portal-topbar">
        <button className="mobile-menu" onClick={() => setMobileNavOpen(true)} aria-label="Open navigation"><span /><span /><span /></button>
        <div className="breadcrumb"><a href="#/app/dashboard">{admin ? "Admin" : "Workspace"}</a><span>/</span><strong>{titlePage[page] || pageTitle}</strong></div>
        <div className="topbar-end">{lots.length > 0 && <label className="topbar-lot"><Icon name="building" size={15} /><select value={lotId} onChange={(event) => setLotId(event.target.value)} aria-label="Selected parking lot">{lots.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>)}</select></label>}<span className="topbar-role">{admin ? "ADMIN" : "USER"}</span><span className="avatar topbar-avatar">{(user.name || "U").slice(0, 1).toUpperCase()}</span></div>
      </header>
      <main className="portal-content">
        {lotsError && <div className="portal-alert" role="alert">{lotsError}</div>}
        {page === "dashboard" && (admin ? <AdminDashboard lots={lots} lotId={lotId} onLotChange={setLotId} /> : <UserDashboard user={user} lots={lots} selectedLot={selectedLot} onLotChange={setLotId} />)}
        {(page === "availability" || page === "claim") && !admin && <AvailabilityPage lots={lots} selectedLot={selectedLot} onLotChange={setLotId} />}
        {page === "lots" && admin && <LotsPage lots={lots} onLotsUpdated={setLots} />}
        {page === "spaces" && admin && <SpacesPage selectedLot={selectedLot} />}
        {page === "layout" && admin && <div className="embedded-editor"><ParkingLayoutApp initialLotSlug={selectedLot?.slug} lots={lots} /></div>}
        {page === "video-detection" && admin && <VideoDetectionPage lots={lots} selectedLot={selectedLot} />}
        {page === "simulator-detection" && admin && <SimulatorDetectionPage />}
        {page === "my-parking" && !admin && <ActiveParkingPage />}
        {page === "history" && !admin && <SessionHistoryPage lots={lots} />}
        {page === "reports" && (admin ? <AdminReportsPage lots={lots} lotId={lotId} /> : <UserReportsPage lots={lots} lotId={lotId} />)}
        {page === "fares" && admin && <FareRulesPage lots={lots} lotId={lotId} />}
        {page === "users" && admin && <AdminUsersPage />}
        {page === "activity" && admin && <AdminActivityPage />}
        {page === "login-activity" && admin && <LoginActivityPage admin />}
        {page === "login-activity" && !admin && <LoginActivityPage admin={false} />}
        {page === "settings" && <AccountSecuritySettings user={user} onLogout={onLogout} />}
        {!titlePage[page] && <UnavailablePage title="Page unavailable" explanation="This page is not part of your current account workspace." />}
      </main>
      <footer className="portal-footer"><span>ParkingSpace</span><span>Live information provided by the connected parking system.</span></footer>
    </div>
    {mobileNavOpen && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
  </div>;
}

function useLotSpaces(lot) {
  const [state, setState] = useState({ spaces: [], loading: Boolean(lot), error: "" });
  const refresh = useCallback(async () => {
    if (!lot) {
      setState({ spaces: [], loading: false, error: "" });
      return;
    }
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const spaces = await apiRequest(`/parking/?lot_id=${lot.lot_id}`);
      setState({ spaces, loading: false, error: "" });
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error: error.message }));
    }
  }, [lot?.lot_id]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    if (!lot) return undefined;
    const timer = window.setInterval(refresh, 30000);
    return () => window.clearInterval(timer);
  }, [lot?.lot_id, refresh]);
  return { ...state, refresh };
}

function UserDashboard({ user, lots, selectedLot, onLotChange }) {
  const { spaces, loading, error, refresh } = useLotSpaces(selectedLot);
  const [activeSessions, setActiveSessions] = useState([]);
  const [recentHistory, setRecentHistory] = useState([]);
  const [sessionError, setSessionError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([apiRequest("/users/me/parking"), apiRequest("/users/me/history?limit=5")])
      .then(([parking, history]) => {
        if (!active) return;
        setActiveSessions(parking.active_sessions || []);
        setRecentHistory(history.items || []);
        setSessionError("");
      })
      .catch((err) => { if (active) setSessionError(err.message); });
    return () => { active = false; };
  }, [selectedLot?.lot_id]);
  const vacant = spaces.filter((space) => space.status === "vacant").length;
  const occupied = spaces.filter((space) => space.status === "occupied").length;
  const rates = spaces.map((space) => Number(space.current_rate) || 0).filter((value) => value > 0);
  const rate = rates.length ? Math.min(...rates) : null;
  const occupancy = spaces.length ? Math.round(occupied / spaces.length * 100) : 0;
  return <div className="page-stack">
    <PageHeading eyebrow="YOUR PARKING OVERVIEW" title={`Good to see you, ${user.name?.split(" ")[0] || "there"}.`} description="Here’s what’s happening across your selected parking lot." actions={<button className="button button-outline" onClick={refresh}><span className="refresh-mark">↻</span> Refresh</button>} />
    <LotPicker lots={lots} value={selectedLot?.lot_id || ""} onChange={onLotChange} />
    {error && <div className="portal-alert">{error}</div>}
    <div className="metric-grid">
      <Metric label="Total spaces" value={loading ? "—" : spaces.length} hint={selectedLot?.name || "Select a parking lot"} icon="parking" color="blue" />
      <Metric label="Vacant spaces" value={loading ? "—" : vacant} hint="Available right now" icon="check" color="green" />
      <Metric label="Occupied spaces" value={loading ? "—" : occupied} hint="Currently occupied" icon="car" color="red" />
      <Metric label="Occupancy" value={loading ? "—" : `${occupancy}%`} hint="Current lot utilization" icon="chart" color="violet" />
    </div>
    <div className="content-grid dashboard-grid">
      <section className="panel overview-panel"><PanelTitle title="Parking availability" description={selectedLot?.name || "Select a lot to view occupancy"} action={<a href="#/app/availability" className="text-link">Open map <Icon name="arrow" size={14} /></a>} />
        <div className="dashboard-map-preview">{spaces.length ? <div className="dashboard-space-grid">{spaces.slice(0, 36).map((space) => <span key={space.parking_id} title={`${space.slot_number}: ${space.status}`} className={`map-mini-space ${space.status}`}>{space.slot_number}</span>)}</div> : <EmptyInline loading={loading} error={error} message="No parking-space records are available for this lot." />}</div>
        <MapLegend />
      </section>
      <div className="right-stack">
        <section className="panel current-rate-panel"><PanelTitle title="Current rate" description="Based on current lot data" /><div className="rate-display">{loading ? "—" : rate === null ? "Not available" : <><strong>₹{rate.toFixed(2)}</strong><span>/ hour</span></>}</div><p>Rates are supplied by the existing fare engine.</p></section>
        <section className="panel session-panel"><span className="panel-overline">YOUR ACTIVE SESSION</span>{activeSessions.length ? <><span className="session-empty-icon"><Icon name="car" size={21} /></span><h3>{activeSessions[0].space_id} · {activeSessions[0].parking_lot}</h3><p>{Number(activeSessions[0].duration_hours || 0).toFixed(2)} hours · Recorded fare {moneyValue(activeSessions[0].recorded_fare)}</p><a href="#/app/my-parking" className="text-link">View session <Icon name="arrow" size={14} /></a></> : <><span className="session-empty-icon"><Icon name="car" size={21} /></span><h3>{sessionError ? "Session unavailable" : "No active session"}</h3><p>{sessionError || "Claim an eligible occupied space to see your session here."}</p><a href="#/app/my-parking" className="text-link">View parking <Icon name="arrow" size={14} /></a></>}</section>
      </div>
    </div>
    <div className="panel activity-panel"><PanelTitle title="Recent activity" description="Parking activity associated with your account" action={<a href="#/app/history" className="text-link">View history <Icon name="arrow" size={14} /></a>} />{sessionError && <div className="portal-alert">{sessionError}</div>}{recentHistory.length ? <div className="table-wrap"><table><thead><tr><th>SPACE</th><th>PARKING LOT</th><th>ARRIVAL RECORDED</th><th>STATUS</th><th>RECORDED FARE</th></tr></thead><tbody>{recentHistory.map((item) => <tr key={item.history_id}><td><strong>{item.space_id}</strong></td><td>{item.parking_lot}</td><td>{item.recorded_start ? new Date(item.recorded_start).toLocaleString() : "—"}</td><td><StatusPill status={item.status === "active" ? "occupied" : "vacant"} /></td><td>₹{Number(item.recorded_fare || 0).toFixed(2)}</td></tr>)}</tbody></table></div> : !sessionError && <div className="empty-state compact-empty"><span className="empty-icon"><Icon name="clock" size={20} /></span><strong>No parking activity recorded</strong><span>Your claimed parking sessions will appear here.</span></div>}</div>
  </div>;
}

function AdminDashboard({ lots, lotId, onLotChange }) {
  const [allSpaces, setAllSpaces] = useState([]);
  const [report, setReport] = useState(null);
  const [recentEvents, setRecentEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(true);
  const [error, setError] = useState("");
  const [reportError, setReportError] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all(lots.map((lot) => apiRequest(`/parking/?lot_id=${lot.lot_id}`).then((spaces) => spaces.map((space) => ({ ...space, lot_name: lot.name })))))
      .then((result) => { if (active) { setAllSpaces(result.flat()); setError(""); } })
      .catch((err) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [lots]);
  useEffect(() => {
    let active = true;
    const query = lotId ? `?lot_id=${encodeURIComponent(lotId)}` : "";
    setReportLoading(true);
    Promise.all([
      apiRequest(`/admin/reports${query}`),
      apiRequest("/admin/activity?limit=5"),
    ]).then(([summary, events]) => {
      if (!active) return;
      setReport(summary);
      setRecentEvents(events.items || []);
      setReportError("");
    }).catch((err) => { if (active) setReportError(err.message); })
      .finally(() => { if (active) setReportLoading(false); });
    return () => { active = false; };
  }, [lotId]);
  const filtered = lotId ? allSpaces.filter((space) => String(space.lot_id) === String(lotId)) : allSpaces;
  const vacant = filtered.filter((space) => space.status === "vacant").length;
  const occupied = filtered.filter((space) => space.status === "occupied").length;
  const occupancy = filtered.length ? Math.round(occupied / filtered.length * 100) : 0;
  const avgRate = filtered.length ? filtered.reduce((sum, space) => sum + Number(space.current_rate || 0), 0) / filtered.length : 0;
  return <div className="page-stack">
    <PageHeading eyebrow="ADMINISTRATOR WORKSPACE" title="System overview" description="A real-time snapshot from configured parking lots and spaces." actions={<select className="select-control dashboard-lot-select" value={lotId} onChange={(event) => onLotChange(event.target.value)}><option value="">All parking lots</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>)}</select>} />
    {error && <div className="portal-alert">{error}</div>}
    <div className="metric-grid">
      <Metric label="Parking lots" value={lots.length} hint="Configured in the system" icon="building" color="blue" />
      <Metric label="Total spaces" value={loading ? "—" : filtered.length} hint={lotId ? "Selected parking lot" : "Across all lots"} icon="parking" color="violet" />
      <Metric label="Vacant spaces" value={loading ? "—" : vacant} hint="Ready for arrivals" icon="check" color="green" />
      <Metric label="Occupied spaces" value={loading ? "—" : occupied} hint={`${loading ? "—" : occupancy}% occupancy`} icon="car" color="red" />
      <Metric label="Recorded charges" value={reportLoading ? "—" : `₹${Number(report?.total_recorded_charges || 0).toFixed(2)}`} hint="Recorded fares, not payments" icon="chart" color="violet" />
    </div>
    {reportError && <div className="portal-alert" role="alert">{reportError}</div>}
    <div className="content-grid admin-dashboard-grid">
      <section className="panel"><PanelTitle title="Occupancy overview" description={lotId ? lots.find((lot) => String(lot.lot_id) === String(lotId))?.name : "System-wide space status"} />
        <div className="occupancy-chart">
          <div className="chart-labels"><span>Space status</span><strong>{loading ? "—" : `${occupancy}%`} occupied</strong></div>
          <div className="occupancy-bar"><i style={{ width: `${occupancy}%` }} /></div>
          <div className="chart-key"><span><i className="legend-vacant" />Vacant <strong>{loading ? "—" : vacant}</strong></span><span><i className="legend-occupied" />Occupied <strong>{loading ? "—" : occupied}</strong></span></div>
          {report?.activity_over_time?.length ? <div className="chart-placeholder data-chart admin-dashboard-trend">{report.activity_over_time.slice(-14).map((item) => {
            const max = Math.max(1, ...report.activity_over_time.map((entry) => entry.session_count));
            return <div className="data-chart-column" key={item.date} title={`${item.date}: ${item.session_count} sessions`}><i style={{ height: `${Math.max(5, item.session_count / max * 100)}%` }} /><small>{item.date.slice(5)}</small></div>;
          })}</div> : <div className="chart-placeholder"><div className="chart-grid-lines"><i /><i /><i /><i /></div><span>{reportLoading ? "Loading session trend…" : "No recorded sessions in this period."}</span></div>}
        </div>
      </section>
      <section className="panel"><PanelTitle title="Current rates" description="Average of configured space rates" /><div className="rate-display">{loading || !filtered.length ? "—" : <><strong>₹{avgRate.toFixed(2)}</strong><span>/ hour average</span></>}</div><p className="muted-paragraph">Rates are the current values returned for each space. Recorded charges are not payment confirmations.</p><a href="#/app/fares" className="text-link">View fare rules <Icon name="arrow" size={14} /></a><div className="admin-lot-summary"><span>System coverage</span><strong>{lots.length} <small>lots</small></strong><strong>{loading ? "—" : filtered.length} <small>spaces</small></strong></div></section>
    </div>
    <section className="panel"><PanelTitle title="Parking lots" description="Select a lot to focus the dashboard" action={<a href="#/app/lots" className="text-link">Manage lots <Icon name="arrow" size={14} /></a>} />
      {lots.length ? <div className="lot-card-grid">{lots.map((lot) => {
        const lotSpaces = allSpaces.filter((space) => space.lot_id === lot.lot_id);
        const count = lotSpaces.filter((space) => space.status === "occupied").length;
        return <button key={lot.lot_id} className={`lot-card ${String(lotId) === String(lot.lot_id) ? "lot-card-active" : ""}`} onClick={() => onLotChange(String(lot.lot_id))}><span className="lot-card-icon"><Icon name="building" /></span><strong>{lot.name}</strong><small>{lot.location || lot.slug}</small><span className="lot-card-stat">{loading ? "Loading…" : `${count} of ${lotSpaces.length} occupied`}</span></button>;
      })}</div> : <EmptyInline loading={false} message="No parking lots are configured yet." />}
    </section>
    <section className="panel"><PanelTitle title="Recent system activity" description="Latest events recorded by the backend" action={<a href="#/app/activity" className="text-link">View all <Icon name="arrow" size={14} /></a>} />
      {recentEvents.length ? <div className="table-wrap"><table><thead><tr><th>TIME</th><th>EVENT</th><th>DESCRIPTION</th><th>ACTOR</th></tr></thead><tbody>{recentEvents.map((item) => <tr key={item.event_id}><td>{new Date(item.timestamp).toLocaleString()}</td><td><span className="code-pill">{item.event_type}</span></td><td>{item.description}</td><td>{item.account_email || item.actor_user_id || "System"}</td></tr>)}</tbody></table></div> : !reportLoading && <div className="empty-state compact-empty">{reportError ? reportError : "No activity has been recorded yet."}</div>}
    </section>
  </div>;
}

function AvailabilityPage({ lots, selectedLot, onLotChange }) {
  const { spaces, loading, error, refresh } = useLotSpaces(selectedLot);
  const [layout, setLayout] = useState(null);
  const [layoutLoading, setLayoutLoading] = useState(false);
  const [layoutError, setLayoutError] = useState("");
  const [selectedSpace, setSelectedSpace] = useState(null);
  const [spaceQuery, setSpaceQuery] = useState("");
  const [mapFocusSpace, setMapFocusSpace] = useState("");
  const [mapZoom, setMapZoom] = useState(1);
  const [mapNotice, setMapNotice] = useState("");
  const [claimCode, setClaimCode] = useState("");
  const [claimToken, setClaimToken] = useState("");
  const [claimTime, setClaimTime] = useState(0);
  const [claimMessage, setClaimMessage] = useState("");
  const [claimError, setClaimError] = useState(false);
  const [claimBusy, setClaimBusy] = useState(false);

  const loadLayout = useCallback(async () => {
    if (!selectedLot) { setLayout(null); return; }
    setLayoutLoading(true); setLayoutError(""); setLayout(null);
    try {
      const scope = encodeURIComponent(selectedLot.slug);
      const { cameras = [] } = await apiRequest(`/layouts/${scope}`);
      if (!cameras.length) { setLayout(null); return; }
      const preferredCamera = {
        simulator: "default",
        "campus-west": "gate-a",
        "khare-parking": "camera-1",
      }[selectedLot.slug];
      const selectedCamera = cameras.includes(preferredCamera) ? preferredCamera : cameras.includes("default") ? "default" : cameras[0];
      const result = await apiRequest(`/layouts/${scope}/${encodeURIComponent(selectedCamera)}`);
      setLayout(result);
    } catch (err) { setLayoutError(err.message); }
    finally { setLayoutLoading(false); }
  }, [selectedLot]);
  useEffect(() => {
    if (!selectedLot) return;
    setMapFocusSpace(""); setMapZoom(1);
  }, [selectedLot?.slug]);
  useEffect(() => { loadLayout(); }, [loadLayout]);

  useEffect(() => {
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (claimTime <= 0 || !claimToken) return undefined;
    const timer = window.setInterval(() => setClaimTime((time) => Math.max(0, time - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [claimTime > 0, claimToken]);
  useEffect(() => {
    if (claimToken && claimTime === 0) {
      setClaimToken("");
      setClaimMessage("The confirmation token expired. Start the claim again with your code.");
      setClaimError(true);
    }
  }, [claimTime, claimToken]);
  const slotsByName = useMemo(() => new Map(spaces.map((space) => [space.slot_number.trim().toLocaleLowerCase(), space])), [spaces]);
  const selectedRecord = selectedSpace ? slotsByName.get(selectedSpace.slot_number.trim().toLocaleLowerCase()) : null;
  const statusCounts = spaces.reduce((acc, space) => { acc[space.status] = (acc[space.status] || 0) + 1; return acc; }, {});
  const lastUpdated = spaces.map((space) => space.last_updated).filter(Boolean).sort().at(-1);
  const mapItems = useMemo(() => {
    const rawItems = (layout?.spaces || []).map((item) => {
      const points = item.polygon || [];
      const xs = points.map(([x]) => x);
      const ys = points.map(([, y]) => y);
      if (!xs.length || !ys.length) return null;
      return {
        ...item,
        record: slotsByName.get(item.slot_number.trim().toLocaleLowerCase()),
        center: [xs.reduce((sum, x) => sum + x, 0) / xs.length, ys.reduce((sum, y) => sum + y, 0) / ys.length],
        width: Math.max(...xs) - Math.min(...xs),
        height: Math.max(...ys) - Math.min(...ys),
      };
    }).filter(Boolean);
    const median = (values) => {
      const sorted = [...values].filter((value) => value > 0).sort((a, b) => a - b);
      return sorted.length ? sorted[Math.floor(sorted.length / 2)] : 30;
    };
    const typicalWidth = median(rawItems.map((item) => item.width));
    const typicalHeight = median(rawItems.map((item) => item.height));
    const bayWidth = typicalWidth * 0.86;
    const bayHeight = typicalHeight * 0.62;
    const rowTolerance = typicalHeight * 0.42;
    const rows = [];
    rawItems.slice().sort((a, b) => a.center[1] - b.center[1]).forEach((item) => {
      let row = rows[rows.length - 1];
      if (!row || item.center[1] - row.lastY > rowTolerance) {
        row = { items: [], lastY: item.center[1] };
        rows.push(row);
      }
      row.items.push(item);
      row.lastY = item.center[1];
    });
    let lowerEdge = -Infinity;
    return rows.flatMap((row) => {
      const detectedRowY = row.items.reduce((sum, item) => sum + item.center[1], 0) / row.items.length;
      const rowY = Math.max(detectedRowY, lowerEdge + bayHeight * 0.16 + bayHeight / 2);
      lowerEdge = rowY + bayHeight / 2;
      let rightEdge = -Infinity;
      return row.items.slice().sort((a, b) => a.center[0] - b.center[0]).map((item) => {
        // Keep the detected left-to-right order, but prevent noisy/overlapping polygons
        // from drawing on top of one another in the customer-facing schematic.
        const x = Math.max(item.center[0], rightEdge + bayWidth * 0.16);
        rightEdge = x + bayWidth / 2;
        return { ...item, center: [x, rowY], displayWidth: bayWidth, displayHeight: bayHeight };
      });
    });
  }, [layout, slotsByName]);
  const mapGeometry = useMemo(() => {
    if (!mapItems.length) return null;
    const minX = Math.min(...mapItems.map((item) => item.center[0] - item.displayWidth / 2));
    const maxX = Math.max(...mapItems.map((item) => item.center[0] + item.displayWidth / 2));
    const minY = Math.min(...mapItems.map((item) => item.center[1] - item.displayHeight / 2));
    const maxY = Math.max(...mapItems.map((item) => item.center[1] + item.displayHeight / 2));
    const width = Math.max(1, maxX - minX);
    const height = Math.max(1, maxY - minY);
    const padding = Math.max(width, height) * 0.08;
    return { minX, maxX, minY, maxY, width, height, padding };
  }, [layout, mapItems]);
  const focusedMapItem = mapItems.find((item) => item.slot_number === mapFocusSpace);
  const viewWidth = mapGeometry ? (mapGeometry.width + mapGeometry.padding * 2) / mapZoom : 100;
  const viewHeight = mapGeometry ? (mapGeometry.height + mapGeometry.padding * 2) / mapZoom : 100;
  const viewCenterX = focusedMapItem?.center[0] ?? (mapGeometry ? (mapGeometry.minX + mapGeometry.maxX) / 2 : 50);
  const viewCenterY = focusedMapItem?.center[1] ?? (mapGeometry ? (mapGeometry.minY + mapGeometry.maxY) / 2 : 50);
  const viewBox = `${viewCenterX - viewWidth / 2} ${viewCenterY - viewHeight / 2} ${viewWidth} ${viewHeight}`;
  const matchingMapItem = mapItems.find((item) => item.slot_number.trim().toLocaleLowerCase() === spaceQuery.trim().toLocaleLowerCase());
  useEffect(() => { setSelectedSpace(null); setClaimToken(""); setClaimCode(""); setClaimMessage(""); }, [selectedLot?.lot_id]);

  const initiateClaim = async (event) => {
    event.preventDefault();
    if (!selectedRecord) return;
    setClaimBusy(true); setClaimMessage("");
    setClaimError(false);
    try {
      const result = await apiRequest(`/parking/${selectedRecord.parking_id}/claim/initiate?lot_id=${selectedRecord.lot_id}`, { method: "POST", body: JSON.stringify({ claim_code: claimCode.trim() }) });
      setClaimToken(result.claim_token);
      setClaimTime(result.expires_in);
      setClaimMessage(result.message);
    } catch (err) { setClaimMessage(err.message); setClaimError(true); }
    finally { setClaimBusy(false); }
  };
  const confirmClaim = async () => {
    if (!selectedRecord || !claimToken || claimTime <= 0) return;
    setClaimBusy(true);
    setClaimError(false);
    try {
      const result = await apiRequest(`/parking/${selectedRecord.parking_id}/claim/confirm?lot_id=${selectedRecord.lot_id}`, { method: "POST", body: JSON.stringify({ claim_token: claimToken }) });
      setClaimMessage(result.message);
      setClaimError(false);
      setClaimToken(""); setClaimCode("");
      await refresh();
    } catch (err) { setClaimMessage(err.message); setClaimError(true); }
    finally { setClaimBusy(false); }
  };
  const chooseSpace = (layoutSpace) => {
    setSelectedSpace(layoutSpace.record || layoutSpace);
    setMapFocusSpace(layoutSpace.slot_number);
    setMapZoom(2.4);
    setClaimCode("");
    setClaimToken("");
    setClaimError(false);
    setClaimMessage("");
  };
  const locateSpace = (event) => {
    event.preventDefault();
    if (!matchingMapItem) { setMapNotice("That space is not on this lot’s configured map."); return; }
    chooseSpace(matchingMapItem);
    setMapNotice("");
  };

  return <div className="page-stack">
    <PageHeading eyebrow="LIVE PARKING VIEW" title="Parking availability" description="Explore the lot layout, check live bay availability, and select a space for its details." actions={<button className="button button-outline" onClick={() => { refresh(); loadLayout(); }}><span className="refresh-mark">↻</span> Refresh map</button>} />
    {!lots.length && !loading && <div className="portal-alert">No parking lots are configured in the backend.</div>}
    <section className="panel map-controls"><LotPicker lots={lots} value={selectedLot?.lot_id || ""} onChange={onLotChange} /><form className="space-search" onSubmit={locateSpace}><label htmlFor="space-map-search">Find a space</label><input id="space-map-search" value={spaceQuery} onChange={(event) => { setSpaceQuery(event.target.value); setMapNotice(""); }} placeholder="e.g. P042" /><button className="button button-outline" type="submit">Locate</button></form><div className="map-view-tools"><button className="button button-outline" type="button" aria-label="Zoom out" onClick={() => setMapZoom((zoom) => Math.max(1, zoom / 1.35))}>−</button><button className="button button-outline" type="button" aria-label="Zoom in" onClick={() => setMapZoom((zoom) => Math.min(5, zoom * 1.35))}>+</button><button className="button button-outline" type="button" onClick={() => { setMapFocusSpace(""); setMapZoom(1); }}>Fit lot</button></div></section>
    {(error || layoutError) && <div className="portal-alert" role="alert">{error || layoutError}<button onClick={() => { refresh(); loadLayout(); }}>Retry</button></div>}
    <div className="content-grid availability-content">
      <section className="panel live-map-panel"><PanelTitle title={selectedLot?.name || "Parking spaces"} description={`${mapItems.length} mapped spaces · spatial layout`} action={<span className="live-badge"><i /> LIVE STATUS</span>} />
        <div className="live-map-stage">
          {(loading || layoutLoading) ? <div className="map-loading"><span className="spinner" /> Loading parking map…</div> : mapGeometry ? <>
            <svg className="live-parking-map schematic-parking-map" viewBox={viewBox} role="group" aria-label={`Schematic parking map for ${selectedLot?.name || "selected lot"}`}>
              <rect x={mapGeometry.minX - mapGeometry.padding} y={mapGeometry.minY - mapGeometry.padding} width={mapGeometry.width + mapGeometry.padding * 2} height={mapGeometry.height + mapGeometry.padding * 2} rx={mapGeometry.padding * .12} className="map-lot-surface" />
              {mapItems.map((item) => {
                const status = item.record?.status || "unknown";
                const selected = selectedSpace?.slot_number === item.slot_number;
                const matched = matchingMapItem?.slot_number === item.slot_number;
                const width = item.displayWidth;
                const height = item.displayHeight;
                return <g key={item.slot_number} className={`map-space-shape ${status} ${selected ? "selected" : ""} ${matched ? "map-space-match" : ""}`} role="button" tabIndex="0" aria-label={`${item.slot_number}: ${status}`} aria-pressed={selected} onClick={() => chooseSpace(item)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); chooseSpace(item); } }}>
                  <title>{item.slot_number} · {status}</title>
                  <rect x={item.center[0] - width / 2} y={item.center[1] - height / 2} width={width} height={height} rx={Math.min(width, height) * .12} />
                  {(mapZoom >= 2 || selected || matched) && <text x={item.center[0]} y={item.center[1]} textAnchor="middle" dominantBaseline="central">{item.slot_number}</text>}
                </g>;
              })}
            </svg>
            {mapNotice && <div className="map-notice" role="status">{mapNotice}</div>}
          </> : <div className="map-empty-state"><span className="map-empty-icon"><Icon name="map" size={27} /></span><strong>{layoutError ? "Customer map unavailable" : "No map configured for this lot"}</strong><p>{layoutError ? "This parking lot does not have a saved layout available. Ask an administrator to configure its reviewed map." : "A reviewed parking layout is needed before spaces can be shown in their real positions."}</p></div>}
        </div>
        <div className="map-panel-footer"><MapLegend /><span>Last updated: {lastUpdated ? new Date(lastUpdated).toLocaleString() : "not provided"}</span></div>
      </section>
      <div className="right-stack">
        <section className="panel map-stat-panel"><PanelTitle title="Occupancy" description="Live parking-space records" /><div className="occupancy-ring" style={{ "--occupancy": `${spaces.length ? Math.round((statusCounts.occupied || 0) / spaces.length * 100) : 0}%` }}><div><strong>{spaces.length ? Math.round((statusCounts.occupied || 0) / spaces.length * 100) : 0}%</strong><span>occupied</span></div></div><div className="map-stat-list"><span><i className="legend-vacant" />Vacant <strong>{statusCounts.vacant || 0}</strong></span><span><i className="legend-occupied" />Occupied <strong>{statusCounts.occupied || 0}</strong></span><span><i className="legend-unknown" />Unknown <strong>{Math.max(statusCounts.unknown || 0, mapItems.filter((item) => !item.record).length)}</strong></span></div><button className="button button-outline full-width" onClick={refresh}>Refresh occupancy</button></section>
        <section className="panel space-detail-panel"><PanelTitle title="Space details" description={selectedSpace ? "Selected parking space" : "Select a space on the map"} />
          {!selectedSpace ? <div className="empty-state compact-empty"><span className="empty-icon"><Icon name="parking" size={20} /></span><span>Select a mapped space to view live details.</span></div> : <><div className="space-detail-heading"><span className={`detail-status ${selectedRecord?.status || "unknown"}`} /><div><strong>{selectedSpace.slot_number}</strong><small>{selectedLot?.name || "Parking lot"}</small></div></div><DetailRow label="Status" value={selectedRecord?.status || "Unknown / no matching parking record"} /><DetailRow label="Current rate" value={selectedRecord ? `₹${Number(selectedRecord.current_rate).toFixed(2)} / hour` : "Not available"} /><DetailRow label="Last updated" value={selectedRecord?.last_updated ? new Date(selectedRecord.last_updated).toLocaleString() : "Not provided"} />
            {selectedRecord?.status === "occupied" && selectedRecord.user_id == null && <form className="claim-form" onSubmit={initiateClaim}><label>Claim code<input value={claimCode} onChange={(event) => setClaimCode(event.target.value)} placeholder="Enter the code provided" required disabled={Boolean(claimToken)} /></label>{claimToken ? <><p className="claim-timer">Confirmation expires in <strong>{claimTime}s</strong></p><button className="button button-primary full-width" type="button" disabled={claimBusy || claimTime <= 0} onClick={confirmClaim}>{claimBusy ? "Confirming…" : "Confirm claim"}</button></> : <button className="button button-primary full-width" disabled={claimBusy}>{claimBusy ? "Checking code…" : "Initiate claim"}</button>}</form>}
            {claimMessage && <div className={`claim-result ${claimError ? "claim-result-error" : "claim-result-success"}`} role="status">{claimMessage}</div>}
          </>}
        </section>
      </div>
    </div>
  </div>;
}

function LotsPage({ lots, onLotsUpdated }) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", location: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/lots/", { method: "POST", body: JSON.stringify({ ...form, slug: form.slug.trim().toLowerCase() }) });
      onLotsUpdated(await apiRequest("/lots/"));
      setMessage("Parking lot created.");
      setForm({ name: "", slug: "", location: "" }); setShowForm(false);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <div className="page-stack"><PageHeading eyebrow="PARKING OPERATIONS" title="Parking lots" description="View configured facilities and create a new lot." actions={<button className="button button-primary" onClick={() => setShowForm((show) => !show)}>＋ Create parking lot</button>} />
    {error && <div className="portal-alert">{error}</div>}{message && <div className="portal-success">{message}</div>}
    {showForm && <form className="panel lot-create-form" onSubmit={submit}><PanelTitle title="Create a parking lot" description="A unique URL-safe slug identifies the lot in camera-layout paths." /><div className="form-row"><label>Lot name<input required maxLength={120} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value, slug: form.slug || event.target.value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") })} placeholder="e.g. North Campus" /></label><label>Lot slug<input required pattern="[a-z0-9][a-z0-9_-]*" maxLength={80} value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} placeholder="north-campus" /></label><label>Location<input maxLength={255} value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Optional address or description" /></label></div><button className="button button-primary" disabled={busy}>{busy ? "Creating…" : "Create lot"}</button></form>}
    <section className="panel"><PanelTitle title="Configured parking lots" description={`${lots.length} lot${lots.length === 1 ? "" : "s"} available`} /><div className="table-wrap"><table><thead><tr><th>LOT</th><th>SLUG</th><th>LOCATION</th><th>SPACES</th><th>ACTION</th></tr></thead><tbody>{lots.map((lot) => <LotRow key={lot.lot_id} lot={lot} />)}</tbody></table>{!lots.length && <EmptyInline message="No parking lots are configured." />}</div></section>
  </div>;
}

function LotRow({ lot }) {
  const { spaces, loading } = useLotSpaces(lot);
  return <tr><td><strong>{lot.name}</strong></td><td><span className="code-pill">{lot.slug}</span></td><td>{lot.location || "—"}</td><td>{loading ? "…" : spaces.length}</td><td><a href="#/app/dashboard" className="table-action">View dashboard <Icon name="arrow" size={13} /></a></td></tr>;
}

function SpacesPage({ selectedLot }) {
  const { spaces, loading, error, refresh } = useLotSpaces(selectedLot);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ slot_number: "", location: "", claim_code: "", current_rate: "50" });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const visible = spaces.filter((space) => space.slot_number.toLowerCase().includes(search.toLowerCase()) && (status === "all" || space.status === status));
  const createSpace = async (event) => {
    event.preventDefault();
    if (!selectedLot) return;
    setSaving(true); setMessage(""); setSaveError("");
    try {
      await apiRequest("/parking/", { method: "POST", body: JSON.stringify({
        lot_id: selectedLot.lot_id,
        slot_number: form.slot_number.trim(),
        location: form.location.trim(),
        claim_code: form.claim_code.trim(),
        current_rate: Number(form.current_rate),
      }) });
      setForm({ slot_number: "", location: "", claim_code: "", current_rate: "50" });
      setShowForm(false);
      setMessage("Parking space created. Occupancy remains controlled by the detection pipeline.");
      await refresh();
    } catch (err) { setSaveError(err.message); }
    finally { setSaving(false); }
  };
  return <div className="page-stack"><PageHeading eyebrow="PARKING OPERATIONS" title="Parking spaces" description="Inspect live occupancy and rates. Space state is maintained by the detection pipeline." actions={<button className="button button-outline" onClick={refresh}><span className="refresh-mark">↻</span> Refresh spaces</button>} />
    <section className="panel"><PanelTitle title={selectedLot?.name || "Select a parking lot"} description={`${spaces.length} recorded spaces`} action={<button className="button button-primary" onClick={() => { setShowForm((show) => !show); setSaveError(""); setMessage(""); }}>＋ Add space</button>} />
      {message && <div className="portal-success">{message}</div>}{saveError && <div className="portal-alert">{saveError}</div>}
      {showForm && <form className="space-create-form" onSubmit={createSpace}><label>Space ID<input required maxLength={20} value={form.slot_number} onChange={(event) => setForm({ ...form, slot_number: event.target.value })} placeholder="P01" /></label><label>Location<input required maxLength={100} value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Row A, bay 1" /></label><label>Claim code<input required maxLength={20} value={form.claim_code} onChange={(event) => setForm({ ...form, claim_code: event.target.value })} placeholder="Securely provisioned code" /></label><label>Rate per hour<input required type="number" min="0.01" step="0.01" value={form.current_rate} onChange={(event) => setForm({ ...form, current_rate: event.target.value })} /></label><button className="button button-primary" disabled={saving || !selectedLot}>{saving ? "Creating…" : "Create space"}</button></form>}
      <div className="table-tools"><label className="table-search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search space identifier…" /></label><select className="select-control" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="vacant">Vacant</option><option value="occupied">Occupied</option></select></div>{error && <div className="portal-alert">{error}</div>}<div className="table-wrap"><table><thead><tr><th>SPACE</th><th>PARKING LOT</th><th>STATUS</th><th>CURRENT RATE</th><th>LAST UPDATED</th></tr></thead><tbody>{visible.map((space) => <tr key={space.parking_id}><td><strong>{space.slot_number}</strong></td><td>{selectedLot?.name || "—"}</td><td><StatusPill status={space.status} /></td><td>₹{Number(space.current_rate).toFixed(2)} / hr</td><td>{space.last_updated ? new Date(space.last_updated).toLocaleString() : "—"}</td></tr>)}</tbody></table>{loading ? <EmptyInline loading message="" /> : !visible.length ? <EmptyInline message="No spaces match these filters." /> : null}</div></section>
  </div>;
}

function SettingsPage({ user, onLogout }) {
  return <div className="page-stack"><PageHeading eyebrow="ACCOUNT" title="Profile & settings" description="Your account details and available security options." />
    <div className="content-grid settings-grid"><section className="panel profile-panel"><PanelTitle title="Account information" description="Details returned by your authenticated profile" /><DetailRow label="Full name" value={user.name} /><DetailRow label="Email address" value={user.email} /><DetailRow label="Account role" value={user.role} /><p className="muted-paragraph">Profile editing is not available through the current backend.</p></section><section className="panel security-panel"><PanelTitle title="Security" description="Authentication and account protection" /><div className="security-item"><span className="security-item-icon"><Icon name="shield" /></span><div><strong>Password settings</strong><p>Password-change API is not implemented.</p></div><span className="feature-status">Unavailable</span></div><div className="security-item"><span className="security-item-icon"><Icon name="key" /></span><div><strong>Two-step verification</strong><p>The backend does not support OTP enrollment or verification.</p></div><span className="feature-status">Unavailable</span></div><button className="button button-outline logout-settings" onClick={onLogout}><Icon name="logout" size={16} /> Sign out</button></section></div>
  </div>;
}

function UnavailablePage({ title, explanation }) {
  return <div className="page-stack"><PageHeading eyebrow="BACKEND CAPABILITY" title={title} description="The interface will show real information as soon as an authorized API is available." /><section className="panel unavailable-panel"><span className="unavailable-icon"><Icon name="shield" size={24} /></span><div><span className="section-kicker">NOT CONNECTED</span><h2>Backend support is required</h2><p>{explanation}</p><p className="unavailable-secondary">This page intentionally does not use sample data or display information belonging to other accounts.</p></div></section></div>;
}

function PageHeading({ eyebrow, title, description, actions }) {
  return <div className="page-heading"><div><p className="section-kicker">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-heading-actions">{actions}</div>}</div>;
}
function PanelTitle({ title, description, action }) {
  return <div className="panel-title"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>;
}
function Metric({ label, value, hint, icon, color }) {
  return <article className="metric-card"><div className={`metric-icon ${color}`}><Icon name={icon} size={18} /></div><div className="metric-value">{value}</div><div className="metric-label">{label}</div><div className="metric-hint">{hint}</div></article>;
}
function DetailRow({ label, value }) {
  return <div className="detail-row"><span>{label}</span><strong>{value || "—"}</strong></div>;
}
function StatusPill({ status }) {
  return <span className={`status-pill ${status || "unknown"}`}><i />{status || "Unknown"}</span>;
}
function MapLegend() {
  return <div className="map-legend"><span><i className="legend-vacant" />Vacant</span><span><i className="legend-occupied" />Occupied</span><span><i className="legend-unknown" />Unknown</span></div>;
}
function LotPicker({ lots, value, onChange }) {
  return <label className="lot-picker"><Icon name="building" size={16} /><span>Parking lot</span><select value={value} onChange={(event) => onChange(event.target.value)} disabled={!lots.length}><option value="">{lots.length ? "Choose a lot" : "No lots configured"}</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>)}</select></label>;
}
function EmptyInline({ loading, error, message }) {
  return <div className="empty-inline">{loading ? <><span className="spinner" />Loading parking data…</> : error || message || "No results to show."}</div>;
}

export default App;
