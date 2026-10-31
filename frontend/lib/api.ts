
const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function checkBackend() {
  try {
    const response = await fetch(`${API_URL}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error("Backend request failed");
    }

    return await response.json();
  } catch (error) {
    console.error("Backend connection error:", error);
    throw error;
  }
}
