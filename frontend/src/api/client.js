const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";
const REQUEST_TIMEOUT_MS = 70_000;

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const { timeoutMs = REQUEST_TIMEOUT_MS, ...fetchOptions } = options;
  let response;
  const accessToken = localStorage.getItem("adaptive_access_token") || sessionStorage.getItem("adaptive_access_token");
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(localStorage.getItem("adaptive_access_token")
          ? { Authorization: `Bearer ${localStorage.getItem("adaptive_access_token")}` }
          : {}),
        ...options.headers,
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      ...fetchOptions,
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("The request timed out. Check whether the activity completed before trying again.");
    }
    throw new Error("The learning service is unavailable. Check your connection and try again.");
  } finally {
    window.clearTimeout(timeoutId);
  }
  let body;
  try {
    body = await response.json();
  } catch {
    if (response.ok) {
      throw new Error("The service returned an unreadable response. Reload to check whether the activity was saved.");
    }
    body = {};
  }
  if (!response.ok) {
    const messages = {
      401: "Your session has expired. Please log in again.",
      403: "This learning activity is not available for your current path.",
      404: "We could not find that learner activity.",
      422: "Please check the submitted information and try again.",
      500: "The learning service encountered a problem. Please try again.",
      408: "The learning service took too long to respond. Please try again.",
      429: "Too many requests were made. Please wait a moment and try again.",
      502: "The learning service is temporarily unavailable. Please try again.",
      503: "The learning service is temporarily unavailable. Please try again.",
      504: "The learning service took too long to respond. Please try again.",
    };
    const sandboxUnavailable = response.status === 503
      && typeof body.detail === "string"
      && body.detail.includes("CODE_SANDBOX_URL");
    const message = sandboxUnavailable
      ? "Code execution is currently unavailable. Please try again later."
      : messages[response.status]
        || (response.status < 500 && typeof body.detail === "string"
          ? body.detail
          : "The learning service could not complete this request.");
    throw new ApiError(message, response.status);
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

export function getLearnerSummary(learnerId, courseId = null) {
  const courseQuery = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return request(`/learners/${learnerId}/dashboard${courseQuery}`);
}

export function getLearningPath(learnerId, courseId = null) {
  const courseQuery = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return request(`/learners/${learnerId}/learning-path${courseQuery}`);
}

export function regenerateLearningPath(learnerId, courseId = null) {
  const courseQuery = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return request(`/learners/${learnerId}/learning-path/regenerate${courseQuery}`, { method: "POST" });
}

export function getCurrentTopic(learnerId, courseId = null, topicId = null) {
  const params = new URLSearchParams();
  if (courseId) params.set("course_id", courseId);
  if (topicId) params.set("topic_id", topicId);
  const query = params.size ? `?${params.toString()}` : "";
  return request(`/learners/${learnerId}/learning-path/current${query}`);
}

export function getLearningContent(learnerId, topicId) {
  return request(`/learners/${learnerId}/topics/${topicId}/content`);
}

export function completeTopic(learnerId, topicId) {
  return request(`/learners/${learnerId}/topics/${topicId}/complete`, { method: "POST" });
}

export function generateAssessment(learnerId, topicId, payload) {
  return request(`/learners/${learnerId}/topics/${topicId}/assessment/generate`, {
    method: "POST",
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  });
}

export function getPendingAssessment(learnerId, topicId) {
  return request(`/learners/${learnerId}/topics/${topicId}/assessment/pending`);
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

export function getTutorContext(learnerId, topicId) {
  const params = new URLSearchParams({ current_topic_id: topicId });
  return request(`/learners/${learnerId}/tutor/context?${params.toString()}`);
}

export function listTutorConversations(learnerId, topicId) {
  const params = new URLSearchParams({ topic_id: topicId });
  return request(`/learners/${learnerId}/tutor/conversations?${params.toString()}`);
}

export function createTutorConversation(learnerId, topicId) {
  return request(`/learners/${learnerId}/tutor/conversations`, {
    method: "POST",
    body: JSON.stringify({ topic_id: topicId }),
  });
}

export function getTutorConversation(learnerId, conversationId) {
  return request(`/learners/${learnerId}/tutor/conversations/${conversationId}`);
}

export function sendTutorMessage(learnerId, conversationId, content, sectionContext = null, teachingStyle = null) {
  return request(`/learners/${learnerId}/tutor/conversations/${conversationId}/messages`, {
    method: "POST",
    timeoutMs: 20_000,
    body: JSON.stringify({
      content,
      ...(sectionContext ? { section_context: sectionContext } : {}),
      ...(teachingStyle ? { teaching_style: teachingStyle } : {}),
    }),
  });
}

export function submitAssessment(learnerId, assessmentId, answers) {
  return request(`/learners/${learnerId}/assessments/${assessmentId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export function saveAssessmentResponses(learnerId, assessmentId, answers) {
  return request(`/learners/${learnerId}/assessments/${assessmentId}/responses`, {
    method: "PUT",
    body: JSON.stringify({ answers }),
  });
}
