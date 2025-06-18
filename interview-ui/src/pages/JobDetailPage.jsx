import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ClipLoader } from "react-spinners";

export default function JobDetailPage() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [jobRes, candidateRes] = await Promise.all([
          fetch("http://localhost:8001/jobs"),
          fetch(`http://localhost:8001/candidates_for_job?job_id=${jobId}`)
        ]);

        const jobData = await jobRes.json();
        const jobItem = jobData.jobs.find((j) => j.job_id === jobId);
        setJob(jobItem);

        const candidateData = await candidateRes.json();
        setCandidates(candidateData.candidates || []);
      } catch (err) {
        setError("Failed to fetch job or candidate details.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [jobId]);

  if (error) {
    return <div className="text-red-600 p-4">{error}</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-blue-900 text-white px-6 py-4 flex justify-between items-center shadow">
        <h1 className="text-xl font-semibold">Job Overview</h1>
        <div className="absolute left-1/2 transform -translate-x-1/2 flex items-center gap-2">
          <span className="text-xl font-bold tracking-wide text-white">HireMind</span>
        </div>
        <div className="flex gap-4">
          <button
            className="bg-white text-blue-900 font-medium px-3 py-1 rounded hover:bg-gray-100"
            onClick={() => window.history.back()}
          >
            ⬅ Back
          </button>
          <button
            className="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700"
            onClick={() => {
              sessionStorage.removeItem("recruiter_user");
              window.location.href = "/login";
            }}
          >
            Logout
          </button>
        </div>
      </nav>

      <div className="p-6 max-w-5xl mx-auto space-y-6">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ClipLoader size={20} color="#1E3A8A" loading={true} /> Loading job details...
          </div>
        ) : (
          <>
            <div className="p-4 border rounded shadow bg-white">
              <p className="text-lg font-semibold text-gray-800">{job?.title || "Untitled Job"}</p>
              <p className="text-sm text-gray-500 mb-2">Job ID: {job?.job_id}</p>
              {job?.file_path && (
                <button
                  onClick={() => window.open(`http://localhost:8001/${job.file_path.replace(/\\|\\/g, "/")}`, "_blank")}
                  className="bg-blue-800 text-white px-3 py-1 rounded hover:bg-blue-900"
                >
                  View Job Description
                </button>
              )}
            </div>

            <div>
              <h2 className="text-xl font-semibold text-blue-900 mb-3">Candidates Applied</h2>
              {candidates.length === 0 ? (
                <p className="text-gray-500">No candidates have applied yet.</p>
              ) : (
                <ul className="space-y-3">
                  {candidates.map((cand) => (
                    <li
                      key={cand.candidate_id}
                      className="p-4 border rounded shadow-sm hover:shadow-md bg-white flex justify-between items-center"
                    >
                      <div>
                        <p className="font-medium text-gray-800">{cand.candidate_name || "Unnamed Candidate"}</p>
                        <p className="text-sm text-gray-600">{cand.candidate_email}</p>
                        <p className="text-xs text-gray-400">Applied: {new Date(cand.applied_at).toLocaleString()}</p>
                      </div>
                      <Link
                        to={`/recruiter/job/${jobId}/candidate/${cand.candidate_id}`}
                        className="bg-blue-800 text-white px-3 py-1 rounded hover:bg-blue-900"
                      >
                        View Details
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
