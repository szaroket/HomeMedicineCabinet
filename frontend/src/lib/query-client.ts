import { QueryClient } from "@tanstack/react-query";
import { AuthError } from "@/lib/errors";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Never retry on 401 or a failed-refresh AuthError — the api-client
        // handles refresh, and AuthError means re-auth is required.
        if (error instanceof Response && error.status === 401) return false;
        if (error instanceof AuthError) return false;
        return failureCount < 2;
      },
    },
  },
});
