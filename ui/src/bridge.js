export function waitForBridge() {
  if (window.pywebview?.api) return Promise.resolve(window.pywebview.api);
  return new Promise((resolve) => {
    window.addEventListener(
      "pywebviewready",
      () => resolve(window.pywebview.api),
      { once: true },
    );
  });
}
