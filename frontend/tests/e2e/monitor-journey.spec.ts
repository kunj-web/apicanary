import { expect, test } from "@playwright/test";

test("a user can create, edit, pause, and inspect a monitor", async ({
  page,
}) => {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const monitorName = `Checkout API ${suffix}`;
  const updatedName = `Payments API ${suffix}`;

  await page.goto("/signup");
  await page.getByPlaceholder("John Doe").fill("E2E Owner");
  await page
    .getByPlaceholder("you@example.com")
    .fill(`e2e-${suffix}@example.com`);
  await page
    .getByPlaceholder("Min 8 chars, uppercase, number, special char")
    .fill("ValidPassword1!");
  await page.getByRole("button", { name: "Create Account" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "monitors",
      exact: true,
    }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Add Monitor" }).click();
  await page.getByPlaceholder("e.g. Login API").fill(monitorName);
  await page
    .getByPlaceholder("https://api.example.com/health")
    .fill("https://example.com/health");
  const createButton = page.getByRole("button", {
    name: "Start Monitoring",
  });
  const createForm = createButton.locator("xpath=ancestor::form");
  const invalidFields = await createForm.evaluate(
    (form: HTMLFormElement) =>
      Array.from(form.querySelectorAll(":invalid")).map((element) => {
        const field = element as HTMLInputElement;
        return {
          placeholder: field.placeholder,
          type: field.type,
          validationMessage: field.validationMessage,
          value: field.value,
        };
      }),
  );
  expect(invalidFields).toEqual([]);
  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/monitors") &&
      response.request().method() === "POST",
  );
  await createButton.click();
  const createResponse = await createResponsePromise;
  expect(
    createResponse.ok(),
    await createResponse.text(),
  ).toBe(true);

  await expect(page.getByRole("link", { name: monitorName })).toBeVisible();
  await page.getByRole("link", { name: monitorName }).click();

  await expect(page).toHaveURL(/\/dashboard\/monitors\/[^/]+$/, {
    timeout: 15_000,
  });
  await expect(
    page.getByRole("heading", { name: monitorName }),
  ).toBeVisible();
  await expect(page.getByText("No checks yet")).toBeVisible();

  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Name").fill(updatedName);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(
    page.getByRole("heading", { name: updatedName }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText("Monitoring paused.")).toBeVisible();
  await expect(page.getByText("paused", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "All monitors" }).click();
  await page.getByRole("button", { name: /Incidents/ }).click();
  await expect(page.getByText("No incidents recorded")).toBeVisible();

  await page.getByRole("button", { name: /Alerts/ }).click();
  await page.getByRole("button", { name: /Add Alert$/ }).click();
  const alertDialog = page.getByRole("dialog", { name: "Add Email Alert" });
  await alertDialog.locator("select").first().selectOption({
    label: updatedName,
  });
  await alertDialog
    .getByPlaceholder("you@example.com")
    .fill(`alerts-${suffix}@example.com`);
  await alertDialog.getByRole("button", { name: "Save Alert" }).click();

  await expect(
    page.getByText(`alerts-${suffix}@example.com`).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Send test" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Test alert saved for delivery",
  );
  await expect(page.getByText("test", { exact: true })).toBeVisible();
});
