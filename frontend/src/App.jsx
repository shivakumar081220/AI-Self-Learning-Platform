import { useEffect, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "./auth";

import {
  createLearner,
  completeTopic,
  askTutor,
  generateAssessment,
  generateDiagnostic,
  getDiagnosticResult,
  getAssessment,
  getCurrentTopic,
  getLearningContent,
  getGoals,
  getTracks,
  getLearningPath,
  getLearnerSummary,
  getMyLearner,
  generateMyCurriculum,
  getMyCurriculum,
  getSkillAnalysis,
  regenerateLearningPath,
  submitAssessment,
  submitDiagnostic,
} from "./api/client";

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
        <div className="hero-actions"><Link className="primary-button" to="/register">Get started</Link><Link className="primary-button" to="/login">Log in</Link></div>
        <div className="home-highlights" aria-label="Platform benefits">
          <article><strong>Start with evidence</strong><span>A short diagnostic maps what you already know.</span></article>
          <article><strong>Learn the next thing</strong><span>Your path adapts to skill gaps and assessment results.</span></article>
          <article><strong>Keep your momentum</strong><span>Lessons, practice, and progress stay in one learning space.</span></article>
        </div>
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

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <main className="center-state"><span className="loading-mark">● ● ●</span><p>Restoring your session...</p></main>;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await login(form); navigate("/dashboard"); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  return <div className="app-shell"><main className="auth-shell"><section className="auth-card"><p className="eyebrow">Welcome back</p><h1>Return to your learning.</h1><p className="auth-intro">Pick up your current path, revisit a lesson, and keep building from your latest result.</p><form className="auth-form" onSubmit={submit}><label className="field-label" htmlFor="login-email">Email</label><input id="login-email" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /><label className="field-label" htmlFor="login-password">Password</label><input id="login-password" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /><ErrorMessage message={error} /><button className="primary-button" disabled={busy} type="submit">{busy ? "Logging in..." : "Log in"}</button><div className="auth-link-row"><Link className="text-link" to="/register">Create an account</Link><Link className="auth-back-link" to="/">← Home</Link></div></form></section></main></div>;
}

function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setError("");
    if (form.password !== form.confirmPassword) { setError("Passwords do not match."); return; }
    setBusy(true);
    try { await register(form); navigate("/dashboard"); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  return <div className="app-shell"><main className="auth-shell"><section className="auth-card"><p className="eyebrow">Create your account</p><h1>Build your learning space.</h1><p className="auth-intro">Create a private learner profile and let the platform shape a practical path around your goal.</p><form className="auth-form" onSubmit={submit}><label className="field-label" htmlFor="register-name">Name</label><input id="register-name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /><label className="field-label" htmlFor="register-email">Email</label><input id="register-email" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /><label className="field-label" htmlFor="register-password">Password</label><input id="register-password" type="password" minLength="8" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /><label className="field-label" htmlFor="register-confirm">Confirm password</label><input id="register-confirm" type="password" value={form.confirmPassword} onChange={(event) => setForm({ ...form, confirmPassword: event.target.value })} required /><ErrorMessage message={error} /><button className="primary-button" disabled={busy} type="submit">{busy ? "Creating account..." : "Create account"}</button><div className="auth-link-row"><Link className="text-link" to="/login">Already have an account?</Link><Link className="auth-back-link" to="/">← Home</Link></div></form></section></main></div>;
}

function CourseLibrary({ curriculum, learnerId }) {
  const courses = curriculum?.courses || [];
  const [selectedCourseId, setSelectedCourseId] = useState(String(courses[0]?.course_id || ""));
  if (courses.length < 2) return null;
  const selectedCourse = courses.find((course) => String(course.course_id) === selectedCourseId) || courses[0];
  return (
    <section className="course-library" aria-labelledby="course-library-heading">
      <div className="course-library-heading">
        <div><p className="eyebrow">Your AI course library</p><h2 id="course-library-heading">Every course you have enrolled in.</h2></div>
        <Link className="secondary-button" to="/profile">Enroll new course</Link>
      </div>
      <div className="course-library-grid">
        {courses.map((course) => (
          <button className={`${course.is_current ? "course-library-card current" : "course-library-card"}${String(course.course_id) === String(selectedCourse.course_id) ? " selected" : ""}`} key={String(course.course_id)} onClick={() => setSelectedCourseId(String(course.course_id))} type="button">
            <div className="course-library-card-top"><span>{course.is_current ? "Current course" : "Previous course"}</span><strong>{course.track_name}</strong></div>
            <h3>{course.course_title}</h3>
            <p>{course.description}</p>
            <div className="course-library-meta"><span>{course.topics?.length || 0} topics</span><span>{course.level}</span><span>{course.generation_source === "openrouter" ? "AI-generated" : "Fallback-generated"}</span></div>
            <p className="course-library-goal"><strong>Goal:</strong> {course.goal}</p>
            <span className="course-library-action">{String(course.course_id) === String(selectedCourse.course_id) ? "Selected course" : "View course details"}</span>
          </button>
        ))}
      </div>
      <article className="course-detail-panel">
        <div><p className="eyebrow">Selected course details</p><h3>{selectedCourse.course_title}</h3><p>{selectedCourse.description}</p><p><strong>Goal:</strong> {selectedCourse.goal}</p></div>
        <div className="course-detail-topics"><p className="eyebrow">Course topics</p><ul>{(selectedCourse.topics || []).map((topic) => <li key={topic.topic_id || topic.title}><strong>{topic.title}</strong><span>{topic.description}</span></li>)}</ul></div>
        {selectedCourse.is_current && <Link className="primary-button" to={`/learning-path/${learnerId}`}>Continue current course</Link>}
      </article>
    </section>
  );
}

function DashboardPageV2() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [learner, setLearner] = useState(null);
  const [summary, setSummary] = useState(null);
  const [curriculum, setCurriculum] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getMyLearner()
      .then((profile) => {
        setLearner(profile);
        return Promise.all([getLearnerSummary(profile.id), getMyCurriculum().catch(() => null)]);
      })
      .then(([nextSummary, nextCurriculum]) => {
        setSummary(nextSummary);
        setCurriculum(nextCurriculum);
      })
      .catch((requestError) => setError(requestError.message));
  }, []);

  function signOut() {
    logout();
    navigate("/", { replace: true });
  }

  if (error) {
    return <div className="app-shell"><main className="center-state"><p className="eyebrow">Your learning space</p><h1>Choose your first course.</h1><p className="hero-copy">Set your experience, choose an AI learning track, and the platform will generate your diagnostic and personalized path.</p><ErrorMessage message={error} /><Link className="primary-button" to="/profile">Choose a course</Link></main></div>;
  }
  if (!learner) return <main className="center-state"><span className="loading-mark">● ● ●</span><p>Loading your learning space...</p></main>;

  return (
    <div className="app-shell">
      <header className="dashboard-header">
        <Link className="brand-link" to="/dashboard">Adaptive AI</Link>
        <button className="menu-toggle" aria-expanded={isMenuOpen} aria-controls="dashboard-navigation-v2" aria-label={isMenuOpen ? "Close navigation" : "Open navigation"} onClick={() => setIsMenuOpen((open) => !open)} type="button"><span /><span /><span /></button>
        <nav id="dashboard-navigation-v2" className={isMenuOpen ? "is-open" : ""} onClick={() => setIsMenuOpen(false)}><Link to={`/learning-path/${learner.id}`}>My learning</Link><Link to="/profile">Profile</Link><button className="text-button" onClick={signOut} type="button">Log out</button></nav>
      </header>
      <main className="dashboard-shell">
        <p className="eyebrow">Your learning space</p>
        <h1>Welcome, {learner.name}.</h1>
        {curriculum && <section className="course-banner"><div><p className="eyebrow">Current course</p><h2>{curriculum.course_title}</h2><p>{curriculum.description}</p></div><span>{curriculum.topics.length} topics · {curriculum.generation_source === "openrouter" ? "AI-generated" : "Fallback-generated"}</span></section>}
        <CourseLibrary curriculum={curriculum} learnerId={learner.id} />
        <section className="dashboard-grid"><div><p className="eyebrow">Progress</p><strong className="dashboard-number">{summary?.progress_percentage || 0}%</strong><p>{summary?.completed_topics || 0} of {summary?.total_topics || 0} topics complete</p></div><div><p className="eyebrow">Current topic</p><strong>{summary?.current_topic_title || "Ready to begin"}</strong><p>{summary?.recommendation?.summary || "Your next recommendation will appear here."}</p></div><div><p className="eyebrow">Skill readiness</p><strong className="dashboard-number">{summary?.overall_skill_percentage || 0}%</strong><p>across recorded concepts</p></div></section>
        <section className="profile-snapshot"><div><p className="eyebrow">Learner profile</p><strong>{learner.experience_level} · {learner.track.replaceAll("_", " ")}</strong><p>{learner.goal_text}</p>{learner.target_outcome && <p>{learner.target_outcome}</p>}</div><div><p className="eyebrow">Latest assessment</p><strong>{summary?.latest_assessment ? `${summary.latest_assessment.percentage}% · ${summary.latest_assessment.topic_title}` : "No assessment yet"}</strong><p>{summary?.latest_assessment ? "Your latest result is included in your learning state." : "Complete the diagnostic to establish your starting point."}</p></div><div><p className="eyebrow">Needs attention</p><div className="mini-tags weak-tags">{summary?.weak_concepts?.length ? summary.weak_concepts.slice(0, 3).map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No open skill gaps</em>}</div></div><div><p className="eyebrow">Recommended next step</p><strong>{summary?.recommendation?.target_topic_title || "Start your learning path"}</strong><p>{summary?.recommendation?.next_action || "Your personalized path will guide the next activity."}</p></div></section>
        <div className="dashboard-actions"><Link className="primary-button" to={`/learning-path/${learner.id}`}>{summary?.current_topic_id ? "Continue learning" : "Open my learning"}</Link><Link className="secondary-button" to="/profile">Enroll new course</Link><button className="secondary-button" onClick={signOut} type="button">Log out</button></div>
      </main>
    </div>
  );
}

function DashboardPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
          const [learner, setLearner] = useState(null);
              const [summary, setSummary] = useState(null);
              const [curriculum, setCurriculum] = useState(null);
            const [error, setError] = useState(null);
        useEffect(() => { getMyLearner().then((profile) => { setLearner(profile); return Promise.all([getLearnerSummary(profile.id), getMyCurriculum().catch(() => null)]); }).then((result) => { if (result) { setSummary(result[0]); setCurriculum(result[1]); } }).catch((requestError) => setError(requestError.message)); }, []);
        function signOut() { logout(); navigate("/", { replace: true }); }
        if (error) return <div className="app-shell"><main className="center-state"><p className="eyebrow">Your learning space</p><h1>Choose your first course.</h1><p className="hero-copy">Set your experience, choose an AI learning track, and the platform will generate your diagnostic and personalized path.</p><ErrorMessage message={error} /><Link className="primary-button" to="/profile">Choose a course</Link></main></div>;
        if (!learner) return <main className="center-state"><span className="loading-mark">● ● ●</span><p>Loading your learning space...</p></main>;
    return <div className="app-shell"><header className="dashboard-header"><Link className="brand-link" to="/dashboard">Adaptive AI</Link><button className="menu-toggle" aria-expanded={isMenuOpen} aria-controls="dashboard-navigation" aria-label={isMenuOpen ? "Close navigation" : "Open navigation"} onClick={() => setIsMenuOpen((open) => !open)} type="button"><span /><span /><span /></button><nav id="dashboard-navigation" className={isMenuOpen ? "is-open" : ""} onClick={() => setIsMenuOpen(false)}><Link to="/dashboard">Dashboard</Link><Link to={`/learning-path/${learner.id}`}>My learning</Link><Link to="/profile">Profile</Link><button className="text-button" onClick={signOut} type="button">Log out</button></nav></header><main className="dashboard-shell"><p className="eyebrow">Your learning space</p><h1>Welcome, {learner.name}.</h1>{curriculum && <section className="course-banner"><div><p className="eyebrow">Current course</p><h2>{curriculum.course_title}</h2><p>{curriculum.description}</p></div><span>{curriculum.topics.length} topics · {curriculum.generation_source === "openrouter" ? "AI-generated" : curriculum.generation_source === "deterministic_fallback" ? "Fallback-generated" : "Source unrecorded"}</span></section>}<section className="dashboard-grid"><div><p className="eyebrow">Progress</p><strong className="dashboard-number">{summary?.progress_percentage || 0}%</strong><p>{summary?.completed_topics || 0} of {summary?.total_topics || 0} topics complete</p></div><div><p className="eyebrow">Current topic</p><strong>{summary?.current_topic_title || "Ready to begin"}</strong><p>{summary?.recommendation?.summary || "Your next recommendation will appear here."}</p></div><div><p className="eyebrow">Skill readiness</p><strong className="dashboard-number">{summary?.overall_skill_percentage || 0}%</strong><p>across recorded concepts</p></div></section><section className="profile-snapshot"><div><p className="eyebrow">Learner profile</p><strong>{learner.experience_level} · {learner.track.replaceAll("_", " ")}</strong><p>{learner.goal_text}</p>{learner.target_outcome && <p>{learner.target_outcome}</p>}</div><div><p className="eyebrow">Latest assessment</p><strong>{summary?.latest_assessment ? `${summary.latest_assessment.percentage}% · ${summary.latest_assessment.topic_title}` : "No assessment yet"}</strong><p>{summary?.latest_assessment ? "Your latest result is included in your learning state." : "Complete the diagnostic to establish your starting point."}</p></div><div><p className="eyebrow">Needs attention</p><div className="mini-tags weak-tags">{summary?.weak_concepts?.length ? summary.weak_concepts.slice(0, 3).map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No open skill gaps</em>}</div></div><div><p className="eyebrow">Recommended next step</p><strong>{summary?.recommendation?.target_topic_title || "Start your learning path"}</strong><p>{summary?.recommendation?.next_action || "Your personalized path will guide the next activity."}</p></div></section><div className="dashboard-actions"><Link className="primary-button" to={`/learning-path/${learner.id}`}>{summary?.current_topic_id ? "Continue learning" : "Open my learning"}</Link><button className="secondary-button" onClick={signOut} type="button">Log out</button></div></main></div>;
  const [legacySummary, setLegacySummary] = useState(null);
  const [legacyCurriculum, setLegacyCurriculum] = useState(null);
  const [legacyError, setLegacyError] = useState("");
  useEffect(() => { getMyLearner().then((profile) => { setLearner(profile); return Promise.all([getLearnerSummary(profile.id), getMyCurriculum().catch(() => null)]); }).then((result) => { if (result) { setSummary(result[0]); setCurriculum(result[1]); } }).catch((requestError) => setError(requestError.message)); }, []);
  function signOut() { logout(); navigate("/", { replace: true }); }
  if (error) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to="/profile">Complete onboarding</Link></main></div>;
  if (!learner) return <main className="center-state"><span className="loading-mark">● ● ●</span><p>Loading your learning space...</p></main>;
  return <div className="app-shell"><header className="dashboard-header"><Link className="brand-link" to="/">Adaptive AI</Link><nav><Link to="/dashboard">Dashboard</Link><Link to={`/learning-path/${learner.id}`}>My learning</Link><Link to="/profile">Profile</Link><button className="text-button" onClick={signOut} type="button">Log out</button></nav></header><main className="dashboard-shell"><p className="eyebrow">Your learning space</p><h1>Welcome, {learner.name}.</h1>{curriculum && <section className="course-banner"><div><p className="eyebrow">Current course</p><h2>{curriculum.course_title}</h2><p>{curriculum.description}</p></div><span>{curriculum.topics.length} topics · {curriculum.generation_source === "openrouter" ? "AI-generated" : curriculum.generation_source === "deterministic_fallback" ? "Fallback-generated" : "Source unrecorded"}</span></section>}<section className="dashboard-grid"><div><p className="eyebrow">Progress</p><strong className="dashboard-number">{summary?.progress_percentage || 0}%</strong><p>{summary?.completed_topics || 0} of {summary?.total_topics || 0} topics complete</p></div><div><p className="eyebrow">Current topic</p><strong>{summary?.current_topic_title || "Ready to begin"}</strong><p>{summary?.recommendation?.summary || "Your next recommendation will appear here."}</p></div><div><p className="eyebrow">Skill readiness</p><strong className="dashboard-number">{summary?.overall_skill_percentage || 0}%</strong><p>across recorded concepts</p></div></section><section className="profile-snapshot"><div><p className="eyebrow">Learner profile</p><strong>{learner.experience_level} · {learner.track.replaceAll("_", " ")}</strong><p>{learner.goal_text}</p>{learner.target_outcome && <p>{learner.target_outcome}</p>}</div><div><p className="eyebrow">Latest assessment</p><strong>{summary?.latest_assessment ? `${summary.latest_assessment.percentage}% · ${summary.latest_assessment.topic_title}` : "No assessment yet"}</strong><p>{summary?.latest_assessment ? "Your latest result is included in your learning state." : "Complete the diagnostic to establish your starting point."}</p></div><div><p className="eyebrow">Needs attention</p><div className="mini-tags weak-tags">{summary?.weak_concepts?.length ? summary.weak_concepts.slice(0, 3).map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No open skill gaps</em>}</div></div><div><p className="eyebrow">Recommended next step</p><strong>{summary?.recommendation?.target_topic_title || "Start your learning path"}</strong><p>{summary?.recommendation?.next_action || "Your personalized path will guide the next activity."}</p></div></section><div className="dashboard-actions"><Link className="primary-button" to={`/learning-path/${learner.id}`}>{summary?.current_topic_id ? "Continue learning" : "Open my learning"}</Link><button className="secondary-button" onClick={signOut} type="button">Log out</button></div></main></div>;
}

function ProgressHeader({ activeStep }) {
  return (
    <header className="workflow-header">
      <Link className="brand-link" to="/">
        Adaptive AI
      </Link>
      <div className="progress-track" aria-label={`Step ${activeStep} of 4`}>
        <span className={activeStep >= 1 ? "progress-dot active" : "progress-dot"}>01</span>
        <span className="progress-line" />
        <span className={activeStep >= 2 ? "progress-dot active" : "progress-dot"}>02</span>
        <span className="progress-line" />
        <span className={activeStep >= 3 ? "progress-dot active" : "progress-dot"}>03</span>
        <span className="progress-line" />
        <span className={activeStep >= 4 ? "progress-dot active" : "progress-dot"}>04</span>
      </div>
      <span className="track-label">Generative AI</span>
    </header>
  );
}

function ErrorMessage({ message }) {
  if (!message) return null;
  return <p className="error-message" role="alert">{message}</p>;
}

function ProfilePage() {
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [learnerId, setLearnerId] = useState(null);
  const [goals, setGoals] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [form, setForm] = useState({ name: "", experience_level: "beginner", goal_key: "", custom_goal: "", target_outcome: "", track_id: "generative_ai" });
  const [isCustomGoal, setIsCustomGoal] = useState(false);
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const goalSelectionRef = useRef(null);

  useEffect(() => {
    getGoals().then(setGoals).catch((requestError) => setError(requestError.message));
    getTracks().then(setTracks).catch((requestError) => setError(requestError.message));
    if (isAuthenticated) {
      getMyLearner().then((learner) => {
        setLearnerId(learner.id);
        setForm({
          name: learner.name,
          experience_level: learner.experience_level,
          goal_key: "",
          custom_goal: learner.goal_text,
          target_outcome: learner.target_outcome || "",
          track_id: learner.track || "generative_ai",
        });
        setIsCustomGoal(true);
      }).catch(() => {});
    }
  }, []);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function selectGoal(goalKey) {
    setIsCustomGoal(false);
    const trackByGoal = { llm_apps: "generative_ai", prompt_engineering: "generative_ai", rag: "rag", ai_agents: "ai_agents" };
    setForm((current) => ({ ...current, goal_key: goalKey, custom_goal: "", track_id: trackByGoal[goalKey] || current.track_id }));
  }

  function selectTrack(track) {
    setIsCustomGoal(true);
    setForm((current) => ({
      ...current,
      track_id: track.id,
      goal_key: "",
      custom_goal: track.example_goals[0] || "",
    }));
    requestAnimationFrame(() => {
      goalSelectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function selectTrackGoal(goal) {
    setIsCustomGoal(true);
    setForm((current) => ({ ...current, goal_key: "", custom_goal: goal }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSaving(true);
    try {
      const learner = await createLearner({
        ...form,
        goal_key: isCustomGoal ? null : form.goal_key,
        custom_goal: isCustomGoal ? form.custom_goal : null,
      });
      navigate(`/diagnostic/${learner.id}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  }

  function signOut() {
    logout();
    navigate("/", { replace: true });
  }

  const selectedTrack = tracks.find((track) => track.id === form.track_id);
  const trackGoals = selectedTrack?.example_goals || [];

  return (
    <div className="app-shell">
      <header className="dashboard-header">
        <Link className="brand-link" to="/dashboard">Adaptive AI</Link>
        <button className="menu-toggle" aria-expanded={isMenuOpen} aria-controls="profile-navigation" aria-label={isMenuOpen ? "Close navigation" : "Open navigation"} onClick={() => setIsMenuOpen((open) => !open)} type="button"><span /><span /><span /></button>
        <nav id="profile-navigation" className={isMenuOpen ? "is-open" : ""} onClick={() => setIsMenuOpen(false)}>
          <Link to="/dashboard">Dashboard</Link>
          {learnerId && <Link to={`/learning-path/${learnerId}`}>My learning</Link>}
          <Link to="/profile">Profile</Link>
          <button className="text-button" onClick={signOut} type="button">Log out</button>
        </nav>
      </header>
      <main className="form-shell">
        <section className="form-intro">
          {isAuthenticated && <div className="page-back-row"><Link className="back-link" to="/dashboard">← Back to dashboard</Link></div>}
          <p className="eyebrow">Step 01 / learner profile</p>
          <h1>Start from where you are.</h1>
          <p className="hero-copy">Your answers shape the diagnostic and the learning decisions that follow.</p>
        </section>
        <form className="profile-form" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="name">What should we call you?</label>
          <input id="name" name="name" value={form.name} onChange={updateField} placeholder="Your name" required />

          <section className="track-selection" aria-labelledby="track-heading">
            <div><p className="eyebrow">AI Learning Tracks</p><h2 id="track-heading">Choose a direction.</h2></div>
            <div className="track-grid">
              {tracks.map((track) => (
                <article className={form.track_id === track.id ? "track-card selected" : "track-card"} key={track.id}>
                  <div className="track-card-heading"><h3>{track.name}</h3><span>{track.difficulty}</span></div>
                  <p>{track.description}</p>
                  <p><strong>Objective:</strong> {track.learning_objective}</p>
                  <p><strong>Example goals:</strong> {track.example_goals.join(" · ")}</p>
                  <button className="secondary-button" onClick={() => selectTrack(track)} type="button">
                    {form.track_id === track.id ? "Selected track" : "Select track"}
                  </button>
                </article>
              ))}
            </div>
          </section>

          <span className="field-label">How much AI experience do you have?</span>
          <div className="choice-row">
            {["beginner", "intermediate", "advanced"].map((level) => (
              <button
                className={form.experience_level === level ? "choice-button selected" : "choice-button"}
                key={level}
                onClick={() => setForm((current) => ({ ...current, experience_level: level }))}
                type="button"
              >
                {level}
              </button>
            ))}
          </div>

          <span className="field-label goal-selection-label" ref={goalSelectionRef}>What do you want to make possible?</span>
          <div className="goal-grid">
            {(trackGoals.length ? trackGoals.map((goal) => ({ key: goal, label: goal, description: selectedTrack.learning_objective })) : goals).map((goal) => (
              <button
                className={form.custom_goal === goal.label && isCustomGoal ? "goal-card selected" : "goal-card"}
                key={goal.key}
                onClick={() => trackGoals.length ? selectTrackGoal(goal.label) : selectGoal(goal.key)}
                type="button"
              >
                <strong>{goal.label}</strong>
                <span>{goal.description}</span>
              </button>
            ))}
            <button
              className={isCustomGoal ? "goal-card selected" : "goal-card"}
              onClick={() => { setIsCustomGoal(true); setForm((current) => ({ ...current, goal_key: "", custom_goal: "" })); }}
              type="button"
            >
              <strong>Something specific</strong>
              <span>Describe a {selectedTrack?.name || "track"} goal in your own words.</span>
            </button>
          </div>
          {isCustomGoal && (
            <input name="custom_goal" value={form.custom_goal} onChange={updateField} placeholder="I want to..." required />
          )}
          <label className="field-label" htmlFor="target-outcome">What would success look like?</label>
          <input id="target-outcome" name="target_outcome" maxLength="240" value={form.target_outcome} onChange={updateField} placeholder="A project or capability you want to build" />
          <ErrorMessage message={error} />
          <button className="primary-button form-submit" disabled={isSaving || (!form.goal_key && !form.custom_goal)} type="submit">
            {isSaving ? "Saving profile..." : "Begin diagnostic"}
          </button>
        </form>
      </main>
    </div>
  );
}

function DiagnosticPage() {
  const navigate = useNavigate();
  const { learnerId } = useParams();
  const generationStarted = useRef(false);
  const [assessment, setAssessment] = useState(null);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (generationStarted.current) return;
    generationStarted.current = true;
    generateMyCurriculum()
      .then(() => generateDiagnostic(learnerId))
      .then(setAssessment)
      .catch((requestError) => setError(requestError.message));
  }, [learnerId]);

  function chooseAnswer(questionId, optionIndex) {
    setAnswers((current) => ({ ...current, [questionId]: optionIndex }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const submittedAnswers = assessment.questions.map((question) => ({
        question_id: question.id,
        selected_option: answers[question.id],
      }));
      const analysis = await submitDiagnostic(learnerId, assessment.assessment_id, submittedAnswers);
      await generateMyCurriculum();
      await getLearningPath(learnerId);
      navigate(`/analysis/${learnerId}?assessment_id=${analysis.assessment_id}`, { state: { analysis } });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (error && !assessment) {
    return <div className="app-shell"><ProgressHeader activeStep={2} /><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to="/profile">Return to profile</Link></main></div>;
  }
  if (!assessment) {
    return <div className="app-shell"><ProgressHeader activeStep={2} /><main className="center-state"><span className="loading-mark">● ● ●</span><p>Building a diagnostic around your goal...</p></main></div>;
  }

  const answeredCount = Object.keys(answers).length;
  return (
    <div className="app-shell">
      <ProgressHeader activeStep={2} />
      <main className="assessment-shell">
        <section className="assessment-heading">
          <p className="eyebrow">Step 02 / diagnostic</p>
          <h1>Let’s find your edges.</h1>
          <p className="hero-copy">Eight quick questions aligned to your selected AI track. Choose the answer that feels most accurate.</p>
          <div className="question-progress"><span style={{ width: `${(answeredCount / assessment.questions.length) * 100}%` }} /></div>
          <p className="progress-copy">{answeredCount} of {assessment.questions.length} answered</p>
        </section>
        <form className="question-list" onSubmit={handleSubmit}>
          {assessment.questions.map((question, index) => (
            <fieldset className="question-card" key={question.id}>
              <legend><span>0{index + 1}</span>{question.question}</legend>
              <div className="option-list">
                {question.options.map((option, optionIndex) => (
                  <label className={answers[question.id] === optionIndex ? "option selected" : "option"} key={option}>
                    <input checked={answers[question.id] === optionIndex} onChange={() => chooseAnswer(question.id, optionIndex)} type="radio" name={question.id} />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          <ErrorMessage message={error} />
          <button className="primary-button form-submit" disabled={isSubmitting || answeredCount !== assessment.questions.length} type="submit">
            {isSubmitting ? "Mapping your skills..." : "See my skill analysis"}
          </button>
        </form>
      </main>
    </div>
  );
}

function SkillBar({ skill }) {
  return (
    <div className="skill-row">
      <div className="skill-meta"><span>{skill.concept.replaceAll("_", " ")}</span><strong>{skill.percentage}%</strong></div>
      <div className="skill-bar"><span className={`skill-fill ${skill.level}`} style={{ width: `${skill.percentage}%` }} /></div>
    </div>
  );
}

function AnalysisPage() {
  const { learnerId } = useParams();
  const location = useLocation();
  const assessmentId = new URLSearchParams(location.search).get("assessment_id");
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const nextAnalysis = location.state?.analysis ?? null;
    setAnalysis(nextAnalysis);
    if (nextAnalysis) {
      setError("");
      return;
    }

    setError("");
    (assessmentId ? getDiagnosticResult(learnerId, assessmentId) : getSkillAnalysis(learnerId))
      .then(setAnalysis)
      .catch((requestError) => setError(requestError.message));
  }, [assessmentId, learnerId, location.key]);

  if (error) return <div className="app-shell"><ProgressHeader activeStep={3} /><main className="center-state"><ErrorMessage message={error} /></main></div>;
  if (!analysis) return <div className="app-shell"><ProgressHeader activeStep={3} /><main className="center-state"><span className="loading-mark">● ● ●</span><p>Reading your results...</p></main></div>;

  return (
    <div className="app-shell">
      <ProgressHeader activeStep={3} />
      <main className="analysis-shell">
        <section className="analysis-heading">
          <p className="eyebrow">Step 03 / skill analysis</p>
          <h1>Your starting map.</h1>
          <p className="hero-copy">This is a concept-level view of your diagnostic, ready to shape the next learning path.</p>
          <div className="score-display"><strong>{analysis.overall_percentage}%</strong><span>diagnostic readiness</span></div>
        </section>
        {analysis.ai_interpretation && <section className="interpretation-panel"><p className="eyebrow">{analysis.ai_interpretation.source === "openrouter" ? "AI knowledge assessment" : "Knowledge assessment / fallback"}</p><div className="knowledge-assessment"><strong>{analysis.ai_interpretation.knowledge_level}</strong>{analysis.ai_interpretation.knowledge_assessment && <p>{analysis.ai_interpretation.knowledge_assessment}</p>}</div><p>{analysis.ai_interpretation.summary}</p>{analysis.ai_interpretation.focus_concepts.length > 0 && <div className="mini-tags weak-tags">{analysis.ai_interpretation.focus_concepts.map((concept) => <span key={concept}>{concept.replaceAll("_", " ")}</span>)}</div>}</section>}
        <section className="analysis-grid">
          <div className="analysis-column"><h2>Strong areas</h2>{analysis.strong_areas.length ? analysis.strong_areas.map((skill) => <SkillBar key={skill.concept} skill={skill} />) : <p className="empty-copy">Your strengths are still taking shape.</p>}</div>
          <div className="analysis-column"><h2>Developing areas</h2>{analysis.developing_areas.length ? analysis.developing_areas.map((skill) => <SkillBar key={skill.concept} skill={skill} />) : <p className="empty-copy">No developing areas yet.</p>}</div>
          <div className="analysis-column"><h2>Needs attention</h2>{analysis.weak_areas.length ? analysis.weak_areas.map((skill) => <SkillBar key={skill.concept} skill={skill} />) : <p className="empty-copy">No weak areas detected.</p>}</div>
        </section>
        {analysis.question_review?.length > 0 && <section className="diagnostic-review"><h2>Diagnostic feedback</h2><div className="review-list">{analysis.question_review.map((item) => <article className={item.is_correct ? "review-item correct" : "review-item wrong"} key={item.question_id}><div className="review-header"><span>{item.is_correct ? "Correct" : "Wrong"}</span><strong>{item.concept.replaceAll("_", " ")}</strong></div><p>{item.question}</p><ul>{item.options.map((option, index) => <li className={index === item.correct_option ? "correct-answer" : index === item.selected_option ? "selected-answer" : ""} key={`${item.question_id}-${option}`}>{option}</li>)}</ul><p><strong>Your answer:</strong> {item.options[item.selected_option]}</p><p><strong>Explanation:</strong> {item.explanation}</p></article>)}</div></section>}
        <Link className="next-step-banner" to={`/learning-path/${learnerId}`}><div><p className="eyebrow">Prepared for the next step</p><h2>Open your personalized learning path.</h2></div><span className="next-arrow">→</span></Link>
      </main>
    </div>
  );
}

function LearningPathPage() {
  const { learnerId } = useParams();
  const [path, setPath] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [isRegenerating, setIsRegenerating] = useState(false);

  useEffect(() => {
    getLearningPath(learnerId).then(setPath).catch((requestError) => setError(requestError.message));
    getLearnerSummary(learnerId).then(setSummary).catch(() => {});
  }, [learnerId]);

  async function handleRegenerate() {
    setError("");
    setIsRegenerating(true);
    try {
      setPath(await regenerateLearningPath(learnerId));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsRegenerating(false);
    }
  }

  if (error && !path) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to="/profile">Start a learner profile</Link></main></div>;
  if (!path) return <div className="app-shell"><main className="center-state"><span className="loading-mark">● ● ●</span><p>Assembling the sequence that fits you...</p></main></div>;

  const completedCount = path.topics.filter((topic) => topic.status === "completed").length;
  return (
    <div className="app-shell">
      <main className="path-shell">
        <div className="page-back-row"><Link className="back-link" to="/dashboard">← Back to dashboard</Link><Link className="text-link" to="/profile">Change course</Link></div>
        {summary && <section className="learner-overview"><div><p className="eyebrow">Learner dashboard</p><h2>{summary.name}</h2><p>{summary.goal}</p></div><div className="overview-stat"><strong>{summary.progress_percentage}%</strong><span>path progress</span></div><div className="overview-stat"><strong>{summary.overall_skill_percentage}%</strong><span>skill readiness</span></div>{summary.latest_assessment && <div className="overview-stat"><strong>{summary.latest_assessment.percentage}%</strong><span>latest assessment</span></div>}</section>}
        <section className="path-heading">
          <div>
            <p className="eyebrow">Step 04 / personalized path</p>
            <h1>Built around your next move.</h1>
            <p className="hero-copy">{path.overall_rationale}</p>
          </div>
          <div className="path-summary"><strong>{completedCount}/{path.topics.length}</strong><span>topics completed</span></div>
        </section>
        <section className="path-progress-panel" aria-label="Learning progress"><div className="path-progress-heading"><div><p className="eyebrow">Current status</p><strong>{summary?.progress_percentage || 0}% complete</strong></div><span>{completedCount} of {path.topics.length} topics complete</span></div><div className="path-progress-bar"><span style={{ width: `${summary?.progress_percentage || 0}%` }} /></div><p>{path.current_topic_title ? `Next up: ${path.current_topic_title}` : "Your learning path is ready."}</p></section>
        <div className="path-toolbar"><span>{path.current_topic_title ? `Current focus: ${path.current_topic_title}` : "Path ready for learning"}</span><button className="secondary-button" disabled={isRegenerating} onClick={handleRegenerate} type="button">{isRegenerating ? "Recalculating..." : "Recalculate path"}</button></div>
        <ErrorMessage message={error} />
        {summary?.recommendation && <section className={`recommendation-strip ${summary.recommendation.action_type}`}><div><p className="eyebrow">Current recommendation</p><strong>{summary.recommendation.target_topic_title || "Continue your path"}</strong><p>{summary.recommendation.summary}</p></div><span>{summary.recommendation.action_type}</span></section>}
        {summary && <section className="concept-overview"><div><p className="eyebrow">Strong concepts</p><div className="mini-tags">{summary.strong_concepts.length ? summary.strong_concepts.map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No strong concepts recorded yet</em>}</div></div><div><p className="eyebrow">Needs attention</p><div className="mini-tags weak-tags">{summary.weak_concepts.length ? summary.weak_concepts.map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No open weaknesses</em>}</div></div></section>}
        <section className="path-list">
          {path.topics.map((topic, index) => (
            <article className={`path-card ${topic.status}`} key={topic.topic_id}>
              <div className="path-index">{String(index + 1).padStart(2, "0")}</div>
              <div className="path-card-main">
                <div className="path-card-heading"><div><p className="path-status">{topic.status}</p>{topic.topic_id === path.current_topic_id ? <Link className="path-topic-link" to={`/learn/${learnerId}`}><h2>{topic.title}</h2></Link> : <h2>{topic.title}</h2>}</div><span className="difficulty-label">{topic.difficulty}</span></div>
                <p className="path-reason">{topic.reason}</p>
                {topic.prerequisites.length > 0 && <p className="prerequisite-line"><strong>Prerequisites:</strong> {topic.prerequisites.join(", ")}</p>}
              </div>
              {topic.topic_id === path.current_topic_id && <Link className="current-marker" to={`/learn/${learnerId}`} aria-label={`Open ${topic.title} learning experience`}>Next</Link>}
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}

function LearningExperiencePage() {
  const { learnerId } = useParams();
  const navigate = useNavigate();
  const [currentTopic, setCurrentTopic] = useState(null);
  const [learningContent, setLearningContent] = useState(null);
  const [error, setError] = useState("");
  const [isCompleting, setIsCompleting] = useState(false);
  const [tutorQuestion, setTutorQuestion] = useState("");
  const [tutorAnswer, setTutorAnswer] = useState(null);
  const [isAskingTutor, setIsAskingTutor] = useState(false);

  useEffect(() => {
    getCurrentTopic(learnerId)
      .then((topic) => {
        setCurrentTopic(topic);
        return getLearningContent(learnerId, topic.topic_id);
      })
      .then(setLearningContent)
      .catch((requestError) => setError(requestError.message));
  }, [learnerId]);

  async function handleComplete() {
    setError("");
    setIsCompleting(true);
    try {
      await completeTopic(learnerId, currentTopic.topic_id);
      const assessment = await generateAssessment(learnerId, currentTopic.topic_id);
      navigate(`/assessment/${learnerId}/${assessment.assessment_id}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsCompleting(false);
    }
  }

  async function handleTutorAsk() {
    if (!tutorQuestion.trim()) return;
    setIsAskingTutor(true);
    setTutorAnswer(null);
    try {
      const response = await askTutor(learnerId, {
        question: tutorQuestion,
        topic_id: currentTopic.topic_id,
      });
      setTutorAnswer(response);
    } catch (requestError) {
      setTutorAnswer({ answer: requestError.message, weak_concepts: [], follow_up: "Please try again in a moment." });
    } finally {
      setIsAskingTutor(false);
    }
  }

  if (error && !learningContent) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to={`/learning-path/${learnerId}`}>Return to learning path</Link></main></div>;
  if (!currentTopic || !learningContent) return <div className="app-shell"><main className="center-state"><span className="loading-mark">● ● ●</span><p>Preparing a lesson for your current focus...</p></main></div>;

  const content = learningContent.content;
  return (
    <div className="app-shell">
      <main className="lesson-shell">
        <header className="lesson-heading">
          <div><p className="eyebrow">Learn / topic {currentTopic.position} of {currentTopic.total_topics}</p><h1>{content.topic_title}</h1><p className="hero-copy">{content.overview}</p></div>
          <div className="lesson-status"><span>{learningContent.source === "openrouter" ? "Personalized lesson" : "Curated lesson"}</span><strong>{currentTopic.status.replace("_", " ")}</strong></div>
        </header>
        <div className="lesson-layout">
          <aside className="lesson-sidebar">
            <p className="section-label">Learning objectives</p>
            <ul>{content.learning_objectives.map((objective) => <li key={objective}>{objective}</li>)}</ul>
            {currentTopic.prerequisites.length > 0 && <><p className="section-label">Prerequisites</p><p className="lesson-muted">{currentTopic.prerequisites.join(", ")}</p></>}
          </aside>
          <article className="lesson-content">
            <section className="lesson-section"><p className="eyebrow">The idea</p><h2>Build the mental model.</h2><p>{content.explanation}</p>{content.analogy && <blockquote>{content.analogy}</blockquote>}</section>
            <section className="lesson-section"><p className="eyebrow">Key concepts</p><div className="concept-tags">{content.key_concepts.map((concept) => <span key={concept}>{concept}</span>)}</div><div className="example-grid">{content.examples.map((example, index) => <div className="example-block" key={example}><span>Example 0{index + 1}</span><p>{example}</p></div>)}</div></section>
            <section className="lesson-section practical-section"><p className="eyebrow">Put it to work</p><h2>A practical example.</h2><p>{content.practical_example}</p>{content.real_world_example && <p><strong>In practice:</strong> {content.real_world_example}</p>}</section>
            {content.coding_example ? <section className="lesson-section coding-example"><p className="eyebrow">Coding example</p><h2>{content.coding_example.title}</h2><p>{content.coding_example.explanation}</p><pre><code>{content.coding_example.code}</code></pre>{content.coding_example.expected_output && <p><strong>Expected output:</strong> <code>{content.coding_example.expected_output}</code></p>}<p><strong>Why it matters:</strong> {content.coding_example.why_it_matters}</p><p><strong>Common mistake:</strong> {content.coding_example.common_mistake}</p></section> : content.code_example && <pre><code>{content.code_example}</code></pre>}
            <section className="lesson-section split-section"><div><p className="eyebrow">Watch for</p><ul>{content.common_mistakes.map((mistake) => <li key={mistake}>{mistake}</li>)}</ul></div><div><p className="eyebrow">Quick recap</p><ul>{content.quick_recap.map((item) => <li key={item}>{item}</li>)}</ul></div></section>
            {content.important_notes.length > 0 && <section className="note-strip"><strong>Important:</strong> {content.important_notes.join(" ")}</section>}
            {content.practice_suggestion && <section className="note-strip practice-suggestion"><strong>Targeted practice:</strong> {content.practice_suggestion}</section>}
            <section className="doubt-assistant">
              <p className="eyebrow">AI tutor / doubt assistant</p>
              <h2>Ask about this topic.</h2>
              <textarea rows="3" value={tutorQuestion} onChange={(event) => setTutorQuestion(event.target.value)} placeholder="Ask for a simpler explanation or one example..." />
              <div className="lesson-actions"><button className="secondary-button" disabled={isAskingTutor || !tutorQuestion.trim()} onClick={handleTutorAsk} type="button">{isAskingTutor ? "Thinking..." : "Ask tutor"}</button></div>
              {tutorAnswer && (
                <div className="tutor-response">
                  <p className="eyebrow">{tutorAnswer.source === "openrouter" ? "OpenRouter AI Tutor" : "Tutor fallback"}</p>
                  <p>{tutorAnswer.answer}</p>
                  {tutorAnswer.example && <p><strong>Example:</strong> {tutorAnswer.example}</p>}
                  {tutorAnswer.key_points?.length > 0 && <><strong>Key points</strong><ul>{tutorAnswer.key_points.map((point) => <li key={point}>{point}</li>)}</ul></>}
                  {tutorAnswer.weak_concepts?.length > 0 && <div className="mini-tags weak-tags">{tutorAnswer.weak_concepts.map((concept) => <span key={concept}>{concept.replaceAll("_", " ")}</span>)}</div>}
                  {tutorAnswer.course_connection && <p><strong>Course connection:</strong> {tutorAnswer.course_connection}</p>}
                  {tutorAnswer.follow_up && <strong>{tutorAnswer.follow_up}</strong>}
                  {tutorAnswer.module_title && <Link className="text-link tutor-module-link" to={`/learn/${learnerId}`}>Open Module: {tutorAnswer.module_title}</Link>}
                </div>
              )}
            </section>
            <ErrorMessage message={error} />
            <div className="lesson-actions"><button className="primary-button" disabled={isCompleting} onClick={handleComplete} type="button">{isCompleting ? "Saving progress..." : "Mark topic complete"}</button><Link className="text-link" to={`/learning-path/${learnerId}`}>Back to path</Link></div>
          </article>
        </div>
      </main>
    </div>
  );
}

function AssessmentResult({ learnerId, result, onRetry, isRetrying }) {
  const weak = result.weak_concepts || [];
  return (
    <main className="assessment-result-shell">
      <section className="result-heading"><p className="eyebrow">Assessment result / {result.topic_title}</p><h1>Now we know what changed.</h1><p className="hero-copy">Your result is now part of the learner state that controls what comes next.</p><div className="result-score"><strong>{result.percentage}%</strong><span>{result.correct_count} / {result.total_questions} correct</span></div></section>
      <section className="result-grid"><div><h2>Concept performance</h2>{result.concept_results.map((concept) => <div className="result-concept" key={concept.concept}><div><span>{concept.concept.replaceAll("_", " ")}</span><strong>{concept.percentage}%</strong></div><div className="skill-bar"><span className={`skill-fill ${concept.level}`} style={{ width: `${concept.percentage}%` }} /></div><p>{concept.level}</p></div>)}</div><div className={`adaptation-card ${result.recommendation.action_type}`}><p className="eyebrow">What changed based on your result?</p><h2>{weak.length ? weak.map((concept) => concept.replaceAll("_", " ")).join(", ") : "Your next step"}</h2><p>{result.recommendation.summary}</p><strong>{result.recommendation.next_action}</strong>{result.recommendation.remediation && <blockquote>{result.recommendation.remediation}</blockquote>}{result.recommendation.practice_suggestion && <p><strong>Targeted practice:</strong> {result.recommendation.practice_suggestion}</p>}{result.recommendation.remediation_source && <p className="ai-source-label">{result.recommendation.remediation_source === "openrouter" ? "AI remediation" : "Deterministic remediation"}</p>}</div></section>
      {result.question_review && result.question_review.length > 0 && (
        <section className="result-review-panel">
          <h2>Question-by-question feedback</h2>
          <div className="review-list">
            {result.question_review.map((item) => (
              <article className={item.is_correct ? "review-item correct" : "review-item wrong"} key={item.question_id}>
                <div className="review-header">
                  <span>{item.is_correct ? "Correct" : "Wrong"}</span>
                  <strong>{item.concept.replaceAll("_", " ")}</strong>
                </div>
                <p>{item.question}</p>
                <ul>
                  {item.options.map((option, index) => (
                    <li className={index === item.correct_option ? "correct-answer" : index === item.selected_option ? "selected-answer" : ""} key={`${item.question_id}-${option}`}>
                      {option}
                    </li>
                  ))}
                </ul>
                <p><strong>Your answer:</strong> {item.selected_option === null ? "No answer submitted" : item.options[item.selected_option]}</p>
                <p><strong>Explanation:</strong> {item.explanation}</p>
              </article>
            ))}
          </div>
        </section>
      )}
      <div className="result-actions"><Link className="primary-button" to={weak.length ? `/learn/${learnerId}` : `/learning-path/${learnerId}`}>{weak.length ? "Review weak topic" : "Continue learning"}</Link><button className="secondary-button" disabled={isRetrying} onClick={onRetry} type="button">{isRetrying ? "Preparing retry..." : "Retry assessment"}</button></div>
    </main>
  );
}

function AssessmentPage() {
  const { learnerId, assessmentId } = useParams();
  const navigate = useNavigate();
  const [assessment, setAssessment] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  useEffect(() => {
    setAssessment(null);
    setAnswers({});
    setResult(null);
    setError("");
    getAssessment(learnerId, assessmentId).then((data) => {
      if (data.concept_results) setResult(data);
      else setAssessment(data);
    }).catch((requestError) => setError(requestError.message));
  }, [assessmentId, learnerId]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const submitted = assessment.questions.map((question) => ({ question_id: question.question_id, selected_option: answers[question.question_id] }));
      setResult(await submitAssessment(learnerId, assessmentId, submitted));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRetry() {
    setError("");
    setIsRetrying(true);
    try {
      const nextAssessment = await generateAssessment(learnerId, result.topic_id);
      navigate(`/assessment/${learnerId}/${nextAssessment.assessment_id}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsRetrying(false);
    }
  }

  if (error) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to={`/learning-path/${learnerId}`}>Return to path</Link></main></div>;
  if (result) return <div className="app-shell"><AssessmentResult learnerId={learnerId} result={result} onRetry={handleRetry} isRetrying={isRetrying} /></div>;
  if (!assessment) return <div className="app-shell"><main className="center-state"><span className="loading-mark">● ● ●</span><p>Preparing your topic assessment...</p></main></div>;

  const answeredCount = Object.keys(answers).length;
  return <div className="app-shell"><main className="assessment-shell post-learning-assessment"><section className="assessment-heading"><p className="eyebrow">Assess / {assessment.topic_title}</p><h1>Show what stuck.</h1><p className="hero-copy">Answer these questions from the topic you just completed. Your result will shape the next recommendation.</p><div className="question-progress"><span style={{ width: `${(answeredCount / assessment.questions.length) * 100}%` }} /></div><p className="progress-copy">{answeredCount} of {assessment.questions.length} answered</p></section><form className="question-list" onSubmit={handleSubmit}>{assessment.questions.map((question, index) => <fieldset className="question-card" key={question.question_id}><legend><span>0{index + 1}</span>{question.question}</legend><div className="option-list">{question.options.map((option, optionIndex) => <label className={answers[question.question_id] === optionIndex ? "option selected" : "option"} key={option}><input checked={answers[question.question_id] === optionIndex} onChange={() => setAnswers((current) => ({ ...current, [question.question_id]: optionIndex }))} type="radio" name={question.question_id} /><span>{option}</span></label>)}</div></fieldset>)}<ErrorMessage message={error} /><button className="primary-button form-submit" disabled={isSubmitting || answeredCount !== assessment.questions.length} type="submit">{isSubmitting ? "Scoring your result..." : "Submit assessment"}</button></form></main></div>;
}

function RouteTitle() {
  const location = useLocation();

  useEffect(() => {
    const path = location.pathname;
    const title = path === "/"
      ? "Adaptive AI Learning"
      : path === "/login"
        ? "Log In | Adaptive AI"
        : path === "/register"
          ? "Create Account | Adaptive AI"
          : path === "/profile"
            ? "Choose Your AI Track | Adaptive AI"
            : path === "/dashboard"
              ? "Learning Dashboard | Adaptive AI"
              : path.startsWith("/diagnostic/")
                ? "Diagnostic Assessment | Adaptive AI"
                : path.startsWith("/analysis/")
                  ? "Skill Analysis | Adaptive AI"
                  : path.startsWith("/learning-path/")
                    ? "Personalized Learning Path | Adaptive AI"
                    : path.startsWith("/learn/")
                      ? "Learning Experience | Adaptive AI"
                      : path.startsWith("/assessment/")
                        ? "Topic Assessment | Adaptive AI"
                        : "Adaptive AI Learning";
    document.title = title;
  }, [location.pathname]);

  return null;
}

function App() {
  return (
    <>
      <RouteTitle />
      <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPageV2 /></ProtectedRoute>} />
      <Route path="/diagnostic/:learnerId" element={<ProtectedRoute><DiagnosticPage /></ProtectedRoute>} />
      <Route path="/analysis/:learnerId" element={<ProtectedRoute><AnalysisPage /></ProtectedRoute>} />
      <Route path="/learning-path/:learnerId" element={<ProtectedRoute><LearningPathPage /></ProtectedRoute>} />
      <Route path="/learn/:learnerId" element={<ProtectedRoute><LearningExperiencePage /></ProtectedRoute>} />
      <Route path="/assessment/:learnerId/:assessmentId" element={<ProtectedRoute><AssessmentPage /></ProtectedRoute>} />
      </Routes>
    </>
  );
}

export default App;
