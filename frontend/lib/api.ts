
const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Company {
  id: number;
  name: string;
  symbol: string;
  provider_symbol: string;
  exchange: string;
  sector: string | null;
  instrument_type: string;
  is_active: boolean;
}

export interface BackendHealth {
  status: string;
  application: string;
}

function isCompany(value: unknown): value is Company {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const company = value as Record<string, unknown>;
  return (
    typeof company.id === "number" &&
    typeof company.name === "string" &&
    typeof company.symbol === "string" &&
    typeof company.provider_symbol === "string" &&
    typeof company.exchange === "string" &&
    (typeof company.sector === "string" || company.sector === null) &&
    typeof company.instrument_type === "string" &&
    typeof company.is_active === "boolean"
  );
}

export async function fetchCompanies(): Promise<Company[]> {
  const response = await fetch(`${API_URL}/api/v1/companies`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Companies request failed (${response.status})`);
  }

  const payload: unknown = await response.json();
  if (!Array.isArray(payload) || !payload.every(isCompany)) {
    throw new Error("Companies response has an unexpected structure");
  }

  return payload;
}

export async function checkBackend(): Promise<BackendHealth> {
  try {
    const response = await fetch(`${API_URL}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error("Backend request failed");
    }

    return (await response.json()) as BackendHealth;
  } catch (error) {
    console.error("Backend connection error:", error);
    throw error;
  }
}
