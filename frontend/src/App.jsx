import { Link, Route, Routes } from "react-router-dom";

const steps = [
  "Profile",
  "Diagnostic",
  "Skill analysis",
  "Learning path",
  "Learn",
  "Assessment",
  "Adapt",
];

function HomePage() {
  return (
    <main className="hero-shell">
      <section className="hero-card">
        <p className="eyebrow">Generative AI learning studio</p>
        <h1>Learn what you need next.</h1>
        <p className="hero-copy">
          A diagnostic-first learning experience that adjusts to your strengths,
          gaps, and assessment results.
        </p>
        <Link className="primary-button" to="/profile">
          Start learner profile
        </Link>
      </section>
      <section className="journey-panel" aria-label="Learning journey">
        <p className="section-label">Your adaptive journey</p>
        <div className="step-list">
          {steps.map((step, index) => (
            <div className="step" key={step}>
              <span className="step-number">{String(index + 1).padStart(2, "0")}</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function ProfilePage() {
  return (
    <main className="page-shell">
      <p className="eyebrow">Step 01</p>
      <h1>Tell us where you are starting.</h1>
      <p className="hero-copy">Profile capture will be implemented in the next phase.</p>
      <Link className="text-link" to="/">Back to overview</Link>
    </main>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/profile" element={<ProfilePage />} />
    </Routes>
  );
}

export default App;
