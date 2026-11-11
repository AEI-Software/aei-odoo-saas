/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const TAB_KEYS = ["ArrowLeft", "ArrowRight", "Home", "End"];

/**
 * Behavior of the AEI public pages: mobile menu, client logo motion, company
 * profile tabs, billing period, detail dialogs and reveal-on-scroll.
 *
 * Every state change goes through classes, attributes and textContent. The
 * markup for tab panels and dialogs is rendered by QWeb, so nothing is built
 * from strings.
 */
publicWidget.registry.AeiLanding = publicWidget.Widget.extend({
    selector: ".aei-site",
    events: {
        "click [data-aei-menu-toggle]": "_onMenuToggle",
        "click [data-aei-client-motion]": "_onClientMotionToggle",
        "click [data-aei-profile]": "_onProfileClick",
        "keydown [data-aei-profile]": "_onProfileKeydown",
        "click [data-billing]": "_onBillingClick",
        "click [data-aei-plan-details]": "_onPlanDetailsClick",
        "click [data-aei-module-details]": "_onModuleDetailsClick",
        "click [data-aei-dialog-close]": "_onDialogCloseClick",
        "click dialog": "_onDialogBackdropClick",
    },

    start() {
        this._enableRevealOnScroll();
        return this._super(...arguments);
    },

    destroy() {
        if (this._observer) {
            this._observer.disconnect();
        }
        this.el.classList.remove("aei-motion");
        this._super(...arguments);
    },

    // -- Reveal on scroll ----------------------------------------------------

    _enableRevealOnScroll() {
        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (prefersReducedMotion || !("IntersectionObserver" in window)) {
            return;
        }
        this._observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("aei-is-visible");
                        this._observer.unobserve(entry.target);
                    }
                }
            },
            { threshold: 0.08, rootMargin: "0px 0px 30px 0px" }
        );
        this.el.classList.add("aei-motion");
        for (const node of this.el.querySelectorAll(".aei-reveal")) {
            this._observer.observe(node);
        }
    },

    // -- Mobile menu ---------------------------------------------------------

    _onMenuToggle(ev) {
        const button = ev.currentTarget;
        const nav = this.el.querySelector("#" + button.getAttribute("aria-controls"));
        const open = button.getAttribute("aria-expanded") !== "true";
        button.setAttribute("aria-expanded", String(open));
        button.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
        button.textContent = open ? "✕" : "☰";
        if (nav) {
            nav.classList.toggle("aei-is-open", open);
        }
    },

    // -- Client logos --------------------------------------------------------

    _onClientMotionToggle(ev) {
        const button = ev.currentTarget;
        const paused = button.getAttribute("aria-pressed") !== "true";
        const lanes = this.el.querySelector("#" + button.getAttribute("aria-controls"));
        button.setAttribute("aria-pressed", String(paused));
        if (lanes) {
            lanes.setAttribute("data-paused", String(paused));
        }
        button.querySelector("[data-aei-client-motion-label]").textContent = paused
            ? "Reanudar logos"
            : "Pausar logos";
        button.querySelector("[data-aei-client-motion-icon]").textContent = paused ? "▶" : "Ⅱ";
    },

    // -- Billing period -----------------------------------------------------

    _onBillingClick(ev) {
        const cycle = ev.currentTarget.dataset.billing;
        for (const button of this.el.querySelectorAll("[data-billing]")) {
            button.setAttribute("aria-pressed", String(button.dataset.billing === cycle));
        }
        // Each plan card renders both periods; only the chosen one is visible.
        for (const node of this.el.querySelectorAll("[data-aei-cycle]")) {
            node.hidden = node.dataset.aeiCycle !== cycle;
        }
        // The forms carry the period so the internal wiring can read it later.
        for (const input of this.el.querySelectorAll("[data-aei-cycle-input]")) {
            input.value = cycle;
        }
    },

    // -- Detail dialogs ------------------------------------------------------

    _openDialog(dialogId) {
        const dialog = this.el.querySelector("#" + dialogId);
        if (dialog && !dialog.open) {
            dialog.showModal();
        }
    },

    _onPlanDetailsClick(ev) {
        this._openDialog("aei-plan-dialog-" + ev.currentTarget.dataset.aeiPlanDetails);
    },

    _onModuleDetailsClick(ev) {
        this._openDialog("aei-module-dialog-" + ev.currentTarget.dataset.aeiModuleDetails);
    },

    _onDialogCloseClick(ev) {
        ev.currentTarget.closest("dialog").close();
    },

    _onDialogBackdropClick(ev) {
        // A click on the dialog element itself (not its content) is a click on the backdrop.
        if (ev.target === ev.currentTarget) {
            ev.currentTarget.close();
        }
    },

    // -- Company profile tabs ------------------------------------------------

    _onProfileClick(ev) {
        this._selectProfile(ev.currentTarget.dataset.aeiProfile, false);
    },

    _onProfileKeydown(ev) {
        if (!TAB_KEYS.includes(ev.key)) {
            return;
        }
        ev.preventDefault();
        const tabs = [...this.el.querySelectorAll("[data-aei-profile]")];
        const current = tabs.indexOf(ev.currentTarget);
        let next = current + (ev.key === "ArrowLeft" ? -1 : 1);
        if (ev.key === "Home") {
            next = 0;
        } else if (ev.key === "End") {
            next = tabs.length - 1;
        }
        this._selectProfile(tabs[(next + tabs.length) % tabs.length].dataset.aeiProfile, true);
    },

    _selectProfile(profileId, moveFocus) {
        for (const tab of this.el.querySelectorAll("[data-aei-profile]")) {
            const selected = tab.dataset.aeiProfile === profileId;
            tab.setAttribute("aria-selected", String(selected));
            tab.tabIndex = selected ? 0 : -1;
            if (selected && moveFocus) {
                tab.focus();
            }
        }
        for (const panel of this.el.querySelectorAll(".aei-profile-panel")) {
            panel.hidden = panel.id !== "aei-profile-panel-" + profileId;
        }
    },
});
