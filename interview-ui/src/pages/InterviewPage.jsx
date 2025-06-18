import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ClipLoader } from "react-spinners";

export default function InterviewPage() {
  const { jobId } = useParams();
  const [questionData, setQuestionData] = useState(null);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [displayedText, setDisplayedText] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [canAnswer, setCanAnswer] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [recognition, setRecognition] = useState(null);
  const [report, setReport] = useState(null); // ✅ Added report state

  const api = "http://localhost:8004";
  const user = JSON.parse(sessionStorage.getItem("candidate_user") || "{}");
  const candidateId = user.candidate_id;
  const companyId = user.company_id || getCompanyIdFromApplications();

  function getCompanyIdFromApplications() {
    const apps = JSON.parse(sessionStorage.getItem("applications") || "[]");
    const match = apps.find((a) => a.job_id === jobId);
    return match?.company_id || "default-company-id";
  }

  const fetchReport = async () => {
try {
    // Check if report already exists
    const res = await fetch(`http://localhost:8006/score/candidate?candidate_id=${candidateId}&job_id=${jobId}`);
    const data = await res.json();

    if (data.score_report) {
      setReport(data.score_report);
    } else {
      // If not, generate it
      const auto = await fetch(`http://localhost:8006/score/candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, job_id: jobId })
      });
      const result = await auto.json();
      if (result.score_report) setReport(result.score_report);
    }
  } catch (err) {
    console.error("Failed to fetch or generate report:", err);
  }
  };

  useEffect(() => {
    const initOrFetch = async () => {
      try {
        const res = await fetch(`${api}/interview/next`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ candidate_id: String(candidateId), job_id: jobId }),
        });

        if (res.status === 404) {
          const gen = await fetch(`${api}/interview/question`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              candidate_id: String(candidateId),
              job_id: jobId,
              company_id: companyId,
              previous_answers: [],
            }),
          });

          if (gen.ok) {
            fetchNextQuestion();
          } else {
            setStatus("error");
            setMessage("Failed to initialize interview.");
          }
        } else {
          const data = await res.json();
          if (data.interview_complete) {
            setStatus("complete");
            setQuestionData(null);
            fetchReport(); // ✅ Fetch report after interview complete
          } else {
            setQuestionData(data);
            setStatus("ready");
            setDisplayedText(data.question);
            setCanAnswer(false);
            setTimeout(() => {
              speakAndAnimateQuestion(data.question);
            }, 300);
          }
        }
      } catch (err) {
        setStatus("error");
        setMessage("Interview session could not be started.");
      }
    };

    initOrFetch();
  }, [candidateId, jobId, companyId]);

  const fetchNextQuestion = async () => {
    setStatus("loading");
    const res = await fetch(`${api}/interview/next`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: String(candidateId), job_id: jobId }),
    });

    const data = await res.json();
    if (data.interview_complete) {
      setStatus("complete");
      setQuestionData(null);
      fetchReport();
    } else {
      setQuestionData(data);
      setStatus("ready");
      setCanAnswer(false);
      setTimeout(() => {
        speakAndAnimateQuestion(data.question);
      }, 300);
    }
  };

  const speakAndAnimateQuestion = (question) => {
    const synth = window.speechSynthesis;
    const utterance = new SpeechSynthesisUtterance(question);
    utterance.lang = "en-US";
    utterance.onend = () => {
      setIsSpeaking(false);
      setCanAnswer(true);
    };
    synth.cancel();
    synth.speak(utterance);
    setIsSpeaking(true);
    setDisplayedText(question);
  };

  const startRecording = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition not supported in this browser.");
      return;
    }

    const recog = new SpeechRecognition();
    recog.continuous = true;
    recog.interimResults = true;
    recog.lang = "en-US";

    recog.onstart = () => setIsRecording(true);
    recog.onend = () => setIsRecording(false);
    recog.onerror = (e) => console.error("Speech Error:", e);

    recog.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        if (res.isFinal) {
          setTranscript((prev) => prev + res[0].transcript + " ");
        } else {
          interim += res[0].transcript;
        }
      }
    };

    setRecognition(recog);
    recog.start();
  };

  const stopRecording = () => {
    if (recognition) recognition.stop();
  };

  const submitAnswer = async () => {
    stopRecording();
    const text = transcript.trim();
    if (!text) return;
    setStatus("submitting");

    const payload = {
      candidate_id: String(candidateId),
      job_id: jobId,
      question: questionData.question,
      answer: text,
    };

    const res = await fetch(`${api}/interview/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      setTranscript("");
      fetchNextQuestion();
    } else {
      setStatus("error");
      setMessage("Failed to submit answer.");
    }
  };

  const retryAnswer = () => {
    stopRecording();
    setTranscript("");
    setDisplayedText(questionData?.question || "");
    setCanAnswer(true);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-blue-900 text-white px-6 py-4 flex justify-between items-center shadow relative">
        <h1 className="text-xl font-semibold">AI Interview</h1>
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

      <div className="max-w-3xl mx-auto p-6">
        {status === "loading" && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ClipLoader size={20} color="#1E3A8A" loading={true} /> Loading next question...
          </div>
        )}

        {status === "complete" && (
          <div className="p-4 bg-green-100 border border-green-400 rounded">
            <p className="text-green-800 font-semibold">✅ Interview completed. Thank you!</p>
          </div>
        )}

        {report && (
          <>
            <section className="flex flex-col sm:flex-row sm:justify-between gap-6 mt-6 p-4 bg-white border rounded shadow-sm">
              <div className="sm:w-1/2 space-y-3">
                <h3 className="text-lg font-semibold text-gray-800">Your Scores</h3>
                <ul className="space-y-3 text-sm text-gray-700">
                  {[
                    { label: "🧠 Technical", value: report.technical, color: "bg-blue-600" },
                    { label: "🗣️ Communication", value: report.communication, color: "bg-purple-600" },
                    { label: "🤝 Leadership", value: report.leadership, color: "bg-orange-600" },
                    { label: "📋 Completeness", value: report.completeness, color: "bg-green-600" },
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
              
            </section>

            {Array.isArray(report.skill_match_graph) && (
              <div className="mt-6 p-4 bg-white border rounded shadow-sm">
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Skill Match Overview</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm text-left text-gray-700 border">
                    <thead className="bg-gray-100 text-gray-600">
                      <tr>
                        <th className="px-4 py-2">Skill</th>
                        <th className="px-4 py-2">Matched?</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.skill_match_graph.map((item, idx) => (
                        <tr key={idx} className="border-t">
                          <td className="px-4 py-2">{item.skill}</td>
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
          </>
        )}

        {status === "error" && <div className="text-red-600">{message}</div>}

        {questionData && status !== "complete" && (
          <div className="space-y-4 mt-4">
            <div className="p-4 bg-white border rounded shadow">
              <p className="text-sm text-gray-600 mb-1">{(questionData?.category || "general").toUpperCase()} QUESTION</p>
              <p className="text-lg font-medium text-gray-800 whitespace-pre-wrap">{displayedText}</p>
            </div>

            {canAnswer && (
              <div className="space-y-3">
                {!isRecording ? (
                  <button onClick={startRecording} className="bg-green-600 text-white px-4 py-2 rounded">
                    🎤 Start Speaking
                  </button>
                ) : (
                  <button onClick={stopRecording} className="bg-yellow-500 text-white px-4 py-2 rounded">
                    ⏹️ Stop
                  </button>
                )}

                <div className="p-3 bg-gray-100 rounded min-h-[80px]">
                  <p className="text-sm text-gray-600">Your Answer:</p>
                  <textarea
                    rows="5"
                    className="w-full mt-1 px-3 py-2 border rounded bg-white"
                    placeholder="Speak or type your answer..."
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                  />
                </div>

                <div className="flex gap-4 mt-2">
                  <button className="bg-blue-600 text-white px-4 py-1 rounded" onClick={submitAnswer}>Submit</button>
                  <button className="bg-red-500 text-white px-4 py-1 rounded" onClick={retryAnswer}>Retry</button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
