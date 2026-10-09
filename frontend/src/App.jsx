import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "./auth";

import {
  createLearner,
  completeTopic,
  generateAssessment,
  generateDiagnostic,
  getDiagnosticResult,
  getAssessment,
  getCurrentTopic,
  getPendingAssessment,
  getLearningContent,
  getGoals,
  getTracks,
  getLearningPath,
  getLearnerSummary,
  getMyLearner,
  generateMyCurriculum,
  getMyCurriculum,
  getTutorContext,
  listTutorConversations,
  createTutorConversation,
  getTutorConversation,
  sendTutorMessage,
  getSkillAnalysis,
  saveAssessmentResponses,
  submitAssessment,
  submitDiagnostic,
} from "./api/client";

const steps = [
  "Profile",
  "Diagnostic",
  "Skill analysis",
  "Personalized course",
  "Learn",
  "Assessment",
  "Adapt",
];

const assessmentTypes = [
  ["mcq", "MCQ", "Concept/application questions with plausible distractors."],
  ["conceptual", "Conceptual", "Explain a concept in your own words."],
  ["scenario", "Scenario-based", "Solve a practical situation."],
  ["code_output", "Code Output", "Predict or interpret Python/AI code behavior."],
  ["coding", "Coding", "Implement a small solution."],
  ["debugging", "Debugging", "Identify and fix incorrect code/logic."],
  ["comparison", "Comparison", "Compare AI concepts, methods, models, or architectures."],
];

const tutorTeachingStyles = [
  ["simplified", "Simplified explanation"],
  ["analogy", "Real-world analogy"],
  ["technical", "Technical explanation"],
  ["code_based", "Code-based explanation"],
  ["step_by_step", "Step-by-step explanation"],
];

const recommendedTypesByTrack = {
  python_for_ai: ["mcq", "code_output", "coding", "debugging"],
  machine_learning: ["mcq", "scenario", "coding", "comparison"],
  deep_learning: ["conceptual", "scenario", "code_output", "comparison"],
  nlp: ["mcq", "conceptual", "scenario", "comparison"],
  generative_ai: ["mcq", "scenario", "comparison"],
  llms: ["conceptual", "scenario", "code_output", "comparison"],
  rag: ["scenario", "coding", "debugging", "comparison"],
  ai_agents: ["scenario", "coding", "debugging", "comparison"],
};

function WaitMessage({ children }) {
  const [takingLonger, setTakingLonger] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setTakingLonger(true), 12000);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <>
      <p>{children}</p>
      {takingLonger && <p role="status">AI generation is taking longer than expected. Your progress is safe.</p>}
    </>
  );
}

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
  const { isAuthenticated, loading, restoreError, retryRestore } = useAuth();
  if (loading) return <main className="center-state"><span className="loading-mark">● ● ●</span><p>Restoring your session...</p></main>;
  if (restoreError) {
    return <main className="center-state">
      <ErrorMessage message={restoreError} />
      <button className="secondary-button" onClick={retryRestore} type="button">Retry connection</button>
      <Link className="text-link" to="/login">Go to log in</Link>
    </main>;
  }
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await login(form, rememberMe); navigate("/dashboard"); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  return <div className="app-shell"><main className="auth-shell"><section className="auth-card"><p className="eyebrow">Welcome back</p><h1>Return to your learning.</h1><p className="auth-intro">Pick up your current path, revisit a lesson, and keep building from your latest result.</p><form className="auth-form" onSubmit={submit}><label className="field-label" htmlFor="login-email">Email</label><input id="login-email" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /><label className="field-label" htmlFor="login-password">Password</label><input id="login-password" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /><label className="remember-me"><input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} />Remember me</label><ErrorMessage message={error} /><button className="primary-button" disabled={busy} type="submit">{busy ? "Logging in..." : "Log in"}</button><div className="auth-link-row"><Link className="text-link" to="/register">Create an account</Link><Link className="auth-back-link" to="/">← Home</Link></div></form></section></main></div>;
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

function CourseLibrary({ curriculum, learnerId, selectedCourseId, onSelectCourse }) {
  const courses = curriculum?.courses || [];
  if (courses.length === 0) return null;
  const selectedCourse = courses.find((course) => String(course.course_id) === selectedCourseId)
    || courses.find((course) => course.is_current)
    || courses[0];
  return (
    <section className="course-library" aria-labelledby="course-library-heading">
      <div className="course-library-heading">
        <div><p className="eyebrow">Your AI course library</p><h2 id="course-library-heading">Every course you have enrolled in.</h2></div>
        <Link className="secondary-button" to="/profile">Enroll new course</Link>
      </div>
      <div className="course-library-grid">
        {courses.map((course) => (
          <button className={`${course.is_current ? "course-library-card current" : "course-library-card"}${String(course.course_id) === String(selectedCourse.course_id) ? " selected" : ""}`} key={String(course.course_id)} onClick={() => onSelectCourse(String(course.course_id))} type="button">
            <div className="course-library-card-top"><span>Enrolled course</span><strong>{course.track_name}</strong></div>
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
        <Link className="primary-button" to={`/learning-path/${learnerId}?course_id=${encodeURIComponent(selectedCourse.course_id)}`}>
          Open learning path
        </Link>
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
  const [error, setError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isStartingAssessment, setIsStartingAssessment] = useState(false);
  const [actionError, setActionError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [summaryRefreshKey, setSummaryRefreshKey] = useState(0);
  const [summaryRefreshError, setSummaryRefreshError] = useState(false);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [dashboardReady, setDashboardReady] = useState(false);
  const hasSummary = useRef(false);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(false);
    setDashboardReady(false);
    setSummary(null);
    hasSummary.current = false;
    setSummaryRefreshError(false);
    getMyLearner()
      .then(async (profile) => {
        if (!active) return;
        setLearner(profile);
        const nextCurriculum = await getMyCurriculum().catch(() => null);
        if (!active) return;
        setCurriculum(nextCurriculum);
        setSelectedCourseId((currentCourseId) => (
          currentCourseId
          && nextCurriculum?.courses?.some((course) => String(course.course_id) === currentCourseId)
            ? currentCourseId
            : String(nextCurriculum?.course_id || "")
        ));
        setDashboardReady(true);
      })
      .catch(() => {
        if (active) {
          setError(true);
          setIsLoading(false);
        }
      });
    return () => { active = false; };
  }, [reloadKey]);

  useEffect(() => {
    if (!dashboardReady || !learner) return undefined;
    let active = true;
    if (!hasSummary.current) setIsLoading(true);
    setError(false);
    getLearnerSummary(learner.id, selectedCourseId || null)
      .then((nextSummary) => {
        if (active) {
          setSummary(nextSummary);
          hasSummary.current = true;
          setSummaryRefreshError(false);
        }
      })
      .catch(() => {
        if (active) {
          if (hasSummary.current) setSummaryRefreshError(true);
          else setError(true);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, [dashboardReady, learner, selectedCourseId, summaryRefreshKey]);

  useEffect(() => {
    if (!dashboardReady) return undefined;
    const refreshIfVisible = () => {
      if (document.visibilityState === "visible") {
        setSummaryRefreshKey((key) => key + 1);
      }
    };
    const refreshOnVisibility = () => {
      if (document.visibilityState === "visible") refreshIfVisible();
    };
    const interval = window.setInterval(refreshIfVisible, 30000);
    window.addEventListener("focus", refreshIfVisible);
    document.addEventListener("visibilitychange", refreshOnVisibility);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refreshIfVisible);
      document.removeEventListener("visibilitychange", refreshOnVisibility);
    };
  }, [dashboardReady]);

  function selectCourse(courseId) {
    if (courseId === selectedCourseId) return;
    setIsLoading(true);
    setSummary(null);
    hasSummary.current = false;
    setSelectedCourseId(courseId);
  }

  function signOut() {
    logout();
    navigate("/", { replace: true });
  }

  function topicRoute(topicId) {
    if (!learner || !topicId) return `/learning-path/${learner?.id || ""}`;
    const courseQuery = summary?.course_id ? `?course_id=${encodeURIComponent(summary.course_id)}&` : "?";
    return `/learn/${learner.id}${courseQuery}topic_id=${encodeURIComponent(topicId)}`;
  }

  function recommendationRoute() {
    const targetId = summary?.recommendation?.target_topic_id || summary?.current_topic?.topic_id;
    if (!targetId || !summary?.course_id) return `/learning-path/${learner.id}`;
    const available = targetId === summary.current_topic?.topic_id
      || summary.completed_topic_items.some((topic) => topic.topic_id === targetId);
    return available
      ? topicRoute(targetId)
      : `/learning-path/${learner.id}?course_id=${encodeURIComponent(summary.course_id)}`;
  }

  async function handleTakeAssessment() {
    if (!learner || isStartingAssessment) return;
    setActionError("");
    setIsStartingAssessment(true);
    try {
      const currentTopic = summary?.current_topic;
      if (currentTopic && !currentTopic.lesson_completed && currentTopic.status !== "completed") {
        navigate(topicRoute(currentTopic.topic_id));
        return;
      }
      let topicId = currentTopic?.topic_id
        || summary?.latest_assessment?.topic_id
        || summary?.completed_topic_items[0]?.topic_id;
      if (!topicId) {
        const path = await getLearningPath(learner.id, summary?.course_id || null);
        topicId = path.current_topic_id
          || path.topics.find((topic) => topic.status !== "completed")?.topic_id;
        if (topicId) {
          navigate(`/learn/${learner.id}?course_id=${encodeURIComponent(path.course_id || "")}&topic_id=${encodeURIComponent(topicId)}`);
          return;
        }
      }
      if (!topicId) {
        setActionError("Your learning path has no available topic to assess yet.");
        return;
      }
      const pending = await getPendingAssessment(learner.id, topicId);
      const assessment = pending?.assessment_id
        ? pending
        : await generateAssessment(learner.id, topicId, {
          selected_types: ["mcq"],
          question_count: 5,
        });
      navigate(`/assessment/${learner.id}/${assessment.assessment_id}?course_id=${encodeURIComponent(summary?.course_id || "")}`);
    } catch {
      setActionError("Unable to start an assessment right now. Please try again.");
    } finally {
      setIsStartingAssessment(false);
    }
  }

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? ""
      : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
  }

  if (isLoading) {
    return <div className="app-shell"><main className="dashboard-shell dashboard-loading" aria-busy="true" aria-label="Loading your learning dashboard"><div className="dashboard-skeleton dashboard-skeleton-heading" /><div className="dashboard-skeleton dashboard-skeleton-hero" /><div className="dashboard-skeleton-grid"><div className="dashboard-skeleton" /><div className="dashboard-skeleton" /><div className="dashboard-skeleton" /></div><p className="sr-only" role="status">Loading your progress...</p></main></div>;
  }
  if (error || !learner || !summary) {
    return <div className="app-shell"><main className="center-state dashboard-error"><p className="eyebrow">Your learning space</p><h1>Unable to load your progress.</h1><p className="hero-copy">Your saved learning data is unchanged. Retry loading it or open your learning path.</p><div className="dashboard-actions"><button className="primary-button" onClick={() => setReloadKey((key) => key + 1)} type="button">Retry</button>{learner ? <Link className="secondary-button" to={`/learning-path/${learner.id}`}>Go to Learning Path</Link> : <Link className="secondary-button" to="/profile">Set up your learning path</Link>}</div></main></div>;
  }

  const progress = summary.progress_percentage;
  const courseTitle = summary.course_title || curriculum?.course_title || "Your personalized course";
  const activity = summary.recent_activity || [];
  const assessments = summary.assessment_performance;
  const recommendation = summary.recommendation;
  const assessmentReady = summary.current_topic?.lesson_completed
    || (!summary.current_topic && (
      summary.completed_topic_items.length > 0
      || Boolean(summary.latest_assessment?.topic_id)
    ));
  const learningPathLink = `/learning-path/${learner.id}${summary.course_id ? `?course_id=${encodeURIComponent(summary.course_id)}` : ""}`;

  return (
    <div className="app-shell">
      <header className="dashboard-header">
        <Link className="brand-link" to="/dashboard">Adaptive AI</Link>
        <button className="menu-toggle" aria-expanded={isMenuOpen} aria-controls="dashboard-navigation-v2" aria-label={isMenuOpen ? "Close navigation" : "Open navigation"} onClick={() => setIsMenuOpen((open) => !open)} type="button"><span /><span /><span /></button>
        <nav id="dashboard-navigation-v2" className={isMenuOpen ? "is-open" : ""} onClick={() => setIsMenuOpen(false)}><Link to="/dashboard">Dashboard</Link><button className="text-button" onClick={signOut} type="button">Log out</button></nav>
      </header>
      <main className="dashboard-shell dashboard-v3">
        <section className="dashboard-welcome"><div><p className="eyebrow">Your learning space</p><h1>Welcome, {learner.name}.</h1><p>{learner.goal_text}</p></div></section>
        <CourseLibrary
          curriculum={curriculum}
          learnerId={learner.id}
          selectedCourseId={selectedCourseId}
          onSelectCourse={selectCourse}
        />
        {summaryRefreshError && <p className="dashboard-inline-error" role="status">Your saved progress is shown, but the latest update could not be loaded. <button className="text-link" onClick={() => setSummaryRefreshKey((key) => key + 1)} type="button">Retry refresh</button></p>}

        <section className="dashboard-continue" aria-labelledby="dashboard-continue-title">
          <div className="dashboard-continue-copy"><p className="eyebrow">Continue learning</p><h2 id="dashboard-continue-title">{summary.current_topic?.title || (summary.path_completed ? "Course topics completed!" : "Start your personalized course")}</h2><p>{summary.current_topic ? `${courseTitle} · ${summary.current_topic.status.replaceAll("_", " ")}` : summary.path_completed ? "You have completed every topic in this course." : "Open your course to begin the next topic."}</p>{summary.current_topic?.lesson_completed && summary.current_topic.status !== "completed" && <p className="dashboard-hint">Lesson studied · pass the assessment to complete this topic.</p>}</div>
          <div className="dashboard-continue-progress"><strong>{progress}%</strong><span>overall progress</span><div className="dashboard-progress-track" role="progressbar" aria-label="Overall learning progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}><span style={{ width: `${progress}%` }} /></div><span>{summary.completed_topics} of {summary.total_topics} topics completed</span></div>
          <Link className="primary-button" to={summary.current_topic ? topicRoute(summary.current_topic.topic_id) : learningPathLink}>{summary.current_topic ? "Continue Learning" : summary.path_completed ? "Review course" : "Open course"} →</Link>
        </section>

        <section className="dashboard-overview-grid">
          <article className="dashboard-panel">
            <div className="dashboard-panel-heading"><div><p className="eyebrow">Overall progress</p><h2>{progress}%</h2></div><span>{summary.completed_topics} / {summary.total_topics} modules</span></div>
            <div className="dashboard-progress-track" role="progressbar" aria-label="Course completion" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}><span style={{ width: `${progress}%` }} /></div>
            <p>{summary.total_topics ? `${summary.completed_topics} of ${summary.total_topics} topics completed in ${courseTitle}.` : "Your course will show progress after its topics are created."}</p><Link className="text-link" to={learningPathLink}>View course →</Link>
          </article>
          <article className="dashboard-panel">
            <div className="dashboard-panel-heading"><div><p className="eyebrow">Completed topics</p><h2>{summary.completed_topic_items.length}</h2></div><Link className="text-link" to={learningPathLink}>View course →</Link></div>
            {summary.completed_topic_items.length ? <ul className="dashboard-completed-list">{summary.completed_topic_items.slice().sort((a, b) => new Date(b.completed_at || 0) - new Date(a.completed_at || 0)).slice(0, 4).map((topic) => <li key={topic.topic_id}><Link to={topicRoute(topic.topic_id)}><span aria-hidden="true">✓</span><span>{topic.title}<small>{topic.course_title || courseTitle}{topic.completed_at ? ` · ${formatDate(topic.completed_at)}` : ""}</small></span></Link></li>)}</ul> : <p>Start learning to build your progress. No topics completed yet.</p>}
          </article>
        </section>

        <section className="dashboard-insights-grid">
          <article className="dashboard-panel"><p className="eyebrow">Your strengths</p><h2>Strong areas</h2><p>Based on your saved assessment results for this course.</p>{summary.strong_concepts.length ? <ul className="dashboard-skills">{summary.strong_concepts.slice().sort((a, b) => b.score - a.score).slice(0, 5).map((skill) => <li key={skill.concept}><div><span>{skill.concept.replaceAll("_", " ")}</span><strong>{skill.percentage}%</strong></div><div className="dashboard-skill-track"><span className="strong" style={{ width: `${skill.percentage}%` }} /></div></li>)}</ul> : <p>Complete an assessment to discover your strengths.</p>}</article>
          <article className="dashboard-panel"><p className="eyebrow">Needs practice</p><h2>Weak areas</h2><p>Updated from your saved assessment results for this course.</p>{summary.weak_concepts.length ? <ul className="dashboard-skills">{summary.weak_concepts.slice(0, 5).map((skill) => <li key={skill.concept}><div><span>{skill.concept.replaceAll("_", " ")} <small className="dashboard-severity">{skill.score < 0.25 ? "Critical" : skill.score < 0.4 ? "High" : "Needs practice"}</small></span><strong>{skill.percentage}%</strong></div><div className="dashboard-skill-track"><span className="weak" style={{ width: `${skill.percentage}%` }} /></div></li>)}</ul> : <p>Great! No weak areas detected.</p>}{summary.weak_concepts.length > 0 && <Link className="secondary-button" to={recommendationRoute()}>Practice Now →</Link>}</article>
        </section>

        <section className="dashboard-performance-grid">
          <article className="dashboard-panel dashboard-assessment-panel">
            <div className="dashboard-panel-heading"><div><p className="eyebrow">Assessment performance</p><h2>Real assessment history</h2></div><button className="secondary-button" disabled={isStartingAssessment} onClick={handleTakeAssessment} type="button">{isStartingAssessment ? "Preparing..." : assessmentReady ? "Take Assessment →" : "Continue Learning →"}</button></div>
            {actionError && <p className="dashboard-inline-error" role="alert">{actionError}</p>}
            {assessments.completed_count ? <><div className="dashboard-assessment-stats"><div><span>Average</span><strong>{assessments.average_percentage}%</strong></div><div><span>Latest</span><strong>{assessments.latest_percentage}%</strong></div><div><span>Completed</span><strong>{assessments.completed_count}</strong></div></div><div className="dashboard-score-chart" aria-label="Recent assessment scores">{assessments.recent_scores.map((item) => <div className="dashboard-score-column" key={item.assessment_id} title={`${item.topic_title}: ${item.percentage}%`}><span>{item.percentage}%</span><div><span style={{ height: `${Math.max(item.percentage, 3)}%` }} /></div><small>{item.topic_title}</small></div>)}</div><ol className="sr-only">{assessments.recent_scores.map((item) => <li key={item.assessment_id}>{item.topic_title}: {item.percentage}%</li>)}</ol></> : <p>Complete your first assessment to see performance. No assessments completed yet.</p>}
          </article>
          <article className="dashboard-panel dashboard-recommendation-panel"><p className="eyebrow">Adaptive recommendation</p><h2>{summary.path_completed ? "Course topics completed!" : recommendation?.target_topic_title || "Your course is up to date."}</h2><p>{summary.path_completed ? "You have completed every module in this course." : recommendation?.summary || (summary.current_topic ? `Continue with ${summary.current_topic.title}.` : "Your course is up to date.")}</p>{!summary.path_completed && <Link className="primary-button" to={recommendationRoute()}>{recommendation?.action_type === "remediate" || recommendation?.action_type === "practice" ? "Start Remediation →" : "Start Next Topic →"}</Link>}</article>
        </section>

        <section className="dashboard-panel dashboard-activity-panel"><div className="dashboard-panel-heading"><div><p className="eyebrow">Your learning history</p><h2>Recent activity</h2></div></div>{activity.length ? <ol className="dashboard-activity-list">{activity.map((item, index) => <li key={`${item.activity_type}-${item.assessment_id || item.topic_id || index}-${item.occurred_at}`}><span className={`dashboard-activity-marker ${item.activity_type}`} aria-hidden="true">{item.activity_type === "tutor_message" ? "AI" : item.activity_type === "progress_updated" ? "•" : "✓"}</span><div><strong>{item.title}</strong><p>{item.description}</p><time dateTime={item.occurred_at}>{formatDate(item.occurred_at)}</time></div></li>)}</ol> : <p>No learning activity yet.</p>}</section>
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
    return <div className="app-shell"><header className="dashboard-header"><Link className="brand-link" to="/dashboard">Adaptive AI</Link><button className="menu-toggle" aria-expanded={isMenuOpen} aria-controls="dashboard-navigation" aria-label={isMenuOpen ? "Close navigation" : "Open navigation"} onClick={() => setIsMenuOpen((open) => !open)} type="button"><span /><span /><span /></button><nav id="dashboard-navigation" className={isMenuOpen ? "is-open" : ""} onClick={() => setIsMenuOpen(false)}><Link to="/dashboard">Dashboard</Link><button className="text-button" onClick={signOut} type="button">Log out</button></nav></header><main className="dashboard-shell"><p className="eyebrow">Your learning space</p><h1>Welcome, {learner.name}.</h1>{curriculum && <section className="course-banner"><div><p className="eyebrow">Current course</p><h2>{curriculum.course_title}</h2><p>{curriculum.description}</p></div><span>{curriculum.topics.length} topics · {curriculum.generation_source === "openrouter" ? "AI-generated" : curriculum.generation_source === "deterministic_fallback" ? "Fallback-generated" : "Source unrecorded"}</span></section>}<section className="dashboard-grid"><div><p className="eyebrow">Progress</p><strong className="dashboard-number">{summary?.progress_percentage || 0}%</strong><p>{summary?.completed_topics || 0} of {summary?.total_topics || 0} topics complete</p></div><div><p className="eyebrow">Current topic</p><strong>{summary?.current_topic_title || "Ready to begin"}</strong><p>{summary?.recommendation?.summary || "Your next recommendation will appear here."}</p></div><div><p className="eyebrow">Skill readiness</p><strong className="dashboard-number">{summary?.overall_skill_percentage || 0}%</strong><p>across recorded concepts</p></div></section><section className="profile-snapshot"><div><p className="eyebrow">Learner profile</p><strong>{learner.experience_level} · {learner.track.replaceAll("_", " ")}</strong><p>{learner.goal_text}</p>{learner.target_outcome && <p>{learner.target_outcome}</p>}</div><div><p className="eyebrow">Latest assessment</p><strong>{summary?.latest_assessment ? `${summary.latest_assessment.percentage}% · ${summary.latest_assessment.topic_title}` : "No assessment yet"}</strong><p>{summary?.latest_assessment ? "Your latest result is included in your learning state." : "Complete the diagnostic to establish your starting point."}</p></div><div><p className="eyebrow">Needs attention</p><div className="mini-tags weak-tags">{summary?.weak_concepts?.length ? summary.weak_concepts.slice(0, 3).map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No open skill gaps</em>}</div></div><div><p className="eyebrow">Recommended next step</p><strong>{summary?.recommendation?.target_topic_title || "Start your learning path"}</strong><p>{summary?.recommendation?.next_action || "Your personalized path will guide the next activity."}</p></div></section><div className="dashboard-actions"><Link className="primary-button" to={`/learning-path/${learner.id}`}>{summary?.current_topic_id ? "Continue learning" : "Open my learning"}</Link><button className="secondary-button" onClick={signOut} type="button">Log out</button></div></main></div>;
  const [legacySummary, setLegacySummary] = useState(null);
  const [legacyCurriculum, setLegacyCurriculum] = useState(null);
  const [legacyError, setLegacyError] = useState("");
  useEffect(() => { getMyLearner().then((profile) => { setLearner(profile); return Promise.all([getLearnerSummary(profile.id), getMyCurriculum().catch(() => null)]); }).then((result) => { if (result) { setSummary(result[0]); setCurriculum(result[1]); } }).catch((requestError) => setError(requestError.message)); }, []);
  function signOut() { logout(); navigate("/", { replace: true }); }
  if (error) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to="/profile">Complete onboarding</Link></main></div>;
  if (!learner) return <main className="center-state"><span className="loading-mark">● ● ●</span><p>Loading your learning space...</p></main>;
  return <div className="app-shell"><header className="dashboard-header"><Link className="brand-link" to="/">Adaptive AI</Link><nav><Link to="/dashboard">Dashboard</Link><button className="text-button" onClick={signOut} type="button">Log out</button></nav></header><main className="dashboard-shell"><p className="eyebrow">Your learning space</p><h1>Welcome, {learner.name}.</h1><section className="dashboard-grid"><div><p className="eyebrow">Progress</p><strong className="dashboard-number">{summary?.progress_percentage || 0}%</strong><p>{summary?.completed_topics || 0} of {summary?.total_topics || 0} topics complete</p></div><div><p className="eyebrow">Current topic</p><strong>{summary?.current_topic_title || "Ready to begin"}</strong><p>{summary?.recommendation?.summary || "Your next recommendation will appear here."}</p></div><div><p className="eyebrow">Skill readiness</p><strong className="dashboard-number">{summary?.overall_skill_percentage || 0}%</strong><p>across recorded concepts</p></div></section><section className="profile-snapshot"><div><p className="eyebrow">Learner profile</p><strong>{learner.experience_level} · {learner.track.replaceAll("_", " ")}</strong><p>{learner.goal_text}</p>{learner.target_outcome && <p>{learner.target_outcome}</p>}</div><div><p className="eyebrow">Latest assessment</p><strong>{summary?.latest_assessment ? `${summary.latest_assessment.percentage}% · ${summary.latest_assessment.topic_title}` : "No assessment yet"}</strong><p>{summary?.latest_assessment ? "Your latest result is included in your learning state." : "Complete the diagnostic to establish your starting point."}</p></div><div><p className="eyebrow">Needs attention</p><div className="mini-tags weak-tags">{summary?.weak_concepts?.length ? summary.weak_concepts.slice(0, 3).map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No open skill gaps</em>}</div></div><div><p className="eyebrow">Recommended next step</p><strong>{summary?.recommendation?.target_topic_title || "Start your learning path"}</strong><p>{summary?.recommendation?.next_action || "Your personalized path will guide the next activity."}</p></div></section><div className="dashboard-actions"><Link className="primary-button" to={`/learning-path/${learner.id}`}>{summary?.current_topic_id ? "Continue learning" : "Open my learning"}</Link><button className="secondary-button" onClick={signOut} type="button">Log out</button></div></main></div>;
}

function ProgressHeader({ activeStep }) {
  const [trackLabel, setTrackLabel] = useState("Loading track...");

  useEffect(() => {
    let cancelled = false;
    Promise.all([getMyLearner(), getTracks()])
      .then(([learner, tracks]) => {
        const track = tracks.find((item) => item.id === learner.track);
        if (!cancelled) {
          setTrackLabel(track?.name || "Track unavailable");
        }
      })
      .catch(() => {
        if (!cancelled) setTrackLabel("Track unavailable");
      });
    return () => { cancelled = true; };
  }, []);

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
      <span className="track-label">{trackLabel}</span>
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
  const [savingMessage, setSavingMessage] = useState("Saving profile...");
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
    setSavingMessage("Saving profile...");
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
            {isSaving ? savingMessage : "Begin diagnostic"}
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
    generateDiagnostic(learnerId)
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
    return <div className="app-shell"><ProgressHeader activeStep={2} /><main className="center-state"><span className="loading-mark">● ● ●</span><WaitMessage>Creating your diagnostic...</WaitMessage></main></div>;
  }

  const answeredCount = Object.keys(answers).length;
  return (
    <div className="app-shell">
      <ProgressHeader activeStep={2} />
      <main className="assessment-shell">
        <section className="assessment-heading">
          <p className="eyebrow">Step 02 / diagnostic</p>
          <h1>Let’s find your edges.</h1>
          <p className="hero-copy">Eight questions check your starting knowledge across the selected AI track. Choose the answer you believe is best; the results will show evidence by concept, not just a total score.</p>
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
            {isSubmitting ? "Building your personalized course..." : "See my skill analysis"}
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
          <div className="score-display"><strong>{analysis.overall_percentage}%</strong><span>overall correct</span></div>
        </section>
        {analysis.ai_interpretation && <section className="interpretation-panel"><p className="eyebrow">{analysis.ai_interpretation.source === "openrouter" ? "AI knowledge assessment" : "Knowledge assessment / fallback"}</p><div className="knowledge-assessment"><strong>{analysis.ai_interpretation.knowledge_level}</strong>{analysis.ai_interpretation.knowledge_assessment && <p>{analysis.ai_interpretation.knowledge_assessment}</p>}</div><p>{analysis.ai_interpretation.summary}</p>{analysis.ai_interpretation.focus_concepts.length > 0 && <div className="mini-tags weak-tags">{analysis.ai_interpretation.focus_concepts.map((concept) => <span key={concept}>{concept.replaceAll("_", " ")}</span>)}</div>}</section>}
        {analysis.concept_insights?.length > 0 && (
          <section className="diagnostic-insights">
            <p className="eyebrow">Evidence by concept</p>
            <h2>What you know and what to improve</h2>
            <p className="insights-intro">Each note is based on the questions tagged to that concept. Treat this short diagnostic as a starting estimate; use practice to confirm mastery.</p>
            <div className="insight-grid">
              {analysis.concept_insights.map((insight) => (
                <article className={`insight-card ${insight.level}`} key={insight.concept}>
                  <div className="insight-heading">
                    <h3>{insight.concept.replaceAll("_", " ")}</h3>
                    <span>{insight.level} · {insight.percentage}%</span>
                  </div>
                  <p className="insight-evidence">{insight.evidence_statement}</p>
                  <p><strong>Current signal</strong>{insight.current_strength}</p>
                  <p><strong>Gap to address</strong>{insight.knowledge_gap}</p>
                  {insight.improvement_plan.length > 0 && <div><strong>What to improve next</strong><ul>{insight.improvement_plan.map((step) => <li key={step}>{step}</li>)}</ul></div>}
                  {insight.supporting_topics.length > 0 && <p className="insight-topics"><strong>Related course topics</strong>{insight.supporting_topics.join(" · ")}</p>}
                </article>
              ))}
            </div>
          </section>
        )}
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
  const [searchParams] = useSearchParams();
  const courseId = searchParams.get("course_id");
  const [path, setPath] = useState(null);
  const [currentCourse, setCurrentCourse] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [courseError, setCourseError] = useState("");

  useEffect(() => {
    setPath(null);
    setCurrentCourse(null);
    getLearningPath(learnerId, courseId)
      .then((nextPath) => {
        setPath(nextPath);
        getMyCurriculum()
          .then((curriculum) => {
          const selectedCourse = curriculum.courses?.find(
            (course) => String(course.course_id) === String(nextPath.course_id),
          );
          setCurrentCourse(selectedCourse || curriculum);
          })
          .catch((requestError) => setCourseError(requestError.message));
      })
      .catch((requestError) => setError(requestError.message));
    getLearnerSummary(learnerId).then(setSummary).catch(() => {});
  }, [learnerId, courseId]);

  if (error && !path) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to="/profile">Start a learner profile</Link></main></div>;
  if (!path) return <div className="app-shell"><main className="center-state"><span className="loading-mark">● ● ●</span><p>Loading your personalized course...</p></main></div>;

  const completedCount = path.topics.filter((topic) => topic.status === "completed").length;
  const pathProgressPercentage = path.topics.length
    ? Math.round((completedCount / path.topics.length) * 100)
    : 0;
  const pathTopics = new Map(path.topics.map((topic) => [topic.topic_id, topic]));
  const modules = currentCourse?.modules?.length
    ? currentCourse.modules.map((module) => ({
      ...module,
      topics: module.topics
        .map((topic) => pathTopics.get(topic.topic_id) || topic)
        .filter(Boolean),
    }))
    : [{
      module_id: "course-topics",
      order: 1,
      title: "Course topics",
      description: currentCourse?.description || path.overall_rationale,
      learning_objectives: [],
      practical_exercises: [],
      topics: path.topics,
    }];
  return (
    <div className="app-shell">
      <main className="path-shell">
        <div className="page-back-row"><Link className="back-link" to="/dashboard">← Back to dashboard</Link><Link className="text-link" to="/profile">Change course</Link></div>
        {summary && <section className="learner-overview"><div><p className="eyebrow">Learner dashboard</p><h2>{summary.name}</h2><p>{currentCourse?.goal || summary.goal}</p></div><div className="overview-stat"><strong>{pathProgressPercentage}%</strong><span>course progress</span></div><div className="overview-stat"><strong>{summary.overall_skill_percentage}%</strong><span>skill readiness</span></div>{summary.latest_assessment && path.topics.some((topic) => topic.topic_id === summary.latest_assessment.topic_id) && <div className="overview-stat"><strong>{summary.latest_assessment.percentage}%</strong><span>latest course assessment</span></div>}</section>}
        <section className="path-heading">
          <div>
            <p className="eyebrow">
              {currentCourse
                ? `Currently open course / ${currentCourse.track_name}`
                : "Your personalized course"}
            </p>
            <h1>{currentCourse?.course_title || "Built around your next move."}</h1>
            {currentCourse ? (
              <>
                <p className="hero-copy">{currentCourse.description}</p>
                <p className="path-course-meta">
                  {currentCourse.level} level · {currentCourse.estimated_duration}
                </p>
                <p className="path-course-goal"><strong>Course goal:</strong> {currentCourse.goal}</p>
                {currentCourse.learning_objectives?.length > 0 && (
                  <div className="path-course-objectives">
                    <p className="eyebrow">What you will learn</p>
                    <ul>
                      {currentCourse.learning_objectives.map((objective) => (
                        <li key={objective}>{objective}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <p className="hero-copy">{path.overall_rationale}</p>
            )}
          </div>
          <div className="path-summary"><strong>{completedCount}/{path.topics.length}</strong><span>topics completed</span></div>
        </section>
        {currentCourse && <p className="path-reason">This course is organized into ordered modules based on your learning goal and recorded skills.</p>}
        <ErrorMessage message={courseError} />
        <section className="path-progress-panel" aria-label="Course progress"><div className="path-progress-heading"><div><p className="eyebrow">Course progress</p><strong>{pathProgressPercentage}% complete</strong></div><span>{completedCount} of {path.topics.length} topics complete</span></div><div className="path-progress-bar"><span style={{ width: `${pathProgressPercentage}%` }} /></div><p>{path.current_topic_title ? `Next topic: ${path.current_topic_title}` : "You have completed the course topics."}</p></section>
        <ErrorMessage message={error} />
        {summary?.recommendation && <section className={`recommendation-strip ${summary.recommendation.action_type}`}><div><p className="eyebrow">Adaptive recommendation</p><strong>{summary.recommendation.target_topic_title || "Continue your course"}</strong><p>{summary.recommendation.summary}</p></div><span>{summary.recommendation.action_type}</span></section>}
        {summary && <section className="concept-overview"><div><p className="eyebrow">Strong concepts</p><div className="mini-tags">{summary.strong_concepts.length ? summary.strong_concepts.map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No strong concepts recorded yet</em>}</div></div><div><p className="eyebrow">Needs attention</p><div className="mini-tags weak-tags">{summary.weak_concepts.length ? summary.weak_concepts.map((concept) => <span key={concept.concept}>{concept.concept.replaceAll("_", " ")}</span>) : <em>No open weaknesses</em>}</div></div></section>}
        <section className="path-list course-module-list" aria-label="Course modules">
          {modules.map((module, moduleIndex) => {
            const moduleCompleted = module.topics.filter((topic) => topic.status === "completed").length;
            return (
              <article className="course-module-card" key={module.module_id}>
                <div className="course-module-heading">
                  <div>
                    <p className="eyebrow">Module {module.order || moduleIndex + 1}</p>
                    <h2>{module.title}</h2>
                    <p>{module.description}</p>
                    {module.estimated_minutes && <span className="lesson-muted">{module.estimated_minutes} minutes</span>}
                  </div>
                  <span className="difficulty-label">{moduleCompleted}/{module.topics.length} topics complete</span>
                </div>
                {module.learning_objectives?.length > 0 && (
                  <div className="path-course-objectives">
                    <p className="eyebrow">Module objectives</p>
                    <ul>{module.learning_objectives.map((objective) => <li key={objective}>{objective}</li>)}</ul>
                  </div>
                )}
                {module.practical_exercises?.length > 0 && (
                  <p className="prerequisite-line"><strong>Practice:</strong> {module.practical_exercises.join(" · ")}</p>
                )}
                <div className="module-topic-list">
                  {module.topics.map((topic, topicIndex) => {
                    const pendingAssessment = path.pending_assessments?.find(
                      (assessment) => assessment.topic_id === topic.topic_id,
                    );
                    const canOpen = topic.status === "completed" || topic.topic_id === path.current_topic_id;
                    return (
                      <article className={`path-card ${topic.status}`} key={topic.topic_id}>
                        <div className="path-index">{String(topicIndex + 1).padStart(2, "0")}</div>
                        <div className="path-card-main">
                          <div className="path-card-heading">
                            <div>
                              <p className="path-status">{topic.status}</p>
                              {canOpen
                                ? <Link className="path-topic-link" to={`/learn/${learnerId}?course_id=${encodeURIComponent(path.course_id || "")}&topic_id=${encodeURIComponent(topic.topic_id)}`}><h3>{topic.title}</h3></Link>
                                : <h3>{topic.title}</h3>}
                            </div>
                            <span className="difficulty-label">{topic.difficulty}</span>
                          </div>
                          {topic.prerequisites?.length > 0 && <p className="prerequisite-line"><strong>Prerequisites:</strong> {topic.prerequisites.join(", ")}</p>}
                          {pendingAssessment && <Link className="text-link" to={`/assessment/${learnerId}/${pendingAssessment.assessment_id}?course_id=${encodeURIComponent(path.course_id || "")}`}>Resume assessment</Link>}
                        </div>
                        {topic.status === "completed" && <Link className="current-marker" to={`/learn/${learnerId}?course_id=${encodeURIComponent(path.course_id || "")}&topic_id=${encodeURIComponent(topic.topic_id)}`} aria-label={`Review ${topic.title}`}>Review</Link>}
                        {topic.topic_id === path.current_topic_id && topic.status !== "completed" && <Link className="current-marker" to={`/learn/${learnerId}?course_id=${encodeURIComponent(path.course_id || "")}&topic_id=${encodeURIComponent(topic.topic_id)}`} aria-label={`Open ${topic.title}`}>Start</Link>}
                      </article>
                    );
                  })}
                </div>
              </article>
            );
          })}
        </section>
      </main>
    </div>
  );
}

function LearningExperiencePage() {
  const { learnerId } = useParams();
  const [searchParams] = useSearchParams();
  const courseId = searchParams.get("course_id");
  const topicId = searchParams.get("topic_id");
  const navigate = useNavigate();
  const [currentTopic, setCurrentTopic] = useState(null);
  const [learningContent, setLearningContent] = useState(null);
  const [error, setError] = useState("");
  const [isCompleting, setIsCompleting] = useState(false);
  const [isGeneratingAssessment, setIsGeneratingAssessment] = useState(false);
  const [assessmentSetup, setAssessmentSetup] = useState(false);
  const [pendingAssessment, setPendingAssessment] = useState(null);
  const [selectedTypes, setSelectedTypes] = useState(["mcq"]);
  const [questionCount, setQuestionCount] = useState(7);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [focusedSection, setFocusedSection] = useState(null);
  const [sectionTutorPrompt, setSectionTutorPrompt] = useState(null);
  const [isTutorOpen, setIsTutorOpen] = useState(false);
  const [startTutorWithVoice, setStartTutorWithVoice] = useState(null);
  const closeLessonTutor = useCallback(() => setIsTutorOpen(false), []);

  useEffect(() => {
    setCurrentTopic(null);
    setLearningContent(null);
    setFocusedSection(null);
    setSectionTutorPrompt(null);
    setIsTutorOpen(false);
    setStartTutorWithVoice(null);
    getCurrentTopic(learnerId, courseId, topicId)
      .then((topic) => {
        setCurrentTopic(topic);
        setSelectedTypes(recommendedTypesByTrack[topic.track_id] || ["mcq", "scenario", "conceptual"]);
        return Promise.all([
          getLearningContent(learnerId, topic.topic_id),
          getPendingAssessment(learnerId, topic.topic_id),
        ]);
      })
      .then(([content, pending]) => {
        setLearningContent(content);
        setPendingAssessment(pending);
      })
      .catch((requestError) => setError(requestError.message));
  }, [learnerId, courseId, topicId, loadAttempt]);

  async function handleComplete() {
    setError("");
    setIsCompleting(true);
    try {
      await completeTopic(learnerId, currentTopic.topic_id);
      const pending = await getPendingAssessment(learnerId, currentTopic.topic_id);
      if (pending) {
        navigate(`/assessment/${learnerId}/${pending.assessment_id}?course_id=${encodeURIComponent(courseId || currentTopic.course_id || "")}`);
      } else {
        setAssessmentSetup(true);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsCompleting(false);
    }
  }

  function toggleAssessmentType(type) {
    setSelectedTypes((current) => current.includes(type)
      ? current.filter((selected) => selected !== type)
      : [...current, type]);
  }

  function focusTutorOnSection(sectionTitle, subsectionTitle, text, useVoice = false, prompt = null) {
    setFocusedSection({
      section_title: sectionTitle,
      subsection_title: subsectionTitle || null,
      content: text.slice(0, 5000),
    });
    setSectionTutorPrompt(prompt ? { id: Date.now(), text: prompt } : null);
    setStartTutorWithVoice(useVoice ? Date.now() : null);
    setIsTutorOpen(true);
  }

  function clearTutorSection() {
    setFocusedSection(null);
    setSectionTutorPrompt(null);
  }

  async function handleGenerateAssessment() {
    if (!selectedTypes.length) {
      setError("Select at least one assessment type.");
      return;
    }
    setError("");
    setIsGeneratingAssessment(true);
    try {
      const assessment = await generateAssessment(learnerId, currentTopic.topic_id, {
        selected_types: selectedTypes,
        question_count: questionCount,
      });
      navigate(`/assessment/${learnerId}/${assessment.assessment_id}?course_id=${encodeURIComponent(courseId || currentTopic.course_id || "")}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsGeneratingAssessment(false);
    }
  }

  if (error && !learningContent) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><button className="secondary-button" onClick={() => { setError(""); setLoadAttempt((attempt) => attempt + 1); }} type="button">Retry lesson</button><Link className="text-link" to={`/learning-path/${learnerId}?course_id=${encodeURIComponent(courseId || "")}`}>Return to course</Link></main></div>;
  if (!currentTopic || !learningContent) return <div className="app-shell"><main className="center-state"><span className="loading-mark">● ● ●</span><WaitMessage>Generating your lesson...</WaitMessage></main></div>;

  const content = learningContent.content;
  const lessonNavigation = [
    { id: "lesson-introduction", label: "Introduction" },
    ...content.sections.map((section, index) => ({
      id: `lesson-section-${index}`,
      label: section.title,
    })),
    ...(content.code_examples.length ? [{ id: "lesson-code-examples", label: "Code examples" }] : []),
    ...(content.common_mistake_details.length ? [{ id: "lesson-mistakes", label: "Common mistakes" }] : []),
    ...(content.self_check.length ? [{ id: "lesson-self-check", label: "Quick self-check" }] : []),
    ...(content.key_takeaways.length ? [{ id: "lesson-takeaways", label: "Key takeaways" }] : []),
  ];
  return (
    <div className="app-shell">
      <main className="lesson-shell">
        <header className="lesson-heading">
          <div><p className="eyebrow">{currentTopic.module_order ? `Module ${currentTopic.module_order} / ` : ""}Topic {currentTopic.position} of {currentTopic.total_topics}</p><h1>{currentTopic.module_title || currentTopic.title}</h1>{currentTopic.module_description && <p className="hero-copy">{currentTopic.module_description}</p>}<p className="lesson-muted"><strong>Current topic:</strong> {currentTopic.title}. {content.overview}</p></div>
          <div className="lesson-status"><span>{learningContent.source === "cache" ? "Saved personalized lesson" : learningContent.source === "openrouter" ? "Personalized lesson" : "Curated lesson"}</span><strong>{currentTopic.status.replace("_", " ")}</strong></div>
        </header>
        <div className="lesson-layout">
          <aside className="lesson-sidebar">
            <p className="section-label">In this lesson</p>
            <nav className="lesson-module-nav" aria-label="Module sections">{lessonNavigation.map((item) => <a href={`#${item.id}`} key={item.id}>{item.label}</a>)}</nav>
            {currentTopic.module_learning_objectives?.length > 0 && <><p className="section-label">Module objectives</p><ul>{currentTopic.module_learning_objectives.map((objective) => <li key={objective}>{objective}</li>)}</ul></>}
            <p className="section-label">Learning objectives</p>
            <ul>{content.learning_objectives.map((objective) => <li key={objective}>{objective}</li>)}</ul>
            {(content.prerequisites.length > 0 || currentTopic.prerequisites.length > 0) && <><p className="section-label">Prerequisites</p><p className="lesson-muted">{content.prerequisites.length ? content.prerequisites.join(", ") : currentTopic.prerequisites.join(", ")}</p></>}
            {content.recommended_focus.length > 0 && <><p className="section-label">Recommended focus</p><div className="concept-tags">{content.recommended_focus.map((concept) => <span key={concept}>{concept.replaceAll("_", " ")}</span>)}</div></>}
          </aside>
          <article className="lesson-content">
            <section className="lesson-section lesson-introduction" id="lesson-introduction"><p className="eyebrow">Introduction</p><h2>{content.title}</h2><p>{content.introduction}</p><h3>Why this topic matters</h3><p>{content.why_it_matters}</p>{content.analogy && <blockquote>{content.analogy}</blockquote>}<div className="lesson-tutor-invite"><span>💡 Have a doubt about this topic?</span><button className="text-link" onClick={() => focusTutorOnSection("Introduction", content.title, `${content.introduction}\n${content.why_it_matters}\n${content.analogy || ""}`)} type="button">Ask AI Tutor</button></div></section>
            {content.sections.map((section, sectionIndex) => {
              const sectionText = [
                section.summary,
                ...section.subsections.flatMap((subsection) => [
                  subsection.title,
                  subsection.explanation,
                  ...subsection.key_points,
                  ...subsection.examples,
                  subsection.practical_application,
                ]),
              ].filter(Boolean).join("\n");
              return (
                <section className="lesson-section structured-lesson-section" id={`lesson-section-${sectionIndex}`} key={section.title}>
                    <p className="eyebrow">Lesson section</p><h2>{section.title}</h2><p className="lesson-section-summary">{section.summary}</p>
                    <button className="text-link section-level-tutor-action" onClick={() => focusTutorOnSection(section.title, null, sectionText)} type="button">💡 Have a doubt about this section? Ask AI Tutor</button>
                    <div className="lesson-subsection-grid">
                      {section.subsections.map((subsection) => {
                        const subsectionText = [
                          subsection.explanation,
                          ...subsection.key_points,
                          ...subsection.examples,
                          subsection.practical_application,
                        ].filter(Boolean).join("\n");
                        return (
                          <article className="lesson-subsection-card" key={`${section.title}-${subsection.title}`}>
                            <p className="eyebrow">🧠 Concept</p><h3>{subsection.title}</h3><p>{subsection.explanation}</p>
                            {subsection.key_points.length > 0 && <div className="lesson-detail-block"><strong>Important points</strong><ul>{subsection.key_points.map((point) => <li key={point}>{point}</li>)}</ul></div>}
                            {subsection.examples.length > 0 && <div className="lesson-detail-block example-detail"><strong>💡 Example</strong>{subsection.examples.map((example) => <p key={example}>{example}</p>)}</div>}
                            {subsection.practical_application && <div className="lesson-detail-block"><strong>🎯 Practical application</strong><p>{subsection.practical_application}</p></div>}
                            {subsection.tutor_prompts.length > 0 && <div className="section-tutor-prompts"><strong>🤖 Ask about this concept</strong>{subsection.tutor_prompts.map((prompt) => <button className="text-link" key={prompt} onClick={() => focusTutorOnSection(section.title, subsection.title, subsectionText, false, prompt)} type="button">{prompt}</button>)}</div>}
                            <div className="section-tutor-actions">
                              <button className="text-link" onClick={() => focusTutorOnSection(section.title, subsection.title, subsectionText)} type="button">💡 Have a doubt? Ask AI Tutor</button>
                              <button className="text-link" onClick={() => focusTutorOnSection(section.title, subsection.title, subsectionText, true)} type="button">🎤 Ask by Voice</button>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                </section>
              );
            })}
            {content.important_points.length > 0 && <section className="lesson-section lesson-card-section"><p className="eyebrow">📌 Important points</p><ul>{content.important_points.map((point) => <li key={point}>{point}</li>)}</ul></section>}
            {content.code_examples.map((example, codeIndex) => (
              <section className="lesson-section lesson-code-card" id={codeIndex === 0 ? "lesson-code-examples" : undefined} key={example.title}>
                <p className="eyebrow">💻 Code · {example.language}</p><h2>{example.title}</h2>
                <pre><code>{example.code}</code></pre><p>{example.explanation}</p>
                {example.expected_output && <p><strong>Expected output:</strong> <code>{example.expected_output}</code></p>}
                <div className="section-tutor-actions">
                  <button className="text-link" onClick={() => focusTutorOnSection("Code example", example.title, `${example.explanation}\n${example.code}\nExpected output: ${example.expected_output || "not specified"}`)} type="button">💡 Have a doubt? Ask AI Tutor</button>
                  <button className="text-link" onClick={() => focusTutorOnSection("Code example", example.title, `${example.explanation}\n${example.code}`, true)} type="button">🎤 Ask by Voice</button>
                </div>
              </section>
            ))}
            {content.common_mistake_details.length > 0 && <section className="lesson-section lesson-mistakes" id="lesson-mistakes"><p className="eyebrow">⚠ Common mistakes</p><div className="lesson-detail-grid">{content.common_mistake_details.map((item) => <article className="lesson-detail-card" key={item.mistake}><h3>{item.mistake}</h3><p>{item.explanation}</p><p><strong>Correction:</strong> {item.correction}</p><button className="text-link" onClick={() => focusTutorOnSection("Common mistake", item.mistake, `${item.explanation}\nCorrection: ${item.correction}`)} type="button">Ask AI Tutor about this mistake</button></article>)}</div></section>}
            {content.self_check.length > 0 && <section className="lesson-section lesson-card-section" id="lesson-self-check"><p className="eyebrow">📝 Quick self-check</p>{content.self_check.map((item) => <details className="lesson-self-check" key={item.question}><summary>{item.question}</summary><p><strong>Hint:</strong> {item.hint}</p><button className="text-link" onClick={() => focusTutorOnSection("Self-check", item.question, `Question: ${item.question}\nHint: ${item.hint}`, false, `Help me reason through this self-check without giving away an answer: ${item.question}`)} type="button">Not sure? Ask AI Tutor</button></details>)}</section>}
            {content.key_takeaways.length > 0 && <section className="lesson-section lesson-card-section lesson-takeaways" id="lesson-takeaways"><p className="eyebrow">🎯 Key takeaways</p><ul>{content.key_takeaways.map((item) => <li key={item}>{item}</li>)}</ul></section>}
            <section className="note-strip practice-suggestion"><strong>🎯 Practice:</strong> {content.practice_suggestion} <span>{content.assessment_recommendation}</span></section>
            <ErrorMessage message={error} />
            {pendingAssessment && <section className="assessment-setup-panel"><p className="eyebrow">Assessment in progress</p><p>You have saved answers for this topic.</p><Link className="primary-button" to={`/assessment/${learnerId}/${pendingAssessment.assessment_id}?course_id=${encodeURIComponent(courseId || currentTopic.course_id || "")}`}>Resume assessment</Link></section>}
            {assessmentSetup && <section className="assessment-setup-panel"><p className="eyebrow">Personalized assessment</p><h2>Choose how to check your understanding.</h2><p>Select one or more question types. Recommended for this track: {((recommendedTypesByTrack[currentTopic.track_id] || ["mcq", "scenario", "conceptual"]).map((type) => assessmentTypes.find(([key]) => key === type)?.[1])).join(", ")}.</p><div className="assessment-type-grid">{assessmentTypes.map(([type, label, description]) => <label className="assessment-type-option" key={type}><input checked={selectedTypes.includes(type)} onChange={() => toggleAssessmentType(type)} type="checkbox" /><span><strong>{label}</strong><small>{description}</small></span></label>)}</div><label className="question-count-label">Question count<select value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))}>{[4, 5, 6, 7, 8, 10].map((count) => <option key={count} value={count}>{count}</option>)}</select></label><button className="primary-button" disabled={isGeneratingAssessment || selectedTypes.length === 0} onClick={handleGenerateAssessment} type="button">{isGeneratingAssessment ? "Generating your personalized assessment..." : "Generate assessment"}</button></section>}
            <div className="lesson-actions"><button className="primary-button" disabled={isCompleting || assessmentSetup || Boolean(pendingAssessment) || currentTopic.status === "completed"} onClick={handleComplete} type="button">{currentTopic.status === "completed" ? "Topic passed" : isCompleting ? "Saving progress..." : pendingAssessment ? "Assessment saved" : assessmentSetup ? "Topic completed" : "Take assessment"}</button><Link className="text-link" to={`/learning-path/${learnerId}?course_id=${encodeURIComponent(courseId || currentTopic.course_id || "")}`}>Back to course</Link></div>
          </article>
        </div>
        <TutorPage learnerId={learnerId} topicId={currentTopic.topic_id} courseId={courseId || currentTopic.course_id} embedded isOpen={isTutorOpen} onClose={closeLessonTutor} sectionContext={focusedSection} sectionPrompt={sectionTutorPrompt} startWithVoiceId={startTutorWithVoice} onClearSectionContext={clearTutorSection} />
      </main>
    </div>
  );
}

function TutorPage({
  learnerId: learnerIdProp,
  topicId: topicIdProp,
  courseId: courseIdProp,
  embedded = false,
  isOpen = true,
  onClose,
  sectionContext: sectionContextProp = null,
  sectionPrompt: sectionPromptProp = null,
  startWithVoiceId = null,
  onClearSectionContext,
}) {
  const routeParams = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const learnerId = learnerIdProp || routeParams.learnerId;
  const topicId = topicIdProp || searchParams.get("topic_id");
  const courseId = courseIdProp || searchParams.get("course_id");
  const [context, setContext] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [styleChooserMessageId, setStyleChooserMessageId] = useState(null);
  const [draft, setDraft] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [voiceState, setVoiceState] = useState("idle");
  const [voiceError, setVoiceError] = useState("");
  const [isMuted, setIsMuted] = useState(false);
  const [reloadContextKey, setReloadContextKey] = useState(0);
  const recognitionRef = useRef(null);
  const utteranceRef = useRef(null);
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  useEffect(() => {
    if (!sectionPromptProp?.text) return;
    setDraft(sectionPromptProp.text);
    if (embedded && isOpen) sendMessage(sectionPromptProp.text);
  }, [sectionPromptProp?.id]);

  useEffect(() => {
    let active = true;
    recognitionRef.current?.stop();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setVoiceState("idle");
    setContext(null);
    setConversation(null);
    setMessages([]);
    setError("");
    if (!topicId) {
      setError("Choose a learning topic before opening the tutor.");
      setIsLoading(false);
      return () => { active = false; };
    }
    setIsLoading(true);
    Promise.all([
      getTutorContext(learnerId, topicId),
      listTutorConversations(learnerId, topicId),
    ])
      .then(async ([nextContext, priorConversations]) => {
        if (!active) return;
        setContext(nextContext);
        setConversations(priorConversations);
        if (priorConversations.length) {
          const latest = await getTutorConversation(learnerId, priorConversations[0].id);
          if (active) {
            setConversation(priorConversations[0]);
            setMessages(latest.messages);
          }
        } else {
          setConversation(null);
          setMessages([]);
        }
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, [learnerId, topicId, reloadContextKey]);

  useEffect(() => {
    if (!embedded || !isOpen) return undefined;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => closeButtonRef.current?.focus());
    function handleDialogKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose?.();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll(
        'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), a[href]',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", handleDialogKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleDialogKeyDown);
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, [embedded, isOpen, onClose]);

  async function openConversation(item) {
    setError("");
    try {
      const loaded = await getTutorConversation(learnerId, item.id);
      setConversation(item);
      setMessages(loaded.messages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function startConversation() {
    setError("");
    try {
      const created = await createTutorConversation(learnerId, topicId);
      setConversation(created);
      setMessages([]);
      setConversations((items) => [created, ...items.filter((item) => item.id !== created.id)]);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function speakResponse(text) {
    if (isMuted) {
      setVoiceState("idle");
      return;
    }
    if (!("speechSynthesis" in window) || typeof window.SpeechSynthesisUtterance !== "function") {
      setVoiceState("idle");
      setVoiceError("Speech playback is not supported in this browser. The tutor response is available as text.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = navigator.language || "en-US";
    utterance.onend = () => setVoiceState("idle");
    utterance.onerror = () => {
      setVoiceState("idle");
      setVoiceError("Speech playback could not start. The tutor response is available as text.");
    };
    utteranceRef.current = utterance;
    setVoiceState("speaking");
    window.speechSynthesis.speak(utterance);
  }

  async function beginAssessment(weakPractice = false) {
    if (!context || !topicId) return;
    try {
      await completeTopic(learnerId, topicId);
      const pending = await getPendingAssessment(learnerId, topicId);
      if (pending) {
        navigate(`/assessment/${learnerId}/${pending.assessment_id}?course_id=${encodeURIComponent(courseId || context.course?.course_id || "")}`);
        return;
      }
      const topicConcepts = context.current_topic.concepts || [];
      const hasWeakTopicConcept = context.weak_concepts.some(
        (item) => topicConcepts.includes(item.concept),
      );
      const selectedTypes = weakPractice && hasWeakTopicConcept
        ? ["conceptual", "scenario"]
        : (recommendedTypesByTrack[context.course?.track_id] || ["mcq", "conceptual", "scenario"]);
      const assessment = await generateAssessment(learnerId, topicId, {
        selected_types: selectedTypes,
        question_count: Math.max(4, selectedTypes.length),
      });
      navigate(`/assessment/${learnerId}/${assessment.assessment_id}?course_id=${encodeURIComponent(courseId || context.course?.course_id || "")}`);
    } catch (requestError) {
      setError(requestError.message);
      setVoiceState("idle");
    }
  }

  async function sendMessage(value = draft, options = {}) {
    const content = value.trim();
    if (!content || isSending) return;
    setError("");
    setVoiceError("");
    setIsSending(true);
    setPendingQuestion(content);
    if (options.fromVoice) setVoiceState("processing");
    try {
      let activeConversation = conversation;
      if (!activeConversation) {
        activeConversation = await createTutorConversation(learnerId, topicId);
        setConversation(activeConversation);
        setConversations((items) => [activeConversation, ...items]);
      }
      const result = await sendTutorMessage(
        learnerId,
        activeConversation.id,
        content,
        sectionContextProp,
        options.teachingStyle || null,
      );
      setMessages((items) => [...items, result.user_message, result.assistant_message]);
      setConversations((items) => items.map((item) => (
        item.id === activeConversation.id
          ? { ...item, updated_at: result.assistant_message.created_at }
          : item
      )));
      setDraft("");
      if (options.fromVoice) speakResponse(result.response.direct_answer || result.response.answer);
      if (/\bquiz me\b|\bstart (?:a )?quiz\b|\btest me\b/i.test(content)) {
        await beginAssessment(false);
      } else if (/\bpractice (?:my )?weak area\b|\bpractice weak\b/i.test(content)) {
        await beginAssessment(true);
      }
    } catch (requestError) {
      setError(requestError.message);
      setDraft(content);
      if (options.fromVoice) setVoiceState("idle");
    } finally {
      setIsSending(false);
      setPendingQuestion("");
    }
  }

  const actions = sectionContextProp
    ? [
      "Explain this simply",
      "Give an example for this section",
      "Give an analogy for this section",
      "Why is this section important?",
      "Show code for this section",
      "Give a real-world use case for this section",
      "Compare this with a related concept",
      "Quiz me on this section",
      "Give me a practice problem for this section",
    ]
    : [
      "Explain this topic",
      "Explain differently",
      "Give me an example",
      "Teach me using an analogy",
      "Show code for this topic",
      "Quiz me",
      "Practice my weak area",
      "Give me a hint",
      "Summarize this topic",
      "Compare related concepts",
    ];
  const focusTitle = sectionContextProp
    ? sectionContextProp.subsection_title || sectionContextProp.section_title
    : context?.current_topic.title || "this topic";
  const contextualSuggestions = [
    `How does ${focusTitle} work in ${context?.current_topic.title || "this topic"}?`,
    `Can you explain ${focusTitle} with a simple example?`,
    `Why is ${focusTitle} useful in this lesson?`,
    `What is a common mistake when using ${focusTitle}?`,
  ].filter((question, index, questions) => (
    question.trim() && questions.findIndex((item) => item.toLowerCase() === question.toLowerCase()) === index
  ));

  useEffect(() => {
    if (embedded && isOpen && startWithVoiceId) startVoiceRecognition();
  }, [embedded, isOpen, startWithVoiceId]);

  const TutorContainer = embedded ? "section" : "main";
  function startVoiceRecognition() {
    setVoiceError("");
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceState("unsupported");
      setVoiceError("Voice input is not supported in this browser. You can type your question.");
      return;
    }
    recognitionRef.current?.stop();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    const recognition = new Recognition();
    recognition.lang = navigator.language || "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => setVoiceState("listening");
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        if (event.results[index].isFinal) transcript += event.results[index][0].transcript;
      }
      if (transcript.trim()) {
        setDraft(transcript.trim());
        recognition.stop();
        sendMessage(transcript.trim(), { fromVoice: true });
      }
    };
    recognition.onerror = (event) => {
      setVoiceState("error");
      setVoiceError(event.error === "not-allowed"
        ? "Microphone permission was denied. You can type your question instead."
        : "Voice input could not be completed. You can type your question instead.");
    };
    recognition.onend = () => {
      setVoiceState((state) => state === "listening" ? "idle" : state);
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      setVoiceState("error");
      setVoiceError("Voice input could not start. You can type your question instead.");
      recognitionRef.current = null;
    }
  }

  function stopVoice() {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setVoiceState("idle");
  }

  function toggleMute() {
    setIsMuted((muted) => !muted);
    if (!isMuted && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setVoiceState("idle");
    }
  }

  if (embedded && !isOpen) return null;
  if (isLoading) return embedded
    ? <div className="tutor-modal-backdrop"><section className="tutor-shell is-embedded tutor-modal" role="dialog" aria-modal="true" aria-label="AI Tutor"><button ref={closeButtonRef} className="tutor-close-button" aria-label="Close AI Tutor" onClick={onClose} type="button">×</button><p role="status">Preparing your learning context...</p></section></div>
    : <div className="app-shell"><main className="center-state"><span className="loading-mark">● ● ●</span><p>Preparing your learning context...</p></main></div>;
  if (!context) return embedded
    ? <div className="tutor-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose?.(); }}><section ref={dialogRef} className="tutor-shell is-embedded tutor-modal" role="dialog" aria-modal="true" aria-labelledby="tutor-modal-title"><header className="tutor-modal-heading"><h1 id="tutor-modal-title">AI Tutor</h1><button ref={closeButtonRef} className="tutor-close-button" aria-label="Close AI Tutor" onClick={onClose} type="button">×</button></header><ErrorMessage message={error} /><div className="tutor-error-actions"><button className="secondary-button" onClick={() => setReloadContextKey((key) => key + 1)} type="button">Retry</button><button className="text-link" onClick={onClose} type="button">Continue reading</button></div></section></div>
    : <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to={`/learning-path/${learnerId}${courseId ? `?course_id=${encodeURIComponent(courseId)}` : ""}`}>Return to learning path</Link></main></div>;

  return (
    <div
      className={embedded ? "tutor-modal-backdrop" : "app-shell"}
      onMouseDown={embedded ? (event) => { if (event.target === event.currentTarget) onClose?.(); } : undefined}
    >
      <TutorContainer className={embedded ? "tutor-shell is-embedded tutor-modal" : "tutor-shell"} ref={dialogRef} role={embedded ? "dialog" : undefined} aria-modal={embedded ? "true" : undefined} aria-labelledby={embedded ? "tutor-modal-title" : undefined}>
        {!embedded && <div className="page-back-row"><Link className="back-link" to={`/learn/${learnerId}?course_id=${encodeURIComponent(courseId || "")}&topic_id=${encodeURIComponent(topicId)}`}>← Back to lesson</Link></div>}
        {embedded && <header className="tutor-modal-heading"><div><p className="eyebrow">🤖 Context-aware AI Tutor</p><h1 id="tutor-modal-title">Ask about what you’re learning</h1><p>Ask a question, explore an example, or work through a doubt.</p></div><button ref={closeButtonRef} className="tutor-close-button" aria-label="Close AI Tutor" onClick={onClose} type="button">×</button></header>}
        <header className="tutor-context-card">
          {embedded && <p className="eyebrow">Current learning context</p>}
          {!embedded && <p className="eyebrow">Context-aware AI Tutor</p>}
          <h1>{context.current_topic.title}</h1>
          <p>{context.course?.title || context.track} · {context.track} · {context.experience_level}</p>
          <p><strong>Your goal:</strong> {context.goal}</p>
          {context.completed_topics.length > 0 && <p><strong>Building on:</strong> {context.completed_topics.map((item) => item.title).join(", ")}</p>}
          {context.weak_concepts.length > 0 && <div><strong>Focus areas</strong><div className="mini-tags weak-tags">{context.weak_concepts.slice(0, 6).map((item) => <span key={item.concept}>{item.concept.replaceAll("_", " ")}</span>)}</div></div>}
          {context.strong_concepts.length > 0 && <p><strong>Known strengths:</strong> {context.strong_concepts.slice(0, 5).map((item) => item.concept.replaceAll("_", " ")).join(", ")}</p>}
          {sectionContextProp && <div className="tutor-section-focus"><p className="eyebrow">Section focus</p><strong>{sectionContextProp.subsection_title || sectionContextProp.section_title}</strong><p>{sectionContextProp.content.slice(0, 360)}</p><button className="text-link" onClick={onClearSectionContext} type="button">Clear section focus</button></div>}
        </header>
        {embedded && <section className="tutor-modal-suggestions" aria-label="Suggested questions"><p className="eyebrow">Try asking</p>{contextualSuggestions.map((question) => <button disabled={isSending} key={question} onClick={() => sendMessage(question)} type="button">{question}</button>)}</section>}
        <div className="tutor-workspace">
          <aside className="tutor-history">
            <h2>Previous conversations</h2>
            <button className="secondary-button" onClick={startConversation} type="button">New conversation</button>
            {conversations.length ? conversations.map((item) => (
              <button className={`tutor-history-item${conversation?.id === item.id ? " is-active" : ""}`} key={item.id} onClick={() => openConversation(item)} type="button">{item.title}</button>
            )) : <p className="empty-copy">Your conversations for this topic will appear here.</p>}
          </aside>
          <section className="tutor-chat">
            <div className="tutor-messages" aria-live="polite">
              {messages.length ? messages.map((message, index) => (
                <article className={`tutor-chat-message ${message.role}`} key={message.id}>
                  <p className="eyebrow">{message.role === "assistant" ? "Tutor" : "You"}</p>
                  <p>{message.response?.direct_answer || message.content}</p>
                  {message.response?.key_points?.length > 0 && <div className="tutor-structured-answer"><strong>Key points</strong><ul>{message.response.key_points.map((point) => <li key={point}>{point}</li>)}</ul></div>}
                  {message.response?.step_by_step?.length > 0 && <div className="tutor-structured-answer"><strong>Step by step</strong><ol>{message.response.step_by_step.map((step) => <li key={step}>{step}</li>)}</ol></div>}
                  {message.response?.example && <p><strong>Example:</strong> {message.response.example}</p>}
                  {message.response?.practical_application && <p><strong>In practice:</strong> {message.response.practical_application}</p>}
                  {message.response?.common_mistake && <p><strong>Common mistake:</strong> {message.response.common_mistake}</p>}
                  {message.response?.takeaway && <p><strong>Takeaway:</strong> {message.response.takeaway}</p>}
                  {message.response?.weak_area_addressed && <span className="tutor-weak-tag">Focused on {message.response.weak_area_addressed.replaceAll("_", " ")}</span>}
                  {message.response?.teaching_approach && <small>{message.response.teaching_approach} · {message.response.difficulty}</small>}
                  {(message.response?.follow_up_question || message.response?.suggested_follow_up) && <button className="text-link" disabled={isSending} onClick={() => sendMessage(message.response.follow_up_question || message.response.suggested_follow_up)} type="button">{message.response.follow_up_question || message.response.suggested_follow_up}</button>}
                  {message.response && index === messages.length - 1 && <div className="tutor-teach-differently">
                    <button
                      className="text-link"
                      disabled={isSending}
                      aria-expanded={styleChooserMessageId === message.id}
                      onClick={() => setStyleChooserMessageId(
                        (current) => current === message.id ? null : message.id,
                      )}
                      type="button"
                    >
                      Teach me differently
                    </button>
                    {styleChooserMessageId === message.id && <div className="tutor-teaching-styles" aria-label="Choose a different teaching style">
                      {tutorTeachingStyles.map(([style, label]) => (
                        <button
                          className="secondary-button"
                          disabled={isSending || message.response.teaching_approach.toLowerCase() === label.toLowerCase()}
                          key={style}
                          onClick={() => sendMessage(
                            "I didn't understand that explanation. Please re-explain the same concept.",
                            { teachingStyle: style },
                          )}
                          type="button"
                        >
                          {label}
                        </button>
                      ))}
                    </div>}
                  </div>}
                </article>
              )) : !pendingQuestion && <div className="empty-copy"><h2>What would you like to understand?</h2><p>Your answers build on your completed topics and focus on relevant learning gaps.</p></div>}
              {pendingQuestion && <article className="tutor-chat-message user"><p className="eyebrow">You</p><p>{pendingQuestion}</p></article>}
              {isSending && <p role="status">Tutor is preparing a context-aware explanation...</p>}
            </div>
            {!embedded && <div className="tutor-suggested-actions">{actions.map((action) => <button disabled={isSending} key={action} onClick={() => sendMessage(action)} type="button">{action}</button>)}</div>}
            <details className="voice-tutor" id="tutor-voice-controls" open={!embedded}>
              <summary className="voice-tutor-summary">🎤 AI Voice Tutor</summary>
              <div className="voice-tutor-heading"><div><p className="eyebrow">AI Voice Tutor</p><h3>Talk through this module</h3></div><span className={`voice-state ${voiceState}`} role="status">{voiceState === "idle" ? "Ready" : voiceState === "listening" ? "Listening..." : voiceState === "processing" ? "Thinking..." : voiceState === "speaking" ? "Speaking..." : voiceState === "unsupported" ? "Voice input unavailable" : "Voice error"}</span></div>
              <p>{sectionContextProp ? `Speak a question about ${sectionContextProp.subsection_title || sectionContextProp.section_title} in ${context.current_topic.title}.` : `Speak a question about ${context.current_topic.title}.`} Your transcript and response use this same saved tutor conversation.</p>
              <div className="voice-tutor-controls">
                <button className="primary-button" disabled={isSending || voiceState === "listening" || voiceState === "processing" || voiceState === "speaking"} onClick={startVoiceRecognition} type="button">🎤 Talk to AI Tutor</button>
                <button className="secondary-button" disabled={voiceState !== "listening" && voiceState !== "speaking"} onClick={stopVoice} type="button">Stop</button>
                <button className="secondary-button" aria-pressed={isMuted} disabled={!("speechSynthesis" in window) || typeof window.SpeechSynthesisUtterance !== "function"} onClick={toggleMute} type="button">{isMuted ? "Unmute" : "Mute"}</button>
              </div>
              {voiceState === "listening" && <p className="voice-transcript-hint">Listening for your question about this module…</p>}
              {voiceError && <p className="voice-error" role="status">{voiceError}</p>}
              {!("speechSynthesis" in window) && <p className="voice-transcript-hint">Speech playback is not supported; tutor responses will remain available as text.</p>}
            </details>
            <form className="tutor-composer" onSubmit={(event) => { event.preventDefault(); sendMessage(); }}>
              <textarea aria-label="Message your tutor" maxLength={2000} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} onChange={(event) => setDraft(event.target.value)} placeholder={`Ask about ${focusTitle}...`} rows="3" value={draft} />
              <button className="primary-button" disabled={isSending || !draft.trim()} type="submit">{isSending ? "Thinking..." : "Send"}</button>
            </form>
            {error && <div className="tutor-error-panel"><ErrorMessage message={error} /><div className="tutor-error-actions"><button className="secondary-button" disabled={isSending || !draft.trim()} onClick={() => sendMessage(draft)} type="button">Retry</button>{embedded && <button className="text-link" onClick={onClose} type="button">Continue reading</button>}</div></div>}
          </section>
        </div>
      </TutorContainer>
    </div>
  );
}

function AssessmentResult({ learnerId, result, onRetry, isRetrying, onBack, onAskTutor }) {
  const weak = result.weak_concepts || [];
  const courseQuery = result.course_id
    ? `?course_id=${encodeURIComponent(result.course_id)}`
    : "";
  return (
    <main className="assessment-result-shell">
      <section className="result-heading"><button className="back-link" onClick={onBack} type="button">← Back</button><p className="eyebrow">Assessment result / {result.topic_title}</p><h1>Now we know what changed.</h1><p className="hero-copy">Your result is now part of the learner state that controls what comes next.</p><div className="result-score"><strong>{result.percentage}%</strong><span>{result.earned_points ?? result.correct_count} / {result.total_points ?? result.total_questions} points</span></div></section>
      {Object.keys(result.type_results || {}).length > 0 && <section className="type-results-panel"><h2>Performance by assessment type</h2><div className="type-results-grid">{Object.entries(result.type_results).map(([type, score]) => <div className="type-result" key={type}><div><strong>{assessmentTypes.find(([key]) => key === type)?.[1] || type}</strong><span>{score.percentage}%</span></div><div className="skill-bar"><span className={score.percentage < 50 ? "skill-fill weak" : score.percentage < 80 ? "skill-fill developing" : "skill-fill strong"} style={{ width: `${score.percentage}%` }} /></div><small>{score.earned_points} / {score.total_points} points</small></div>)}</div></section>}
      <section className="result-grid"><div><h2>Concept performance</h2>{result.concept_results.map((concept) => <div className="result-concept" key={concept.concept}><div><span>{concept.concept.replaceAll("_", " ")}</span><strong>{concept.percentage}%</strong></div><div className="skill-bar"><span className={`skill-fill ${concept.level}`} style={{ width: `${concept.percentage}%` }} /></div><p>{concept.level}</p></div>)}</div><div className={`adaptation-card ${result.recommendation.action_type}`}><p className="eyebrow">What changed based on your result?</p><h2>{weak.length ? weak.map((concept) => concept.replaceAll("_", " ")).join(", ") : "Your next step"}</h2><p>{result.recommendation.summary}</p><strong>{result.recommendation.next_action}</strong>{result.recommendation.remediation && <blockquote>{result.recommendation.remediation}</blockquote>}{result.recommendation.alternative_explanation && <p><strong>Another way to think about it:</strong> {result.recommendation.alternative_explanation}</p>}{result.recommendation.example && <p><strong>Example:</strong> {result.recommendation.example}</p>}{result.recommendation.practice_suggestion && <p><strong>Targeted practice:</strong> {result.recommendation.practice_suggestion}</p>}{result.recommendation.remediation_next_action && <p><strong>Remediation next step:</strong> {result.recommendation.remediation_next_action}</p>}{result.recommendation.remediation_source && <p className="ai-source-label">{result.recommendation.remediation_source === "openrouter" ? "AI remediation" : "Deterministic remediation"}</p>}</div></section>
      {result.ai_interpretation && <section className="interpretation-panel"><p className="eyebrow">{result.ai_interpretation.source === "openrouter" ? "AI interpretation" : "Assessment interpretation"}</p><h2>{result.ai_interpretation.summary}</h2>{result.ai_interpretation.focus_concepts?.length > 0 && <p><strong>Focus next:</strong> {result.ai_interpretation.focus_concepts.map((concept) => concept.replaceAll("_", " ")).join(", ")}</p>}</section>}
      {result.question_results?.length > 0 && <section className="result-review-panel"><h2>Question feedback</h2><div className="review-list">{result.question_results.map((item) => <article className="review-item" key={item.question_id}><div className="review-header"><span>{assessmentTypes.find(([key]) => key === item.question_type)?.[1] || item.question_type}</span><strong>{item.concept.replaceAll("_", " ")}</strong><span>{item.earned_points} / {item.points} points</span></div><p>{item.feedback}</p>{item.missing_concepts?.length > 0 && <p><strong>Review:</strong> {item.missing_concepts.map((concept) => concept.replaceAll("_", " ")).join(", ")}</p>}</article>)}</div></section>}
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
                {!item.is_correct && <button className="text-link" onClick={() => onAskTutor(item)} type="button">Want to understand this? Ask AI Tutor</button>}
              </article>
            ))}
          </div>
        </section>
      )}
      <div className="result-actions"><Link className="primary-button" to={weak.length ? `/learn/${learnerId}${courseQuery}` : `/learning-path/${learnerId}${courseQuery}`}>{weak.length ? "Review weak topic" : "Continue learning"}</Link><button className="secondary-button" disabled={isRetrying} onClick={onRetry} type="button">{isRetrying ? "Preparing retry..." : "Retry assessment"}</button></div>
    </main>
  );
}

function AssessmentPage() {
  const { learnerId, assessmentId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [assessment, setAssessment] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [assessmentTutorFocus, setAssessmentTutorFocus] = useState(null);
  const [assessmentTutorPrompt, setAssessmentTutorPrompt] = useState(null);
  const [isAssessmentTutorOpen, setIsAssessmentTutorOpen] = useState(false);
  const closeAssessmentTutor = useCallback(() => setIsAssessmentTutorOpen(false), []);
  const courseId = result?.course_id || assessment?.course_id || searchParams.get("course_id");

  function handleBack() {
    const courseQuery = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
    navigate(`/learning-path/${learnerId}${courseQuery}`);
  }

  useEffect(() => {
    setAssessment(null);
    setAnswers({});
    setResult(null);
    setError("");
    getAssessment(learnerId, assessmentId).then((data) => {
      if (data.concept_results) setResult(data);
      else {
        setAssessment(data);
        setAnswers(Object.fromEntries(Object.entries(data.saved_answers || {}).map(([questionId, answer]) => [
          questionId,
          typeof answer === "object" && answer !== null && "selected_option" in answer
            ? answer.selected_option
            : answer,
        ])));
      }
    }).catch((requestError) => setError(requestError.message));
  }, [assessmentId, learnerId]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const submitted = assessment.questions.map((question) => {
        const answer = answers[question.question_id];
        return question.question_type === "mcq"
          ? { question_id: question.question_id, selected_option: answer }
          : { question_id: question.question_id, learner_answer: answer };
      });
      setResult(await submitAssessment(learnerId, assessmentId, submitted));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSaveProgress() {
    const saved = assessment.questions.flatMap((question) => {
      const answer = answers[question.question_id];
      if (answer === undefined || answer === null || answer === "") return [];
      return question.question_type === "mcq"
        ? [{ question_id: question.question_id, selected_option: answer }]
        : [{ question_id: question.question_id, learner_answer: answer }];
    });
    if (!saved.length) {
      setSaveMessage("Add at least one answer before saving.");
      return;
    }
    setError("");
    setSaveMessage("");
    setIsSaving(true);
    try {
      const updated = await saveAssessmentResponses(learnerId, assessmentId, saved);
      setAssessment(updated);
      setSaveMessage("Progress saved. You can return to this assessment later.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRetry() {
    setError("");
    setIsRetrying(true);
    try {
      const nextAssessment = await generateAssessment(learnerId, result.topic_id, {
        selected_types: result.selected_types || ["mcq"],
        question_count: result.total_questions || 3,
      });
      navigate(`/assessment/${learnerId}/${nextAssessment.assessment_id}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsRetrying(false);
    }
  }

  function askTutorAboutResult(item) {
    const correctAnswer = item.options[item.correct_option];
    setAssessmentTutorFocus({
      section_title: "Completed assessment review",
      subsection_title: item.concept.replaceAll("_", " "),
      content: [
        `Question: ${item.question}`,
        `Learner's submitted answer: ${item.selected_option === null ? "No answer submitted" : item.options[item.selected_option]}`,
        `Correct answer after submission: ${correctAnswer}`,
        `Assessment explanation: ${item.explanation}`,
      ].join("\n"),
    });
    setAssessmentTutorPrompt({
      id: Date.now(),
      text: `I got this assessment question wrong. Please help me understand the concept and why the correct answer is right: ${item.question}`,
    });
    setIsAssessmentTutorOpen(true);
  }

  if (error) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to={`/learning-path/${learnerId}?course_id=${encodeURIComponent(result?.course_id || "")}`}>Return to path</Link></main></div>;
  if (result) return <div className="app-shell"><AssessmentResult learnerId={learnerId} result={result} onRetry={handleRetry} isRetrying={isRetrying} onBack={handleBack} onAskTutor={askTutorAboutResult} />{result.topic_id && <TutorPage learnerId={learnerId} topicId={result.topic_id} courseId={courseId} embedded isOpen={isAssessmentTutorOpen} onClose={closeAssessmentTutor} sectionContext={assessmentTutorFocus} sectionPrompt={assessmentTutorPrompt} />}</div>;
  if (!assessment) return <div className="app-shell"><main className="center-state"><span className="loading-mark">● ● ●</span><WaitMessage>Preparing your assessment...</WaitMessage></main></div>;

  const hasAnswer = (question, answer) => {
    if (question.question_type === "mcq") return Number.isInteger(answer);
    if (question.question_type === "coding") return Boolean(answer?.code?.trim());
    if (question.question_type === "debugging") return Boolean(answer?.code?.trim() && answer?.bug?.trim() && answer?.explanation?.trim());
    return typeof answer === "string" && answer.trim().length > 0;
  };
  const answeredCount = assessment.questions.filter((question) => hasAnswer(question, answers[question.question_id])).length;
  const updateAnswer = (questionId, value) => setAnswers((current) => ({ ...current, [questionId]: value }));
  return <div className="app-shell"><main className="assessment-shell post-learning-assessment"><section className="assessment-heading"><button className="back-link" onClick={handleBack} type="button">← Back to learning path</button><p className="eyebrow">Assess / {assessment.topic_title}</p><h1>Show what stuck.</h1><p className="hero-copy">Answer these questions from the topic you just completed. Your result will shape the next recommendation.</p><div className="selected-type-tags">{assessment.selected_types?.map((type) => <span key={type}>{assessmentTypes.find(([key]) => key === type)?.[1] || type}</span>)}</div><div className="question-progress"><span style={{ width: `${(answeredCount / assessment.questions.length) * 100}%` }} /></div><p className="progress-copy">{answeredCount} of {assessment.questions.length} answered</p></section><form className="question-list" onSubmit={handleSubmit}>{assessment.questions.map((question, index) => <fieldset className="question-card" key={question.question_id}><legend><span>Question {index + 1} · {assessmentTypes.find(([key]) => key === question.question_type)?.[1] || question.question_type} · {question.points} {question.points === 1 ? "point" : "points"}</span>{question.question}</legend>{question.code && <pre className="assessment-code"><code>{question.code}</code></pre>}{question.question_type === "mcq" ? <div className="option-list">{question.options.map((option, optionIndex) => <label className={answers[question.question_id] === optionIndex ? "option selected" : "option"} key={option}><input checked={answers[question.question_id] === optionIndex} onChange={() => updateAnswer(question.question_id, optionIndex)} type="radio" name={question.question_id} /><span>{option}</span></label>)}</div> : question.question_type === "coding" ? <label className="assessment-answer-field">Your code<textarea rows="8" value={answers[question.question_id]?.code ?? question.starter_code ?? ""} onChange={(event) => updateAnswer(question.question_id, { ...(answers[question.question_id] || {}), code: event.target.value })} /></label> : question.question_type === "debugging" ? <div className="assessment-answer-fields"><label className="assessment-answer-field">Corrected code<textarea rows="8" value={answers[question.question_id]?.code ?? ""} onChange={(event) => updateAnswer(question.question_id, { ...(answers[question.question_id] || {}), code: event.target.value })} /></label><label className="assessment-answer-field">Identify the bug<input value={answers[question.question_id]?.bug ?? ""} onChange={(event) => updateAnswer(question.question_id, { ...(answers[question.question_id] || {}), bug: event.target.value })} /></label><label className="assessment-answer-field">Explain why it is incorrect<textarea rows="3" value={answers[question.question_id]?.explanation ?? ""} onChange={(event) => updateAnswer(question.question_id, { ...(answers[question.question_id] || {}), explanation: event.target.value })} /></label></div> : <label className="assessment-answer-field">{question.question_type === "code_output" ? "Predicted output" : question.question_type === "scenario" ? "Your approach and reasoning" : question.question_type === "comparison" ? "Compare the concepts, use cases, and trade-offs" : "Your explanation"}<textarea rows={question.question_type === "conceptual" ? 5 : 6} value={answers[question.question_id] ?? ""} onChange={(event) => updateAnswer(question.question_id, event.target.value)} /></label>}</fieldset>)}<ErrorMessage message={error} /><p className="save-progress-message" role="status">{saveMessage}</p><div className="assessment-form-actions"><button className="secondary-button" disabled={isSaving || isSubmitting} onClick={handleSaveProgress} type="button">{isSaving ? "Saving..." : "Save progress"}</button><button className="primary-button form-submit" disabled={isSubmitting || isSaving || answeredCount !== assessment.questions.length} type="submit">{isSubmitting ? "Scoring your result..." : "Submit assessment"}</button></div></form></main></div>;
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
                      : path.startsWith("/tutor/")
                        ? "Context-Aware AI Tutor | Adaptive AI"
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
      <Route path="/tutor/:learnerId" element={<ProtectedRoute><TutorPage /></ProtectedRoute>} />
      <Route path="/assessment/:learnerId/:assessmentId" element={<ProtectedRoute><AssessmentPage /></ProtectedRoute>} />
      </Routes>
    </>
  );
}

export default App;
