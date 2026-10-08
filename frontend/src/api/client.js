const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(localStorage.getItem("adaptive_access_token")
          ? { Authorization: `Bearer ${localStorage.getItem("adaptive_access_token")}` }
          : {}),
        ...options.headers,
      },
      ...options,
    });
  } catch {
    throw new Error("The learning service is unavailable. Check that the backend is running and try again.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const messages = {
      403: "This learning activity is not available for your current path.",
      404: "We could not find that learner activity.",
      422: "Please check the submitted information and try again.",
      500: "The learning service encountered a problem. Please try again.",
    };
    throw new Error(messages[response.status] || (typeof body.detail === "string" ? body.detail : "The learning service could not complete this request."));
  }
  return body;
}

export function getGoals() {
  return request("/goals");
}

export function getTracks() {
  return request("/tracks");
}

export function registerAccount(payload) {
  return request("/auth/register", { method: "POST", body: JSON.stringify(payload) });
}

export function loginAccount(payload) {
  return request("/auth/login", { method: "POST", body: JSON.stringify(payload) });
}

export function getCurrentUser() {
  return request("/auth/me");
}

export function getMyLearner() {
  return request("/learners/me");
}

export function generateMyCurriculum() {
  return request("/curriculum/generate", { method: "POST" });
}

export function getMyCurriculum() {
  return request("/curriculum/current");
}

export function createLearner(profile) {
  return request("/learners", { method: "POST", body: JSON.stringify(profile) });
}

export function generateDiagnostic(learnerId) {
  return request(`/learners/${learnerId}/diagnostic`, { method: "POST" });
}

export function submitDiagnostic(learnerId, assessmentId, answers) {
  return request(`/learners/${learnerId}/diagnostic/${assessmentId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export function getDiagnosticResult(learnerId, assessmentId) {
  return request(`/learners/${learnerId}/diagnostic/${assessmentId}`);
}

export function getSkillAnalysis(learnerId) {
  return request(`/learners/${learnerId}/skills`);
}

export function getLearnerSummary(learnerId) {
  return request(`/learners/${learnerId}/summary`);
}

export function getLearningPath(learnerId, courseId = null) {
  const courseQuery = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return request(`/learners/${learnerId}/learning-path${courseQuery}`);
}

export function regenerateLearningPath(learnerId, courseId = null) {
  const courseQuery = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return request(`/learners/${learnerId}/learning-path/regenerate${courseQuery}`, { method: "POST" });
}

export function getCurrentTopic(learnerId, courseId = null) {
  const courseQuery = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return request(`/learners/${learnerId}/learning-path/current${courseQuery}`);
}

export function getLearningContent(learnerId, topicId) {
  return request(`/learners/${learnerId}/topics/${topicId}/content`);
}

export function completeTopic(learnerId, topicId) {
  return request(`/learners/${learnerId}/topics/${topicId}/complete`, { method: "POST" });
}

export function generateAssessment(learnerId, topicId) {
  return request(`/learners/${learnerId}/topics/${topicId}/assessment/generate`, { method: "POST" });
}

export function getAssessment(learnerId, assessmentId) {
  return request(`/learners/${learnerId}/assessments/${assessmentId}`);
}

export function askTutor(learnerId, payload) {
  return request(`/learners/${learnerId}/tutor`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitAssessment(learnerId, assessmentId, answers) {
  return request(`/learners/${learnerId}/assessments/${assessmentId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}
