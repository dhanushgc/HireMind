import React, { useEffect, useState } from "react";
import { ClipLoader } from "react-spinners";

export default function CandidatePortal() {
  const [jobs, setJobs] = useState([]);
  const [applications, setApplications] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [resumeFile, setResumeFile] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const user = JSON.parse(sessionStorage.getItem("candidate_user") || "{}");
  const candidateId = user.candidate_id;

  useEffect(() => {
    fetchJobs();
    fetchApplications();
  }, []);

  const fetchJobs = async () => {
    const res = await fetch("http://localhost:8001/jobs");
    const data = await res.json();
    setJobs(data.jobs || []);
  };

  const fetchApplications = async () => {
    const res = await fetch(`http://localhost:8001/applications_for_candidate?candidate_id=${candidateId}`);
    const data = await res.json();
    setApplications(data.applications || []);
  };

  const handleApply = async () => {
    setLoading(true);
    const form = new FormData();
    form.append("file", resumeFile);
    form.append("candidate_id", candidateId);
    form.append("job_id", selectedJob.job_id);
    form.append("email", user.email);
    form.append("name", user.name);

    const res = await fetch("http://localhost:8001/parse/resume", {
      method: "POST",
      body: form,
    });

    if (res.ok) {
      await fetch("http://localhost:8004/interview/question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: String(candidateId),
          job_id: selectedJob.job_id,
          previous_answers: []
        })
      });
      setMessage("Application submitted.");
      fetchApplications();
    } else {
      setMessage("Failed to apply.");
    }
    setShowModal(false);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-blue-900 text-white px-6 py-4 flex justify-between items-center shadow">
        <h1 className="text-xl font-semibold">Candidate Portal</h1>
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
              sessionStorage.removeItem("candidate_user");
              window.location.href = "/login";
            }}
          >Logout</button>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto p-6 space-y-8">
        {message && <div className="text-blue-600 font-medium">{message}</div>}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ClipLoader size={20} color="#1E3A8A" loading={true} /> Processing application...
          </div>
        )}

        <div>
          <h2 className="text-xl font-semibold text-blue-900 mb-4">Available Jobs</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {jobs.map((job) => (
              <div key={job.job_id} className="p-4 bg-white border rounded shadow-sm">
                <h3 className="text-lg font-medium text-gray-800">{job.title || job.job_id}</h3>
                <p className="text-sm text-gray-500">Posted: {new Date(job.created_at).toLocaleString()}</p>
                <button
                  className="mt-2 bg-blue-800 text-white px-3 py-1 rounded hover:bg-blue-900"
                  onClick={() => {
                    setSelectedJob(job);
                    setShowModal(true);
                  }}
                >Easy Apply</button>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-blue-900 mt-8 mb-4">My Applications</h2>
          {applications.length === 0 ? (
            <p className="text-gray-500">No applications yet.</p>
          ) : (
            <ul className="space-y-3">
              {applications.map((a) => (
                <li key={a.job_id} className="p-4 bg-white border rounded shadow-sm flex justify-between items-center">
                  <div>
                    <p className="font-medium text-gray-800">{a.job_title || a.job_id}</p>
                    <p className="text-sm text-gray-600">Applied: {new Date(a.applied_at).toLocaleString()}</p>
                  </div>
                  <a
                    href={`/candidate/interview/${a.job_id}`}
                    className="bg-blue-800 text-white px-3 py-1 rounded hover:bg-blue-900"
                  >Start Interview</a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded shadow-lg w-full max-w-md">
            <h3 className="text-lg font-semibold mb-2">Apply for {selectedJob?.title}</h3>
            <input
              type="file"
              accept="application/pdf"
              className="w-full mb-4"
              onChange={(e) => setResumeFile(e.target.files[0])}
              required
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowModal(false)}
                className="bg-gray-200 text-gray-800 px-3 py-1 rounded hover:bg-gray-300"
              >Cancel</button>
              <button
                onClick={handleApply}
                className="bg-blue-800 text-white px-4 py-1 rounded hover:bg-blue-900"
              >Apply</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
