// Session owner: the httpOnly cookie is the source of truth, this lib only caches it
// in react-query. Every sign-out must go through useEndSession() so the previous
// account's cache never leaks into the next login.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import type { SessionUser } from "@/lib/types";

export function useSession() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => (await apiGet<{ user: SessionUser | null }>("/auth/me")).user,
    staleTime: 60_000,
    // Keep the header and member balance current when an admin changes coins.
    refetchInterval: 3000,
    // A temporary tunnel/network error is not the same as a signed-out session.
    // Retry transient failures before protected routes decide what to render.
    retry: (failureCount, error) =>
      failureCount < 2 && (!(error instanceof ApiError) || error.status >= 500),
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
  });
}

export function useBeginSession() {
  const qc = useQueryClient();
  return (user: SessionUser) => {
    qc.clear(); // purge any previous account's cache before the new session renders
    // A successful login/register response confirms the new session. Seed the
    // session query before navigation so RequireAuth cannot see a stale null.
    qc.setQueryData(["me"], user);
  };
}

export function useEndSession() {
  const qc = useQueryClient();
  return async () => {
    try {
      await apiPost("/auth/logout");
    } finally {
      qc.clear();
    }
  };
}
