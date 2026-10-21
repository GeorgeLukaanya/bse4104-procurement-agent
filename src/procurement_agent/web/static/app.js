/* The requests page.
 *
 * No framework and no build step. Everything the browser needs is this file,
 * app.css and index.html, which is what lets the page be served by a Python
 * standard-library server with nothing installed.
 *
 * Two rules it keeps.
 *
 * Nothing is computed here. Totals, rankings, exclusions and stop reasons all
 * arrive from the loop. This file chooses words and places boxes. If you find
 * yourself adding arithmetic, it belongs in a tool.
 *
 * Every value from the server goes in through textContent, never innerHTML.
 * Supplier names, item names and typed reasons are data, and data does not get
 * to be markup.
 */

"use strict";

const state = {
  user: null,
  org: null,
  people: null,
  inbox: null,
  tab: "needs_you",
  view: "requests",
  selectedSku: null,
  request: null,
  activity: null,
  busy: false,
  error: null,
  tabChosen: false,
};

/* ------------------------------------------------------------- helpers */

function el(tag, props, children) {
  const node = document.createElement(tag);
  if (props) {
    for (const key of Object.keys(props)) {
      const value = props[key];
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "onClick") node.addEventListener("click", value);
      else node.setAttribute(key, value === true ? "" : String(value));
    }
  }
  for (const child of children || []) {
    if (child === null || child === undefined || child === false) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function money(value) {
  if (typeof value !== "number") return "";
  return value.toLocaleString("en-UG", { maximumFractionDigits: 0 });
}

function initials(name) {
  return String(name || "")
    .split(/[^A-Za-z]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("") || "··";
}

function clockTime(iso) {
  if (!iso) return "";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

async function api(path, options) {
  const response = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, options));
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    const expired = new Error(payload.error || "Sign in first.");
    expired.unauthenticated = true;
    throw expired;
  }
  if (!response.ok) throw new Error(payload.error || "The server said no and did not say why.");
  return payload;
}

/* --------------------------------------------- saying it in plain words
 *
 * The left side of each case is what the loop reported. The right side is what
 * a person reads. Nothing here invents a state: every branch maps to a real
 * stop reason or error code, and the original string stays available under
 * "What I checked".
 */

function errorCode(request) {
  const detail = request.stop_detail || "";
  const match = detail.match(/^([A-Z_]{4,})\s*:/);
  return match ? match[1] : null;
}

function headline(request) {
  const stop = request.stop_reason;
  const code = errorCode(request);
  if (code === "EXCHANGE_RATE_REQUIRED") {
    return { tone: "attention", text: "One of the quotations is priced in US dollars. I will not guess a rate, so tell me the one you are using and I will redo the sums." };
  }
  if (stop === "awaiting_human") {
    if (request.confirmations && request.confirmations.comparison) {
      return { tone: "attention", text: "You have approved the price. Send it to the manager when you are ready." };
    }
    return { tone: "attention", text: "Waiting on you. Approve the price and it goes to the manager for sign-off." };
  }
  if (stop === "completed") {
    const id = request.draft && request.draft.requisition_id;
    return { tone: "ok", text: id ? "Done. " + id + " is with the manager. Nothing else is needed from you." : "Done." };
  }
  if (stop === "no_reorder_required") {
    return { tone: "ok", text: "Nothing is at or below its reorder level, so there is nothing to order." };
  }
  if (stop === "refused") {
    if (code === "INSUFFICIENT_QUOTATIONS") {
      return { tone: "problem", text: "There are not enough comparable quotations for an order this size. Get another quotation, then open this again." };
    }
    if (code === "INCOMPARABLE_QUOTATION") {
      return { tone: "problem", text: "One of the quotations is missing something I need before it can be compared. It is listed below." };
    }
    return { tone: "problem", text: "I stopped before doing anything, because a rule would not allow it. Nothing was saved." };
  }
  if (stop === "failed") {
    return { tone: "problem", text: "I could not read something I needed, so I have stopped. Nothing was saved and nothing was ordered. Ask whoever looks after the system to check it." };
  }
  if (stop === "unauthorized") {
    return { tone: "problem", text: "This account is not allowed to run that. Nothing was saved." };
  }
  if (stop === "no_progress" || stop === "max_iterations" || stop === "timeout") {
    return { tone: "problem", text: "I stopped myself before going round in circles. Nothing was saved, and this is worth telling whoever looks after the system." };
  }
  return { tone: "neutral", text: "Working on it." };
}

/* -------------------------------------------------------------- setup */

const ROLES = [
  ["PROCUREMENT_OFFICER", "I buy for the business", "You run the reorder reviews and prepare requisitions."],
  ["PROCUREMENT_MANAGER", "I approve the spending", "You sign off what somebody else has prepared."],
];

function field(label, input, hint) {
  return el("label", {}, [
    el("span", { text: label }),
    input,
    hint ? el("span", { class: "hint", text: hint }) : null,
  ]);
}

function personFields(key, heading, blurb) {
  const displayName = el("input", { type: "text", id: key + "-name", autocomplete: "off" });
  const username = el("input", { type: "text", id: key + "-username", autocomplete: "off" });
  const password = el("input", { type: "password", id: key + "-password", autocomplete: "new-password" });
  const mine = el("input", { type: "radio", name: "you", id: key + "-mine", value: key });

  const block = el("div", { class: "group" }, [
    el("h2", { text: heading }),
    el("p", { class: "hint", text: blurb }),
    field("Their name", displayName),
    field("Username", username),
    field("First password", password, "At least 10 characters. You will need to tell it to them."),
    el("label", { class: "is-me" }, [mine, el("span", { text: "This one is me" })]),
  ]);
  return { block, displayName, username, password, mine };
}

function renderSetup() {
  document.querySelector(".sidebar").hidden = true;
  document.getElementById("drawer").hidden = true;
  const main = document.getElementById("main");
  clear(main);

  const organisation = el("input", { type: "text", id: "organisation", autocomplete: "organization", autofocus: true });
  const locations = el("input", { type: "text", id: "locations", autocomplete: "off" });

  const buyer = personFields(
    "officer", "Who buys for the business",
    "They run the weekly reorder review, compare the quotations and prepare the requisition.",
  );
  const approver = personFields(
    "manager", "Who approves the spending",
    "They sign off what the buyer prepared. It has to be a second person, or the approval means nothing.",
  );
  buyer.mine.checked = true;

  const form = el("form", { class: "signin setup" }, [
    el("h1", { text: "Set up your business" }),
    el("p", { class: "muted small", text: "This runs on this machine only. Nothing is sent anywhere." }),

    el("div", { class: "group" }, [
      el("h2", { text: "The business" }),
      field("Name", organisation, "What you would write at the top of a requisition."),
      field("Branches", locations, "Optional. Separate them with commas."),
    ]),

    buyer.block,
    approver.block,

    state.error ? el("div", { class: "signin-error", text: state.error }) : null,
    el("button", { class: "btn", "data-kind": "primary", type: "submit", disabled: state.busy,
      text: state.busy ? "Setting it up…" : "Create the business" }),
    el("p", { class: "muted small", text: "You will be signed in as whichever account you marked as yours. You can add more people later." }),
  ]);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy) return;
    const people = [
      { username: buyer.username.value.trim(), display_name: buyer.displayName.value,
        role: "PROCUREMENT_OFFICER", password: buyer.password.value },
      { username: approver.username.value.trim(), display_name: approver.displayName.value,
        role: "PROCUREMENT_MANAGER", password: approver.password.value },
    ];
    const you = buyer.mine.checked ? people[0].username : people[1].username;

    state.busy = true;
    state.error = null;
    render();
    try {
      const payload = await api("/api/setup", {
        method: "POST",
        body: JSON.stringify({
          organisation: organisation.value,
          locations: locations.value,
          people: people,
          you: you,
        }),
      });
      state.user = payload.user;
      state.org = payload.organisation;
      state.needsSetup = false;
      state.busy = false;
      await loadInbox();
      return;
    } catch (error) {
      state.error = error.message;
    }
    state.busy = false;
    render();
  });

  main.appendChild(form);
}

/* ------------------------------------------------------------ sign in */

function renderSignIn() {
  document.querySelector(".sidebar").hidden = true;
  document.getElementById("drawer").hidden = true;
  const main = document.getElementById("main");
  clear(main);

  const username = el("input", { type: "text", id: "username", name: "username", autocomplete: "username", autofocus: true });
  const password = el("input", { type: "password", id: "password", name: "password", autocomplete: "current-password" });

  const form = el("form", { class: "signin" }, [
    el("h1", { text: "Procurement requests" }),
    state.org ? el("p", { class: "muted small", text: state.org.name }) : null,
    el("label", {}, [el("span", { text: "Username" }), username]),
    el("label", {}, [el("span", { text: "Password" }), password]),
    state.error ? el("div", { class: "signin-error", text: state.error }) : null,
    el("button", { class: "btn", "data-kind": "primary", type: "submit", disabled: state.busy,
      text: state.busy ? "Signing in…" : "Sign in" }),
    el("p", { class: "muted small", text: "Whoever set up this workspace can add you to it." }),
  ]);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy) return;
    state.busy = true;
    state.error = null;
    render();
    try {
      const payload = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({ username: username.value, password: password.value }),
      });
      state.user = payload.user;
      state.org = payload.organisation || state.org;
      state.busy = false;
      state.error = null;
      document.querySelector(".sidebar").hidden = false;
      await loadInbox();
      return;
    } catch (error) {
      state.error = error.message;
    }
    state.busy = false;
    render();
  });

  main.appendChild(form);
}

async function signOut() {
  try {
    await api("/api/logout", { method: "POST", body: "{}" });
  } catch (error) {
    // Signing out locally matters more than the server agreeing.
  }
  state.user = null;
  state.inbox = null;
  state.request = null;
  state.activity = null;
  state.tabChosen = false;
  state.error = null;
  render();
}

/* ------------------------------------------------------------ sidebar */

function renderNav() {
  const nav = document.getElementById("nav");
  clear(nav);
  const needs = state.inbox ? state.inbox.items.filter((i) => i.state === "needs_you").length : 0;

  const entries = [
    { label: "Requests", view: "requests", count: needs || null, enabled: true },
    { label: "Stock", view: "stock", enabled: false },
    { group: "Records" },
    { label: "Suppliers", view: "suppliers", enabled: false },
    { label: "Quotations", view: "quotations", enabled: false },
    { label: "Policies", view: "policies", enabled: false },
    { label: "Activity", view: "activity", enabled: true },
    { group: "Workspace" },
    { label: "People", view: "people", enabled: true },
  ];

  for (const entry of entries) {
    if (entry.group) {
      nav.appendChild(el("li", { class: "group", text: entry.group }));
      continue;
    }
    const current = state.view === entry.view;
    const button = el("button", {
      type: "button",
      "aria-current": current ? "page" : null,
      disabled: !entry.enabled,
      title: entry.enabled ? null : "Not built yet",
      onClick: entry.enabled ? () => go(entry.view) : null,
    }, [
      el("span", { class: "bar" }),
      el("span", { text: entry.label }),
      entry.count ? el("span", { class: "count", text: String(entry.count) }) : null,
    ]);
    nav.appendChild(el("li", {}, [button]));
  }

  if (state.org) {
    document.getElementById("org-mark").textContent = (state.org.name || "?").trim()[0].toUpperCase();
    document.getElementById("org-name").textContent = state.org.name;
    document.getElementById("org-locations").textContent = state.org.locations || "";
  }

  if (state.user) {
    const who = document.getElementById("who");
    document.querySelector("#who .avatar").textContent = initials(state.user.display_name);
    document.getElementById("who-name").textContent = state.user.display_name;
    document.getElementById("who-role").textContent = state.user.role === "PROCUREMENT_MANAGER"
      ? "Approves spending" : "Buys for the store";
    let out = document.getElementById("sign-out");
    if (!out) {
      out = el("button", { class: "btn", "data-kind": "quiet", id: "sign-out", type: "button", text: "Sign out", onClick: signOut });
      who.appendChild(out);
    }
  }
}

/* -------------------------------------------------------------- inbox */

const TABS = [
  { key: "needs_you", label: "Needs you", match: (i) => i.state === "needs_you" },
  { key: "in_progress", label: "In progress", match: (i) => i.state === "waiting" || i.state === "not_started" },
  { key: "blocked", label: "Stuck", match: (i) => i.state === "blocked" },
  { key: "done", label: "Done", match: (i) => i.state === "done" },
];

function renderRequests() {
  const main = document.getElementById("main");
  clear(main);
  const data = state.inbox;

  main.appendChild(el("div", { class: "head" }, [
    el("div", {}, [
      el("h1", { text: "Requests" }),
      el("p", { class: "sub", text: data ? data.evaluated + " items checked against their reorder points on " + data.review_date : "" }),
    ]),
    el("div", { class: "spacer" }),
  ]));

  if (!data) {
    main.appendChild(el("div", { class: "loading", text: "Checking stock…" }));
    return;
  }
  if (!data.ok) {
    const first = (data.errors && data.errors[0]) || {};
    main.appendChild(el("div", { class: "banner", text: "I could not read the stock list, so there is nothing to show. " + (first.detail || "") }));
    return;
  }

  const tabs = el("div", { class: "tabs", role: "tablist" });
  for (const tab of TABS) {
    const count = data.items.filter(tab.match).length;
    tabs.appendChild(el("button", {
      type: "button", role: "tab", "aria-selected": state.tab === tab.key ? "true" : "false",
      onClick: () => { state.tab = tab.key; render(); },
    }, [
      el("span", { text: tab.label }),
      count ? el("span", { class: "count", text: String(count) }) : null,
    ]));
  }
  main.appendChild(tabs);

  const shown = data.items.filter(TABS.find((t) => t.key === state.tab).match);

  main.appendChild(el("div", { class: "filters" }, [
    el("input", { type: "search", placeholder: "Search requests", "aria-label": "Search requests", disabled: true }),
    el("span", { class: "count", text: shown.length + " of " + data.items.length }),
  ]));

  if (!shown.length) {
    main.appendChild(el("div", { class: "empty", text: state.tab === "needs_you"
      ? "Nothing needs you right now."
      : "Nothing here." }));
    return;
  }

  const rows = el("div", { class: "rows" });
  for (const item of shown) {
    rows.appendChild(el("button", {
      type: "button", class: "row", "data-state": item.state,
      "aria-selected": state.selectedSku === item.sku ? "true" : "false",
      onClick: () => openRequest(item.sku),
    }, [
      el("span", { class: "what" }, [
        el("div", { class: "title", text: item.order_quantity + " of " + item.name }),
        el("div", { class: "sub", text: item.current_stock + " left, you keep " + item.reorder_point }),
      ]),
      el("span", { class: "amount figure", text: money(item.estimated_total_ugx) }),
      el("span", { class: "state" }, [
        el("span", { class: "dot", "data-tone": item.state }),
        el("span", { text: item.state_label }),
      ]),
      el("span", { class: "age mono muted", text: item.updated_at ? clockTime(item.updated_at) : "" }),
    ]));
  }
  main.appendChild(rows);
}

/* ------------------------------------------------------------- drawer */

function chainList(request) {
  const list = el("ul", { class: "chain" });
  for (const step of request.chain || []) {
    list.appendChild(el("li", { "data-status": step.status }, [
      el("span", { class: "rail" }, [el("span", { class: "node" }), el("span", { class: "tail" })]),
      el("span", {}, [
        el("span", { class: "who" }, [
          el("strong", { text: step.who }),
          step.when ? el("span", { class: "mono muted", text: clockTime(step.when) }) : null,
        ]),
        el("span", { class: "what", text: step.what }),
      ]),
    ]));
  }
  return list;
}

function offerList(request) {
  const wrap = el("div", { class: "offers" });
  const ranked = request.ranked || [];
  for (const offer of ranked) {
    const lead = offer.rank === 1;
    wrap.appendChild(el("div", { class: "offer", "data-lead": lead ? "true" : "false" }, [
      el("span", { class: "name" }, [
        el("div", { text: offer.supplier_name }),
        el("div", { class: "mono muted", text: offer.quotation_id + " · " + offer.lead_time_days + " days" }),
      ]),
      el("span", { class: "figure", text: money(offer.landed_cost_ugx) }),
      el("span", { class: "note-text", text: lead ? "Best total" : plusText(offer, ranked[0]) }),
    ]));
  }
  for (const offer of request.excluded || []) {
    wrap.appendChild(el("div", { class: "offer", "data-excluded": "true" }, [
      el("span", { class: "name" }, [
        el("div", { text: offer.supplier_name }),
        el("div", { class: "mono muted", text: (offer.reasons || []).join(" ") }),
      ]),
      el("span", { class: "note-text", text: "Cannot be used" }),
    ]));
  }
  return wrap;
}

function plusText(offer, best) {
  if (!best || typeof offer.landed_cost_ugx !== "number" || typeof best.landed_cost_ugx !== "number") return "";
  const difference = offer.landed_cost_ugx - best.landed_cost_ugx;
  if (difference === 0) return "Same total";
  return money(difference) + " more";
}

function metaRow(key, value) {
  return el("div", { class: "meta" }, [el("dt", { text: key }), el("dd", { text: value })]);
}

function technicalFold(request) {
  const body = el("dl", { class: "fold-body" });
  body.appendChild(metaRow("Stopped at", (request.step || "") + ", " + (request.iterations || 0) + " steps in"));
  body.appendChild(metaRow("Reported", request.stop_reason + " · " + (request.stop_detail || "")));
  if (request.contract) {
    body.appendChild(metaRow("Bounded by", request.contract.path + " v" + request.contract.version));
  }
  if (request.resumed && request.resumed.restored) {
    body.appendChild(metaRow("Reused", (request.resumed.kept_steps || []).join(", ") + " from an earlier run"));
  }
  for (const call of request.calls || []) {
    body.appendChild(metaRow(call.tool, call.status + ((call.errors || []).length ? " · " + call.errors[0].code : "")));
  }
  return el("details", { class: "fold" }, [el("summary", { text: "What I checked" }), body]);
}

function rateAsk(request) {
  const rate = el("input", { type: "text", inputmode: "decimal", value: "", id: "rate", placeholder: "3,780" });
  const dated = el("input", { type: "date", value: request.review_date || "", id: "rate-date" });
  return el("div", { class: "ask" }, [
    el("p", { text: "I will not guess a rate. Give me the one you are using and I will redo the comparison." }),
    el("div", { class: "fields" }, [
      el("label", {}, [el("span", { text: "Shillings to one dollar" }), rate]),
      el("label", {}, [el("span", { text: "Rate dated" }), dated]),
    ]),
    el("div", { class: "caution", text: "Changing a rate you gave earlier clears the comparison and any approval on it." }),
  ]);
}

function renderDrawer() {
  const drawer = document.getElementById("drawer");
  const request = state.request;
  if (!request) {
    drawer.hidden = true;
    clear(drawer);
    return;
  }
  drawer.hidden = false;
  clear(drawer);

  const said = headline(request);
  const needsRate = errorCode(request) === "EXCHANGE_RATE_REQUIRED";
  const recommended = request.recommended;
  const item = (state.inbox && state.inbox.items.find((i) => i.sku === request.sku)) || {};

  drawer.appendChild(el("div", { class: "drawer-head" }, [
    el("div", { class: "top" }, [
      el("span", { class: "mono muted", text: (request.draft && request.draft.requisition_id) || request.sku }),
      request.draft ? el("span", { class: "pill", "data-tone": "ok", text: "Draft" }) : null,
      el("span", { class: "spacer" }),
      el("button", { class: "btn", "data-kind": "quiet", type: "button", text: "Close", onClick: closeRequest }),
    ]),
    el("div", { class: "title-row" }, [
      el("div", {}, [
        el("h2", { text: (item.order_quantity ? item.order_quantity + " of " : "") + (item.name || request.sku) }),
        el("p", { class: "sub small muted", text: recommended ? recommended.supplier_name + " · " + recommended.lead_time_days + " days" : "" }),
      ]),
      el("div", { class: "spacer" }),
      recommended ? el("span", { class: "total figure", text: money(recommended.landed_cost_ugx) }) : null,
    ]),
  ]));

  const body = el("div", { class: "drawer-body" });
  body.appendChild(el("div", { class: "note", "data-tone": said.tone, text: said.text }));

  if (needsRate) body.appendChild(rateAsk(request));

  body.appendChild(el("div", { class: "block" }, [el("h3", { text: "Approvals" }), chainList(request)]));

  if ((request.ranked || []).length || (request.excluded || []).length) {
    body.appendChild(el("div", { class: "block" }, [
      el("h3", { text: "The price" }),
      offerList(request),
      request.requirement ? el("p", { class: "small muted", text: requirementText(request.requirement) }) : null,
    ]));
  }

  body.appendChild(el("div", { class: "folds" }, [technicalFold(request)]));
  drawer.appendChild(body);

  drawer.appendChild(el("div", { class: "drawer-foot" }, [
    el("button", { class: "btn", "data-kind": "secondary", type: "button", text: "Close", onClick: closeRequest }),
    el("span", { class: "spacer" }),
    primaryAction(request, needsRate),
  ]));
}

/* The contract has two gates and so does this footer. Approving the price is
 * not the same press as sending it, because the loop stops between them and
 * nothing is written until the second one. */
function primaryAction(request, needsRate) {
  const confirmed = (request.confirmations || {}).comparison;
  let label = null;
  let handler = null;
  if (needsRate) {
    label = "Use this rate";
    handler = submitRate;
  } else if (request.draft) {
    return null;
  } else if (!confirmed && (request.ranked || []).length) {
    label = "Approve the price";
    handler = approve;
  } else if (confirmed) {
    label = "Send to the manager";
    handler = send;
  }
  if (!label) return null;
  return el("button", {
    class: "btn", "data-kind": "primary", type: "button",
    disabled: state.busy, text: state.busy ? "Working…" : label, onClick: handler,
  });
}

function requirementText(requirement) {
  if (requirement.satisfied) {
    return requirement.eligible_count + " suppliers could quote, which is what " + requirement.clause + " asks for at this value.";
  }
  return "Policy asks for " + requirement.required_count + " comparable quotations and there are " + requirement.eligible_count + ". An exception would be needed.";
}

/* ------------------------------------------------------------- people */

function renderPeople() {
  const main = document.getElementById("main");
  clear(main);
  main.appendChild(el("div", { class: "head" }, [
    el("div", {}, [
      el("h1", { text: "People" }),
      el("p", { class: "sub", text: "Who can sign in to this workspace, and what each of them does." }),
    ]),
  ]));

  const data = state.people;
  if (!data) {
    main.appendChild(el("div", { class: "loading", text: "Reading the list…" }));
    return;
  }

  const rows = el("div", { class: "rows" });
  for (const person of data.people) {
    rows.appendChild(el("div", { class: "row", "data-state": "done" }, [
      el("span", { class: "avatar", "aria-hidden": "true", text: initials(person.display_name) }),
      el("span", { class: "what" }, [
        el("div", { class: "title", text: person.display_name }),
        el("div", { class: "sub", text: person.username }),
      ]),
      el("span", { class: "state" }, [
        el("span", { text: person.role === "PROCUREMENT_MANAGER" ? "Approves spending" : "Buys for the business" }),
      ]),
      el("span", { class: "age mono muted", text: person.is_owner ? "owner" : "" }),
    ]));
  }
  main.appendChild(rows);

  if (!data.you_may_add) {
    main.appendChild(el("div", { class: "empty small", text: "Only whoever set up the workspace can add people." }));
    return;
  }

  const displayName = el("input", { type: "text", autocomplete: "name" });
  const username = el("input", { type: "text", autocomplete: "off" });
  const password = el("input", { type: "password", autocomplete: "new-password" });
  const role = el("select", {}, [
    el("option", { value: "PROCUREMENT_OFFICER", text: "Buys for the business" }),
    el("option", { value: "PROCUREMENT_MANAGER", text: "Approves spending" }),
  ]);

  const form = el("form", { class: "add-person" }, [
    el("h2", { text: "Add someone" }),
    field("Their name", displayName),
    field("Username", username),
    field("First password", password, "At least 10 characters. Tell it to them yourself; it cannot be read back."),
    field("What they do", role),
    state.error ? el("div", { class: "signin-error", text: state.error }) : null,
    el("button", { class: "btn", "data-kind": "primary", type: "submit", disabled: state.busy,
      text: state.busy ? "Adding…" : "Add them" }),
  ]);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy) return;
    state.busy = true;
    state.error = null;
    render();
    try {
      await api("/api/people", {
        method: "POST",
        body: JSON.stringify({
          display_name: displayName.value,
          username: username.value,
          password: password.value,
          role: role.value,
        }),
      });
      state.busy = false;
      await loadPeople();
      return;
    } catch (error) {
      state.error = error.message;
    }
    state.busy = false;
    render();
  });
  main.appendChild(form);
}

async function loadPeople() {
  try {
    state.people = await api("/api/people");
    state.error = null;
  } catch (error) {
    state.error = error.message;
  }
  render();
}

/* ----------------------------------------------------------- activity */

function renderActivity() {
  const main = document.getElementById("main");
  clear(main);
  main.appendChild(el("div", { class: "head" }, [
    el("div", {}, [
      el("h1", { text: "Activity" }),
      el("p", { class: "sub", text: "Every decision, kept as it was made. Nothing here can be edited." }),
    ]),
  ]));

  const rows = state.activity;
  if (!rows) {
    main.appendChild(el("div", { class: "loading", text: "Reading the record…" }));
    return;
  }
  if (!rows.length) {
    main.appendChild(el("div", { class: "empty", text: "Nothing has been decided yet." }));
    return;
  }

  let lastDay = null;
  for (const row of rows) {
    const day = (row.decided_at || "").slice(0, 10);
    if (day !== lastDay) {
      main.appendChild(el("div", { class: "day", text: day }));
      lastDay = day;
    }
    main.appendChild(el("div", { class: "entry", "data-superseded": row.superseded ? "true" : "false" }, [
      el("span", { class: "rail" }, [el("span", { class: "dot", "data-tone": toneForKind(row.kind) })]),
      el("span", { class: "text" }, [
        el("span", { class: "actor", text: row.actor }),
        " ",
        el("span", { text: describeDecision(row) }),
      ]),
      el("span", { class: "when", text: clockTime(row.decided_at) }),
    ]));
  }
}

function toneForKind(kind) {
  if (kind === "approved" || kind === "comparison_approved" || kind === "requisition_sent") return "done";
  if (kind === "sent_back" || kind === "run_stopped") return "blocked";
  return "waiting";
}

function describeDecision(row) {
  const detail = row.detail || {};
  switch (row.kind) {
    case "comparison_approved":
      return "approved the price for " + row.subject
        + (detail.supplier_name ? " · " + detail.supplier_name : "")
        + (detail.landed_cost_ugx ? " · " + money(detail.landed_cost_ugx) : "");
    case "rate_given":
      return "gave an exchange rate of " + money(detail.ugx_per_usd) + " for " + row.subject;
    case "requisition_sent":
      return "sent " + row.subject + " to the manager";
    case "approved":
      return "approved " + row.subject;
    case "sent_back":
      return "sent " + row.subject + " back" + (detail.reason ? " · " + detail.reason : "");
    case "run_stopped":
      return "stopped on " + row.subject + " · " + (detail.stop_reason || "");
    default:
      return row.kind + " on " + row.subject;
  }
}

/* -------------------------------------------------------------- flow */

function render() {
  if (!state.user) {
    if (state.needsSetup) renderSetup();
    else renderSignIn();
    return;
  }
  document.querySelector(".sidebar").hidden = false;
  renderNav();
  if (state.view === "activity") renderActivity();
  else if (state.view === "people") renderPeople();
  else renderRequests();
  renderDrawer();
  if (state.error) {
    const main = document.getElementById("main");
    main.appendChild(el("div", { class: "banner", text: state.error }));
  }
}

function go(view) {
  state.view = view;
  state.error = null;
  if (view === "activity") loadActivity();
  else if (view === "people") loadPeople();
  render();
}

async function loadInbox() {
  try {
    state.inbox = await api("/api/requests");
    chooseOpeningTab();
  } catch (error) {
    if (error.unauthenticated) {
      state.user = null;
      state.error = "Your session has ended. Sign in again.";
    } else {
      state.error = error.message;
    }
  }
  render();
}

/* Needs you is the right tab to land on when there is something in it. On a
 * week where nothing has been started yet it is empty, and opening on an empty
 * tab reads as a broken page, so fall through to the first tab with rows.
 * Only ever on the first load: after that the tab is the user's choice. */
function chooseOpeningTab() {
  if (state.tabChosen || !state.inbox) return;
  state.tabChosen = true;
  const items = state.inbox.items || [];
  const firstWithRows = TABS.find((tab) => items.some(tab.match));
  if (firstWithRows && !items.some(TABS.find((t) => t.key === state.tab).match)) {
    state.tab = firstWithRows.key;
  }
}

async function loadActivity() {
  try {
    const payload = await api("/api/activity");
    state.activity = payload.decisions;
  } catch (error) {
    state.error = error.message;
  }
  render();
}

async function openRequest(sku) {
  state.selectedSku = sku;
  state.error = null;
  state.busy = true;
  render();
  try {
    state.request = await api("/api/requests/" + encodeURIComponent(sku) + "/open", {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    state.error = error.message;
    state.request = null;
  }
  state.busy = false;
  render();
}

function closeRequest() {
  state.request = null;
  state.selectedSku = null;
  render();
}

async function act(action, body) {
  if (!state.request) return;
  state.busy = true;
  state.error = null;
  render();
  try {
    state.request = await api(
      "/api/requests/" + encodeURIComponent(state.request.sku) + "/" + action,
      { method: "POST", body: JSON.stringify(body || {}) },
    );
    await loadInbox();
  } catch (error) {
    state.error = error.message;
  }
  state.busy = false;
  render();
}

function approve() {
  return act("approve");
}

function send() {
  return act("send");
}

async function submitRate() {
  if (!state.request) return;
  const raw = (document.getElementById("rate") || {}).value || "";
  const dated = (document.getElementById("rate-date") || {}).value || state.request.review_date;
  const rate = Number(raw.replace(/[,\s]/g, ""));
  if (!rate || rate <= 0) {
    state.error = "Put in the rate you are using, as a number.";
    render();
    return;
  }
  return act("rate", { ugx_per_usd: rate, effective_date: dated });
}

async function boot() {
  try {
    const start = await api("/api/bootstrap");
    state.needsSetup = start.needs_setup;
    state.org = start.organisation;
  } catch (error) {
    state.error = error.message;
    render();
    return;
  }
  if (state.needsSetup) {
    render();
    return;
  }
  try {
    const payload = await api("/api/session");
    state.user = payload.user;
    state.org = payload.organisation || state.org;
  } catch (error) {
    // Not signed in is the ordinary visit, not something to report.
    if (!error.unauthenticated) state.error = error.message;
    render();
    return;
  }
  await loadInbox();
}

boot();
