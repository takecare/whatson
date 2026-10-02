/**
 * Shows `dialog` as a modal: under `anchor` on wide screens, and wherever the CSS puts
 * it on phones (above the bottom bar). Closes on Escape, on a click outside it, or
 * through the returned function; focus goes back to `anchor`.
 */
export function showDialog(anchor: HTMLElement, dialog: HTMLDialogElement): () => void {
  const close = () => {
    if (!dialog.isConnected) return;
    dialog.close();
    dialog.remove();
    anchor.focus({ preventScroll: true });
  };
  // A click on the backdrop lands on the dialog element itself.
  dialog.addEventListener("click", (ev) => ev.target === dialog && close());
  dialog.addEventListener("cancel", (ev) => {
    ev.preventDefault();
    close();
  });
  document.body.append(dialog);
  if (!window.matchMedia("(max-width: 860px)").matches) {
    const r = anchor.getBoundingClientRect();
    const height = dialog.offsetHeight || 340;
    // Below the button, or above it when there isn't room below.
    const top = r.bottom + 8 + height > window.innerHeight ? Math.max(8, r.top - 8 - height) : r.bottom + 8;
    dialog.style.top = `${top}px`;
    dialog.style.right = `${Math.max(16, window.innerWidth - r.right)}px`;
  }
  dialog.showModal();
  return close;
}
