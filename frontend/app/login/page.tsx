import Link from "next/link";
import AuthForm from "@/components/AuthForm";

export default function LoginPage() {
  return (
    <main>
      <h1>Log in</h1>
      <AuthForm mode="login" />
      <p className="dim" style={{ marginTop: "1rem" }}>
        New here? <Link href="/signup">Create an account</Link>
      </p>
    </main>
  );
}
