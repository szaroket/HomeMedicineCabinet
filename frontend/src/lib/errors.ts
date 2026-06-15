// Thrown by the api-client when a request is unauthenticated and a token
// refresh has failed. The transport layer stays pure — it never navigates or
// mutates auth state; the React layer (AuthProvider) catches this and clears
// the session, which lets ProtectedLayout redirect to /login.
export class AuthError extends Error {
  constructor(message = "Authentication required.") {
    super(message);
    this.name = "AuthError";
  }
}
