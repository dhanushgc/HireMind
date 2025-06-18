import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ClipLoader } from "react-spinners";

export default function CandidateDetailPage() {
  const { jobId, candidateId } = useParams();
  const [resume, setResume] = useState(null);
  const [report, setReport] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  const apiBase = "http://localhost:8001";
  const scoreApi = "http://localhost:8006";
  const reportApi = "http://localhost:8007";
  const interviewApi = "http://localhost:8004";

  useEffect(() => {
    const fetchResume = async () => {
      try {
        const res = await fetch(`${apiBase}/candidates_for_job?job_id=${jobId}`);
        const data = await res.json();
        const cand = data.candidates.find((c) => c.candidate_id === candidateId);
        if (!cand) throw new Error("Candidate not found.");
        setResume(cand);

        const resp = await fetch(`${interviewApi}/interview/next`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ candidate_id: candidateId, job_id: jobId })
        });

        const next = await resp.json();
        if (next.interview_complete) {
          setStatus("complete");
          await fetchReport();
        } else {
          setStatus("in_progress");
        }
      } catch (err) {
        setError(err.message);
      }
    };

    const fetchReport = async () => {
      try {
        const res = await fetch(`${scoreApi}/score/candidate?candidate_id=${candidateId}&job_id=${jobId}`);
        const data = await res.json();

        if (!data.score_report) {
          const auto = await fetch(`${scoreApi}/score/candidate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ candidate_id: candidateId, job_id: jobId })
          });
          const scored = await auto.json();
          if (scored.score_report) setReport(scored.score_report);
        } else {
          setReport(data.score_report);
        }

        const html = await fetch(`${reportApi}/report/candidate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ candidate_id: candidateId, job_id: jobId })
        });
        const preview = await html.json();
        if (preview?.report) {
        setReport(preview);
        }
      } catch {
        setError("Failed to generate or fetch report.");
      }
    };

    fetchResume();
  }, [candidateId, jobId]);

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-blue-900 text-white px-6 py-4 flex justify-between items-center shadow">
        <h1 className="text-xl font-semibold">Candidate Details</h1>
        <div className="absolute left-1/2 transform -translate-x-1/2 flex items-center gap-2">
          <span className="text-xl font-bold tracking-wide text-white">HireMind</span>
        </div>
        <div className="flex gap-4">
          <button
            className="bg-white text-blue-900 font-medium px-3 py-1 rounded hover:bg-gray-100"
            onClick={() => window.history.back()}
          >⬅ Back</button>
          <button
            className="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700"
            onClick={() => {
              sessionStorage.removeItem("recruiter_user");
              window.location.href = "/login";
            }}
          >Logout</button>
        </div>
      </nav>

      <div className="p-6 max-w-5xl mx-auto space-y-6">
        {error && <div className="text-red-600">{error}</div>}

        {!resume ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ClipLoader size={20} color="#1E3A8A" loading={true} /> Loading candidate details...
          </div>
        ) : (
          <>
            <div className="p-4 border rounded bg-white shadow">
              <p className="text-lg font-semibold text-gray-800">{resume.candidate_name}</p>
              <p className="text-sm text-gray-600">{resume.candidate_email}</p>
              <button
                onClick={() => window.open(`http://localhost:8001/${resume.resume_file_path.replace(/\\|\\/g, "/")}`, "_blank")}
                className="text-white bg-blue-800 px-3 py-1 mt-2 rounded hover:bg-blue-900"
              >
                View Resume
              </button>
            </div>

            <div className="p-4 bg-gray-100 rounded">
              <p className="font-medium text-blue-900">AI Interview Status:</p>
              <p className="text-sm">
                {status === "loading" && "Checking..."}
                {status === "in_progress" && "In progress"}
                {status === "complete" && "Completed ✅"}
              </p>
            </div>

            {report?.report && (
              <div className="mt-6 bg-white shadow-md border border-gray-200 rounded-xl p-8 space-y-6">
                <header className="space-y-1">
                  <h2 className="text-2xl font-bold text-blue-900">
                    Candidate Report: <span className="text-gray-800">{report.candidate_name}</span>
                  </h2>
                   <h2 className="text-2xl font-bold text-blue-900">
                   Role: <span className="text-gray-800">{report.job_title}</span>
                  </h2>
                  <p className="text-sm text-gray-500 flex items-center gap-2">
                    📅 <span>{report.date}</span>
                  </p>
                </header>

                <section className="grid sm:grid-cols-2 sm:justify-between gap-6">
                  <div className="space-y-3">
                    <h3 className="text-lg font-semibold text-gray-800">Scores</h3>
                    <ul className="space-y-3 text-sm text-gray-700">
                      {[
                        { label: "🧠 Technical", value: report.report.technical, color: "bg-blue-600" },
                        { label: "🗣️ Communication", value: report.report.communication, color: "bg-purple-600" },
                        { label: "🤝 Leadership", value: report.report.leadership, color: "bg-orange-600" },
                        { label: "📋 Completeness", value: report.report.completeness, color: "bg-green-600" },
                      ].map((item, idx) => (
                        <li key={idx}>
                          <div className="flex justify-between mb-1">
                            <span className="font-medium">{item.label}</span>
                            <span className="text-gray-500">{item.value}/10</span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-3">
                            <div
                              className={`${item.color} h-3 rounded-full transition-all duration-500 ease-in-out`}
                              style={{ width: `${(item.value / 10) * 100}%` }}
                            ></div>
                          </div>
                        </li>
                      ))}
                    </ul>

                  </div>

                  <div className="sm:w-1/2 flex flex-col sm:items-end">
                    <h3 className="text-lg font-semibold text-gray-800">Recommendation</h3>
                    <div className={`mt-2 px-4 py-3 rounded-lg font-semibold text-white shadow-sm w-fit ${
                      report.report.verdict === "advance"
                        ? "bg-green-600"
                        : report.report.verdict === "maybe"
                        ? "bg-yellow-400 text-gray-900"
                        : "bg-red-600"
                    }`}>
                      {report.report.verdict.toUpperCase()}
                    </div>
                  </div>
                </section>

                <section className="space-y-2">
                  <h3 className="text-lg font-semibold text-gray-800">Summary</h3>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {report.report.summary}
                  </p>
                </section>

                {Array.isArray(report.report.skill_match_graph) && report.report.skill_match_graph.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Skill Match Overview</h3>
                  <div className="overflow-x-auto border rounded">
                    <table className="min-w-full text-sm text-left text-gray-700">
                      <thead className="bg-gray-100 text-xs uppercase text-gray-600">
                        <tr>
                          <th className="px-4 py-2">Skill</th>
                          <th className="px-4 py-2">Matched</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.report.skill_match_graph.map((item, index) => (
                          <tr key={index} className="border-t">
                            <td className="px-4 py-2 font-medium">{item.skill}</td>
                            <td className="px-4 py-2">
                              {item.matched ? (
                                <span className="text-green-600 font-semibold">Yes</span>
                              ) : (
                                <span className="text-red-500 font-semibold">No</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              </div>
            )}

          </>
        )}
      </div>
    </div>
  );
}
