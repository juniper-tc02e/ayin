"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";

function ConfirmInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [message, setMessage] = useState("Confirming…");

  useEffect(() => {
    if (!token) {
      setMessage("Missing confirmation token.");
      return;
    }
    api<{ message: string }>("/exclusions/confirm", { method: "POST", body: { token } })
      .then((res) => setMessage(res.message))
      .catch((err) =>
        setMessage(err instanceof ApiError ? err.message : "Confirmation failed.")
      );
  }, [token]);

  return (
    <main>
      <h1>Exclusion confirmation</h1>
      <div className="card"><p style={{ margin: 0 }}>{message}</p></div>
    </main>
  );
}

export default function ExcludeConfirmPage() {
  return (
    <Suspense>
      <ConfirmInner />
    </Suspense>
  );
}
