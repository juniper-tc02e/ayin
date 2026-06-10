import Link from "next/link";
import AuthForm from "@/components/AuthForm";

export default function SignupPage() {
  return (
    <main>
      <h1>Create your account</h1>
      <p className="dim">
        Ayin scans only identifiers you prove you control — starting with this email.
      </p>
      <AuthForm mode="signup" />
      <p className="dim" style={{ marginTop: "1rem" }}>
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </main>
  );
}
