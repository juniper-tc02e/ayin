"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";

function VerifyInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [message, setMessage] = useState("Verifying…");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setMessage("Missing verification token.");
      setDone(true);
      return;
    }
    api("/identifiers/verify-email", { method: "POST", body: { token } })
      .then(() => setMessage("Identifier verified — it can now be included in your scans."))
      .catch((err) =>
        setMessage(err instanceof ApiError ? err.message : "Verification failed.")
      )
      .finally(() => setDone(true));
  }, [token]);

  return (
    <main>
      <h1>Identifier verification</h1>
      <div className="card">
        <p style={{ margin: 0 }}>{message}</p>
      </div>
      {done && (
        <p className="dim" style={{ marginTop: "1rem" }}>
          <Link href="/dashboard">Go to dashboard</Link>
        </p>
      )}
    </main>
  );
}

export default function VerifyIdentifierPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
