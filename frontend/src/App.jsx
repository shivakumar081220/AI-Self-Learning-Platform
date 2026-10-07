import { useEffect, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "./auth";

import {
  createLearner,
  completeTopic,
  generateAssessment,
  generateDiagnostic,
  getAssessment,
  getCurrentTopic,
  getLearningContent,
  getGoals,
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
        <div className="hero-actions"><Link className="primary-button" to="/register">Get started</Link><Link className="text-link" to="/login">Log in</Link></div>
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
  return <div className="app-shell"><main className="auth-shell"><p className="eyebrow">Welcome back</p><h1>Return to your learning.</h1><form className="auth-form" onSubmit={submit}><label className="field-label" htmlFor="login-email">Email</label><input id="login-email" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /><label className="field-label" htmlFor="login-password">Password</label><input id="login-password" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /><ErrorMessage message={error} /><button className="primary-button" disabled={busy} type="submit">{busy ? "Logging in..." : "Log in"}</button><Link className="text-link" to="/register">Create an account</Link></form></main></div>;
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
    try { await register(form); navigate("/profile"); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  return <div className="app-shell"><main className="auth-shell"><p className="eyebrow">Create your account</p><h1>Build your learning space.</h1><form className="auth-form" onSubmit={submit}><label className="field-label" htmlFor="register-name">Name</label><input id="register-name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /><label className="field-label" htmlFor="register-email">Email</label><input id="register-email" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /><label className="field-label" htmlFor="register-password">Password</label><input id="register-password" type="password" minLength="8" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /><label className="field-label" htmlFor="register-confirm">Confirm password</label><input id="register-confirm" type="password" value={form.confirmPassword} onChange={(event) => setForm({ ...form, confirmPassword: event.target.value })} required /><ErrorMessage message={error} /><button className="primary-button" disabled={busy} type="submit">{busy ? "Creating account..." : "Create account"}</button><Link className="text-link" to="/login">Already have an account?</Link></form></main></div>;
}

function DashboardPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [learner, setLearner] = useState(null);
  const [summary, setSummary] = useState(null);
  const [curriculum, setCurriculum] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { getMyLearner().then((profile) => { setLearner(profile); return Promise.all([getLearnerSummary(profile.id), getMyCurriculum().catch(() => null)]); }).then((result) => { if (result) { setSummary(result[0]); setCurriculum(result[1]); } }).catch((requestError) => setError(requestError.message)); }, []);
  function signOut() { logout(); navigate("/", { replace: true }); }
  if (error) return <div className="app-shell"><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to="/profile">Complete onboarding</Link></main></div>;
  if (!learner) return <main className="center-state"><span className="loading-mark">● ● ●</span><p>Loading your learning space...</p></main>;
  return <div className="app-shell"><header className="dashboard-header"><Link className="brand-link" to="/">Adaptive AI</Link><nav><Link to="/dashboard">Dashboard</Link><Link to={`/learning-path/${learner.id}`}>My learning</Link><Link to="/profile">Profile</Link><button className="text-button" onClick={signOut} type="button">Log out</button></nav></header><main className="dashboard-shell"><p className="eyebrow">Your learning space</p><h1>Welcome, {learner.name}.</h1>{curriculum && <section className="course-banner"><div><p className="eyebrow">Current course</p><h2>{curriculum.course_title}</h2><p>{curriculum.description}</p></div><span>{curriculum.topics.length} topics</span></section>}<section className="dashboard-grid"><div><p className="eyebrow">Progress</p><strong className="dashboard-number">{summary?.progress_percentage || 0}%</strong><p>path completed</p></div><div><p className="eyebrow">Current topic</p><strong>{summary?.current_topic_title || "Ready to begin"}</strong><p>{summary?.recommendation?.summary || "Your next recommendation will appear here."}</p></div><div><p className="eyebrow">Skill readiness</p><strong className="dashboard-number">{summary?.overall_skill_percentage || 0}%</strong><p>across recorded concepts</p></div></section><div className="dashboard-actions"><Link className="primary-button" to={`/learning-path/${learner.id}`}>{summary?.current_topic_id ? "Continue learning" : "Open my learning"}</Link><button className="secondary-button" onClick={signOut} type="button">Log out</button></div></main></div>;
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
  const { isAuthenticated } = useAuth();
  const [goals, setGoals] = useState([]);
  const [form, setForm] = useState({ name: "", experience_level: "beginner", goal_key: "", custom_goal: "" });
  const [isCustomGoal, setIsCustomGoal] = useState(false);
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    getGoals().then(setGoals).catch((requestError) => setError(requestError.message));
  }, []);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function selectGoal(goalKey) {
    setIsCustomGoal(false);
    setForm((current) => ({ ...current, goal_key: goalKey, custom_goal: "" }));
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
      await generateMyCurriculum();
      navigate(`/diagnostic/${learner.id}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="app-shell">
      <ProgressHeader activeStep={1} />
      <main className="form-shell">
        <section className="form-intro">
          <p className="eyebrow">Step 01 / learner profile</p>
          <h1>Start from where you are.</h1>
          <p className="hero-copy">Your answers shape the diagnostic and the learning decisions that follow.</p>
        </section>
        <form className="profile-form" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="name">What should we call you?</label>
          <input id="name" name="name" value={form.name} onChange={updateField} placeholder="Your name" required />

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

          <span className="field-label">What do you want to make possible?</span>
          <div className="goal-grid">
            {goals.map((goal) => (
              <button
                className={form.goal_key === goal.key && !isCustomGoal ? "goal-card selected" : "goal-card"}
                key={goal.key}
                onClick={() => selectGoal(goal.key)}
                type="button"
              >
                <strong>{goal.label}</strong>
                <span>{goal.description}</span>
              </button>
            ))}
            <button
              className={isCustomGoal ? "goal-card selected" : "goal-card"}
              onClick={() => { setIsCustomGoal(true); setForm((current) => ({ ...current, goal_key: "" })); }}
              type="button"
            >
              <strong>Something specific</strong>
              <span>Describe a Generative AI goal in your own words.</span>
            </button>
          </div>
          {isCustomGoal && (
            <input name="custom_goal" value={form.custom_goal} onChange={updateField} placeholder="I want to..." required />
          )}
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
      navigate(`/analysis/${learnerId}`, { state: { analysis } });
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
          <p className="hero-copy">Eight quick questions across the Generative AI essentials. Choose the answer that feels most accurate.</p>
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
  const [analysis, setAnalysis] = useState(location.state?.analysis || null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!analysis) getSkillAnalysis(learnerId).then(setAnalysis).catch((requestError) => setError(requestError.message));
  }, [analysis, learnerId]);

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
        <section className="analysis-grid">
          <div className="analysis-column"><h2>Strong areas</h2>{analysis.strong_areas.length ? analysis.strong_areas.map((skill) => <SkillBar key={skill.concept} skill={skill} />) : <p className="empty-copy">Your strengths are still taking shape.</p>}</div>
          <div className="analysis-column"><h2>Developing areas</h2>{analysis.developing_areas.length ? analysis.developing_areas.map((skill) => <SkillBar key={skill.concept} skill={skill} />) : <p className="empty-copy">No developing areas yet.</p>}</div>
          <div className="analysis-column"><h2>Needs attention</h2>{analysis.weak_areas.length ? analysis.weak_areas.map((skill) => <SkillBar key={skill.concept} skill={skill} />) : <p className="empty-copy">No weak areas detected.</p>}</div>
        </section>
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

  if (error && !path) return <div className="app-shell"><ProgressHeader activeStep={4} /><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to="/profile">Start a learner profile</Link></main></div>;
  if (!path) return <div className="app-shell"><ProgressHeader activeStep={4} /><main className="center-state"><span className="loading-mark">● ● ●</span><p>Assembling the sequence that fits you...</p></main></div>;

  const completedCount = path.topics.filter((topic) => topic.status === "completed").length;
  return (
    <div className="app-shell">
      <ProgressHeader activeStep={4} />
      <main className="path-shell">
        {summary && <section className="learner-overview"><div><p className="eyebrow">Learner dashboard</p><h2>{summary.name}</h2><p>{summary.goal}</p></div><div className="overview-stat"><strong>{summary.progress_percentage}%</strong><span>path progress</span></div><div className="overview-stat"><strong>{summary.overall_skill_percentage}%</strong><span>skill readiness</span></div>{summary.latest_assessment && <div className="overview-stat"><strong>{summary.latest_assessment.percentage}%</strong><span>latest assessment</span></div>}</section>}
        <section className="path-heading">
          <div>
            <p className="eyebrow">Step 04 / personalized path</p>
            <h1>Built around your next move.</h1>
            <p className="hero-copy">{path.overall_rationale}</p>
          </div>
          <div className="path-summary"><strong>{completedCount}/{path.topics.length}</strong><span>topics completed</span></div>
        </section>
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

  if (error && !learningContent) return <div className="app-shell"><ProgressHeader activeStep={4} /><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to={`/learning-path/${learnerId}`}>Return to learning path</Link></main></div>;
  if (!currentTopic || !learningContent) return <div className="app-shell"><ProgressHeader activeStep={4} /><main className="center-state"><span className="loading-mark">● ● ●</span><p>Preparing a lesson for your current focus...</p></main></div>;

  const content = learningContent.content;
  return (
    <div className="app-shell">
      <ProgressHeader activeStep={4} />
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
            <section className="lesson-section practical-section"><p className="eyebrow">Put it to work</p><h2>A practical example.</h2><p>{content.practical_example}</p>{content.code_example && <pre><code>{content.code_example}</code></pre>}</section>
            <section className="lesson-section split-section"><div><p className="eyebrow">Watch for</p><ul>{content.common_mistakes.map((mistake) => <li key={mistake}>{mistake}</li>)}</ul></div><div><p className="eyebrow">Quick recap</p><ul>{content.quick_recap.map((item) => <li key={item}>{item}</li>)}</ul></div></section>
            {content.important_notes.length > 0 && <section className="note-strip"><strong>Important:</strong> {content.important_notes.join(" ")}</section>}
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
      <section className="result-grid"><div><h2>Concept performance</h2>{result.concept_results.map((concept) => <div className="result-concept" key={concept.concept}><div><span>{concept.concept.replaceAll("_", " ")}</span><strong>{concept.percentage}%</strong></div><div className="skill-bar"><span className={`skill-fill ${concept.level}`} style={{ width: `${concept.percentage}%` }} /></div><p>{concept.level}</p></div>)}</div><div className={`adaptation-card ${result.recommendation.action_type}`}><p className="eyebrow">What changed based on your result?</p><h2>{weak.length ? weak.map((concept) => concept.replaceAll("_", " ")).join(", ") : "Your next step"}</h2><p>{result.recommendation.summary}</p><strong>{result.recommendation.next_action}</strong>{result.recommendation.remediation && <blockquote>{result.recommendation.remediation}</blockquote>}</div></section>
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

  if (error) return <div className="app-shell"><ProgressHeader activeStep={4} /><main className="center-state"><ErrorMessage message={error} /><Link className="text-link" to={`/learning-path/${learnerId}`}>Return to path</Link></main></div>;
  if (result) return <div className="app-shell"><ProgressHeader activeStep={4} /><AssessmentResult learnerId={learnerId} result={result} onRetry={handleRetry} isRetrying={isRetrying} /></div>;
  if (!assessment) return <div className="app-shell"><ProgressHeader activeStep={4} /><main className="center-state"><span className="loading-mark">● ● ●</span><p>Preparing your topic assessment...</p></main></div>;

  const answeredCount = Object.keys(answers).length;
  return <div className="app-shell"><ProgressHeader activeStep={4} /><main className="assessment-shell post-learning-assessment"><section className="assessment-heading"><p className="eyebrow">Assess / {assessment.topic_title}</p><h1>Show what stuck.</h1><p className="hero-copy">Answer these questions from the topic you just completed. Your result will shape the next recommendation.</p><div className="question-progress"><span style={{ width: `${(answeredCount / assessment.questions.length) * 100}%` }} /></div><p className="progress-copy">{answeredCount} of {assessment.questions.length} answered</p></section><form className="question-list" onSubmit={handleSubmit}>{assessment.questions.map((question, index) => <fieldset className="question-card" key={question.question_id}><legend><span>0{index + 1}</span>{question.question}</legend><div className="option-list">{question.options.map((option, optionIndex) => <label className={answers[question.question_id] === optionIndex ? "option selected" : "option"} key={option}><input checked={answers[question.question_id] === optionIndex} onChange={() => setAnswers((current) => ({ ...current, [question.question_id]: optionIndex }))} type="radio" name={question.question_id} /><span>{option}</span></label>)}</div></fieldset>)}<ErrorMessage message={error} /><button className="primary-button form-submit" disabled={isSubmitting || answeredCount !== assessment.questions.length} type="submit">{isSubmitting ? "Scoring your result..." : "Submit assessment"}</button></form></main></div>;
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/diagnostic/:learnerId" element={<ProtectedRoute><DiagnosticPage /></ProtectedRoute>} />
      <Route path="/analysis/:learnerId" element={<ProtectedRoute><AnalysisPage /></ProtectedRoute>} />
      <Route path="/learning-path/:learnerId" element={<ProtectedRoute><LearningPathPage /></ProtectedRoute>} />
      <Route path="/learn/:learnerId" element={<ProtectedRoute><LearningExperiencePage /></ProtectedRoute>} />
      <Route path="/assessment/:learnerId/:assessmentId" element={<ProtectedRoute><AssessmentPage /></ProtectedRoute>} />
    </Routes>
  );
}

export default App;
