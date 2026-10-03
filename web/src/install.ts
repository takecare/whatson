import { showDialog } from "./dialog";
import { h } from "./dom";

/** Chrome's install prompt event (not in TypeScript's DOM types). */
interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const ua = navigator.userAgent;
const isIPhone = /iPhone|iPod/.test(ua);
const isAndroidPhone = /Android/.test(ua) && /Mobile/.test(ua);
const installed = () =>
  window.matchMedia("(display-mode: standalone)").matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true;

/**
 * The "Add to home" button, on phones only. Android browsers that can install the
 * site say so with `beforeinstallprompt`, and the button shows their prompt. iPhones
 * have no such prompt, so the button explains Safari's Share → Add to Home Screen.
 * Hidden once the site runs as the installed app.
 */
export function setUpAddToHome(button: HTMLButtonElement): void {
  if ("serviceWorker" in navigator) {
    void navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  if (installed() || !(isIPhone || isAndroidPhone)) return;

  let deferred: InstallPromptEvent | null = null;
  if (isAndroidPhone) {
    window.addEventListener("beforeinstallprompt", (ev) => {
      ev.preventDefault(); // keep the browser's own mini-infobar out of the way
      deferred = ev as InstallPromptEvent;
      button.hidden = false;
    });
  } else {
    button.hidden = false;
  }
  window.addEventListener("appinstalled", () => (button.hidden = true));

  button.addEventListener("click", async () => {
    if (deferred) {
      const prompt = deferred;
      deferred = null; // a prompt can only be shown once
      await prompt.prompt();
      const { outcome } = await prompt.userChoice;
      if (outcome === "accepted") button.hidden = true;
      return;
    }
    if (isIPhone) showIPhoneSteps(button);
  });
}

function showIPhoneSteps(anchor: HTMLElement) {
  const share = h("span", { class: "install-share", "aria-label": "Share" });
  share.innerHTML =
    '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3v12M8 7l4-4 4 4"/><path d="M6 11v9h12v-9"/></svg>';
  const dialog = h(
    "dialog",
    { class: "popover install", "aria-labelledby": "install-title" },
    h(
      "div",
      { class: "popover-head" },
      h("h2", { class: "popover-title", id: "install-title" }, "Add to your home screen"),
      h("button", { type: "button", class: "popover-close", "aria-label": "Close" }, "×"),
    ),
    h(
      "ol",
      { class: "install-steps" },
      h("li", {}, "Tap ", share, " Share in the browser’s toolbar."),
      h("li", {}, "Choose ", h("strong", {}, "Add to Home Screen"), " (you may need to scroll down)."),
    ),
    h("p", { class: "install-note" }, "What’s On then opens full screen from its own icon."),
  );
  const close = showDialog(anchor, dialog);
  dialog.querySelector(".popover-close")!.addEventListener("click", () => close());
}
