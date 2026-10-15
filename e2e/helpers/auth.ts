import { expect, type APIRequestContext } from "@playwright/test";

export function authenticateInvestor(request: APIRequestContext): Promise<string> {
  return authenticate(request, "FRAPPE_USER", "FRAPPE_PASSWORD");
}

export function authenticateAdministrator(
  request: APIRequestContext
): Promise<string> {
  return authenticate(request, "FRAPPE_ADMIN_USER", "FRAPPE_ADMIN_PASSWORD");
}

async function authenticate(
  request: APIRequestContext,
  userVariable: string,
  passwordVariable: string
): Promise<string> {
  const username = requireEnvironmentVariable(userVariable);
  const password = requireEnvironmentVariable(passwordVariable);

  const response = await request.post("/api/method/login", {
    form: {
      usr: username,
      pwd: password,
    },
  });
  expect(response.ok()).toBeTruthy();

  const loggedIn = await request.get("/api/method/frappe.auth.get_logged_user");
  expect(loggedIn.ok()).toBeTruthy();
  expect((await loggedIn.json()).message).toBe(username);

  return username;
}

function requireEnvironmentVariable(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} must be set for browser tests`);
  }
  return value;
}
