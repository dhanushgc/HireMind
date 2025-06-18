import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("recruiter");
  const [name, setName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  const handleSignup = async (e) => {
    e.preventDefault();
    const endpoint =
      role === "recruiter"
        ? "http://localhost:8003/auth/recruiter/signup"
        : "http://localhost:8003/auth/candidate/signup";

    const payload =
      role === "recruiter"
        ? { email, password, name, company_name: companyName }
        : { email, password, name };

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Signup failed");

      setMessage("✅ Signup successful! Redirecting to login...");
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 px-4">
      <div className="w-full max-w-md bg-white p-8 rounded-2xl shadow-xl space-y-4">
         {/* Logo and App Name */}
        <div className="flex flex-col items-center gap-2 mb-4">
          <h1 className="text-2xl font-bold text-blue-900 tracking-wide">HireMind</h1>
          <p className="text-sm text-gray-500">AI-Powered Interview Assistant</p>
        </div>
        <h2 className="text-2xl font-bold text-center">Signup</h2>
        {error && <p className="text-red-500 text-center">{error}</p>}
        {message && <p className="text-green-600 text-center">{message}</p>}

        <form onSubmit={handleSignup} className="space-y-4">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full border px-3 py-2 rounded-lg"
          >
            <option value="recruiter">Recruiter</option>
            <option value="candidate">Candidate</option>
          </select>

          <input
            type="text"
            placeholder="Full Name"
            className="w-full border px-3 py-2 rounded-lg"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          {role === "recruiter" && (
            <input
              type="text"
              placeholder="Company Name"
              className="w-full border px-3 py-2 rounded-lg"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              required
            />
          )}

          <input
            type="email"
            placeholder="Email"
            className="w-full border px-3 py-2 rounded-lg"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <input
            type="password"
            placeholder="Password"
            className="w-full border px-3 py-2 rounded-lg"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700"
          >
            Sign Up
          </button>
        </form>

        <p className="text-sm text-center text-gray-500">
          Already have an account?{" "}
          <a href="/login" className="text-blue-600 underline">
            Login
          </a>
        </p>
      </div>
    </div>
  );
}
