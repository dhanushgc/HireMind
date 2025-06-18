// src/pages/LoginPage.jsx
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("recruiter");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    const endpoint = role === "recruiter"
      ? "http://localhost:8003/auth/recruiter/login"
      : "http://localhost:8003/auth/candidate/login";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");

      if (role === "recruiter") {
        sessionStorage.setItem("recruiter_user", JSON.stringify({ ...data }));
      } else {
        sessionStorage.setItem("candidate_user", JSON.stringify({ ...data }));
      }
      navigate(`/${role}`);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 px-4">
      <div className="w-full max-w-md bg-white p-8 rounded-2xl shadow-xl">
         {/* Logo and App Name */}
        <div className="flex flex-col items-center gap-2 mb-4">
          <h1 className="text-2xl font-bold text-blue-900 tracking-wide">HireMind</h1>
          <p className="text-sm text-gray-500">AI-Powered Interview Assistant</p>
        </div>
        <h2 className="text-2xl font-bold text-center mb-6">Login</h2>
        {error && <p className="text-red-500 text-center mb-4">{error}</p>}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block mb-1 text-sm">Email</label>
            <input
              type="email"
              required
              className="w-full border px-3 py-2 rounded-lg"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="block mb-1 text-sm">Password</label>
            <input
              type="password"
              required
              className="w-full border px-3 py-2 rounded-lg"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div>
            <label className="block mb-1 text-sm">Role</label>
            <select
              className="w-full border px-3 py-2 rounded-lg"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="recruiter">Recruiter</option>
              <option value="candidate">Candidate</option>
            </select>
          </div>
          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700"
          >
            Login
          </button>
          <p className="text-sm text-center text-gray-500">
            Don’t have an account?{" "}
            <a href="/signup" className="text-blue-600 underline">
              Sign Up
            </a>
          </p>
        </form>
      </div>
    </div>
  );
}
