/** Small DOM helpers for the verified intake/workspace boundary. */

import { listActionTypes, listFamilies } from "./queue";
import type { LoadedStream } from "./types";

function element(id: string): HTMLElement {
  const result = document.getElementById(id);
  if (!result) throw new Error(`missing #${id}`);
  return result;
}

export function setWorkspaceLoaded(loaded: boolean): void {
  element("empty-state").hidden = loaded;
  element("review-workspace").hidden = !loaded;
  (element("import-review") as HTMLInputElement).disabled = !loaded;
  (element("import-teacher") as HTMLInputElement).disabled = !loaded;
  (element("btn-export") as HTMLButtonElement).disabled = !loaded;
  (element("btn-reset-packet") as HTMLButtonElement).disabled = !loaded;
}

export function populateReviewFilters(streams: LoadedStream[]): void {
  const family = element("filter-family") as HTMLSelectElement;
  const action = element("filter-action") as HTMLSelectElement;
  family.replaceChildren(new Option("All families", ""));
  action.replaceChildren(new Option("All actions", ""));
  listFamilies(streams).forEach((value) => family.add(new Option(value, value)));
  listActionTypes(streams).forEach((value) => action.add(new Option(value, value)));
}
