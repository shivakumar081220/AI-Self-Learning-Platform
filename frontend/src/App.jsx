import { useEffect, useRef, useState } from "react";
import { Link, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

import {
  createLearner,
  generateDiagnostic,
  getGoals,
  getSkillAnalysis,
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

function ProgressHeader({ activeStep }) {
  return (
    <header className="workflow-header">
      <Link className="brand-link" to="/">
        Adaptive AI
      </Link>
      <div className="progress-track" aria-label={`Step ${activeStep} of 3`}>
        <span className={activeStep >= 1 ? "progress-dot active" : "progress-dot"}>01</span>
        <span className="progress-line" />
        <span className={activeStep >= 2 ? "progress-dot active" : "progress-dot"}>02</span>
        <span className="progress-line" />
        <span className={activeStep >= 3 ? "progress-dot active" : "progress-dot"}>03</span>
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
        <section className="next-step-banner"><div><p className="eyebrow">Prepared for the next step</p><h2>Your learning path will use these scores.</h2></div><span className="next-arrow">→</span></section>
      </main>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/diagnostic/:learnerId" element={<DiagnosticPage />} />
      <Route path="/analysis/:learnerId" element={<AnalysisPage />} />
    </Routes>
  );
}

export default App;
