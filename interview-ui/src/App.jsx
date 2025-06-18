import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

// Page imports
import LoginPage from "./pages/LoginPage";
import RecruiterDashboard from "./pages/RecruiterDashboard";
import CandidatePortal from "./pages/CandidatePortal";
import InterviewPage from "./pages/InterviewPage";
import JobDetailPage from "./pages/JobDetailPage";
import CandidateDetailPage from "./pages/CandidateDetailPage";
import SignupPage from "./pages/SignupPage";


export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Routes>
          {/* Redirect root to login */}
          <Route path="/" element={<Navigate to="/login" />} />

          {/* Auth and dashboards */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/recruiter" element={<RecruiterDashboard />} />
          <Route path="/candidate" element={<CandidatePortal />} />

          {/* Detailed views */}
          <Route path="/recruiter/job/:jobId" element={<JobDetailPage />} />
          <Route path="/candidate/interview/:jobId" element={<InterviewPage />} />
          <Route path="/recruiter/job/:jobId/candidate/:candidateId" element={<CandidateDetailPage />}/>
          <Route path="/test" element={<div className="p-10 text-xl text-green-700">✅ Routing Works</div>} />
        </Routes>
      </div>
    </Router>
  );
}
