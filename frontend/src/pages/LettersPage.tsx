import { useState, useCallback, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import FileDropzone from "../components/FileDropzone";
import "./LettersPage.css";

type JobStatus = "queued" | "uploading" | "processing" | "completed" | "error";
type InputMode = "file" | "text";

interface AuthorInfo {
  last_name?: string;
  first_name?: string;
  middle_name?: string;
  date_of_birth?: string;
  gender?: string;
  phones?: string[];
  email?: string;
  country?: string;
  city?: string;
  region?: string;
  district?: string;
  address?: string;
  date_of_issue?: string;
  date_when_document_was_written?: string;
}

interface Department {
  order?: number;
  id?: string;
  reasoning?: string;
  full_name?: string;
  position?: string;
  responsibilities?: string[];
}

interface Issues {
  issues?: string[];
  keywords?: string[];
}

interface AnalysisResult {
  summary?: string;
  author_info?: AuthorInfo;
  department?: Department;
  issues?: Issues;
  entity?: { entity_type?: string };
  is_repeated?: boolean;
  repeated_dates?: string[];
  document_type?: string;
}

interface HistoryDoc {
  file_id: string;
  status: string;
  total_page_count: number | null;
  created_at: string | null;
  has_content: boolean;
}

interface HistoryDetail {
  loading?: boolean;
  error?: string;
  content?: string;
  result?: AnalysisResult | null;
}

interface LetterJob {
  id: string;
  file: File;
  fileName: string;
  fileSize: number;
  previewUrl: string | null;
  status: JobStatus;
  uploadProgress: number;
  content: string;
  result: AnalysisResult | null;
  error: string;
  fileId: string | null;
}

let jobCounter = 0;

function createJob(file: File): LetterJob {
  const isImage = file.type.startsWith("image/");
  return {
    id: `lj-${++jobCounter}`,
    file,
    fileName: file.name,
    fileSize: file.size,
    previewUrl: isImage ? URL.createObjectURL(file) : null,
    status: "queued",
    uploadProgress: 0,
    content: "",
    result: null,
    error: "",
    fileId: null,
  };
}

export default function LettersPage() {
  const [inputMode, setInputMode] = useState<InputMode>("file");
  const [jobs, setJobs] = useState<LetterJob[]>([]);
  const [history, setHistory] = useState<HistoryDoc[]>([]);
  const [expandedHistoryIds, setExpandedHistoryIds] = useState<string[]>([]);
  const [historyDetails, setHistoryDetails] = useState<
    Record<string, HistoryDetail>
  >({});
  const [historyLoading, setHistoryLoading] = useState(true);
  const [rawText, setRawText] = useState("");
  const [textStatus, setTextStatus] = useState<
    "idle" | "processing" | "completed" | "error"
  >("idle");
  const [textResult, setTextResult] = useState<AnalysisResult | null>(null);
  const [textError, setTextError] = useState("");
  const pollingRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(
    new Map(),
  );
  const jobPreviewsRef = useRef<string[]>([]);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch("/api/documents/?limit=20");
      if (res.ok) {
        setHistory(await res.json());
      }
    } catch {
      /* ignore */
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const updateJob = useCallback((id: string, patch: Partial<LetterJob>) => {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...patch } : j)));
  }, []);

  const pollStatus = useCallback(
    (jobId: string, fileId: string) => {
      const interval = setInterval(async () => {
        try {
          const res = await fetch(`/api/status/${fileId}`);
          if (!res.ok) throw new Error("Status check failed");
          const data = await res.json();

          if (data.status === "completed") {
            clearInterval(interval);
            pollingRefs.current.delete(jobId);
            updateJob(jobId, {
              status: "completed",
              result: data.meta || {},
              content: data.content || "",
            });
            fetchHistory();
          } else if (data.status === "error") {
            clearInterval(interval);
            pollingRefs.current.delete(jobId);
            updateJob(jobId, {
              status: "error",
              error: data.error_message || "Xatolik yuz berdi",
            });
          }
        } catch {
          clearInterval(interval);
          pollingRefs.current.delete(jobId);
          updateJob(jobId, {
            status: "error",
            error: "Serverga ulanib bo'lmadi",
          });
        }
      }, 2000);
      pollingRefs.current.set(jobId, interval);
    },
    [updateJob, fetchHistory],
  );

  const uploadOne = useCallback(
    (job: LetterJob) => {
      updateJob(job.id, { status: "uploading", uploadProgress: 0 });

      const form = new FormData();
      form.append("file", job.file);

      const xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          updateJob(job.id, {
            uploadProgress: Math.round((e.loaded / e.total) * 100),
          });
        }
      });
      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const data = JSON.parse(xhr.responseText);
          updateJob(job.id, { status: "processing", fileId: data.file_id });
          pollStatus(job.id, data.file_id);
        } else {
          let msg = `Server xatosi: ${xhr.status}`;
          try {
            msg = JSON.parse(xhr.responseText).detail || msg;
          } catch {
            /* */
          }
          updateJob(job.id, { status: "error", error: msg });
        }
      });
      xhr.addEventListener("error", () => {
        updateJob(job.id, { status: "error", error: "Tarmoq xatosi" });
      });
      xhr.open("POST", "/api/upload-document/");
      xhr.send(form);
    },
    [updateJob, pollStatus],
  );

  const addFiles = useCallback(
    (files: File[]) => {
      const newJobs = files.map(createJob);
      setJobs((prev) => [...prev, ...newJobs]);
      newJobs.forEach(uploadOne);
    },
    [uploadOne],
  );

  const removeJob = useCallback((id: string) => {
    const interval = pollingRefs.current.get(id);
    if (interval) {
      clearInterval(interval);
      pollingRefs.current.delete(id);
    }
    setJobs((prev) => {
      const job = prev.find((j) => j.id === id);
      if (job?.previewUrl) URL.revokeObjectURL(job.previewUrl);
      return prev.filter((j) => j.id !== id);
    });
  }, []);

  useEffect(() => {
    jobPreviewsRef.current = jobs
      .map((job) => job.previewUrl)
      .filter((previewUrl): previewUrl is string => Boolean(previewUrl));
  }, [jobs]);

  useEffect(() => {
    return () => {
      jobPreviewsRef.current.forEach((previewUrl) =>
        URL.revokeObjectURL(previewUrl),
      );
    };
  }, []);

  const loadHistoryDetail = useCallback(async (fileId: string) => {
    setHistoryDetails((prev) => ({
      ...prev,
      [fileId]: { ...prev[fileId], loading: true, error: "" },
    }));

    try {
      const res = await fetch(`/api/status/${fileId}`);
      if (!res.ok) throw new Error(`Server xatosi: ${res.status}`);
      const data = await res.json();
      setHistoryDetails((prev) => ({
        ...prev,
        [fileId]: {
          loading: false,
          error: "",
          content: data.content || "",
          result: data.meta || null,
        },
      }));
    } catch (error) {
      setHistoryDetails((prev) => ({
        ...prev,
        [fileId]: {
          ...prev[fileId],
          loading: false,
          error:
            error instanceof Error ? error.message : "Ma'lumotni olib bo'lmadi",
        },
      }));
    }
  }, []);

  const toggleHistoryItem = useCallback(
    (fileId: string) => {
      setExpandedHistoryIds((prev) => {
        const isOpen = prev.includes(fileId);
        if (isOpen) return prev.filter((id) => id !== fileId);
        return [...prev, fileId];
      });

      const detail = historyDetails[fileId];
      if (!detail || (!detail.loading && !detail.result && !detail.content)) {
        loadHistoryDetail(fileId);
      }
    },
    [historyDetails, loadHistoryDetail],
  );

  const analyzeText = async () => {
    if (!rawText.trim()) return;
    setTextStatus("processing");
    setTextError("");

    try {
      const res = await fetch("/api/analyze-text/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: rawText }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Server xatosi: ${res.status}`);
      }
      const data = await res.json();
      setTextResult(data.meta || {});
      setTextStatus("completed");
    } catch (e) {
      setTextError(e instanceof Error ? e.message : "Xatolik yuz berdi");
      setTextStatus("error");
    }
  };

  const resetText = () => {
    setRawText("");
    setTextStatus("idle");
    setTextResult(null);
    setTextError("");
  };

  return (
    <div className="letters">
      <nav className="ocr-nav">
        <Link to="/" className="back-link">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m15 18-6-6 6-6" />
          </svg>
          Bosh sahifa
        </Link>
        <h1 className="ocr-nav-title">Hatlar AI</h1>
        <div style={{ width: 120 }} />
      </nav>

      <main className="ocr-main-multi">
        <div className="mode-toggle">
          <button
            className={`mode-btn ${inputMode === "file" ? "active" : ""}`}
            onClick={() => setInputMode("file")}
          >
            Fayl yuklash
          </button>
          <button
            className={`mode-btn ${inputMode === "text" ? "active" : ""}`}
            onClick={() => setInputMode("text")}
          >
            Matn kiritish
          </button>
        </div>

        {inputMode === "file" && (
          <>
            <FileDropzone onFilesSelected={addFiles} />

            {jobs.length > 0 && (
              <div className="jobs-list">
                {jobs.map((job) => (
                  <div className={`job-card job-${job.status}`} key={job.id}>
                    <div className="job-header">
                      <div className="job-file-info">
                        {job.previewUrl ? (
                          <img
                            className="job-thumb"
                            src={job.previewUrl}
                            alt=""
                          />
                        ) : (
                          <div className="job-thumb job-thumb-pdf">PDF</div>
                        )}
                        <div>
                          <span className="job-file-name">{job.fileName}</span>
                          <span className="job-file-size">
                            {(job.fileSize / 1024).toFixed(0)} KB
                          </span>
                        </div>
                      </div>
                      <div className="job-actions">
                        <StatusBadge status={job.status} />
                        <button
                          className="job-remove"
                          onClick={() => removeJob(job.id)}
                          title="Olib tashlash"
                        >
                          &times;
                        </button>
                      </div>
                    </div>

                    {job.status === "uploading" && (
                      <div className="job-progress">
                        <div className="progress-bar-container">
                          <div
                            className="progress-bar"
                            style={{ width: `${job.uploadProgress}%` }}
                          />
                        </div>
                        <span className="progress-label">
                          {job.uploadProgress}%
                        </span>
                      </div>
                    )}

                    {job.status === "processing" && (
                      <div className="job-processing">
                        <div className="spinner-sm" />
                        <span>Tahlil qilinmoqda...</span>
                      </div>
                    )}

                    {job.status === "error" && (
                      <div className="job-error">
                        <p>{job.error}</p>
                      </div>
                    )}

                    {job.status === "completed" && job.result && (
                      <div className="job-result-analysis">
                        <AnalysisDisplay
                          result={job.result}
                          content={job.content}
                          fileId={job.fileId}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {!historyLoading && history.length > 0 && (
              <div className="history-section">
                <h2 className="history-heading">Oxirgi hujjatlar</h2>
                <div className="history-list">
                  {history.map((doc) => (
                    <div
                      className={`history-item history-${doc.status}`}
                      key={doc.file_id}
                    >
                      <button
                        className="history-toggle"
                        onClick={() => toggleHistoryItem(doc.file_id)}
                        type="button"
                      >
                        <div className="history-info">
                          <svg
                            className="history-icon"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                          >
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                            <path d="M14 2v6h6" />
                          </svg>
                          <div>
                            <span className="history-id">
                              {doc.file_id.slice(0, 8)}...
                            </span>
                            {doc.created_at && (
                              <span className="history-date">
                                {new Date(doc.created_at).toLocaleString(
                                  "uz-UZ",
                                )}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="history-meta">
                          {doc.total_page_count && doc.total_page_count > 0 && (
                            <span className="page-badge">
                              {doc.total_page_count} sahifa
                            </span>
                          )}
                          <HistoryStatusBadge status={doc.status} />
                          <span className="history-chevron">
                            {expandedHistoryIds.includes(doc.file_id)
                              ? "Yopish"
                              : "Ko'rish"}
                          </span>
                        </div>
                      </button>

                      {expandedHistoryIds.includes(doc.file_id) && (
                        <div className="history-detail">
                          {historyDetails[doc.file_id]?.loading && (
                            <div className="job-processing">
                              <div className="spinner-sm" />
                              <span>Ma'lumot yuklanmoqda...</span>
                            </div>
                          )}
                          {historyDetails[doc.file_id]?.error && (
                            <div className="job-error">
                              <p>{historyDetails[doc.file_id]?.error}</p>
                            </div>
                          )}
                          {!historyDetails[doc.file_id]?.loading &&
                            !historyDetails[doc.file_id]?.error &&
                            (historyDetails[doc.file_id]?.result ||
                              historyDetails[doc.file_id]?.content) && (
                              <AnalysisDisplay
                                result={
                                  historyDetails[doc.file_id]?.result || {}
                                }
                                content={historyDetails[doc.file_id]?.content}
                                fileId={doc.file_id}
                              />
                            )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {inputMode === "text" && (
          <>
            {textStatus === "idle" && (
              <>
                <textarea
                  className="text-input"
                  placeholder="Hujjat matnini bu yerga kiriting..."
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  rows={10}
                />
                {rawText.trim() && (
                  <button className="upload-btn" onClick={analyzeText}>
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="m5 12 7-7 7 7" />
                      <path d="M12 19V5" />
                    </svg>
                    Tahlil qilish
                  </button>
                )}
              </>
            )}

            {textStatus === "processing" && (
              <div className="processing-state">
                <div className="spinner" />
                <p className="processing-text">Matn tahlil qilinmoqda...</p>
                <p className="processing-hint">
                  Bu bir necha daqiqa davom etishi mumkin
                </p>
              </div>
            )}

            {textStatus === "error" && (
              <div className="error-state">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                <p>{textError}</p>
                <button className="retry-btn" onClick={resetText}>
                  Qayta urinish
                </button>
              </div>
            )}

            {textStatus === "completed" && textResult && (
              <div className="result-container">
                <AnalysisDisplay result={textResult} content={rawText} />
                <button className="retry-btn" onClick={resetText}>
                  Yangi tahlil
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function AnalysisDisplay({
  result,
  content,
  fileId,
}: {
  result: AnalysisResult;
  content?: string;
  fileId?: string | null;
}) {
  const [showPreview, setShowPreview] = useState(false);

  return (
    <>
      {fileId && (
        <section className="card">
          <div className="content-header">
            <h3>Asl hujjat</h3>
            <div className="preview-actions">
              <button
                className="copy-btn"
                onClick={() => setShowPreview(!showPreview)}
                type="button"
              >
                {showPreview ? "Yopish" : "Ko'rish"}
              </button>
              <a
                href={`/api/file/${fileId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="copy-btn"
              >
                Yuklab olish
              </a>
            </div>
          </div>
          {showPreview && (
            <div className="file-preview">
              <FilePreview fileId={fileId} />
            </div>
          )}
        </section>
      )}

      {(result.department?.full_name || result.department?.position) && (
        <section className="card official-hero">
          <h3>Mas'ul xodim</h3>
          {result.department?.full_name && (
            <p className="official-name">{result.department.full_name}</p>
          )}
          {result.department?.position && (
            <p className="official-position">{result.department.position}</p>
          )}
        </section>
      )}

      {result.summary && (
        <section className="card">
          <h3>Qisqacha mazmun</h3>
          <p className="summary-text">{result.summary}</p>
        </section>
      )}

      {result.author_info && (
        <section className="card">
          <h3>Murojaat qiluvchi</h3>
          <AuthorCard info={result.author_info} />
        </section>
      )}

      {result.department && result.department.full_name && (
        <section className="card">
          <h3>Yo'naltirish tafsilotlari</h3>
          <DepartmentCard dept={result.department} />
        </section>
      )}

      {result.issues &&
        ((result.issues.issues?.length ?? 0) > 0 ||
          (result.issues.keywords?.length ?? 0) > 0) && (
          <section className="card">
            <h3>Muammolar va kalit so'zlar</h3>
            {(result.issues.issues?.length ?? 0) > 0 && (
              <ul className="issues-list">
                {result.issues.issues!.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            )}
            {(result.issues.keywords?.length ?? 0) > 0 && (
              <div className="keywords">
                {result.issues.keywords!.map((kw, i) => (
                  <span className="keyword-tag" key={i}>
                    {kw}
                  </span>
                ))}
              </div>
            )}
          </section>
        )}

      <div className="meta-row">
        {result.document_type && (
          <div className="meta-chip">{result.document_type}</div>
        )}
        {result.entity?.entity_type && (
          <div className="meta-chip">
            {result.entity.entity_type === "individual"
              ? "Jismoniy shaxs"
              : "Yuridik shaxs"}
          </div>
        )}
        {result.is_repeated && (
          <div className="meta-chip repeated">Takroriy murojaat</div>
        )}
        {(result.repeated_dates?.length ?? 0) > 0 &&
          result.repeated_dates!.map((date) => (
            <div className="meta-chip" key={date}>
              {date}
            </div>
          ))}
      </div>

      {content && (
        <section className="card">
          <div className="content-header">
            <h3>To'liq matn</h3>
            <CopyButton text={content} />
          </div>
          <pre className="letter-content">{content}</pre>
        </section>
      )}
    </>
  );
}

function StatusBadge({ status }: { status: JobStatus }) {
  const labels: Record<JobStatus, string> = {
    queued: "Navbatda",
    uploading: "Yuklanmoqda",
    processing: "Ishlanmoqda",
    completed: "Tayyor",
    error: "Xatolik",
  };
  return (
    <span className={`status-badge status-${status}`}>{labels[status]}</span>
  );
}

function HistoryStatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    processing: "Ishlanmoqda",
    completed: "Tayyor",
    failed: "Xatolik",
  };
  const css: Record<string, string> = {
    processing: "status-processing",
    completed: "status-completed",
    failed: "status-error",
  };
  return (
    <span className={`status-badge ${css[status] || "status-queued"}`}>
      {labels[status] || status}
    </span>
  );
}

function AuthorCard({ info }: { info: AuthorInfo }) {
  const fullName = [info.last_name, info.first_name, info.middle_name]
    .filter(Boolean)
    .join(" ");
  const fields: [string, string | undefined][] = [
    ["Tug'ilgan sana", info.date_of_birth],
    [
      "Jinsi",
      info.gender === "male"
        ? "Erkak"
        : info.gender === "female"
          ? "Ayol"
          : undefined,
    ],
    ["Telefon", info.phones?.join(", ")],
    ["Email", info.email],
    ["Davlat", info.country],
    ["Viloyat", info.region],
    ["Tuman", info.district],
    ["Shahar", info.city],
    ["Manzil", info.address],
    ["Hujjat berilgan sana", info.date_of_issue],
    ["Hujjat sanasi", info.date_when_document_was_written],
  ];

  return (
    <div className="author-card">
      {fullName && <p className="author-name">{fullName}</p>}
      <div className="author-fields">
        {fields.map(
          ([label, val]) =>
            val && (
              <div className="author-field" key={label}>
                <span className="field-label">{label}</span>
                <span className="field-value">{val}</span>
              </div>
            ),
        )}
      </div>
    </div>
  );
}

function DepartmentCard({ dept }: { dept: Department }) {
  return (
    <div className="dept-card">
      <p className="dept-name">{dept.full_name}</p>
      <p className="dept-position">{dept.position}</p>
      {dept.reasoning && <p className="dept-reasoning">{dept.reasoning}</p>}
      {(dept.responsibilities?.length ?? 0) > 0 && (
        <div className="keywords">
          {dept.responsibilities!.map((r, i) => (
            <span className="keyword-tag" key={i}>
              {r}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function FilePreview({ fileId }: { fileId: string }) {
  const [fileType, setFileType] = useState<"pdf" | "image" | "unknown">(
    "unknown",
  );
  const url = `/api/file/${fileId}`;

  useEffect(() => {
    fetch(url, { method: "HEAD" })
      .then((res) => {
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("pdf")) setFileType("pdf");
        else if (ct.startsWith("image/")) setFileType("image");
        else setFileType("unknown");
      })
      .catch(() => setFileType("unknown"));
  }, [url]);

  if (fileType === "pdf") {
    return (
      <iframe
        src={url}
        className="file-preview-frame"
        title="PDF preview"
      />
    );
  }

  if (fileType === "image") {
    return <img src={url} className="file-preview-image" alt="Document" />;
  }

  return <p className="file-preview-loading">Yuklanmoqda...</p>;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }, [text]);

  return (
    <button className="copy-btn" onClick={handleCopy} type="button">
      {copied ? "Nusxalandi" : "Nusxalash"}
    </button>
  );
}
