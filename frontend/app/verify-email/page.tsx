"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";

function VerifyInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "done" | "failed">("working");
  const [message, setMessage] = useState("Verifying…");

  useEffect(() => {
    if (!token) {
      setState("failed");
      setMessage("Missing verification token.");
      return;
    }
    api("/auth/verify-email", { method: "POST", body: { token } })
      .then(() => {
        setState("done");
        setMessage("Your email is verified. Head to your dashboard to run your first scan.");
      })
      .catch((err) => {
        setState("failed");
        setMessage(err instanceof ApiError ? err.message : "Verification failed.");
      });
  }, [token]);

  return (
    <main>
      <h1>Email verification</h1>
      <div className="card">
        <p style={{ margin: 0 }} role={state === "failed" ? "alert" : "status"}>
          {message}
        </p>
      </div>
      {state !== "working" && (
        <p className="dim" style={{ marginTop: "1rem" }}>
          <Link href="/dashboard">Go to dashboard</Link>
        </p>
      )}
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
