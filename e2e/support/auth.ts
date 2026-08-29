import { expect, type APIRequestContext } from "@playwright/test";

export async function authenticateInvestor(
  request: APIRequestContext
): Promise<string> {
  const username = requireEnvironmentVariable("FRAPPE_USER");
  const password = requireEnvironmentVariable("FRAPPE_PASSWORD");

  const response = await request.post("/api/method/login", {
    form: {
      usr: username,
      pwd: password,
    },
  });
  expect(response.ok()).toBeTruthy();

  const loggedIn = await request.get(
    "/api/method/frappe.auth.get_logged_user"
  );
  expect(loggedIn.ok()).toBeTruthy();
  expect((await loggedIn.json()).message).toBe(username);

  return username;
}

function requireEnvironmentVariable(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} must be set for investor browser tests`);
  }
  return value;
}
