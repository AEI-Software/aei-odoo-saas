/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

/**
 * Step 3 of /checkout: asks the server for the QR payment state and, once the bank
 * confirms the payment, opens the success step.
 *
 * The status route, the success URL and the interval come from data attributes rendered
 * by the server, so nothing here depends on the environment.
 */
publicWidget.registry.AeiCheckoutQrPoll = publicWidget.Widget.extend({
    selector: "[data-aei-qr-poll]",

    start() {
        const data = this.el.dataset;
        this._reference = data.aeiReference;
        this._statusUrl = data.aeiStatusUrl;
        this._doneUrl = data.aeiDoneUrl;
        this._interval = parseInt(data.aeiPollInterval, 10);
        const ready = this._reference && this._isLocalPath(this._statusUrl) && this._isLocalPath(this._doneUrl);
        if (ready && this._interval > 0) {
            this._schedule();
        }
        return this._super(...arguments);
    },

    destroy() {
        clearTimeout(this._timer);
        this._super(...arguments);
    },

    _schedule() {
        this._timer = setTimeout(() => this._poll(), this._interval);
    },

    async _poll() {
        let result = {};
        try {
            result = await rpc(this._statusUrl, { reference: this._reference });
        } catch {
            // A network hiccup must not stop the page: the next tick tries again.
        }
        if (result.state === "done") {
            window.location.assign(this._doneUrl);
        } else if (result.state === "cancel" || result.state === "error") {
            // Reloading renders a fresh QR (new transaction) or the retry message.
            window.location.reload();
        } else {
            this._schedule();
        }
    },

    /** Only same-site paths are followed, never an absolute or protocol-relative URL. */
    _isLocalPath(url) {
        return typeof url === "string" && url.startsWith("/") && !url.startsWith("//");
    },
});
