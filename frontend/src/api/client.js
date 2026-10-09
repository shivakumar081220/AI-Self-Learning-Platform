const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";
const REQUEST_TIMEOUT_MS = 70_000;

class ApiError extends Error {
  constructor(message, status, serverDetail = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.serverDetail = serverDetail;
  }
}

function tutorCodingRequest(path, options) {
  return request(path, options).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    if (error.status === 404 && (!error.serverDetail || error.serverDetail === "Not Found")) {
      throw new ApiError(
        "The running backend does not have this AI Tutor coding endpoint. Restart the backend from this project using its virtual environment, then reload the tutor page.",
        error.status,
        error.serverDetail,
      );
    }
    if ((error.status === 429 || error.status === 503) && error.serverDetail) {
      throw new ApiError(error.serverDetail, error.status, error.serverDetail);
    }
    throw error;
  });
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
        ...(fetchOptions.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
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
      && body.detail.includes("TUTOR_CODE_SANDBOX_URL");
    const message = sandboxUnavailable
      ? "Code execution is unavailable because the isolated sandbox is not configured. Set TUTOR_CODE_SANDBOX_URL on the backend and restart it."
      : messages[response.status]
        || (response.status < 500 && typeof body.detail === "string"
          ? body.detail
          : "The learning service could not complete this request.");
    throw new ApiError(
      message,
      response.status,
      typeof body.detail === "string" ? body.detail : "",
    );
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

export function sendTutorImageMessage(
  learnerId,
  conversationId,
  content,
  files,
  onProgress,
  sectionContext = null,
) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("content", content);
    if (sectionContext) form.append("section_context_json", JSON.stringify(sectionContext));
    files.forEach((file) => form.append("files", file));
    const xhr = new XMLHttpRequest();
    xhr.open(
      "POST",
      `${API_BASE_URL}/learners/${learnerId}/tutor/conversations/${conversationId}/images`,
    );
    const token = localStorage.getItem("adaptive_access_token")
      || sessionStorage.getItem("adaptive_access_token");
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.timeout = REQUEST_TIMEOUT_MS;
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    });
    xhr.addEventListener("load", () => {
      let body = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        reject(new Error("The service returned an unreadable response."));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new ApiError(
          typeof body.detail === "string"
            ? body.detail
            : "The image could not be analyzed. Remove it to continue with a text-only question.",
          xhr.status,
        ));
        return;
      }
      resolve(body);
    });
    xhr.addEventListener("error", () => reject(new Error("The learning service is unavailable.")));
    xhr.addEventListener("timeout", () => reject(new Error("Image upload timed out. Retry or remove the image.")));
    xhr.send(form);
  });
}

export function getTutorAttachment(learnerId, attachmentId) {
  const token = localStorage.getItem("adaptive_access_token")
    || sessionStorage.getItem("adaptive_access_token");
  return fetch(
    `${API_BASE_URL}/learners/${learnerId}/tutor/attachments/${attachmentId}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  ).then(async (response) => {
    if (!response.ok) throw new Error("This attachment is no longer available.");
    return response.blob();
  });
}

export function requestTutorCodingAssistant(learnerId, conversationId, payload) {
  return tutorCodingRequest(
    `/learners/${learnerId}/tutor/conversations/${conversationId}/coding-assistant`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function runTutorCode(learnerId, conversationId, payload) {
  return tutorCodingRequest(
    `/learners/${learnerId}/tutor/conversations/${conversationId}/executions`,
    { method: "POST", body: JSON.stringify(payload), timeoutMs: 20_000 },
  );
}

export function getTutorCodeExecutions(learnerId, conversationId) {
  return tutorCodingRequest(
    `/learners/${learnerId}/tutor/conversations/${conversationId}/executions`,
  );
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
