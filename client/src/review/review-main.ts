import { mountReviewShell } from "./shell";
import "./review.css";

const root = document.getElementById("app");
if (!root) {
  throw new Error("#app missing");
}

const unmount = mountReviewShell(root);

window.addEventListener(
  "pagehide",
  () => {
    unmount();
  },
  { once: true },
);
