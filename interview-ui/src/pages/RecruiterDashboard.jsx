import React, { useState, useEffect } from "react";
import { ClipLoader } from "react-spinners";

export default function RecruiterDashboard() {
  const [companyFile, setCompanyFile] = useState(null);
  const [jobFile, setJobFile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [message, setMessage] = useState("");
  const [companyInfo, setCompanyInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const user = JSON.parse(sessionStorage.getItem("recruiter_user") || "{}");
  const recruiterId = user.recruiter_id;
  const COMPANY_ID = "ABC001";

  const fetchCompanyProfile = async () => {
    const res = await fetch("http://localhost:8001/company_profiles");
    const data = await res.json();
    const profile = data.company_profiles.find((p) => p.company_id === COMPANY_ID);
    setCompanyInfo(profile || null);
  };

  useEffect(() => {
    fetchCompanyProfile();
  }, []);

  const fetchJobs = async () => {
    try {
      const res = await fetch(`http://localhost:8001/jobs?recruiter_id=${recruiterId}`);
      const data = await res.json();
      setJobs(data.jobs || []);
    } catch {
      setMessage("Failed to fetch jobs.");
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const uploadCompanyProfile = async (e) => {
    e.preventDefault();
    setLoading(true);
    const form = new FormData();
    form.append("file", companyFile);
    form.append("company_id", COMPANY_ID);

    const res = await fetch("http://localhost:8001/parse/company_profile", {
      method: "POST",
      body: form,
    });

    setLoading(false);
    setMessage(res.ok ? "Company profile uploaded." : "Failed to upload.");
    if (res.ok) fetchCompanyProfile();
  };

  const uploadJobPost = async (e) => {
    e.preventDefault();
    setLoading(true);
    const form = new FormData();
    form.append("file", jobFile);
    form.append("job_id", crypto.randomUUID());
    form.append("company_id", COMPANY_ID);
    form.append("recruiter_id", recruiterId);

    const res = await fetch("http://localhost:8001/parse/job_post", {
      method: "POST",
      body: form,
    });

    setLoading(false);
    setMessage(res.ok ? "Job post uploaded." : "Failed to upload.");
    if (res.ok) fetchJobs();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-blue-900 text-white px-6 py-4 flex justify-between items-center shadow">
        <h1 className="text-xl font-semibold">Recruiter Panel</h1>
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

      <div className="p-6 max-w-5xl mx-auto space-y-8">
        {message && <div className="text-blue-600 font-medium">{message}</div>}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ClipLoader size={20} color="#1E3A8A" loading={true} /> Processing upload...
          </div>
        )}

        <div className="p-4 border rounded shadow space-y-3 bg-white">
          <h2 className="text-xl font-semibold text-blue-900">Company Profile</h2>

          {companyInfo ? (
            <div className="text-sm text-gray-700 space-y-1">
              <p>📄 <strong>ID:</strong> {COMPANY_ID}</p>
              <button
                onClick={() => window.open(`http://localhost:8001/${companyInfo.file_path.replace(/\\|\\/g, "/")}`, "_blank")}
                className="text-white bg-blue-800 px-3 py-1 rounded hover:bg-blue-900"
              >
                View Company Profile
              </button>
            </div>
          ) : (
            <p className="text-sm text-gray-500">No company profile uploaded yet.</p>
          )}

          <form onSubmit={uploadCompanyProfile} className="flex flex-col gap-2 mt-2">
            <input type="file" accept="application/pdf" onChange={(e) => setCompanyFile(e.target.files[0])} required />
            <button type="submit" className="bg-blue-800 text-white px-4 py-2 rounded hover:bg-blue-900">
              {companyInfo ? "Update Company Profile" : "Upload Company Profile"}
            </button>
          </form>
        </div>

        <div className="p-4 border rounded shadow space-y-3 bg-white">
          <h2 className="text-xl font-semibold text-blue-900">Add Job Post</h2>
          <form onSubmit={uploadJobPost} className="flex flex-col gap-2">
            <input type="file" accept="application/pdf" onChange={(e) => setJobFile(e.target.files[0])} required />
            <button type="submit" className="bg-blue-800 text-white px-4 py-2 rounded hover:bg-blue-900">
              Upload Job Post
            </button>
          </form>
        </div>

        <div className="space-y-3">
          <h2 className="text-xl font-semibold text-blue-900">Posted Jobs</h2>
          {jobs.length === 0 ? (
            <p className="text-gray-500">No jobs posted yet.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {jobs.map((job) => (
                <div key={job.job_id} className="p-4 border rounded shadow-sm hover:shadow-md transition bg-white">
                  <h3 className="text-lg font-medium text-gray-800">{job.title || job.job_id}</h3>
                  <p className="text-sm text-gray-600 mb-2">Created at: {new Date(job.created_at).toLocaleString()}</p>
                  <button
                    onClick={() => window.location.href = `/recruiter/job/${job.job_id}`}
                    className="bg-blue-800 text-white px-3 py-1 rounded hover:bg-blue-900"
                  >
                    View Candidates
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
