const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "The learning service could not complete this request.");
  }
  return body;
}

export function getGoals() {
  return request("/goals");
}

export function createLearner(profile) {
  return request("/learners", { method: "POST", body: JSON.stringify(profile) });
}

export function generateDiagnostic(learnerId) {
  return request(`/learners/${learnerId}/diagnostic/generate`, { method: "POST" });
}

export function submitDiagnostic(learnerId, assessmentId, answers) {
  return request(`/learners/${learnerId}/diagnostic/${assessmentId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export function getSkillAnalysis(learnerId) {
  return request(`/learners/${learnerId}/skills`);
}

export function getLearningPath(learnerId) {
  return request(`/learners/${learnerId}/learning-path`);
}

export function regenerateLearningPath(learnerId) {
  return request(`/learners/${learnerId}/learning-path/regenerate`, { method: "POST" });
}

export function getCurrentTopic(learnerId) {
  return request(`/learners/${learnerId}/learning-path/current`);
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

export function submitAssessment(learnerId, assessmentId, answers) {
  return request(`/learners/${learnerId}/assessments/${assessmentId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}
